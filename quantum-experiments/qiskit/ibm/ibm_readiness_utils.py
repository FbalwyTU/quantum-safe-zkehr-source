"""IBM Quantum readiness helpers for Phase 3.3.

This module performs readiness inspection only. It never submits jobs, never
prints token values, and never stores token values.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
QISKIT_ROOT = REPO_ROOT / "quantum-experiments" / "qiskit"
QRNG_DIR = QISKIT_ROOT / "qrng"
TOY_POLICY_DIR = QISKIT_ROOT / "toy_access_policy"

for path in (QRNG_DIR, TOY_POLICY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

IBM_TOKEN_ENV_VARS = [
    "IBM_QUANTUM_TOKEN",
    "QISKIT_IBM_TOKEN",
    "QISKIT_IBM_INSTANCE",
]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def check_token_presence() -> list[dict[str, Any]]:
    """Return token env-var presence without values."""
    rows = []
    for env_var in IBM_TOKEN_ENV_VARS:
        rows.append(
            {
                "env_var": env_var,
                "present": bool(os.environ.get(env_var)),
                "value_printed": False,
                "status": "PRESENT" if os.environ.get(env_var) else "ABSENT",
                "notes": "Presence check only; token values are never printed or stored.",
            }
        )
    return rows


def _first_token_env_var() -> tuple[str, str] | tuple[None, None]:
    for env_var in ("IBM_QUANTUM_TOKEN", "QISKIT_IBM_TOKEN"):
        value = os.environ.get(env_var)
        if value:
            return env_var, value
    return None, None


def initialize_ibm_service_if_token_present() -> dict[str, Any]:
    """Initialize QiskitRuntimeService only when a token env var is present."""
    token_env_var, token = _first_token_env_var()
    if not token:
        return {
            "token_present": False,
            "service_initialized": False,
            "service": None,
            "status": "READY_FOR_IBM_TOKEN",
            "notes": "No IBM token environment variable is present. This is acceptable for Phase 3.3.",
        }

    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
    except Exception as error:
        return {
            "token_present": True,
            "service_initialized": False,
            "service": None,
            "status": "IBM_RUNTIME_IMPORT_FAILED",
            "notes": f"qiskit-ibm-runtime import failed: {error}",
        }

    try:
        kwargs: dict[str, Any] = {"channel": "ibm_quantum", "token": token}
        instance = os.environ.get("QISKIT_IBM_INSTANCE")
        if instance:
            kwargs["instance"] = instance
        service = QiskitRuntimeService(**kwargs)
        return {
            "token_present": True,
            "token_env_var": token_env_var,
            "service_initialized": True,
            "service": service,
            "status": "IBM_SERVICE_READY",
            "notes": "IBM Runtime service initialized using token from environment. Token value was not printed or stored.",
        }
    except Exception as error:
        return {
            "token_present": True,
            "token_env_var": token_env_var,
            "service_initialized": False,
            "service": None,
            "status": "IBM_SERVICE_INIT_FAILED",
            "notes": f"IBM Runtime service initialization failed without printing token: {error}",
        }


def _backend_name(backend: Any) -> str:
    name = getattr(backend, "name", "unknown_backend")
    return name() if callable(name) else str(name)


def _backend_num_qubits(backend: Any) -> int | str:
    if hasattr(backend, "num_qubits"):
        try:
            return int(backend.num_qubits)
        except Exception:
            pass
    try:
        return int(backend.configuration().num_qubits)
    except Exception:
        return ""


def _backend_basis_gates(backend: Any) -> list[str]:
    try:
        target = getattr(backend, "target", None)
        if target is not None and getattr(target, "operation_names", None):
            return sorted(str(item) for item in target.operation_names)
    except Exception:
        pass
    try:
        return list(backend.configuration().basis_gates)
    except Exception:
        return []


def list_available_backends_if_authenticated(service: Any | None) -> list[dict[str, Any]]:
    if service is None:
        return []

    backends = service.backends()
    metadata = []
    for backend in backends:
        name = _backend_name(backend)
        simulator = bool(getattr(backend, "simulator", False))
        try:
            status = backend.status()
            operational = bool(getattr(status, "operational", False))
            pending_jobs = getattr(status, "pending_jobs", "")
        except Exception:
            operational = ""
            pending_jobs = ""
        metadata.append(
            {
                "name": name,
                "num_qubits": _backend_num_qubits(backend),
                "simulator": simulator,
                "operational": operational,
                "pending_jobs": pending_jobs,
                "basis_gates": _backend_basis_gates(backend),
                "backend": backend,
            }
        )
    return metadata


def select_backend_for_circuit(
    backend_metadata: list[dict[str, Any]],
    min_qubits: int,
) -> dict[str, Any] | None:
    candidates = []
    for item in backend_metadata:
        num_qubits = item.get("num_qubits")
        if not isinstance(num_qubits, int):
            continue
        if num_qubits < min_qubits:
            continue
        if item.get("simulator"):
            continue
        if item.get("operational") is False:
            continue
        candidates.append(item)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (
            item.get("pending_jobs") if isinstance(item.get("pending_jobs"), int) else 999999,
            item["num_qubits"],
            item["name"],
        ),
    )[0]


def build_or_load_qrng_circuit(num_qubits: int = 8):
    from qrng_utils import build_qrng_circuit

    return build_qrng_circuit(num_qubits)


def build_or_load_toy_access_policy_circuit():
    from toy_policy_utils import build_toy_access_policy_circuit

    return build_toy_access_policy_circuit(1, 1, 1)


def transpile_for_backend_or_simulator(circuit, backend: Any | None = None):
    from qiskit import transpile

    if backend is None:
        from qiskit_aer import AerSimulator

        backend = AerSimulator()
    transpiled = transpile(circuit, backend)
    return backend, transpiled


def extract_transpilation_metadata(circuit, transpiled_circuit, backend) -> dict[str, Any]:
    backend_basis_gates = _backend_basis_gates(backend)
    original_gate_counts = dict(circuit.count_ops())
    transpiled_gate_counts = dict(transpiled_circuit.count_ops())
    return {
        "num_qubits": circuit.num_qubits,
        "num_clbits": circuit.num_clbits,
        "original_depth": circuit.depth(),
        "transpiled_depth": transpiled_circuit.depth(),
        "original_gate_counts": original_gate_counts,
        "transpiled_gate_counts": transpiled_gate_counts,
        "backend_name": _backend_name(backend),
        "backend_basis_gates": backend_basis_gates,
        "backend_num_qubits": _backend_num_qubits(backend),
    }


def write_json(path: str | Path, payload: Any) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_csv(path: str | Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
