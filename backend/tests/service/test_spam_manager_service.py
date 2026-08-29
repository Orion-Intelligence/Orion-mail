from __future__ import annotations

from email import message_from_bytes, policy

import pytest

import postfix_incoming_handler as handler
from orion.api.interactive.incoming_mail_manager.incoming_mail_manager import incoming_mail_manager
from orion.constants.constant import CONSTANTS
from orion.services.spam_manager import spam_manager as spam_module
from tests.fake_model.fakes import FakeRspamdClient

SCANNED_SPAM = b"From: promo@spammy-example.com\r\nTo: test1@mail.orionintelligence.org\r\nSubject: Free prize\r\nX-Spam: Yes\r\nX-Spamd-Result: default: False [9.30 / 15.00];\r\n\tBAYES_SPAM(4.00)[99.99%];\r\n\tDMARC_POLICY_REJECT(2.00)[]\r\nAuthentication-Results: mail.orionintelligence.org;\r\n\tdkim=fail;\r\n\tspf=softfail;\r\n\tdmarc=fail\r\n\r\nClaim your prize today\r\n"
SCANNED_HAM = b"From: colleague@orionintelligence.org\r\nTo: test1@mail.orionintelligence.org\r\nSubject: Deployment window\r\nX-Spamd-Result: default: False [-1.20 / 15.00];\r\n\tMIME_GOOD(-0.10)[text/plain]\r\n\r\nCertificate is issued\r\n"


def parse(raw_source: bytes):
    return message_from_bytes(raw_source, policy=policy.default)


def test_extract_spam_verdict_reads_the_score_and_flag_added_by_rspamd():
    assert handler.extract_spam_verdict(parse(SCANNED_SPAM)) == {"score": "9.30", "flag": "yes"}
    assert handler.extract_spam_verdict(parse(SCANNED_HAM)) == {"score": "-1.20", "flag": ""}
    assert handler.extract_spam_verdict(parse(b"Subject: unscanned\r\n\r\nNo milter ran\r\n")) == {"score": "", "flag": ""}


def test_extract_authentication_results_reads_the_header_rspamd_adds():
    assert handler.extract_authentication_results(parse(SCANNED_SPAM)) == {"spf": "softfail", "dkim": "fail", "dmarc": "fail"}


def test_is_spam_verdict_routes_on_the_flag_or_the_configured_threshold():
    assert incoming_mail_manager.is_spam_verdict({"score": "9.30", "flag": "yes"}) == (True, 9.3)
    assert incoming_mail_manager.is_spam_verdict({"score": str(CONSTANTS.S_SPAM_SCORE_THRESHOLD), "flag": ""}) == (True, CONSTANTS.S_SPAM_SCORE_THRESHOLD)
    assert incoming_mail_manager.is_spam_verdict({"score": "-1.20", "flag": ""}) == (False, -1.2)
    assert incoming_mail_manager.is_spam_verdict({"score": "", "flag": ""}) == (False, None)
    assert incoming_mail_manager.is_spam_verdict(None) == (False, None)


@pytest.mark.anyio
async def test_learn_spam_and_learn_ham_post_the_source_to_the_rspamd_controller(monkeypatch):
    FakeRspamdClient.calls.clear()
    monkeypatch.setattr(spam_module.httpx, "AsyncClient", FakeRspamdClient)
    monkeypatch.setattr(CONSTANTS, "S_RSPAMD_CONTROLLER_PASSWORD", "controller-secret")

    manager = spam_module.spam_manager.get_instance()

    assert await manager.learn_spam(SCANNED_SPAM) is True
    assert await manager.learn_ham(SCANNED_HAM) is True

    assert [call["url"] for call in FakeRspamdClient.calls] == [f"{CONSTANTS.S_RSPAMD_CONTROLLER_URL}/learnspam", f"{CONSTANTS.S_RSPAMD_CONTROLLER_URL}/learnham"]
    assert FakeRspamdClient.calls[0]["content"] == SCANNED_SPAM
    assert FakeRspamdClient.calls[0]["headers"]["Password"] == "controller-secret"


@pytest.mark.anyio
async def test_learning_is_skipped_without_a_source_or_controller_password(monkeypatch):
    FakeRspamdClient.calls.clear()
    monkeypatch.setattr(spam_module.httpx, "AsyncClient", FakeRspamdClient)
    monkeypatch.setattr(CONSTANTS, "S_RSPAMD_CONTROLLER_PASSWORD", "controller-secret")

    manager = spam_module.spam_manager.get_instance()
    assert await manager.learn_spam(b"") is False

    monkeypatch.setattr(CONSTANTS, "S_RSPAMD_CONTROLLER_PASSWORD", "")
    assert await manager.learn_spam(SCANNED_SPAM) is False
    assert FakeRspamdClient.calls == []
