from __future__ import annotations

from email import message_from_bytes, policy

SCANNED_SPAM = b"From: promo@spammy-example.com\r\nTo: test1@mail.orionintelligence.org\r\nSubject: Free prize\r\nX-Spam: Yes\r\nX-Spamd-Result: default: False [9.30 / 15.00];\r\n\tBAYES_SPAM(4.00)[99.99%];\r\n\tDMARC_POLICY_REJECT(2.00)[]\r\nAuthentication-Results: mail.orionintelligence.org;\r\n\tdkim=fail;\r\n\tspf=softfail;\r\n\tdmarc=fail\r\n\r\nClaim your prize today\r\n"
SCANNED_HAM = b"From: colleague@orionintelligence.org\r\nTo: test1@mail.orionintelligence.org\r\nSubject: Deployment window\r\nX-Spamd-Result: default: False [-1.20 / 15.00];\r\n\tMIME_GOOD(-0.10)[text/plain]\r\n\r\nCertificate is issued\r\n"


def parse(raw_source: bytes):
    return message_from_bytes(raw_source, policy=policy.default)
