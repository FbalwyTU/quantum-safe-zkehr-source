#!/usr/bin/env python3
"""Phase 3.0 local Qiskit simulator smoke test.

This script runs only a local simulator. It does not authenticate with IBM
Quantum and does not submit jobs to IBM hardware.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "results" / "quantum" / "phase3"
OUTPUT_CSV = RESULTS_DIR / "phase3_0_qiskit_smoke_test.csv"
UTILS_DIR = REPO_ROOT / "quantum-experiments" / "qiskit" / "utils"

sys.path.insert(0, str(UTILS_DIR))

from qiskit_environment import run_local_simulator_smoke_test, utc_timestamp, write_csv


FIELDNAMES = [
    "test_name",
    "status",
    "backend",
    "shots",
    "count_0",
    "count_1",
    "zero_ratio",
    "one_ratio",
    "num_qubits",
    "num_clbits",
    "circuit_depth",
    "notes",
    "timestamp",
]


def main() -> int:
    try:
        result = run_local_simulator_smoke_test(shots=1024)
        row = {
            "test_name": result["test_name"],
            "status": result["status"],
            "backend": result["backend"],
            "shots": result["shots"],
            "count_0": result["count_0"],
            "count_1": result["count_1"],
            "zero_ratio": f"{result['zero_ratio']:.6f}",
            "one_ratio": f"{result['one_ratio']:.6f}",
            "num_qubits": result["num_qubits"],
            "num_clbits": result["num_clbits"],
            "circuit_depth": result["circuit_depth"],
            "notes": result["notes"],
            "timestamp": result["timestamp"],
        }
        write_csv(OUTPUT_CSV, [row], FIELDNAMES)
        print(f"Qiskit smoke test PASS: {OUTPUT_CSV}")
        return 0
    except Exception as error:
        row = {
            "test_name": "one_qubit_h_measurement",
            "status": "FAIL",
            "backend": "",
            "shots": "",
            "count_0": "",
            "count_1": "",
            "zero_ratio": "",
            "one_ratio": "",
            "num_qubits": "",
            "num_clbits": "",
            "circuit_depth": "",
            "notes": str(error),
            "timestamp": utc_timestamp(),
        }
        write_csv(OUTPUT_CSV, [row], FIELDNAMES)
        print(f"Qiskit smoke test FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
