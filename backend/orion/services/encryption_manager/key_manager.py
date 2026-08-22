from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from orion.constants.constant import CONSTANTS
from orion.services.encryption_manager.encryption_manager import encryption_manager
from orion.services.mongo_manager.mongo_controller import mongo_controller
from orion.services.mongo_manager.shared_model.db_user_key_model import db_user_key_model

RSA_KEY_SIZE = 3072
RSA_PUBLIC_EXPONENT = 65537


class key_manager:
    __instance = None

    @staticmethod
    def get_instance():
        if key_manager.__instance is None:
            key_manager()
        return key_manager.__instance

    def __init__(self):
        if key_manager.__instance is not None:
            raise Exception("This class is a singleton!")
        key_manager.__instance = self
        self._engine = mongo_controller.get_instance().get_engine()
        self._master = encryption_manager.create(CONSTANTS.S_ENCRYPTION_KEY)
        self._private_key_cache = {}

    @staticmethod
    def generate_data_key() -> bytes:
        return Fernet.generate_key()

    @staticmethod
    def generate_key_pair() -> tuple[str, str]:
        private_key = rsa.generate_private_key(public_exponent=RSA_PUBLIC_EXPONENT, key_size=RSA_KEY_SIZE)
        private_pem = private_key.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption()).decode()
        public_pem = private_key.public_key().public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        return public_pem, private_pem

    def wrap(self, value: str) -> str:
        return self._master.encrypt(value)

    def unwrap(self, wrapped: str) -> str:
        return self._master.decrypt(wrapped)

    @staticmethod
    def load_public_key(public_pem: str) -> rsa.RSAPublicKey:
        public_key = serialization.load_pem_public_key(public_pem.encode())
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise ValueError("Stored public key is not an RSA key")
        return public_key

    @staticmethod
    def load_private_pem(private_pem: str) -> rsa.RSAPrivateKey:
        private_key = serialization.load_pem_private_key(private_pem.encode(), password=None)
        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise ValueError("Stored private key is not an RSA key")
        return private_key

    @staticmethod
    def seal_data_key(public_pem: str, data_key: bytes) -> bytes:
        return key_manager.load_public_key(public_pem).encrypt(data_key, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))

    @staticmethod
    def open_data_key(private_pem: str, sealed_key: bytes) -> bytes:
        return key_manager.load_private_pem(private_pem).decrypt(sealed_key, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))

    async def create_user_keys(self, auth_id: str) -> db_user_key_model:
        public_pem, private_pem = self.generate_key_pair()
        record = db_user_key_model(auth_id=auth_id, wrapped_key=self.wrap(self.generate_data_key().decode()), public_key=public_pem, wrapped_private_key=self.wrap(private_pem))
        return await self._engine.save(record)

    async def get_user_keys(self, auth_id: str) -> db_user_key_model | None:
        return await self._engine.find_one(db_user_key_model, db_user_key_model.auth_id == auth_id)

    async def get_or_create_user_keys(self, auth_id: str) -> db_user_key_model:
        return await self.get_user_keys(auth_id) or await self.create_user_keys(auth_id)

    async def get_data_key(self, auth_id: str) -> bytes:
        record = await self.get_or_create_user_keys(auth_id)
        return self.unwrap(record.wrapped_key).encode()

    async def get_private_key(self, auth_id: str) -> str | None:
        record = await self.get_user_keys(auth_id)
        return self.unwrap(record.wrapped_private_key) if record else None

    async def load_private_key(self, auth_id: str) -> rsa.RSAPrivateKey | None:
        cached = self._private_key_cache.get(auth_id)
        if cached is not None:
            return cached

        private_pem = await self.get_private_key(auth_id)
        if private_pem is None:
            return None

        loaded = self.load_private_pem(private_pem)
        self._private_key_cache[auth_id] = loaded
        return loaded

    async def unseal_data_key(self, auth_id: str, sealed_key: bytes) -> bytes | None:
        private_key = await self.load_private_key(auth_id)
        if private_key is None:
            return None
        return private_key.decrypt(sealed_key, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
