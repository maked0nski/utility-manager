import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def _fernet_key() -> bytes:
    secret = settings.app_secret_key.encode("utf-8")
    digest = hashlib.sha256(secret).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_text(plain: str | None) -> str | None:
    if not plain:
        return None
    return Fernet(_fernet_key()).encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_text(cipher: str | None) -> str | None:
    if not cipher:
        return None
    return Fernet(_fernet_key()).decrypt(cipher.encode("utf-8")).decode("utf-8")
