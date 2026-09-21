from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from orion.api.interactive.e2e_key_manager.e2e_key_enums import E2E_KEY_LIMITS, E2E_UNLOCK_KIND
from orion.api.interactive.e2e_key_manager.models.e2e_key_param_model import E2eKeyUnlockRequest
from orion.services.encryption_manager.key_manager import key_manager
from orion.services.mongo_manager.shared_model.db_mailbox_model import db_mailbox_model
from orion.services.mongo_manager.shared_model.db_pgp_key_model import PGP_KEY_TYPE, db_pgp_key_model
from tests.model.fakes import RecordingEngine
from tests.scripts.e2e_key_manager.helpers import FINGERPRINT, LOCKED_KEY, OTHER_FINGERPRINT, PUBLIC_KEY, RECOVERY_KEY, RECOVERY_VERIFIER, SESSION_TOKEN, USER, VERIFIER, WRONG_VERIFIER, engine_with_key, make_bundle, make_key, make_mailbox, make_manager, use_identity_client, use_inspector, use_key_wrapper


@pytest.mark.anyio
async def test_state_reports_unconfigured_mailbox():
    mailbox = make_mailbox()
    manager = make_manager(RecordingEngine(find_one={db_mailbox_model: mailbox}))

    assert await manager.get_key_state(USER) == {"configured": False, "mailbox_address": mailbox.mailbox_address}


@pytest.mark.anyio
async def test_state_requires_a_mailbox():
    with pytest.raises(HTTPException) as error:
        await make_manager(RecordingEngine()).get_key_state(USER)

    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_state_never_exposes_private_material():
    engine, _key = engine_with_key()

    state = await make_manager(engine).get_key_state(USER)

    assert state["configured"] is True
    assert state["fingerprint"] == FINGERPRINT
    assert not any("private" in name or "verifier" in name for name in state)
    assert LOCKED_KEY not in state.values() and RECOVERY_KEY not in state.values()


@pytest.mark.anyio
async def test_unlock_releases_locked_key_for_correct_passphrase():
    engine, _key = engine_with_key()

    result = await make_manager(engine).unlock_key(USER, E2eKeyUnlockRequest(verifier=VERIFIER))

    assert result["kind"] == E2E_UNLOCK_KIND.PASSPHRASE
    assert result["private_key"] == LOCKED_KEY


@pytest.mark.anyio
async def test_unlock_releases_recovery_copy_for_recovery_code():
    engine, _key = engine_with_key()

    result = await make_manager(engine).unlock_key(USER, E2eKeyUnlockRequest(verifier=RECOVERY_VERIFIER, kind=E2E_UNLOCK_KIND.RECOVERY))

    assert result["private_key"] == RECOVERY_KEY


@pytest.mark.anyio
async def test_unlock_rejects_wrong_passphrase_and_counts_it():
    engine, key = engine_with_key()

    with pytest.raises(HTTPException) as error:
        await make_manager(engine).unlock_key(USER, E2eKeyUnlockRequest(verifier=WRONG_VERIFIER))

    assert error.value.status_code == 403
    assert key.failed_unlocks == 1


@pytest.mark.anyio
async def test_unlock_does_not_accept_recovery_code_as_passphrase():
    engine, _key = engine_with_key()

    with pytest.raises(HTTPException) as error:
        await make_manager(engine).unlock_key(USER, E2eKeyUnlockRequest(verifier=RECOVERY_VERIFIER, kind=E2E_UNLOCK_KIND.PASSPHRASE))

    assert error.value.status_code == 403


@pytest.mark.anyio
async def test_unlock_blocks_after_too_many_failures():
    engine, key = engine_with_key({"failed_unlocks": E2E_KEY_LIMITS.MAX_FAILED_UNLOCKS - 1})
    manager = make_manager(engine)

    with pytest.raises(HTTPException):
        await manager.unlock_key(USER, E2eKeyUnlockRequest(verifier=WRONG_VERIFIER))
    assert key.unlock_blocked_until is not None

    with pytest.raises(HTTPException) as error:
        await manager.unlock_key(USER, E2eKeyUnlockRequest(verifier=VERIFIER))
    assert error.value.status_code == 429


@pytest.mark.anyio
async def test_unlock_works_again_after_block_expires_and_resets_counter():
    engine, key = engine_with_key({"failed_unlocks": 3, "unlock_blocked_until": datetime.now(UTC) - timedelta(minutes=1)})

    result = await make_manager(engine).unlock_key(USER, E2eKeyUnlockRequest(verifier=VERIFIER))

    assert result["private_key"] == LOCKED_KEY
    assert key.failed_unlocks == 0 and key.unlock_blocked_until is None


@pytest.mark.anyio
async def test_save_creates_key_stores_hashes_and_mirrors_to_orion_intelligence(monkeypatch):
    use_inspector(monkeypatch)
    identity = use_identity_client(monkeypatch)
    mailbox = make_mailbox()
    engine = RecordingEngine(find_one={db_mailbox_model: mailbox})

    result = await make_manager(engine).save_key_bundle(USER, make_bundle(), session_token=SESSION_TOKEN)

    saved = engine.saved[0]
    assert isinstance(saved, db_pgp_key_model)
    assert saved.key_type == PGP_KEY_TYPE.E2E and saved.owner_mailbox_id == mailbox.id
    assert saved.wrapped_private_key == LOCKED_KEY and saved.recovery_private_key == RECOVERY_KEY
    assert key_manager.secret_matches(VERIFIER, saved.verifier_hash)
    assert key_manager.secret_matches(RECOVERY_VERIFIER, saved.recovery_verifier_hash)
    assert VERIFIER not in (saved.verifier_hash or "")
    assert identity.calls == [(SESSION_TOKEN, VERIFIER)]
    assert "private_key" not in result and "locked_private_key" not in result


@pytest.mark.anyio
async def test_save_without_sso_session_skips_mirror(monkeypatch):
    use_inspector(monkeypatch)
    identity = use_identity_client(monkeypatch)
    engine = RecordingEngine(find_one={db_mailbox_model: make_mailbox()})

    await make_manager(engine).save_key_bundle(USER, make_bundle())

    assert identity.calls == [] and len(engine.saved) == 1


@pytest.mark.anyio
async def test_save_aborts_when_orion_intelligence_rejects_the_mirror(monkeypatch):
    use_inspector(monkeypatch)
    use_identity_client(monkeypatch, HTTPException(status_code=503, detail="down"))
    engine = RecordingEngine(find_one={db_mailbox_model: make_mailbox()})

    with pytest.raises(HTTPException) as error:
        await make_manager(engine).save_key_bundle(USER, make_bundle(), session_token=SESSION_TOKEN)

    assert error.value.status_code == 503 and engine.saved == []


@pytest.mark.anyio
async def test_save_requires_recovery_copy_for_a_new_key(monkeypatch):
    use_inspector(monkeypatch)
    engine = RecordingEngine(find_one={db_mailbox_model: make_mailbox()})

    with pytest.raises(HTTPException) as error:
        await make_manager(engine).save_key_bundle(USER, make_bundle(recovery_private_key=None, recovery_verifier=None))

    assert error.value.status_code == 400 and engine.saved == []


@pytest.mark.anyio
async def test_save_rejects_unlocked_private_key(monkeypatch):
    use_inspector(monkeypatch, locked=False)
    engine = RecordingEngine(find_one={db_mailbox_model: make_mailbox()})

    with pytest.raises(HTTPException) as error:
        await make_manager(engine).save_key_bundle(USER, make_bundle())

    assert error.value.status_code == 400 and "locked" in error.value.detail and engine.saved == []


@pytest.mark.anyio
async def test_save_rejects_key_material_with_another_fingerprint(monkeypatch):
    use_inspector(monkeypatch, fingerprint=OTHER_FINGERPRINT)
    engine = RecordingEngine(find_one={db_mailbox_model: make_mailbox()})

    with pytest.raises(HTTPException) as error:
        await make_manager(engine).save_key_bundle(USER, make_bundle())

    assert error.value.status_code == 400 and engine.saved == []


@pytest.mark.anyio
async def test_save_rejects_swapped_armor_blocks(monkeypatch):
    use_inspector(monkeypatch)
    engine = RecordingEngine(find_one={db_mailbox_model: make_mailbox()})

    with pytest.raises(HTTPException) as error:
        await make_manager(engine).save_key_bundle(USER, make_bundle(locked_private_key=PUBLIC_KEY))

    assert error.value.status_code == 400 and engine.saved == []


@pytest.mark.anyio
async def test_save_refuses_to_replace_an_existing_key(monkeypatch):
    use_inspector(monkeypatch, fingerprint=OTHER_FINGERPRINT)
    engine, _key = engine_with_key()

    with pytest.raises(HTTPException) as error:
        await make_manager(engine).save_key_bundle(USER, make_bundle(fingerprint=OTHER_FINGERPRINT, proof=VERIFIER))

    assert error.value.status_code == 409 and engine.saved == []


@pytest.mark.anyio
async def test_relock_requires_proof_of_the_current_secret(monkeypatch):
    use_inspector(monkeypatch)
    engine, key = engine_with_key()
    manager = make_manager(engine)
    relocked = LOCKED_KEY.replace("locked", "relocked")

    with pytest.raises(HTTPException) as missing:
        await manager.save_key_bundle(USER, make_bundle(locked_private_key=relocked, recovery_private_key=None, recovery_verifier=None))
    with pytest.raises(HTTPException) as wrong:
        await manager.save_key_bundle(USER, make_bundle(locked_private_key=relocked, recovery_private_key=None, recovery_verifier=None, proof=WRONG_VERIFIER))

    assert missing.value.status_code == 403 and wrong.value.status_code == 403
    assert key.wrapped_private_key == LOCKED_KEY


@pytest.mark.anyio
async def test_relock_with_recovery_proof_keeps_the_recovery_copy(monkeypatch):
    use_inspector(monkeypatch)
    identity = use_identity_client(monkeypatch)
    engine, key = engine_with_key()
    relocked = LOCKED_KEY.replace("locked", "relocked")
    new_verifier = "D" * 43 + "="

    await make_manager(engine).save_key_bundle(USER, make_bundle(locked_private_key=relocked, verifier=new_verifier, recovery_private_key=None, recovery_verifier=None, proof=RECOVERY_VERIFIER), session_token=SESSION_TOKEN)

    assert key.wrapped_private_key == relocked
    assert key.recovery_private_key == RECOVERY_KEY
    assert key_manager.secret_matches(new_verifier, key.verifier_hash)
    assert key_manager.secret_matches(RECOVERY_VERIFIER, key.recovery_verifier_hash)
    assert identity.calls == [(SESSION_TOKEN, new_verifier)]


@pytest.mark.anyio
async def test_relock_cannot_change_salt_without_new_recovery_copy(monkeypatch):
    use_inspector(monkeypatch)
    engine, _key = engine_with_key()

    with pytest.raises(HTTPException) as error:
        await make_manager(engine).save_key_bundle(USER, make_bundle(kdf_salt="b3RoZXJzYWx0b3RoZXJzYWx0", recovery_private_key=None, recovery_verifier=None, proof=VERIFIER))

    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_delete_removes_key_and_clears_the_mirror_without_failing_on_outage(monkeypatch):
    identity = use_identity_client(monkeypatch, HTTPException(status_code=503, detail="down"))
    engine, key = engine_with_key()

    await make_manager(engine).delete_key_bundle(USER, session_token=SESSION_TOKEN)

    assert engine.deleted == [key]
    assert identity.calls == [(SESSION_TOKEN, None)]


@pytest.mark.anyio
async def test_lookup_returns_only_public_material():
    mailbox = make_mailbox("test2@mail.orionintelligence.org")
    engine = RecordingEngine(find={db_mailbox_model: [mailbox], db_pgp_key_model: [make_key(mailbox)]})

    result = await make_manager(engine).lookup_public_keys([" Test2@mail.orionintelligence.org ", "nobody@mail.orionintelligence.org"])

    assert result == {"keys": [{"address": "test2@mail.orionintelligence.org", "fingerprint": FINGERPRINT, "public_key": PUBLIC_KEY}]}


@pytest.mark.anyio
async def test_lookup_without_known_mailboxes_is_empty():
    assert await make_manager(RecordingEngine()).lookup_public_keys(["nobody@mail.orionintelligence.org"]) == {"keys": []}


def test_requests_reject_malformed_fingerprint_and_raw_passphrase():
    with pytest.raises(ValidationError):
        make_bundle(fingerprint="not-a-fingerprint")
    with pytest.raises(ValidationError):
        make_bundle(verifier="my plain passphrase")
    with pytest.raises(ValidationError):
        E2eKeyUnlockRequest(verifier="my plain passphrase")


@pytest.mark.anyio
async def test_tab_secret_is_stable_within_one_login_session_and_stored_wrapped(monkeypatch):
    use_key_wrapper(monkeypatch)
    engine, key = engine_with_key()
    manager = make_manager(engine)

    first = await manager.tab_secret(USER, SESSION_TOKEN)
    second = await manager.tab_secret(USER, SESSION_TOKEN)

    assert first == second and len(first["secret"]) == 44
    assert key.tab_secret == f"wrapped:{first['secret']}"
    assert SESSION_TOKEN not in (key.tab_secret_binding or "")


@pytest.mark.anyio
async def test_tab_secret_is_not_released_to_another_login_session(monkeypatch):
    use_key_wrapper(monkeypatch)
    engine, _key = engine_with_key()
    manager = make_manager(engine)

    original = await manager.tab_secret(USER, SESSION_TOKEN)
    other = await manager.tab_secret(USER, "another-session-token")

    assert other["secret"] != original["secret"]


@pytest.mark.anyio
async def test_tab_secret_is_replaced_after_it_expires(monkeypatch):
    use_key_wrapper(monkeypatch)
    engine, key = engine_with_key()
    manager = make_manager(engine)

    original = await manager.tab_secret(USER, SESSION_TOKEN)
    key.tab_secret_expires_at = datetime.now(UTC) - timedelta(seconds=1)

    assert (await manager.tab_secret(USER, SESSION_TOKEN))["secret"] != original["secret"]


@pytest.mark.anyio
async def test_tab_secret_needs_a_key_and_a_session(monkeypatch):
    use_key_wrapper(monkeypatch)
    engine, _key = engine_with_key()

    with pytest.raises(HTTPException) as no_session:
        await make_manager(engine).tab_secret(USER, None)
    with pytest.raises(HTTPException) as no_key:
        await make_manager(RecordingEngine(find_one={db_mailbox_model: make_mailbox()})).tab_secret(USER, SESSION_TOKEN)

    assert no_session.value.status_code == 404 and no_key.value.status_code == 404
