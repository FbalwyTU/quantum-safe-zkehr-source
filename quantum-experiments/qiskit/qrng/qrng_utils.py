"""QRNG simulator utilities for Phase 3.1.

This module uses only local Qiskit Aer simulation. It does not import IBM
Runtime, authenticate with IBM Quantum, or submit hardware jobs.
"""

from __future__ import annotations

import csv
import json
import math
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_qrng_circuit(num_qubits: int):
    """Build an H-measure QRNG circuit with one classical bit per qubit."""
    if num_qubits <= 0:
        raise ValueError("num_qubits must be positive.")

    from qiskit import QuantumCircuit

    circuit = QuantumCircuit(num_qubits, num_qubits)
    for index in range(num_qubits):
        circuit.h(index)
    circuit.measure(range(num_qubits), range(num_qubits))
    return circuit


def _backend_name(backend: Any) -> str:
    name = getattr(backend, "name", "aer_simulator")
    return name() if callable(name) else str(name)


def run_qrng_simulator(
    num_qubits: int,
    shots: int,
    seed_simulator: int | None = None,
) -> dict[str, Any]:
    """Run the QRNG circuit on local AerSimulator and return counts/metadata."""
    if shots <= 0:
        raise ValueError("shots must be positive.")

    from qiskit import transpile
    from qiskit_aer import AerSimulator

    circuit = build_qrng_circuit(num_qubits)
    backend = AerSimulator(seed_simulator=seed_simulator)
    compiled = transpile(circuit, backend)
    run_kwargs: dict[str, Any] = {"shots": shots, "memory": True}
    if seed_simulator is not None:
        run_kwargs["seed_simulator"] = seed_simulator

    job = backend.run(compiled, **run_kwargs)
    result = job.result()
    counts = result.get_counts(compiled)
    memory = result.get_memory(compiled)

    return {
        "backend": _backend_name(backend),
        "num_qubits": num_qubits,
        "shots": shots,
        "seed_simulator": seed_simulator,
        "counts": dict(sorted(counts.items())),
        "memory": [str(item).replace(" ", "") for item in memory],
        "circuit_depth": circuit.depth(),
        "num_gates": sum(circuit.count_ops().values()),
        "circuit_ops": dict(circuit.count_ops()),
    }


def counts_to_bitstrings(counts: dict[str, int], max_expanded_shots: int = 100_000) -> list[str]:
    """Expand aggregate Qiskit counts into bitstrings when size is safe.

    Counts do not preserve original shot order, so this is a fallback helper.
    Prefer simulator memory when order-sensitive run metrics are needed.
    """
    total_shots = sum(int(value) for value in counts.values())
    if total_shots > max_expanded_shots:
        raise ValueError(
            f"Refusing to expand {total_shots} shots; max_expanded_shots={max_expanded_shots}."
        )

    expanded: list[str] = []
    for bitstring, count in sorted(counts.items()):
        expanded.extend([str(bitstring).replace(" ", "")] * int(count))
    return expanded


def generate_classical_random_bits(num_bits: int) -> str:
    """Generate classical comparator bits with Python's secrets module."""
    if num_bits <= 0:
        raise ValueError("num_bits must be positive.")

    byte_count = math.ceil(num_bits / 8)
    random_bytes = secrets.token_bytes(byte_count)
    return "".join(f"{byte:08b}" for byte in random_bytes)[:num_bits]


def _longest_run(bitstring: str, target: str) -> int:
    longest = 0
    current = 0
    for bit in bitstring:
        if bit == target:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def compute_bit_metrics(bitstring: str) -> dict[str, Any]:
    """Compute basic bit-level metrics for a binary string."""
    if not bitstring:
        raise ValueError("bitstring must not be empty.")
    if any(bit not in {"0", "1"} for bit in bitstring):
        raise ValueError("bitstring must contain only 0 and 1 characters.")

    total_bits = len(bitstring)
    count_0 = bitstring.count("0")
    count_1 = bitstring.count("1")
    zero_ratio = count_0 / total_bits
    one_ratio = count_1 / total_bits
    entropy = 0.0
    for probability in (zero_ratio, one_ratio):
        if probability > 0:
            entropy -= probability * math.log2(probability)

    transitions_count = sum(
        1 for left, right in zip(bitstring, bitstring[1:]) if left != right
    )
    transitions_ratio = transitions_count / (total_bits - 1) if total_bits > 1 else 0.0

    return {
        "total_bits": total_bits,
        "count_0": count_0,
        "count_1": count_1,
        "zero_ratio": zero_ratio,
        "one_ratio": one_ratio,
        "shannon_entropy_per_bit": entropy,
        "monobit_balance_error": abs(one_ratio - 0.5),
        "longest_run_0": _longest_run(bitstring, "0"),
        "longest_run_1": _longest_run(bitstring, "1"),
        "transitions_count": transitions_count,
        "transitions_ratio": transitions_ratio,
    }


def bitstrings_to_bitstream(bitstrings: Iterable[str]) -> str:
    return "".join(str(item).replace(" ", "") for item in bitstrings)


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
