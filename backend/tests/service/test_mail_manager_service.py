from __future__ import annotations

import pytest

from orion.services.mail_manager.mail_manager import mail_manager
from tests.fake_model.fakes import FakeMailTransport


@pytest.mark.anyio
async def test_send_email_source_dispatches_message_over_smtp(monkeypatch):
    manager = mail_manager.get_instance()
    transport = FakeMailTransport()

    monkeypatch.setattr("aiosmtplib.send", transport.send)

    email_message = manager.build_email_message(sender_address="root@mail.orionintelligence.org", receiver_addresses=["huzaifa@orionintelligence.org"], subject="Deployment window tonight", body="Run ./run.sh build -p once the certificate is issued.")
    raw_source = manager.serialize_email_message(email_message)

    await manager.send_email_source(raw_source=raw_source, sender_address="root@mail.orionintelligence.org", recipient_addresses=["huzaifa@orionintelligence.org"])

    assert len(transport.sent) == 1
    dispatch = transport.sent[0]
    assert dispatch["sender"] == "root@mail.orionintelligence.org"
    assert dispatch["recipients"] == ["huzaifa@orionintelligence.org"]
    assert dispatch["message"] == raw_source
    assert b"Subject: Deployment window tonight" in dispatch["message"]
