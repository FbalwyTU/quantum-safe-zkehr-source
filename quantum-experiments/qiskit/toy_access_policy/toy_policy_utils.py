"""Toy access-policy circuit utilities for Phase 3.2.

This module is a local Qiskit/Aer simulator feasibility demonstration only.
It is not Groth16, not zero-knowledge, and not production access control.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_binary(value: int | bool, label: str) -> int:
    normalized = int(value)
    if normalized not in (0, 1):
        raise ValueError(f"{label} must be 0 or 1.")
    return normalized


def build_toy_access_policy_circuit(
    role_valid: int | bool,
    department_valid: int | bool,
    authorized: int | bool,
    measure_inputs: bool = False,
):
    """Build a reversible toy policy circuit.

    Qubit layout:
    - q0: role_valid
    - q1: department_valid
    - q2: authorized
    - q3: ancilla = role_valid AND department_valid
    - q4: output access_granted = ancilla AND authorized
    """
    from qiskit import QuantumCircuit

    role_bit = _validate_binary(role_valid, "role_valid")
    department_bit = _validate_binary(department_valid, "department_valid")
    authorized_bit = _validate_binary(authorized, "authorized")
    classical_bits = 4 if measure_inputs else 1
    circuit = QuantumCircuit(5, classical_bits)

    if role_bit:
        circuit.x(0)
    if department_bit:
        circuit.x(1)
    if authorized_bit:
        circuit.x(2)

    circuit.barrier()
    circuit.ccx(0, 1, 3)
    circuit.ccx(3, 2, 4)
    circuit.ccx(0, 1, 3)
    circuit.barrier()

    circuit.measure(4, 0)
    if measure_inputs:
        circuit.measure(0, 1)
        circuit.measure(1, 2)
        circuit.measure(2, 3)

    return circuit


def _backend_name(backend: Any) -> str:
    name = getattr(backend, "name", "aer_simulator")
    return name() if callable(name) else str(name)


def extract_circuit_metadata(circuit, transpiled_circuit=None) -> dict[str, Any]:
    gate_counts = dict(circuit.count_ops())
    metadata = {
        "num_qubits": circuit.num_qubits,
        "num_clbits": circuit.num_clbits,
        "circuit_depth": circuit.depth(),
        "transpiled_depth": "",
        "gate_counts": gate_counts,
        "num_gates": sum(gate_counts.values()),
    }

    if transpiled_circuit is not None:
        metadata["transpiled_depth"] = transpiled_circuit.depth()
        metadata["transpiled_gate_counts"] = dict(transpiled_circuit.count_ops())

    return metadata


def run_policy_simulator(circuit, shots: int, seed_simulator: int | None = None) -> dict[str, Any]:
    if shots <= 0:
        raise ValueError("shots must be positive.")

    from qiskit import transpile
    from qiskit_aer import AerSimulator

    backend = AerSimulator(seed_simulator=seed_simulator)
    transpiled = transpile(circuit, backend)
    run_kwargs: dict[str, Any] = {"shots": shots}
    if seed_simulator is not None:
        run_kwargs["seed_simulator"] = seed_simulator
    job = backend.run(transpiled, **run_kwargs)
    result = job.result()
    counts = result.get_counts(transpiled)
    metadata = extract_circuit_metadata(circuit, transpiled)

    return {
        "backend": _backend_name(backend),
        "shots": shots,
        "seed_simulator": seed_simulator,
        "counts": dict(sorted(counts.items())),
        "metadata": metadata,
    }


def evaluate_policy_result(counts: dict[str, int], expected_granted: bool) -> dict[str, Any]:
    expected_bit = "1" if expected_granted else "0"
    total_shots = sum(int(value) for value in counts.values())
    success_count = int(counts.get(expected_bit, 0))
    failure_count = total_shots - success_count
    dominant_output = max(counts.items(), key=lambda item: int(item[1]))[0] if counts else ""

    return {
        "expected_output": expected_bit,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_probability": success_count / total_shots if total_shots else 0.0,
        "dominant_output": dominant_output,
        "dominant_output_matches_expected": dominant_output == expected_bit,
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
