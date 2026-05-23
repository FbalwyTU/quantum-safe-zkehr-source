#!/usr/bin/env python3
"""Phase 3.3 circuit transpilation readiness check.

This script rebuilds circuit objects only. It does not rerun Phase 3.1/3.2
experiments and does not submit any IBM job.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "results" / "quantum" / "phase3"
IBM_DIR = REPO_ROOT / "quantum-experiments" / "qiskit" / "ibm"

sys.path.insert(0, str(IBM_DIR))

from ibm_readiness_utils import (
    build_or_load_qrng_circuit,
    build_or_load_toy_access_policy_circuit,
    extract_transpilation_metadata,
    initialize_ibm_service_if_token_present,
    list_available_backends_if_authenticated,
    select_backend_for_circuit,
    transpile_for_backend_or_simulator,
    utc_timestamp,
    write_csv,
)


CIRCUIT_CSV = RESULTS_DIR / "phase3_3_circuit_readiness.csv"


def hardware_suitability(num_qubits: int, transpiled_depth: int, backend_name: str) -> tuple[str, str]:
    if backend_name == "aer_simulator":
        return (
            "READY_FOR_SIMULATOR_ONLY",
            "No IBM backend selected because service was not initialized; local simulator fallback used.",
        )
    if num_qubits <= 8 and transpiled_depth <= 200:
        return (
            "READY_FOR_HARDWARE",
            "Circuit is small enough for a suitable IBM backend, subject to queue and calibration conditions.",
        )
    return (
        "NEEDS_REDUCTION",
        "Circuit may be too large or deep for a conservative first hardware run.",
    )


def main() -> int:
    service_status = initialize_ibm_service_if_token_present()
    backend_metadata = []
    qrng_backend = None
    toy_backend = None
    if service_status["service_initialized"]:
        backend_metadata = list_available_backends_if_authenticated(service_status["service"])
        qrng_backend = select_backend_for_circuit(backend_metadata, min_qubits=8)
        toy_backend = select_backend_for_circuit(backend_metadata, min_qubits=5)

    circuit_specs = [
        {
            "circuit_name": "phase3_1_qrng_max_8_qubits",
            "circuit": build_or_load_qrng_circuit(num_qubits=8),
            "backend": qrng_backend["backend"] if qrng_backend else None,
            "recommended_shots": 1024,
        },
        {
            "circuit_name": "phase3_2_toy_access_policy_111",
            "circuit": build_or_load_toy_access_policy_circuit(),
            "backend": toy_backend["backend"] if toy_backend else None,
            "recommended_shots": 1024,
        },
    ]

    rows = []
    for spec in circuit_specs:
        try:
            backend, transpiled = transpile_for_backend_or_simulator(
                spec["circuit"],
                backend=spec["backend"],
            )
            metadata = extract_transpilation_metadata(spec["circuit"], transpiled, backend)
            suitability, notes = hardware_suitability(
                metadata["num_qubits"],
                metadata["transpiled_depth"],
                metadata["backend_name"],
            )
            rows.append(
                {
                    "circuit_name": spec["circuit_name"],
                    "backend_for_transpilation": metadata["backend_name"],
                    "num_qubits": metadata["num_qubits"],
                    "num_clbits": metadata["num_clbits"],
                    "original_depth": metadata["original_depth"],
                    "transpiled_depth": metadata["transpiled_depth"],
                    "original_gate_counts": json.dumps(
                        metadata["original_gate_counts"],
                        sort_keys=True,
                    ),
                    "transpiled_gate_counts": json.dumps(
                        metadata["transpiled_gate_counts"],
                        sort_keys=True,
                    ),
                    "recommended_shots": spec["recommended_shots"],
                    "hardware_suitability": suitability,
                    "status": suitability,
                    "notes": notes,
                    "timestamp": utc_timestamp(),
                }
            )
        except Exception as error:
            rows.append(
                {
                    "circuit_name": spec["circuit_name"],
                    "backend_for_transpilation": "",
                    "num_qubits": getattr(spec["circuit"], "num_qubits", ""),
                    "num_clbits": getattr(spec["circuit"], "num_clbits", ""),
                    "original_depth": spec["circuit"].depth() if hasattr(spec["circuit"], "depth") else "",
                    "transpiled_depth": "",
                    "original_gate_counts": "",
                    "transpiled_gate_counts": "",
                    "recommended_shots": spec["recommended_shots"],
                    "hardware_suitability": "CHECK_FAILED",
                    "status": "CHECK_FAILED",
                    "notes": str(error),
                    "timestamp": utc_timestamp(),
                }
            )

    write_csv(
        CIRCUIT_CSV,
        rows,
        [
            "circuit_name",
            "backend_for_transpilation",
            "num_qubits",
            "num_clbits",
            "original_depth",
            "transpiled_depth",
            "original_gate_counts",
            "transpiled_gate_counts",
            "recommended_shots",
            "hardware_suitability",
            "status",
            "notes",
            "timestamp",
        ],
    )
    print(f"Wrote {CIRCUIT_CSV}")
    if any(row["status"] == "CHECK_FAILED" for row in rows):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
