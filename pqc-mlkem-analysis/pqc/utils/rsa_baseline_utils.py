#!/usr/bin/env python3
"""RSA-OAEP helper functions for Phase 4.1 comparison experiments.

These helpers are intentionally isolated from the baseline ZK-EHR code. They
generate transient in-memory test keys only and never write private keys,
session keys, or recovered plaintext keys to result files.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


T = TypeVar("T")


RSA_KEY_SIZE_BITS = 2048
RSA_PUBLIC_EXPONENT = 65537
AES_SESSION_KEY_BYTES = 32


@dataclass(frozen=True)
class TimedResult:
    value: object
    elapsed_ms: float


def measure_ms(function: Callable[[], T]) -> tuple[T, float]:
    start = time.perf_counter()
    value = function()
    return value, (time.perf_counter() - start) * 1000


def generate_rsa_keypair() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(
        public_exponent=RSA_PUBLIC_EXPONENT,
        key_size=RSA_KEY_SIZE_BITS,
    )


def generate_aes_session_key(length_bytes: int = AES_SESSION_KEY_BYTES) -> bytes:
    return os.urandom(length_bytes)


def rsa_oaep_wrap(public_key: rsa.RSAPublicKey, session_key: bytes) -> bytes:
    return public_key.encrypt(
        session_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )


def rsa_oaep_unwrap(private_key: rsa.RSAPrivateKey, ciphertext: bytes) -> bytes:
    return private_key.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )


def rsa_public_key_size_bytes(public_key: rsa.RSAPublicKey) -> int:
    return len(
        public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def rsa_private_key_size_bytes(private_key: rsa.RSAPrivateKey) -> int:
    return len(
        private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


def run_rsa_oaep_iteration(iteration: int) -> dict[str, object]:
    private_key, keygen_ms = measure_ms(generate_rsa_keypair)
    public_key = private_key.public_key()
    session_key = generate_aes_session_key()

    wrapped_key, wrap_ms = measure_ms(lambda: rsa_oaep_wrap(public_key, session_key))
    recovered_key, unwrap_ms = measure_ms(lambda: rsa_oaep_unwrap(private_key, wrapped_key))
    recovered_matches = recovered_key == session_key

    public_key_size = rsa_public_key_size_bytes(public_key)
    private_key_size = rsa_private_key_size_bytes(private_key)
    wrapped_key_size = len(wrapped_key)
    session_key_size = len(session_key)

    return {
        "iteration": iteration,
        "algorithm": "RSA-OAEP-2048-SHA256",
        "rsa_key_size_bits": RSA_KEY_SIZE_BITS,
        "oaep_hash": "SHA256",
        "aes_session_key_size": session_key_size,
        "public_key_size": public_key_size,
        "private_key_size": private_key_size,
        "wrapped_key_size": wrapped_key_size,
        "keygen_ms": keygen_ms,
        "wrap_ms": wrap_ms,
        "unwrap_ms": unwrap_ms,
        "recovered_key_match": recovered_matches,
        "total_artifact_size": public_key_size + private_key_size + wrapped_key_size,
        "status": "PASS" if recovered_matches else "FAIL",
        "notes": "Transient in-memory comparison iteration; no keys persisted.",
    }
