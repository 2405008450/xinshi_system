import base64
import json
import os

import pytest

from crypto_utils import (
    CredentialCryptoConfigurationError,
    credential_fingerprint,
    decrypt_credential,
    encrypt_credential,
)


def configure_key(monkeypatch, version="v1"):
    key = bytes(range(32))
    monkeypatch.setenv(
        "CREDENTIAL_ENCRYPTION_KEYS",
        json.dumps({version: base64.b64encode(key).decode("ascii")}),
    )
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_ACTIVE_VERSION", version)


def test_credential_aes_gcm_round_trip_and_random_nonce(monkeypatch):
    configure_key(monkeypatch)
    first, version = encrypt_credential("demo@example.com")
    second, _ = encrypt_credential("demo@example.com")

    assert version == "v1"
    assert first != second
    assert decrypt_credential(first, version) == "demo@example.com"


def test_credential_fingerprint_is_normalized_and_stable(monkeypatch):
    configure_key(monkeypatch)
    assert credential_fingerprint(" Demo@Example.COM ") == credential_fingerprint("demo@example.com")
    assert len(credential_fingerprint("demo@example.com")) == 64


def test_credential_crypto_refuses_missing_configuration(monkeypatch):
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_KEYS", raising=False)
    monkeypatch.delenv("CREDENTIAL_ENCRYPTION_ACTIVE_VERSION", raising=False)
    with pytest.raises(CredentialCryptoConfigurationError):
        encrypt_credential("secret")


def test_credential_crypto_detects_tampering(monkeypatch):
    configure_key(monkeypatch)
    ciphertext, version = encrypt_credential("secret")
    tampered = ciphertext[:-1] + bytes([ciphertext[-1] ^ 1])
    with pytest.raises(Exception):
        decrypt_credential(tampered, version)
