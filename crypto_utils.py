"""标注平台凭据的可逆加密与账号指纹工具。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CredentialCryptoConfigurationError(RuntimeError):
    """凭据密钥没有正确配置。"""


@dataclass(frozen=True)
class CredentialKeyring:
    keys: dict[str, bytes]
    active_version: str


def _load_keyring() -> CredentialKeyring:
    raw_keys = os.getenv("CREDENTIAL_ENCRYPTION_KEYS", "").strip()
    active_version = os.getenv("CREDENTIAL_ENCRYPTION_ACTIVE_VERSION", "").strip()
    if not raw_keys or not active_version:
        raise CredentialCryptoConfigurationError(
            "未配置 CREDENTIAL_ENCRYPTION_KEYS 或 CREDENTIAL_ENCRYPTION_ACTIVE_VERSION"
        )
    try:
        values = json.loads(raw_keys)
        keys = {
            str(version): base64.b64decode(encoded, validate=True)
            for version, encoded in values.items()
        }
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise CredentialCryptoConfigurationError("凭据加密密钥配置不是有效的版本/Base64 映射") from exc
    if active_version not in keys:
        raise CredentialCryptoConfigurationError("当前凭据加密密钥版本不存在")
    if any(len(key) != 32 for key in keys.values()):
        raise CredentialCryptoConfigurationError("每个凭据加密密钥必须是 32 字节的 AES-256 密钥")
    return CredentialKeyring(keys=keys, active_version=active_version)


def encrypt_credential(value: str) -> tuple[bytes, str]:
    """使用当前版本密钥加密字符串，密文格式为 12 字节 nonce + AES-GCM 输出。"""
    keyring = _load_keyring()
    nonce = os.urandom(12)
    plaintext = value.encode("utf-8")
    ciphertext = AESGCM(keyring.keys[keyring.active_version]).encrypt(
        nonce, plaintext, keyring.active_version.encode("utf-8")
    )
    return nonce + ciphertext, keyring.active_version


def decrypt_credential(ciphertext: bytes, key_version: str) -> str:
    keyring = _load_keyring()
    key = keyring.keys.get(key_version)
    if key is None:
        raise CredentialCryptoConfigurationError(f"找不到凭据加密密钥版本：{key_version}")
    if len(ciphertext) < 29:
        raise ValueError("凭据密文格式无效")
    value = AESGCM(key).decrypt(
        ciphertext[:12], ciphertext[12:], key_version.encode("utf-8")
    )
    return value.decode("utf-8")


def credential_fingerprint(login_account: str, key_version: str | None = None) -> str:
    """生成不暴露账号明文的稳定 HMAC-SHA256 指纹。"""
    keyring = _load_keyring()
    version = key_version or keyring.active_version
    key = keyring.keys.get(version)
    if key is None:
        raise CredentialCryptoConfigurationError(f"找不到凭据加密密钥版本：{version}")
    normalized = login_account.strip().casefold().encode("utf-8")
    fingerprint_key = hmac.new(key, b"xinshi-credential-fingerprint-v1", hashlib.sha256).digest()
    return hmac.new(fingerprint_key, normalized, hashlib.sha256).hexdigest()
