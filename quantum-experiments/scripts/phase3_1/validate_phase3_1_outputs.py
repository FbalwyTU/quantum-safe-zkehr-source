#!/usr/bin/env python3
"""Validate Phase 3.1 QRNG simulator outputs."""

from __future__ import annotations

import csv
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "results" / "quantum" / "phase3"
DETAILED_CSV = RESULTS_DIR / "phase3_1_qrng_simulator_detailed.csv"
SUMMARY_CSV = RESULTS_DIR / "phase3_1_qrng_simulator_summary.csv"
COUNTS_JSON = RESULTS_DIR / "phase3_1_qrng_counts.json"
VALIDATION_CSV = RESULTS_DIR / "phase3_1_validation.csv"
EXPECTED_CONFIGS = {
    (num_qubits, shots)
    for num_qubits in (1, 2, 4, 8)
    for shots in (1024, 4096)
}


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


def main() -> int:
    rows: list[dict[str, str]] = []

    detailed_exists = DETAILED_CSV.exists() and DETAILED_CSV.stat().st_size > 0
    summary_exists = SUMMARY_CSV.exists() and SUMMARY_CSV.stat().st_size > 0
    counts_exists = COUNTS_JSON.exists() and COUNTS_JSON.stat().st_size > 0
    rows.append(status_row("detailed_csv_exists", detailed_exists, str(DETAILED_CSV)))
    rows.append(status_row("summary_csv_exists", summary_exists, str(SUMMARY_CSV)))
    rows.append(status_row("counts_json_exists", counts_exists, str(COUNTS_JSON)))

    detailed_rows = read_csv(DETAILED_CSV) if detailed_exists else []
    summary_rows = read_csv(SUMMARY_CSV) if summary_exists else []
    rows.append(
        status_row("detailed_csv_has_rows", len(detailed_rows) > 0, f"rows={len(detailed_rows)}")
    )
    rows.append(
        status_row("summary_csv_has_rows", len(summary_rows) > 0, f"rows={len(summary_rows)}")
    )

    try:
        counts_payload = json.loads(COUNTS_JSON.read_text(encoding="utf-8"))
        counts_valid = True
        counts_details = f"runs={len(counts_payload.get('runs', []))}"
    except Exception as error:
        counts_payload = {}
        counts_valid = False
        counts_details = str(error)
    rows.append(status_row("counts_json_valid", counts_valid, counts_details))

    summary_configs = {
        (int(row["num_qubits"]), int(row["shots"]))
        for row in summary_rows
        if row.get("num_qubits") and row.get("shots")
    }
    detailed_configs = {
        (int(row["num_qubits"]), int(row["shots"]))
        for row in detailed_rows
        if row.get("num_qubits") and row.get("shots")
    }
    json_configs = {
        (int(run["num_qubits"]), int(run["shots"]))
        for run in counts_payload.get("runs", [])
        if "num_qubits" in run and "shots" in run
    }
    all_configs_ok = (
        summary_configs == EXPECTED_CONFIGS
        and detailed_configs == EXPECTED_CONFIGS
        and json_configs == EXPECTED_CONFIGS
    )
    rows.append(
        status_row(
            "all_configurations_ran",
            all_configs_ok,
            f"summary={sorted(summary_configs)} detailed={sorted(detailed_configs)} json={sorted(json_configs)}",
        )
    )

    ratio_ok = all(
        abs(float(row["qrng_zero_ratio"]) - 0.5) <= 0.08
        and abs(float(row["qrng_one_ratio"]) - 0.5) <= 0.08
        for row in summary_rows
    )
    rows.append(
        status_row(
            "qrng_zero_one_ratios_reasonable",
            ratio_ok,
            "threshold=abs(ratio-0.5)<=0.08 for simulator sanity check",
        )
    )

    entropy_ok = all(float(row["qrng_shannon_entropy_per_bit"]) >= 0.98 for row in summary_rows)
    rows.append(
        status_row(
            "qrng_entropy_near_one",
            entropy_ok,
            "threshold=shannon_entropy_per_bit>=0.98",
        )
    )

    classical_ok = all(
        row.get("classical_zero_ratio")
        and row.get("classical_one_ratio")
        and row.get("classical_shannon_entropy_per_bit")
        for row in summary_rows
    )
    rows.append(
        status_row("classical_comparator_results_exist", classical_ok, "summary contains classical metrics")
    )

    no_hardware = counts_payload.get("hardware_used") is False
    no_auth = counts_payload.get("ibm_authentication_attempted") is False
    rows.append(status_row("no_ibm_hardware_used", no_hardware, f"hardware_used={counts_payload.get('hardware_used')}"))
    rows.append(
        status_row(
            "no_ibm_authentication_attempted",
            no_auth,
            f"ibm_authentication_attempted={counts_payload.get('ibm_authentication_attempted')}",
        )
    )

    no_baseline_outputs = all("baseline_results" not in str(path) for path in (DETAILED_CSV, SUMMARY_CSV, COUNTS_JSON))
    rows.append(
        status_row(
            "no_baseline_results_output",
            no_baseline_outputs,
            "Phase 3.1 outputs are under results/quantum/phase3/",
        )
    )

    write_validation(rows)
    failures = [row for row in rows if row["status"] != "PASS"]
    print(f"Wrote {VALIDATION_CSV}")
    if failures:
        print(f"Validation failed: {len(failures)} checks")
        return 1
    print("Phase 3.1 output validation PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
