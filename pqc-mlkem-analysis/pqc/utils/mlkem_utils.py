#!/usr/bin/env python3
"""ML-KEM helper functions for Phase 4.1 comparison experiments.

These helpers use liboqs through the local ``oqs`` Python module. They are a
parallel experimental path only and do not alter the baseline ZK-EHR system.
"""

from __future__ import annotations

import time
from typing import Callable, TypeVar


T = TypeVar("T")


PREFERRED_KEM = "ML-KEM-768"
FALLBACK_KEMS = ["ML-KEM-512", "ML-KEM-1024", "Kyber768", "Kyber512", "Kyber1024"]


def measure_ms(function: Callable[[], T]) -> tuple[T, float]:
    start = time.perf_counter()
    value = function()
    return value, (time.perf_counter() - start) * 1000


def available_kems() -> list[str]:
    import oqs

    return sorted(oqs.get_enabled_kem_mechanisms())


def select_mlkem_algorithm() -> tuple[str, str]:
    algorithms = available_kems()
    if PREFERRED_KEM in algorithms:
        return PREFERRED_KEM, "preferred"
    for candidate in FALLBACK_KEMS:
        if candidate in algorithms:
            return candidate, "fallback"
    for algorithm in algorithms:
        upper = algorithm.upper().replace("_", "-")
        if "ML-KEM" in upper or "KYBER" in upper:
            return algorithm, "fallback"
    raise RuntimeError("No ML-KEM or Kyber-family KEM is available through oqs.")


def export_secret_key_size(kem: object) -> int | str:
    export_secret_key = getattr(kem, "export_secret_key", None)
    if callable(export_secret_key):
        secret_key = export_secret_key()
        if isinstance(secret_key, bytes):
            return len(secret_key)
    details = getattr(kem, "details", {}) or {}
    return details.get("length_secret_key", "")


def run_mlkem_iteration(iteration: int, algorithm_name: str | None = None) -> dict[str, object]:
    import oqs

    selected_algorithm, selection_mode = select_mlkem_algorithm()
    if algorithm_name:
        algorithms = available_kems()
        if algorithm_name not in algorithms:
            raise RuntimeError(f"Requested KEM is not available: {algorithm_name}")
        selected_algorithm = algorithm_name
        selection_mode = "requested"

    with oqs.KeyEncapsulation(selected_algorithm) as kem:
        public_key, keygen_ms = measure_ms(kem.generate_keypair)
        secret_key_size = export_secret_key_size(kem)
        (ciphertext, shared_secret_sender), encapsulation_ms = measure_ms(
            lambda: kem.encap_secret(public_key)
        )
        shared_secret_receiver, decapsulation_ms = measure_ms(lambda: kem.decap_secret(ciphertext))
        shared_secret_match = shared_secret_sender == shared_secret_receiver

    public_key_size = len(public_key)
    ciphertext_size = len(ciphertext)
    shared_secret_size = len(shared_secret_sender)
    total_artifact_size = public_key_size + ciphertext_size
    if isinstance(secret_key_size, int):
        total_artifact_size += secret_key_size

    return {
        "iteration": iteration,
        "algorithm": selected_algorithm,
        "selection_mode": selection_mode,
        "public_key_size": public_key_size,
        "secret_key_size": secret_key_size,
        "ciphertext_size": ciphertext_size,
        "shared_secret_size": shared_secret_size,
        "keygen_ms": keygen_ms,
        "encapsulation_ms": encapsulation_ms,
        "decapsulation_ms": decapsulation_ms,
        "shared_secret_match": shared_secret_match,
        "total_artifact_size": total_artifact_size,
        "status": "PASS" if shared_secret_match else "FAIL",
        "notes": "Transient in-memory comparison iteration; no keys or shared secrets persisted.",
    }
