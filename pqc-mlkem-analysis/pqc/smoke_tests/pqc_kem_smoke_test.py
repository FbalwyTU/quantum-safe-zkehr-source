#!/usr/bin/env python3
"""Run a minimal local KEM key generation, encapsulation, and decapsulation test."""

from __future__ import annotations

import csv
import time
from datetime import datetime, timezone
from pathlib import Path


PREFERRED_KEMS = [
    "ML-KEM-768",
    "ML-KEM-512",
    "ML-KEM-1024",
    "Kyber768",
    "Kyber512",
    "Kyber1024",
]


def find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if (parent / "pqc-mlkem-analysis").exists() and (parent / "results").exists():
            return parent
    return Path.cwd()


def choose_preferred_kem(algorithms: list[str]) -> str | None:
    for candidate in PREFERRED_KEMS:
        if candidate in algorithms:
            return candidate
    for algorithm in algorithms:
        if "ML-KEM" in algorithm.upper().replace("_", "-"):
            return algorithm
    for algorithm in algorithms:
        if "KYBER" in algorithm.upper():
            return algorithm
    return algorithms[0] if algorithms else None


def get_secret_key_bytes(kem: object) -> bytes:
    export_secret_key = getattr(kem, "export_secret_key", None)
    if callable(export_secret_key):
        secret_key = export_secret_key()
        if isinstance(secret_key, bytes):
            return secret_key
    return b""


def main() -> int:
    repo_root = find_repo_root()
    results_dir = repo_root / "results" / "pqc" / "phase4"
    results_dir.mkdir(parents=True, exist_ok=True)
    output_csv = results_dir / "phase4_0_kem_smoke_test.csv"

    row = {
        "algorithm_name": "NOT_SELECTED",
        "public_key_size": "",
        "secret_key_size": "",
        "ciphertext_size": "",
        "shared_secret_size": "",
        "keygen_ms": "",
        "encapsulation_ms": "",
        "decapsulation_ms": "",
        "shared_secret_match": "false",
        "status": "FAIL",
        "notes": "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        import oqs

        algorithms = sorted(oqs.get_enabled_kem_mechanisms())
        algorithm_name = choose_preferred_kem(algorithms)
        if not algorithm_name:
            raise RuntimeError("No enabled KEM algorithms were reported by oqs.")

        with oqs.KeyEncapsulation(algorithm_name) as kem:
            start = time.perf_counter()
            public_key = kem.generate_keypair()
            keygen_ms = (time.perf_counter() - start) * 1000

            secret_key = get_secret_key_bytes(kem)

            start = time.perf_counter()
            ciphertext, shared_secret_encapsulated = kem.encap_secret(public_key)
            encapsulation_ms = (time.perf_counter() - start) * 1000

            start = time.perf_counter()
            shared_secret_decapsulated = kem.decap_secret(ciphertext)
            decapsulation_ms = (time.perf_counter() - start) * 1000

            shared_secret_match = shared_secret_encapsulated == shared_secret_decapsulated
            details = getattr(kem, "details", {}) or {}
            secret_key_size = len(secret_key) if secret_key else details.get("length_secret_key", "")

            row.update(
                {
                    "algorithm_name": algorithm_name,
                    "public_key_size": len(public_key),
                    "secret_key_size": secret_key_size,
                    "ciphertext_size": len(ciphertext),
                    "shared_secret_size": len(shared_secret_encapsulated),
                    "keygen_ms": f"{keygen_ms:.6f}",
                    "encapsulation_ms": f"{encapsulation_ms:.6f}",
                    "decapsulation_ms": f"{decapsulation_ms:.6f}",
                    "shared_secret_match": str(shared_secret_match).lower(),
                    "status": "PASS" if shared_secret_match else "FAIL",
                    "notes": "Local smoke test only; no ZK-EHR workflow integration performed.",
                }
            )
    except Exception as exc:
        row["notes"] = f"{type(exc).__name__}: {exc}"

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "algorithm_name",
                "public_key_size",
                "secret_key_size",
                "ciphertext_size",
                "shared_secret_size",
                "keygen_ms",
                "encapsulation_ms",
                "decapsulation_ms",
                "shared_secret_match",
                "status",
                "notes",
                "timestamp",
            ],
        )
        writer.writeheader()
        writer.writerow(row)

    print(f"kem_smoke_test_csv={output_csv}")
    print(f"algorithm_name={row['algorithm_name']}")
    print(f"shared_secret_match={row['shared_secret_match']}")
    print(f"status={row['status']}")
    return 0 if row["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
