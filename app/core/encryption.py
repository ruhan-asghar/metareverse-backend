"""AES-256-GCM encryption for Facebook/Meta access tokens."""

import hashlib
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import get_settings


def _get_key() -> bytes:
    settings = get_settings()
    key_source = settings.encryption_key or settings.clerk_secret_key
    return hashlib.sha256(key_source.encode()).digest()


def encrypt_token(plaintext: str) -> bytes:
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # Store as: nonce (12 bytes) + ciphertext+tag
    return nonce + ciphertext


def decrypt_token(data: bytes) -> str:
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = data[:12]
    ciphertext = data[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
