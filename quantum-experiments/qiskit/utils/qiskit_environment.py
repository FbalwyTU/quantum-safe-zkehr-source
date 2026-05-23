"""Safe Qiskit environment helpers for the Quantum-Aware ZK-EHR track.

Phase 3.0 intentionally supports only local simulator checks. It does not
authenticate with IBM Quantum, submit jobs, or execute hardware backends.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Iterable


QISKIT_PACKAGES = [
    "qiskit",
    "qiskit-aer",
    "qiskit-ibm-runtime",
    "numpy",
    "pandas",
]

IBM_TOKEN_ENV_VARS = [
    "IBM_QUANTUM_TOKEN",
    "QISKIT_IBM_TOKEN",
    "QISKIT_IBM_INSTANCE",
]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_package_version(package_name: str) -> str:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return ""


def detect_qiskit_package_versions() -> dict[str, str]:
    return {package: get_package_version(package) for package in QISKIT_PACKAGES}


def check_import(module_name: str) -> tuple[bool, str]:
    try:
        __import__(module_name)
        return True, ""
    except Exception as error:  # pragma: no cover - reported to CSV.
        return False, str(error)


def check_ibm_token_environment() -> dict[str, bool]:
    return {name: bool(os.environ.get(name)) for name in IBM_TOKEN_ENV_VARS}


def any_ibm_token_present() -> bool:
    return any(check_ibm_token_environment().values())


def create_one_qubit_test_circuit():
    from qiskit import QuantumCircuit

    circuit = QuantumCircuit(1, 1)
    circuit.h(0)
    circuit.measure(0, 0)
    return circuit


def extract_circuit_metadata(circuit, counts: dict[str, int] | None = None) -> dict[str, Any]:
    counts = counts or {}
    return {
        "num_qubits": circuit.num_qubits,
        "num_clbits": circuit.num_clbits,
        "circuit_depth": circuit.depth(),
        "num_gates": sum(circuit.count_ops().values()),
        "measurement_counts": dict(counts),
    }


def run_local_simulator_smoke_test(shots: int = 1024) -> dict[str, Any]:
    from qiskit import transpile
    from qiskit_aer import AerSimulator

    circuit = create_one_qubit_test_circuit()
    backend = AerSimulator()
    compiled = transpile(circuit, backend)
    job = backend.run(compiled, shots=shots)
    result = job.result()
    counts = result.get_counts(compiled)
    metadata_row = extract_circuit_metadata(circuit, counts)
    count_0 = int(counts.get("0", 0))
    count_1 = int(counts.get("1", 0))
    total_shots = count_0 + count_1

    return {
        "test_name": "one_qubit_h_measurement",
        "status": "PASS",
        "backend": backend.name,
        "shots": total_shots,
        "count_0": count_0,
        "count_1": count_1,
        "zero_ratio": count_0 / total_shots if total_shots else 0,
        "one_ratio": count_1 / total_shots if total_shots else 0,
        "num_qubits": metadata_row["num_qubits"],
        "num_clbits": metadata_row["num_clbits"],
        "circuit_depth": metadata_row["circuit_depth"],
        "num_gates": metadata_row["num_gates"],
        "measurement_counts": metadata_row["measurement_counts"],
        "notes": "Local Aer simulator execution only; no IBM authentication or hardware call.",
        "timestamp": utc_timestamp(),
    }


def write_json(path: str | Path, payload: Any) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: str | Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
