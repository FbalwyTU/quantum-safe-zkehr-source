#!/usr/bin/env python3
"""Phase 3.1 QRNG simulator experiment.

Runs only local Qiskit Aer simulation. This script does not authenticate with
IBM Quantum, query IBM backends, or submit hardware jobs.
"""

from __future__ import annotations

import json
import sys
import time
from importlib import metadata
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "results" / "quantum" / "phase3"
QRNG_DIR = REPO_ROOT / "quantum-experiments" / "qiskit" / "qrng"

sys.path.insert(0, str(QRNG_DIR))

from qrng_utils import (
    bitstrings_to_bitstream,
    compute_bit_metrics,
    generate_classical_random_bits,
    run_qrng_simulator,
    utc_timestamp,
    write_csv,
    write_json,
)


DETAILED_CSV = RESULTS_DIR / "phase3_1_qrng_simulator_detailed.csv"
SUMMARY_CSV = RESULTS_DIR / "phase3_1_qrng_simulator_summary.csv"
COUNTS_JSON = RESULTS_DIR / "phase3_1_qrng_counts.json"

CONFIGURATIONS = [
    {"num_qubits": num_qubits, "shots": shots}
    for num_qubits in (1, 2, 4, 8)
    for shots in (1024, 4096)
]

DETAILED_FIELDS = [
    "experiment",
    "backend",
    "num_qubits",
    "shots",
    "total_bits",
    "circuit_depth",
    "num_gates",
    "qiskit_counts",
    "qrng_count_0",
    "qrng_count_1",
    "qrng_zero_ratio",
    "qrng_one_ratio",
    "qrng_shannon_entropy_per_bit",
    "qrng_monobit_balance_error",
    "qrng_longest_run_0",
    "qrng_longest_run_1",
    "qrng_transitions_count",
    "qrng_transitions_ratio",
    "classical_count_0",
    "classical_count_1",
    "classical_zero_ratio",
    "classical_one_ratio",
    "classical_shannon_entropy_per_bit",
    "classical_monobit_balance_error",
    "classical_longest_run_0",
    "classical_longest_run_1",
    "classical_transitions_count",
    "classical_transitions_ratio",
    "runtime_ms",
    "timestamp",
    "notes",
]

SUMMARY_FIELDS = [
    "experiment",
    "backend",
    "num_qubits",
    "shots",
    "total_bits",
    "qrng_zero_ratio",
    "qrng_one_ratio",
    "qrng_shannon_entropy_per_bit",
    "qrng_monobit_balance_error",
    "classical_zero_ratio",
    "classical_one_ratio",
    "classical_shannon_entropy_per_bit",
    "classical_monobit_balance_error",
    "runtime_ms",
    "status",
    "notes",
    "timestamp",
]


def rounded(value: float) -> str:
    return f"{value:.6f}"


def metric_value(metrics: dict, key: str):
    value = metrics[key]
    if isinstance(value, float):
        return rounded(value)
    return value


def prefixed_metrics(prefix: str, metrics: dict) -> dict:
    return {f"{prefix}_{key}": metric_value(metrics, key) for key in metrics}


def run_experiments() -> tuple[list[dict], list[dict], dict]:
    detailed_rows: list[dict] = []
    summary_rows: list[dict] = []
    counts_payload = {
        "phase": "3.1",
        "experiment": "qrng_simulator",
        "hardware_used": False,
        "ibm_authentication_attempted": False,
        "backend_type": "local_aer_simulator",
        "qiskit_version": metadata.version("qiskit"),
        "qiskit_aer_version": metadata.version("qiskit-aer"),
        "created_at": utc_timestamp(),
        "runs": [],
    }

    for index, config in enumerate(CONFIGURATIONS, start=1):
        num_qubits = config["num_qubits"]
        shots = config["shots"]
        seed_simulator = 3100 + index
        start = time.perf_counter()
        simulator_result = run_qrng_simulator(
            num_qubits=num_qubits,
            shots=shots,
            seed_simulator=seed_simulator,
        )
        runtime_ms = (time.perf_counter() - start) * 1000

        qrng_bitstream = bitstrings_to_bitstream(simulator_result["memory"])
        qrng_metrics = compute_bit_metrics(qrng_bitstream)
        classical_bitstream = generate_classical_random_bits(qrng_metrics["total_bits"])
        classical_metrics = compute_bit_metrics(classical_bitstream)
        timestamp = utc_timestamp()
        notes = "Local Aer simulator only; no IBM token, authentication, backend query, or hardware job."

        qiskit_counts_json = json.dumps(simulator_result["counts"], sort_keys=True)
        detailed_row = {
            "experiment": "phase3_1_qrng_simulator",
            "backend": simulator_result["backend"],
            "num_qubits": num_qubits,
            "shots": shots,
            "total_bits": qrng_metrics["total_bits"],
            "circuit_depth": simulator_result["circuit_depth"],
            "num_gates": simulator_result["num_gates"],
            "qiskit_counts": qiskit_counts_json,
            "runtime_ms": rounded(runtime_ms),
            "timestamp": timestamp,
            "notes": notes,
        }
        detailed_row.update(prefixed_metrics("qrng", qrng_metrics))
        detailed_row.update(prefixed_metrics("classical", classical_metrics))
        detailed_rows.append(detailed_row)

        summary_rows.append(
            {
                "experiment": "phase3_1_qrng_simulator",
                "backend": simulator_result["backend"],
                "num_qubits": num_qubits,
                "shots": shots,
                "total_bits": qrng_metrics["total_bits"],
                "qrng_zero_ratio": rounded(qrng_metrics["zero_ratio"]),
                "qrng_one_ratio": rounded(qrng_metrics["one_ratio"]),
                "qrng_shannon_entropy_per_bit": rounded(
                    qrng_metrics["shannon_entropy_per_bit"]
                ),
                "qrng_monobit_balance_error": rounded(
                    qrng_metrics["monobit_balance_error"]
                ),
                "classical_zero_ratio": rounded(classical_metrics["zero_ratio"]),
                "classical_one_ratio": rounded(classical_metrics["one_ratio"]),
                "classical_shannon_entropy_per_bit": rounded(
                    classical_metrics["shannon_entropy_per_bit"]
                ),
                "classical_monobit_balance_error": rounded(
                    classical_metrics["monobit_balance_error"]
                ),
                "runtime_ms": rounded(runtime_ms),
                "status": "PASS",
                "notes": notes,
                "timestamp": timestamp,
            }
        )

        counts_payload["runs"].append(
            {
                "backend": simulator_result["backend"],
                "num_qubits": num_qubits,
                "shots": shots,
                "seed_simulator": seed_simulator,
                "counts": simulator_result["counts"],
                "circuit_depth": simulator_result["circuit_depth"],
                "num_gates": simulator_result["num_gates"],
                "circuit_ops": simulator_result["circuit_ops"],
                "qrng_total_bits": qrng_metrics["total_bits"],
                "qrng_sample_bitstrings": simulator_result["memory"][:16],
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
