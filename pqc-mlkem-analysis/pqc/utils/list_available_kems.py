#!/usr/bin/env python3
"""List liboqs KEM algorithms available to the Phase 4.0 PQC environment."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if (parent / "pqc-mlkem-analysis").exists() and (parent / "results").exists():
            return parent
    return Path.cwd()


def classify_algorithm(name: str) -> str:
    upper = name.upper().replace("_", "-")
    if "ML-KEM" in upper:
        return "ML-KEM"
    if "KYBER" in upper:
        return "Kyber-family"
    return "Other KEM"


def main() -> int:
    repo_root = find_repo_root()
    results_dir = repo_root / "results" / "pqc" / "phase4"
    results_dir.mkdir(parents=True, exist_ok=True)
    output_csv = results_dir / "phase4_0_available_kems.csv"
    output_json = results_dir / "phase4_0_available_kems.json"

    rows: list[dict[str, str]] = []
    status = "PASS"
    notes = ""

    try:
        import oqs

        algorithms = sorted(oqs.get_enabled_kem_mechanisms())
        for algorithm_name in algorithms:
            category = classify_algorithm(algorithm_name)
            rows.append(
                {
                    "algorithm_name": algorithm_name,
                    "category": category,
                    "available": "true",
                    "status": "AVAILABLE",
                    "notes": "Enabled by the local liboqs build.",
                }
            )
    except Exception as exc:
        algorithms = []
        status = "FAIL"
        notes = f"{type(exc).__name__}: {exc}"
        rows.append(
            {
                "algorithm_name": "NOT_AVAILABLE",
                "category": "UNKNOWN",
                "available": "false",
                "status": "ENUMERATION_FAILED",
                "notes": notes,
            }
        )

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["algorithm_name", "category", "available", "status", "notes"],
        )
        writer.writeheader()
        writer.writerows(rows)

    ml_kem = [name for name in algorithms if classify_algorithm(name) == "ML-KEM"]
    kyber = [name for name in algorithms if classify_algorithm(name) == "Kyber-family"]
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_kems": len(algorithms),
        "ml_kem_available": bool(ml_kem),
        "ml_kem_algorithms": ml_kem,
        "kyber_available": bool(kyber),
        "kyber_algorithms": kyber,
        "algorithms": algorithms,
        "notes": notes or "KEM enumeration completed successfully.",
    }
    output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"available_kems_csv={output_csv}")
    print(f"available_kems_json={output_json}")
    print(f"status={status}")
    print(f"total_kems={len(algorithms)}")
    print(f"ml_kem_available={bool(ml_kem)}")
    print(f"kyber_available={bool(kyber)}")
    return 0 if status == "PASS" and algorithms else 1


if __name__ == "__main__":
    raise SystemExit(main())
