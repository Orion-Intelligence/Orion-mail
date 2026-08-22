from pathlib import Path

from orion.helper_manager.env_handler import env_handler


class CONSTANTS:
    BASE_DIR = Path(__file__).resolve().parents[2]

    S_MAIL_DOMAIN = env_handler.get_instance().env("MAIL_DOMAIN", "mail.orionintelligence.org")
    S_SEED_LOCAL_TEST_MAILBOXES = env_handler.get_instance().env("SEED_LOCAL_TEST_MAILBOXES", "false").lower() == "true"

    S_ORION_MAIL_SESSION_MAX_AGE_SECONDS = int(
        env_handler.get_instance().env("ORION_MAIL_SESSION_MAX_AGE_SECONDS", "1800")
    )

    S_ORION_INTELLIGENCE_INTERNAL_URL = env_handler.get_instance().env(
        "ORION_INTELLIGENCE_INTERNAL_URL", "http://trusted-web-main:8070"
    ).strip().rstrip("/")
    S_ORION_INTELLIGENCE_PUBLIC_URL = env_handler.get_instance().env(
        "ORION_INTELLIGENCE_PUBLIC_URL", "http://localhost:4200"
    ).strip().rstrip("/")
    S_ORION_MAIL_SSO_CLIENT_SECRET = env_handler.get_instance().env(
        "ORION_MAIL_SSO_CLIENT_SECRET", ""
    )
    S_ORION_MAIL_PUBLIC_URLS = [
        url.strip().rstrip("/")
        for url in env_handler.get_instance().env(
            "ORION_MAIL_PUBLIC_URLS",
            "http://localhost:4300,http://mail.localhost:4200,https://mail.orionintelligence.org",
        ).split(",")
        if url.strip()
    ]
    S_ORION_SSO_TIMEOUT_SECONDS = float(
        env_handler.get_instance().env("ORION_SSO_TIMEOUT_SECONDS", "5")
    )

    S_SMTP_HOST = env_handler.get_instance().env("SMTP_HOST", "localhost")
    S_SMTP_PORT = int(env_handler.get_instance().env("SMTP_PORT", "25"))
    S_SMTP_USERNAME = env_handler.get_instance().env("SMTP_USERNAME") or None
    S_SMTP_PASSWORD = env_handler.get_instance().env("SMTP_PASSWORD") or None
    S_SMTP_START_TLS = env_handler.get_instance().env("SMTP_START_TLS", "false").lower() == "true"

    S_ATTACHMENT_DIR = Path(env_handler.get_instance().env("ATTACHMENT_STORAGE_DIR", str(BASE_DIR / "static" / "resource" / "attachments"))).resolve()
    S_RAW_MESSAGE_DIR = (S_ATTACHMENT_DIR / "raw").resolve()
    S_ATTACHMENT_CLEANUP_INTERVAL_SECONDS = int(env_handler.get_instance().env("ATTACHMENT_CLEANUP_INTERVAL_SECONDS", "3600"))
    S_SCHEDULED_DELIVERY_INTERVAL_SECONDS = int(env_handler.get_instance().env("SCHEDULED_DELIVERY_INTERVAL_SECONDS", "60"))

    S_TRANSLATION_API_URL = env_handler.get_instance().env("TRANSLATION_API_URL", "https://translate.googleapis.com/translate_a/single").strip()
    S_TRANSLATION_TIMEOUT_SECONDS = int(env_handler.get_instance().env("TRANSLATION_TIMEOUT_SECONDS", "20"))

    S_ENCRYPTION_KEY = env_handler.get_instance().env("ENCRYPTION_KEY", "")

    S_CLAMAV_HOST = env_handler.get_instance().env("CLAMAV_HOST", "clamav")
    S_CLAMAV_PORT = int(env_handler.get_instance().env("CLAMAV_PORT", "3310"))
    S_CLAMAV_TIMEOUT_SECONDS = float(env_handler.get_instance().env("CLAMAV_TIMEOUT_SECONDS", "30"))

    S_COOKIE_SECURE = env_handler.get_instance().env("COOKIE_SECURE", "true").lower() == "true"
    S_INCOMING_MAIL_TOKEN = env_handler.get_instance().env("INCOMING_MAIL_TOKEN", "")
    S_ALLOWED_HOSTS = [host.strip() for host in env_handler.get_instance().env("ALLOWED_HOSTS", f"{S_MAIL_DOMAIN},localhost,127.0.0.1").split(",") if host.strip()]
    S_CORS_ALLOWED_ORIGINS = [origin.strip() for origin in env_handler.get_instance().env("CORS_ALLOWED_ORIGINS", "http://localhost:4300,http://127.0.0.1:4300").split(",") if origin.strip()]
