import logging
import os
import re


class log:
    __instance = None

    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    OBJECT_ID_PATTERN = re.compile(r"\b[a-fA-F0-9]{24}\b")
    UUID_PATTERN = re.compile(r"\b[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}\b")
    IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    LONG_TOKEN_PATTERN = re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")
    SECRET_FIELD_PATTERN = re.compile(r"(?i)\b(token|secret|password|authorization|cookie|session|key)\s*[:=]\s*['\"]?[^'\"\s,}]+")

    @staticmethod
    def g():
        if log.__instance is None:
            log()
        return log.__instance

    def __init__(self):
        if log.__instance is not None:
            raise Exception("This class is a singleton!")

        log.__instance = self
        self.__logger = logging.getLogger("orion_mail")

        if not self.__logger.hasHandlers():
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
            self.__logger.addHandler(handler)

        log_level = os.getenv("ORION_MAIL_LOG_LEVEL", "WARNING").upper()
        self.__logger.setLevel(log_level)
        self.__logger.propagate = False

    @classmethod
    def sanitize(cls, message: str) -> str:
        safe_message = str(message)

        safe_message = cls.SECRET_FIELD_PATTERN.sub(r"\1=[redacted]", safe_message)
        safe_message = cls.EMAIL_PATTERN.sub("[redacted-email]", safe_message)
        safe_message = cls.UUID_PATTERN.sub("[redacted-uuid]", safe_message)
        safe_message = cls.OBJECT_ID_PATTERN.sub("[redacted-id]", safe_message)
        safe_message = cls.IP_PATTERN.sub("[redacted-ip]", safe_message)
        safe_message = cls.LONG_TOKEN_PATTERN.sub("[redacted-token]", safe_message)

        return safe_message

    @staticmethod
    def safe_error(error: Exception) -> str:
        return error.__class__.__name__

    def i(self, message: str) -> None:
        self.__logger.info(self.sanitize(message))

    def e(self, message: str) -> None:
        self.__logger.error(self.sanitize(message))
