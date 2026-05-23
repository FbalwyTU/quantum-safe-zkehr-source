#!/usr/bin/env python3
"""Validate Phase 3.3 IBM readiness outputs without exposing tokens."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "results" / "quantum" / "phase3"
IBM_DIR = REPO_ROOT / "quantum-experiments" / "qiskit" / "ibm"
TOOLS_DIR = REPO_ROOT / "quantum-experiments" / "scripts" / "phase3_3"

TOKEN_CSV = RESULTS_DIR / "phase3_3_token_check.csv"
SERVICE_CSV = RESULTS_DIR / "phase3_3_ibm_service_check.csv"
CIRCUIT_CSV = RESULTS_DIR / "phase3_3_circuit_readiness.csv"
BACKENDS_JSON = RESULTS_DIR / "phase3_3_visible_backends.json"
VALIDATION_CSV = RESULTS_DIR / "phase3_3_validation.csv"
TEMPLATE_FILES = [
    IBM_DIR / "run_ibm_qrng_hardware_TEMPLATE.py",
    IBM_DIR / "run_ibm_toy_policy_hardware_TEMPLATE.py",
]


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def status_row(check: str, ok: bool, details: str) -> dict[str, str]:
    return {"check": check, "status": "PASS" if ok else "FAIL", "details": details}


def write_validation(rows: list[dict[str, str]]) -> None:
    with VALIDATION_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "status", "details"])
        writer.writeheader()
        writer.writerows(rows)


def token_values_written_to_phase3_files() -> bool:
    token_values = [
        value
        for value in (
            os.environ.get("IBM_QUANTUM_TOKEN"),
            os.environ.get("QISKIT_IBM_TOKEN"),
            os.environ.get("QISKIT_IBM_INSTANCE"),
        )
        if value
    ]
    if not token_values:
        return False

    files_to_scan = list(RESULTS_DIR.glob("phase3_3_*")) + list(IBM_DIR.glob("*.py")) + list(TOOLS_DIR.glob("*.py"))
    for file_path in files_to_scan:
        if not file_path.is_file():
            continue
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        if any(token_value in text for token_value in token_values):
            return True
    return False


def main() -> int:
    rows: list[dict[str, str]] = []

    token_exists = TOKEN_CSV.exists() and TOKEN_CSV.stat().st_size > 0
    service_exists = SERVICE_CSV.exists() and SERVICE_CSV.stat().st_size > 0
    circuit_exists = CIRCUIT_CSV.exists() and CIRCUIT_CSV.stat().st_size > 0
    rows.append(status_row("token_check_csv_exists", token_exists, str(TOKEN_CSV)))
    rows.append(status_row("ibm_service_check_csv_exists", service_exists, str(SERVICE_CSV)))
    rows.append(status_row("circuit_readiness_csv_exists", circuit_exists, str(CIRCUIT_CSV)))

    try:
        backends_payload = json.loads(BACKENDS_JSON.read_text(encoding="utf-8"))
        jobs_submitted = bool(backends_payload.get("jobs_submitted"))
        backends_valid = True
    except Exception as error:
        backends_payload = {}
        jobs_submitted = True
        backends_valid = False
        rows.append(status_row("visible_backends_json_valid", False, str(error)))
    else:
        rows.append(status_row("visible_backends_json_valid", backends_valid, str(BACKENDS_JSON)))
    rows.append(status_row("no_ibm_job_submitted", not jobs_submitted, f"jobs_submitted={jobs_submitted}"))

    token_rows = read_csv(TOKEN_CSV) if token_exists else []
    value_printed_ok = all(str(row.get("value_printed", "")).lower() == "false" for row in token_rows)
    rows.append(status_row("no_token_value_printed", value_printed_ok, "token_check.csv value_printed is false for all env vars"))

    token_written = token_values_written_to_phase3_files()
    rows.append(status_row("no_token_value_written_to_file", not token_written, "Phase 3.3 files scanned for token env values without printing them"))

    circuit_rows = read_csv(CIRCUIT_CSV) if circuit_exists else []
    circuit_names = {row.get("circuit_name", "") for row in circuit_rows}
    rows.append(status_row("qrng_circuit_readiness_recorded", "phase3_1_qrng_max_8_qubits" in circuit_names, str(sorted(circuit_names))))
    rows.append(status_row("toy_access_policy_readiness_recorded", "phase3_2_toy_access_policy_111" in circuit_names, str(sorted(circuit_names))))

    templates_ok = all(path.exists() and path.stat().st_size > 0 for path in TEMPLATE_FILES)
    rows.append(status_row("hardware_templates_created", templates_ok, ", ".join(str(path) for path in TEMPLATE_FILES)))

    service_rows = read_csv(SERVICE_CSV) if service_exists else []
    final_statuses = {row.get("status", "") for row in service_rows}
    final_ready = bool(final_statuses & {"READY_FOR_IBM_TOKEN", "IBM_SERVICE_READY", "IBM_SERVICE_INIT_FAILED", "IBM_RUNTIME_IMPORT_FAILED"})
    rows.append(status_row("final_readiness_status_determined", final_ready, str(sorted(final_statuses))))

    write_validation(rows)
    failures = [row for row in rows if row["status"] != "PASS"]
    print(f"Wrote {VALIDATION_CSV}")
    if failures:
        print(f"Validation failed: {len(failures)} checks")
        return 1
    print("Phase 3.3 output validation PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
