#!/usr/bin/env python3
"""Validate Phase 3.2 toy access-policy simulator outputs."""

from __future__ import annotations

import csv
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "results" / "quantum" / "phase3"
DETAILED_CSV = RESULTS_DIR / "phase3_2_toy_access_policy_detailed.csv"
SUMMARY_CSV = RESULTS_DIR / "phase3_2_toy_access_policy_summary.csv"
COUNTS_JSON = RESULTS_DIR / "phase3_2_toy_access_policy_counts.json"
VALIDATION_CSV = RESULTS_DIR / "phase3_2_validation.csv"
EXPECTED_CONFIGS = {
    (role_valid, department_valid, authorized)
    for role_valid in (0, 1)
    for department_valid in (0, 1)
    for authorized in (0, 1)
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


def bool_from_csv(value: str) -> bool:
    return str(value).strip().lower() == "true"


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
    rows.append(status_row("detailed_csv_has_8_rows", len(detailed_rows) == 8, f"rows={len(detailed_rows)}"))
    rows.append(status_row("summary_csv_has_8_rows", len(summary_rows) == 8, f"rows={len(summary_rows)}"))

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
        (int(row["role_valid"]), int(row["department_valid"]), int(row["authorized"]))
        for row in summary_rows
        if row.get("role_valid") != "" and row.get("department_valid") != "" and row.get("authorized") != ""
    }
    json_configs = {
        (int(run["role_valid"]), int(run["department_valid"]), int(run["authorized"]))
        for run in counts_payload.get("runs", [])
        if all(key in run for key in ("role_valid", "department_valid", "authorized"))
    }
    rows.append(
        status_row(
            "all_8_input_combinations_ran",
            summary_configs == EXPECTED_CONFIGS and json_configs == EXPECTED_CONFIGS,
            f"summary={sorted(summary_configs)} json={sorted(json_configs)}",
        )
    )

    only_111_grants = all(
        bool_from_csv(row["expected_granted"])
        == (
            int(row["role_valid"]) == 1
            and int(row["department_valid"]) == 1
            and int(row["authorized"]) == 1
        )
        for row in summary_rows
    )
    rows.append(status_row("only_111_expected_grants", only_111_grants, "expected_granted is true only for 1,1,1"))

    grant_case_ok = any(
        int(row["role_valid"]) == 1
        and int(row["department_valid"]) == 1
        and int(row["authorized"]) == 1
        and row["dominant_output"] == "1"
        and float(row["success_probability"]) >= 0.999
        for row in summary_rows
    )
    rows.append(status_row("input_111_results_in_access_granted", grant_case_ok, "dominant_output=1 for 1,1,1"))

    denied_cases_ok = all(
        row["dominant_output"] == "0"
        and float(row["success_probability"]) >= 0.999
        for row in summary_rows
        if not (
            int(row["role_valid"]) == 1
            and int(row["department_valid"]) == 1
            and int(row["authorized"]) == 1
        )
    )
    rows.append(status_row("all_other_inputs_access_denied", denied_cases_ok, "dominant_output=0 for all non-111 inputs"))

    deterministic_ok = all(float(row["success_probability"]) >= 0.999 for row in summary_rows)
    rows.append(status_row("success_probability_deterministic", deterministic_ok, "threshold=success_probability>=0.999"))

    metadata_ok = all(
        row.get("num_qubits")
        and row.get("num_gates")
        and row.get("circuit_depth")
        and row.get("transpiled_depth")
        for row in summary_rows
    ) and all("metadata" in run for run in counts_payload.get("runs", []))
    rows.append(status_row("circuit_metadata_present", metadata_ok, "CSV and JSON include qubits, gate count, depth, transpiled depth"))

    no_hardware = counts_payload.get("hardware_used") is False
    no_auth = counts_payload.get("ibm_authentication_attempted") is False
    rows.append(status_row("no_ibm_hardware_used", no_hardware, f"hardware_used={counts_payload.get('hardware_used')}"))
    rows.append(
        status_row(
            "no_ibm_token_required",
            no_auth,
            f"ibm_authentication_attempted={counts_payload.get('ibm_authentication_attempted')}",
        )
    )

    no_baseline_outputs = all(
        "baseline_results" not in str(path)
        for path in (DETAILED_CSV, SUMMARY_CSV, COUNTS_JSON)
    )
    rows.append(status_row("no_baseline_results_output", no_baseline_outputs, "Phase 3.2 outputs are under results/quantum/phase3/"))

    write_validation(rows)
    failures = [row for row in rows if row["status"] != "PASS"]
    print(f"Wrote {VALIDATION_CSV}")
    if failures:
        print(f"Validation failed: {len(failures)} checks")
        return 1
    print("Phase 3.2 output validation PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
