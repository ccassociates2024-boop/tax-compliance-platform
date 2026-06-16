"""
AES-256-GCM Credential Vault
- Plaintext passwords are NEVER persisted
- Each credential encrypted with: master_key XOR client_id_derived_key
- Nonce is random 12 bytes, unique per encryption operation
- Auth tag validates integrity (tamper detection)
"""
import os
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import get_settings
from models import PortalCredential, PortalType

settings = get_settings()


def _derive_client_key(client_id: str) -> bytes:
    """Derive a per-client key from master key + client_id as salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=f"{settings.VAULT_SALT}:{client_id}".encode(),
        iterations=600_000,  # NIST recommended minimum for PBKDF2-SHA256
    )
    master_key_bytes = bytes.fromhex(settings.VAULT_MASTER_KEY)
    return kdf.derive(master_key_bytes)


def encrypt_secret(plaintext: str, client_id: str) -> dict:
    """
    Encrypts a secret using AES-256-GCM.
    Returns: {encrypted_password, nonce, auth_tag} as hex strings.
    """
    key = _derive_client_key(client_id)
    nonce = secrets.token_bytes(12)   # 96-bit random nonce
    aesgcm = AESGCM(key)

    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # AESGCM appends 16-byte auth tag to ciphertext
    ciphertext = ciphertext_with_tag[:-16]
    auth_tag = ciphertext_with_tag[-16:]

    return {
        "encrypted_password": ciphertext.hex(),
        "nonce": nonce.hex(),
        "auth_tag": auth_tag.hex(),
    }


def decrypt_secret(encrypted_password: str, nonce: str, auth_tag: str, client_id: str) -> str:
    """
    Decrypts a secret. Raises ValueError if integrity check fails (tampered data).
    """
    key = _derive_client_key(client_id)
    aesgcm = AESGCM(key)

    ciphertext = bytes.fromhex(encrypted_password)
    nonce_bytes = bytes.fromhex(nonce)
    tag_bytes = bytes.fromhex(auth_tag)

    # Reconstruct ciphertext+tag as AESGCM expects
    ciphertext_with_tag = ciphertext + tag_bytes

    try:
        plaintext = aesgcm.decrypt(nonce_bytes, ciphertext_with_tag, None)
        return plaintext.decode("utf-8")
    except Exception:
        raise ValueError("Credential decryption failed — data may be corrupted or tampered")


class CredentialVault:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def store_credential(
        self,
        client_id: str,
        portal_type: PortalType,
        username: str,
        password: str,
    ) -> PortalCredential:
        """Store encrypted credential, replacing existing if present."""
        encrypted = encrypt_secret(password, client_id)

        # Check if credential already exists for this client+portal
        result = await self.db.execute(
            select(PortalCredential).where(
                PortalCredential.client_id == client_id,
                PortalCredential.portal_type == portal_type,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.username = username
            existing.encrypted_password = encrypted["encrypted_password"]
            existing.nonce = encrypted["nonce"]
            existing.auth_tag = encrypted["auth_tag"]
            return existing
        else:
            cred = PortalCredential(
                client_id=client_id,
                portal_type=portal_type,
                username=username,
                **encrypted,
            )
            self.db.add(cred)
            return cred

    async def get_decrypted_password(
        self,
        client_id: str,
        portal_type: PortalType,
    ) -> Optional[tuple[str, str]]:
        """Returns (username, plaintext_password) or None if not found."""
        result = await self.db.execute(
            select(PortalCredential).where(
                PortalCredential.client_id == client_id,
                PortalCredential.portal_type == portal_type,
            )
        )
        cred = result.scalar_one_or_none()
        if not cred:
            return None

        password = decrypt_secret(
            cred.encrypted_password,
            cred.nonce,
            cred.auth_tag,
            client_id,
        )
        return (cred.username, password)

    async def delete_credential(self, client_id: str, portal_type: PortalType) -> bool:
        result = await self.db.execute(
            select(PortalCredential).where(
                PortalCredential.client_id == client_id,
                PortalCredential.portal_type == portal_type,
            )
        )
        cred = result.scalar_one_or_none()
        if cred:
            await self.db.delete(cred)
            return True
        return False

    async def has_credential(self, client_id: str, portal_type: PortalType) -> bool:
        result = await self.db.execute(
            select(PortalCredential.id).where(
                PortalCredential.client_id == client_id,
                PortalCredential.portal_type == portal_type,
            )
        )
        return result.scalar_one_or_none() is not None
