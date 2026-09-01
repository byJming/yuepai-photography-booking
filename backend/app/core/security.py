from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65_536, parallelism=2)


class FieldCipher:
    """AES-256-GCM 字段加密器，AAD 用于绑定表、字段和业务记录。"""

    def __init__(self, base64_key: str) -> None:
        key = base64.b64decode(base64_key, validate=True)
        if len(key) != 32:
            raise ValueError("字段加密密钥必须为 32 字节")
        self._cipher = AESGCM(key)

    def encrypt(self, plaintext: str, aad: str) -> bytes:
        nonce = secrets.token_bytes(12)
        encrypted = self._cipher.encrypt(nonce, plaintext.encode("utf-8"), aad.encode("utf-8"))
        return b"v1:" + base64.b64encode(nonce + encrypted)

    def decrypt(self, ciphertext: bytes, aad: str) -> str:
        if not ciphertext.startswith(b"v1:"):
            raise ValueError("不支持的密文版本")
        payload = base64.b64decode(ciphertext[3:], validate=True)
        if len(payload) < 29:
            raise ValueError("密文格式无效")
        nonce, encrypted = payload[:12], payload[12:]
        try:
            plaintext = self._cipher.decrypt(nonce, encrypted, aad.encode("utf-8"))
        except Exception as exc:
            raise ValueError("敏感字段解密失败") from exc
        return plaintext.decode("utf-8")


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(secret: str, pepper: str) -> str:
    return hmac.new(pepper.encode("utf-8"), secret.encode("utf-8"), hashlib.sha256).hexdigest()


def hmac_bytes(value: str, key: str) -> bytes:
    return hmac.new(key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).digest()


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verify_password(encoded: str, password: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(encoded, password)
    except (VerifyMismatchError, InvalidHashError):
        return False
