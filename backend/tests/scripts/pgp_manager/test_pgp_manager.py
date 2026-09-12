from __future__ import annotations

from pathlib import Path

import pytest

from orion.services.encryption_manager.key_manager import key_manager
from orion.services.pgp_manager import pgp_manager as pgp_module
from orion.services.pgp_manager.pgp_manager import pgp_manager
from tests.scripts.pgp_manager.fakes import FakeProcess
from tests.scripts.pgp_manager.helpers import patch_subprocess


@pytest.mark.anyio
async def test_run_gpg_returns_stdout_on_success(monkeypatch):
    patch_subprocess(monkeypatch, FakeProcess(stdout=b"OUTPUT", returncode=0))
    manager = object.__new__(pgp_manager)
    assert await manager._run_gpg(["--version"]) == b"OUTPUT"


@pytest.mark.anyio
async def test_run_gpg_raises_on_nonzero_return(monkeypatch):
    patch_subprocess(monkeypatch, FakeProcess(stderr=b"failure", returncode=2))
    manager = object.__new__(pgp_manager)
    with pytest.raises(pgp_module.HTTPException) as error:
        await manager._run_gpg(["--homedir", "/tmp/x", "--bad"])
    assert error.value.status_code == 500


@pytest.mark.anyio
async def test_generate_key_pair_returns_keys_and_fingerprint(monkeypatch):
    manager = object.__new__(pgp_manager)

    async def fake_run_gpg(args, _input_data=None):
        if "--generate-key" in args:
            return b""
        if "--list-secret-keys" in args:
            return b"sec:::::::::::\nfpr:::::::::ABCDEF1234567890:\n"
        if "--export-secret-keys" in args:
            return b"PRIVATE"
        if "--export" in args:
            return b"PUBLIC"
        return b""

    manager._run_gpg = fake_run_gpg
    public_key, private_key, fingerprint = await manager.generate_key_pair()
    assert public_key == "PUBLIC"
    assert private_key == "PRIVATE"
    assert fingerprint == "ABCDEF1234567890"


@pytest.mark.anyio
async def test_generate_key_pair_raises_without_fingerprint(monkeypatch):
    manager = object.__new__(pgp_manager)

    async def fake_run_gpg(args, _input_data=None):
        if "--list-secret-keys" in args:
            return b"sec:::::::::::\n"
        return b""

    manager._run_gpg = fake_run_gpg
    with pytest.raises(pgp_module.HTTPException) as error:
        await manager.generate_key_pair()
    assert error.value.status_code == 500


@pytest.mark.anyio
async def test_sign_bytes_returns_detached_signature(monkeypatch):
    manager = object.__new__(pgp_manager)

    class FakeKeyManager:
        @staticmethod
        def unwrap(_wrapped):
            return "PRIVATE-KEY-PEM"

    monkeypatch.setattr(key_manager, "get_instance", staticmethod(lambda: FakeKeyManager()))

    async def fake_run_gpg(args, _input_data=None):
        if "--output" in args:
            Path(args[args.index("--output") + 1]).write_text("-----SIGNATURE-----")
        return b""

    manager._run_gpg = fake_run_gpg
    signature = await manager.sign_bytes(b"payload", "wrapped-private-key")
    assert signature == "-----SIGNATURE-----"
