from orion.helper_manager.env_handler import env_handler


class MONGO_CONNECTIONS:
    S_MONGO_URL = env_handler.get_instance().env("MONGODB_URL", "mongodb://localhost:27017")
    S_MONGO_DATABASE_NAME = env_handler.get_instance().env("MONGODB_DATABASE", "orion_mail")


class MONGO_COLLECTIONS:
    USERS = "users"
    MAILBOXES = "mailboxes"
    ADDRESS_BOOK = "address_book"
    MESSAGES = "messages"
    LABELS = "labels"
    DOMAIN_REPORTS = "domain_reports"
    DOMAIN_REPUTATIONS = "domain_reputations"
    SENDER_BLOCKS = "sender_blocks"
    ATTACHMENTS = "attachments"
    SYSTEM_CONFIG = "system_config"
    USER_KEYS = "user_keys"
