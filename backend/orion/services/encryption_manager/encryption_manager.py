from cryptography.fernet import Fernet


class encryption_manager:
    def __init__(self, secret_key: str | bytes):
        key = secret_key.encode() if isinstance(secret_key, str) else secret_key
        self.fernet = Fernet(key)

    @staticmethod
    def create(secret_key: str | bytes):
        return encryption_manager(secret_key)

    def encrypt(self, data: str) -> str:
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt(self, token: str) -> str:
        return self.fernet.decrypt(token.encode()).decode()

    def encrypt_bytes(self, data: bytes) -> bytes:
        return self.fernet.encrypt(data)

    def decrypt_bytes(self, token: bytes) -> bytes:
        return self.fernet.decrypt(token)
