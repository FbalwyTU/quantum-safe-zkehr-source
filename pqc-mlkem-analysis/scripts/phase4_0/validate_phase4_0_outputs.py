#!/usr/bin/env python3
"""Validate Phase 4.0 PQC setup outputs."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if (parent / "pqc-mlkem-analysis").exists() and (parent / "results").exists():
            return parent
    return Path.cwd()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    repo_root = find_repo_root()
    results_dir = repo_root / "results" / "pqc" / "phase4"
    output_csv = results_dir / "phase4_0_validation.csv"

    package_csv = results_dir / "phase4_0_package_check.csv"
    kems_csv = results_dir / "phase4_0_available_kems.csv"
    kems_json = results_dir / "phase4_0_available_kems.json"
    smoke_csv = results_dir / "phase4_0_kem_smoke_test.csv"

    package_rows = read_csv_rows(package_csv)
    kem_rows = read_csv_rows(kems_csv)
    smoke_rows = read_csv_rows(smoke_csv)
    smoke = smoke_rows[0] if smoke_rows else {}

    def add(check: str, ok: bool, details: str) -> None:
        rows.append({"check": check, "status": "PASS" if ok else "FAIL", "details": details})

    rows: list[dict[str, str]] = []
    oqs_ok = any(
        row.get("package") in {"liboqs-python", "oqs"}
        and row.get("import_success") == "true"
        and row.get("status") == "PASS"
        for row in package_rows
    )
    add("oqs import succeeded", oqs_ok, f"package_check={package_csv}")

    available_count = sum(1 for row in kem_rows if row.get("available") == "true")
    add("available KEMs enumerated", available_count > 0, f"available_count={available_count}; csv={kems_csv}")

    ml_kem_available = False
    if kems_json.exists():
        payload = json.loads(kems_json.read_text(encoding="utf-8"))
        ml_kem_available = bool(payload.get("ml_kem_available"))
    add("ML-KEM availability checked", ml_kem_available, f"json={kems_json}")

    preferred_selected = bool(smoke.get("algorithm_name")) and smoke.get("algorithm_name") != "NOT_SELECTED"
    add("preferred KEM selected", preferred_selected, f"algorithm={smoke.get('algorithm_name', 'NONE')}")

    add("keypair generation succeeded", smoke.get("status") == "PASS", f"keygen_ms={smoke.get('keygen_ms', '')}")
    add(
        "encapsulation succeeded",
        smoke.get("status") == "PASS",
        f"encapsulation_ms={smoke.get('encapsulation_ms', '')}",
    )
    add(
        "decapsulation succeeded",
        smoke.get("status") == "PASS",
        f"decapsulation_ms={smoke.get('decapsulation_ms', '')}",
    )
    add(
        "shared secret matched",
        smoke.get("shared_secret_match") == "true",
        f"shared_secret_size={smoke.get('shared_secret_size', '')}",
    )

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "status", "details"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"validation_csv={output_csv}")
    for row in rows:
        print(f"{row['check']}: {row['status']} ({row['details']})")
    return 0 if all(row["status"] == "PASS" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
