from __future__ import annotations

import os

os.environ.setdefault("ORION_TESTING", "true")
os.environ.setdefault("MAIL_DOMAIN", "mail.orionintelligence.org")
os.environ.setdefault("SEED_LOCAL_TEST_MAILBOXES", "false")
