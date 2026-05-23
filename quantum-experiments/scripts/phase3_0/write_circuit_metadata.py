#!/usr/bin/env python3
"""Write explicit Phase 3.0 circuit metadata from the local simulator smoke path."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
UTILS_DIR = REPO_ROOT / "quantum-experiments" / "qiskit" / "utils"
OUTPUT_JSON = REPO_ROOT / "results" / "quantum" / "phase3" / "phase3_0_circuit_metadata.json"

sys.path.insert(0, str(UTILS_DIR))

from qiskit_environment import run_local_simulator_smoke_test, write_json


def main() -> int:
    result = run_local_simulator_smoke_test(shots=1024)
    payload = {
        "test_name": result["test_name"],
        "backend": result["backend"],
        "shots": result["shots"],
        "num_qubits": result["num_qubits"],
        "num_clbits": result["num_clbits"],
        "circuit_depth": result["circuit_depth"],
        "num_gates": result["num_gates"],
        "measurement_counts": result["measurement_counts"],
        "timestamp": result["timestamp"],
        "notes": "Explicit metadata artifact for Phase 3.0. Local simulator only.",
    }
    write_json(OUTPUT_JSON, payload)
    print(f"Wrote {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
