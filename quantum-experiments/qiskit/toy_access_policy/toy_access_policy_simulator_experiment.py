#!/usr/bin/env python3
"""Phase 3.2 toy access-policy simulator experiment.

Runs all eight role/department/authorization combinations on local Qiskit Aer.
This is not Groth16, not zero-knowledge, and not IBM hardware execution.
"""

from __future__ import annotations

import json
import sys
import time
from importlib import metadata
from itertools import product
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "results" / "quantum" / "phase3"
POLICY_DIR = REPO_ROOT / "quantum-experiments" / "qiskit" / "toy_access_policy"

sys.path.insert(0, str(POLICY_DIR))

from toy_policy_utils import (
    build_toy_access_policy_circuit,
    evaluate_policy_result,
    run_policy_simulator,
    utc_timestamp,
    write_csv,
    write_json,
)


DETAILED_CSV = RESULTS_DIR / "phase3_2_toy_access_policy_detailed.csv"
SUMMARY_CSV = RESULTS_DIR / "phase3_2_toy_access_policy_summary.csv"
COUNTS_JSON = RESULTS_DIR / "phase3_2_toy_access_policy_counts.json"
SHOTS = 1024

DETAILED_FIELDS = [
    "experiment",
    "backend",
    "role_valid",
    "department_valid",
    "authorized",
    "expected_granted",
    "expected_output",
    "dominant_output",
    "dominant_output_matches_expected",
    "success_count",
    "failure_count",
    "success_probability",
    "counts",
    "num_qubits",
    "num_clbits",
    "circuit_depth",
    "transpiled_depth",
    "gate_counts",
    "num_gates",
    "shots",
    "runtime_ms",
    "timestamp",
    "notes",
]

SUMMARY_FIELDS = [
    "role_valid",
    "department_valid",
    "authorized",
    "expected_granted",
    "dominant_output",
    "success_probability",
    "status",
    "shots",
    "backend",
    "circuit_depth",
    "transpiled_depth",
    "num_qubits",
    "num_gates",
    "runtime_ms",
    "timestamp",
]


def rounded(value: float) -> str:
    return f"{value:.6f}"


def run_experiments() -> tuple[list[dict], list[dict], dict]:
    detailed_rows: list[dict] = []
    summary_rows: list[dict] = []
    counts_payload = {
        "phase": "3.2",
        "experiment": "toy_access_policy_simulator",
        "policy": "access_granted = role_valid AND department_valid AND authorized",
        "hardware_used": False,
        "ibm_authentication_attempted": False,
        "backend_type": "local_aer_simulator",
        "qiskit_version": metadata.version("qiskit"),
        "qiskit_aer_version": metadata.version("qiskit-aer"),
        "shots": SHOTS,
        "created_at": utc_timestamp(),
        "runs": [],
    }

    for index, (role_valid, department_valid, authorized) in enumerate(
        product((0, 1), repeat=3),
        start=1,
    ):
        expected_granted = bool(role_valid and department_valid and authorized)
        circuit = build_toy_access_policy_circuit(
            role_valid=role_valid,
            department_valid=department_valid,
            authorized=authorized,
        )
        start = time.perf_counter()
        simulator_result = run_policy_simulator(
            circuit,
            shots=SHOTS,
            seed_simulator=3200 + index,
        )
        runtime_ms = (time.perf_counter() - start) * 1000
        evaluation = evaluate_policy_result(
            simulator_result["counts"],
            expected_granted=expected_granted,
        )
        metadata_row = simulator_result["metadata"]
        timestamp = utc_timestamp()
        status = (
            "PASS"
            if evaluation["dominant_output_matches_expected"]
            and evaluation["failure_count"] == 0
            else "FAIL"
        )
        notes = (
            "Local Aer simulator only; toy AND policy feasibility circuit; "
            "not Groth16, not zero-knowledge, not production access control."
        )

        detailed_rows.append(
            {
                "experiment": "phase3_2_toy_access_policy",
                "backend": simulator_result["backend"],
                "role_valid": role_valid,
                "department_valid": department_valid,
                "authorized": authorized,
                "expected_granted": expected_granted,
                "expected_output": evaluation["expected_output"],
                "dominant_output": evaluation["dominant_output"],
                "dominant_output_matches_expected": evaluation[
                    "dominant_output_matches_expected"
                ],
                "success_count": evaluation["success_count"],
                "failure_count": evaluation["failure_count"],
                "success_probability": rounded(evaluation["success_probability"]),
                "counts": json.dumps(simulator_result["counts"], sort_keys=True),
                "num_qubits": metadata_row["num_qubits"],
                "num_clbits": metadata_row["num_clbits"],
                "circuit_depth": metadata_row["circuit_depth"],
                "transpiled_depth": metadata_row["transpiled_depth"],
                "gate_counts": json.dumps(metadata_row["gate_counts"], sort_keys=True),
                "num_gates": metadata_row["num_gates"],
                "shots": SHOTS,
                "runtime_ms": rounded(runtime_ms),
                "timestamp": timestamp,
                "notes": notes,
            }
        )

        summary_rows.append(
            {
                "role_valid": role_valid,
                "department_valid": department_valid,
                "authorized": authorized,
                "expected_granted": expected_granted,
                "dominant_output": evaluation["dominant_output"],
                "success_probability": rounded(evaluation["success_probability"]),
                "status": status,
                "shots": SHOTS,
                "backend": simulator_result["backend"],
                "circuit_depth": metadata_row["circuit_depth"],
                "transpiled_depth": metadata_row["transpiled_depth"],
                "num_qubits": metadata_row["num_qubits"],
                "num_gates": metadata_row["num_gates"],
                "runtime_ms": rounded(runtime_ms),
                "timestamp": timestamp,
            }
        )

        counts_payload["runs"].append(
            {
                "role_valid": role_valid,
                "department_valid": department_valid,
                "authorized": authorized,
                "expected_granted": expected_granted,
                "expected_output": evaluation["expected_output"],
                "dominant_output": evaluation["dominant_output"],
                "success_probability": evaluation["success_probability"],
                "counts": simulator_result["counts"],
                "metadata": metadata_row,
                "backend": simulator_result["backend"],
                "shots": SHOTS,
                "seed_simulator": 3200 + index,
                "runtime_ms": runtime_ms,
                "timestamp": timestamp,
            }
        )

    return detailed_rows, summary_rows, counts_payload


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    detailed_rows, summary_rows, counts_payload = run_experiments()
    write_csv(DETAILED_CSV, detailed_rows, DETAILED_FIELDS)
    write_csv(SUMMARY_CSV, summary_rows, SUMMARY_FIELDS)
    write_json(COUNTS_JSON, counts_payload)
    print(f"Wrote {DETAILED_CSV}")
    print(f"Wrote {SUMMARY_CSV}")
    print(f"Wrote {COUNTS_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
