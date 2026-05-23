#!/usr/bin/env python3
"""Phase 3.5 IBM toy access-policy hardware execution.

This script submits at most one small hardware job unless an existing
non-secret Phase 3.5 job state is present. It requires IBM_QUANTUM_TOKEN from
the inherited process environment and never prints or stores token values.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "results" / "quantum" / "phase3"
TOY_POLICY_DIR = REPO_ROOT / "quantum-experiments" / "qiskit" / "toy_access_policy"

if str(TOY_POLICY_DIR) not in sys.path:
    sys.path.insert(0, str(TOY_POLICY_DIR))

from toy_policy_utils import build_toy_access_policy_circuit, evaluate_policy_result


BACKEND_SELECTION_CSV = RESULTS_DIR / "phase3_5_backend_selection.csv"
TRANSPILATION_JSON = RESULTS_DIR / "phase3_5_transpilation_metadata.json"
BACKEND_METADATA_JSON = RESULTS_DIR / "phase3_5_ibm_toy_policy_backend_metadata.json"
JOB_STATE_JSON = RESULTS_DIR / "phase3_5_job_state.json"
COUNTS_JSON = RESULTS_DIR / "phase3_5_ibm_toy_policy_counts.json"
SUMMARY_CSV = RESULTS_DIR / "phase3_5_ibm_toy_policy_summary.csv"

SHOTS = 1024
ROLE_VALID = 1
DEPARTMENT_VALID = 1
AUTHORIZED = 1
EXPECTED_OUTPUT = "1"
PREFERRED_BACKEND = "ibm_fez"
MAX_WAIT_SECONDS = int(os.environ.get("PHASE3_5_MAX_WAIT_SECONDS", "3600"))
POLL_SECONDS = int(os.environ.get("PHASE3_5_POLL_SECONDS", "15"))


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fieldnames} for row in rows])


def require_env_token() -> str:
    token = os.environ.get("IBM_QUANTUM_TOKEN")
    if not token:
        raise RuntimeError("IBM_QUANTUM_TOKEN is not available in the inherited process environment.")
    return token


def backend_name(backend: Any) -> str:
    name = getattr(backend, "name", "unknown_backend")
    return name() if callable(name) else str(name)


def backend_num_qubits(backend: Any) -> int | str:
    if hasattr(backend, "num_qubits"):
        try:
            return int(backend.num_qubits)
        except Exception:
            pass
    try:
        return int(backend.configuration().num_qubits)
    except Exception:
        return ""


def backend_basis_gates(backend: Any) -> list[str]:
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


def backend_status_info(backend: Any) -> tuple[bool | str, int | str]:
    try:
        status = backend.status()
        return bool(getattr(status, "operational", False)), getattr(status, "pending_jobs", "")
    except Exception:
        return "", ""


def list_hardware_backends(service: Any) -> list[dict[str, Any]]:
    rows = []
    for backend in service.backends():
        simulator = bool(getattr(backend, "simulator", False))
        if simulator:
            continue
        operational, pending_jobs = backend_status_info(backend)
        rows.append(
            {
                "backend_name": backend_name(backend),
                "num_qubits": backend_num_qubits(backend),
                "operational": operational,
                "pending_jobs": pending_jobs,
                "basis_gates": backend_basis_gates(backend),
                "backend": backend,
            }
        )
    return rows


def select_backend(backends: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = []
    for item in backends:
        if not isinstance(item["num_qubits"], int) or item["num_qubits"] < 5:
            continue
        if item["operational"] is False:
            continue
        candidates.append(item)
    if not candidates:
        raise RuntimeError("No operational IBM hardware backend with at least 5 qubits is visible.")

    preferred = [item for item in candidates if item["backend_name"] == PREFERRED_BACKEND]
    if preferred:
        return preferred[0]

    return sorted(
        candidates,
        key=lambda item: (
            item["pending_jobs"] if isinstance(item["pending_jobs"], int) else 999999,
            item["num_qubits"],
            item["backend_name"],
        ),
    )[0]


def write_backend_selection(backends: list[dict[str, Any]], selected_name: str) -> None:
    rows = []
    for item in sorted(backends, key=lambda row: str(row["backend_name"])):
        rows.append(
            {
                "backend_name": item["backend_name"],
                "num_qubits": item["num_qubits"],
                "operational": item["operational"],
                "pending_jobs": item["pending_jobs"],
                "basis_gates": json.dumps(item["basis_gates"]),
                "selected": item["backend_name"] == selected_name,
                "status": "SELECTED" if item["backend_name"] == selected_name else "VISIBLE",
                "notes": "Hardware backend metadata only; no job submitted during selection.",
            }
        )
    write_csv(
        BACKEND_SELECTION_CSV,
        rows,
        [
            "backend_name",
            "num_qubits",
            "operational",
            "pending_jobs",
            "basis_gates",
            "selected",
            "status",
            "notes",
        ],
    )


def extract_counts_from_sampler_result(result: Any) -> tuple[dict[str, int], list[str], dict[str, Any]]:
    pub_result = result[0]
    data = getattr(pub_result, "data", None)
    if data is None:
        raise RuntimeError("Sampler result did not contain a data payload.")

    for register_name, bit_array in data.items():
        if hasattr(bit_array, "get_counts"):
            counts = {str(key).replace(" ", ""): int(value) for key, value in bit_array.get_counts().items()}
            memory: list[str] = []
            if hasattr(bit_array, "get_bitstrings"):
                memory = [str(item).replace(" ", "") for item in bit_array.get_bitstrings()]
            metadata_payload = {
                "classical_register": str(register_name),
                "pub_metadata": getattr(pub_result, "metadata", {}),
                "result_metadata": getattr(result, "metadata", {}),
            }
            return counts, memory, metadata_payload

    raise RuntimeError("Sampler result did not expose count-bearing bit arrays.")


def job_status_name(job: Any) -> str:
    try:
        status = job.status()
        return getattr(status, "name", str(status))
    except Exception as error:
        return f"STATUS_ERROR: {error}"


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if JOB_STATE_JSON.exists():
        state = json.loads(JOB_STATE_JSON.read_text(encoding="utf-8"))
        job_id = state.get("job_id")
        if job_id and state.get("counts_collected"):
            print(f"Existing completed Phase 3.5 job state found for job_id={job_id}; no new job submitted.")
            return 0

    token = require_env_token()

    from qiskit import transpile
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler

    service = QiskitRuntimeService(channel="ibm_quantum_platform", token=token)
    backends = list_hardware_backends(service)
    selected = select_backend(backends)
    backend = selected["backend"]
    selected_name = selected["backend_name"]
    write_backend_selection(backends, selected_name)

    circuit = build_toy_access_policy_circuit(ROLE_VALID, DEPARTMENT_VALID, AUTHORIZED)
    original_depth = circuit.depth()
    original_gate_counts = dict(circuit.count_ops())
    transpile_started = time.perf_counter()
    transpiled = transpile(circuit, backend=backend, optimization_level=1, seed_transpiler=3500)
    transpilation_time_ms = (time.perf_counter() - transpile_started) * 1000
    transpiled_depth = transpiled.depth()
    transpiled_gate_counts = dict(transpiled.count_ops())

    write_json(
        TRANSPILATION_JSON,
        {
            "phase": "3.5",
            "backend_name": selected_name,
            "shots": SHOTS,
            "inputs": {
                "role_valid": ROLE_VALID,
                "department_valid": DEPARTMENT_VALID,
                "authorized": AUTHORIZED,
            },
            "expected_output": EXPECTED_OUTPUT,
            "original_depth": original_depth,
            "transpiled_depth": transpiled_depth,
            "original_gate_counts": original_gate_counts,
            "transpiled_gate_counts": transpiled_gate_counts,
            "transpilation_time_ms": transpilation_time_ms,
            "backend_basis_gates": selected["basis_gates"],
            "backend_num_qubits": selected["num_qubits"],
            "created_at": utc_timestamp(),
        },
    )

    write_json(
        BACKEND_METADATA_JSON,
        {
            "phase": "3.5",
            "backend_name": selected_name,
            "num_qubits": selected["num_qubits"],
            "operational": selected["operational"],
            "pending_jobs_at_selection": selected["pending_jobs"],
            "basis_gates": selected["basis_gates"],
            "simulator": False,
            "qiskit_version": metadata.version("qiskit"),
            "qiskit_ibm_runtime_version": metadata.version("qiskit-ibm-runtime"),
            "created_at": utc_timestamp(),
            "token_value_stored": False,
        },
    )

    if JOB_STATE_JSON.exists():
        state = json.loads(JOB_STATE_JSON.read_text(encoding="utf-8"))
        job_id = state.get("job_id")
        if not job_id:
            raise RuntimeError("Job state exists but does not contain a job_id.")
        print(f"Existing Phase 3.5 job state found for job_id={job_id}; attempting result retrieval without resubmitting.")
        job = service.job(job_id)
        submit_started = None
    else:
        submit_started = time.perf_counter()
        sampler = Sampler(mode=backend)
        job = sampler.run([transpiled], shots=SHOTS)
        job_id = job.job_id()
        write_json(
            JOB_STATE_JSON,
            {
                "job_id": job_id,
                "backend_name": selected_name,
                "shots": SHOTS,
                "submitted_at": utc_timestamp(),
                "submission_count": 1,
                "counts_collected": False,
                "primitive": "SamplerV2",
                "token_value_stored": False,
            },
        )
        print(f"Submitted one IBM hardware job: job_id={job_id}")

    wait_started = time.perf_counter()
    while True:
        status = job_status_name(job)
        elapsed = time.perf_counter() - wait_started
        print(f"job_status={status} elapsed_seconds={int(elapsed)}")
        if status in {"DONE", "COMPLETED"}:
            break
        if any(term in status.upper() for term in ("ERROR", "CANCEL", "FAIL")):
            raise RuntimeError(f"IBM hardware job ended unsuccessfully: {status}")
        if elapsed >= MAX_WAIT_SECONDS:
            state = json.loads(JOB_STATE_JSON.read_text(encoding="utf-8"))
            state["last_status"] = status
            state["counts_collected"] = False
            state["wait_timeout_seconds"] = MAX_WAIT_SECONDS
            state["updated_at"] = utc_timestamp()
            write_json(JOB_STATE_JSON, state)
            raise TimeoutError(f"IBM hardware job did not complete within {MAX_WAIT_SECONDS} seconds; job_id={job.job_id()}")
        time.sleep(POLL_SECONDS)

    result_started = time.perf_counter()
    result = job.result()
    runtime_ms = None
    if submit_started is not None:
        runtime_ms = (time.perf_counter() - submit_started) * 1000
    result_fetch_ms = (time.perf_counter() - result_started) * 1000
    counts, memory, sampler_metadata = extract_counts_from_sampler_result(result)
    metrics = evaluate_policy_result(counts, expected_granted=True)
    mismatch_probability = 1.0 - metrics["success_probability"]
    status = job_status_name(job)

    write_json(
        COUNTS_JSON,
        {
            "phase": "3.5",
            "experiment": "ibm_toy_access_policy_hardware",
            "hardware_used": True,
            "backend_name": selected_name,
            "job_id": job.job_id(),
            "shots": SHOTS,
            "inputs": {
                "role_valid": ROLE_VALID,
                "department_valid": DEPARTMENT_VALID,
                "authorized": AUTHORIZED,
            },
            "expected_output": EXPECTED_OUTPUT,
            "counts": dict(sorted(counts.items())),
            "memory_sample": memory[:16],
            "memory_count": len(memory),
            "sampler_metadata": sampler_metadata,
            "job_status": status,
            "runtime_ms": runtime_ms,
            "result_fetch_ms": result_fetch_ms,
            "token_value_stored": False,
            "created_at": utc_timestamp(),
        },
    )

    write_csv(
        SUMMARY_CSV,
        [
            {
                "backend_name": selected_name,
                "job_id": job.job_id(),
                "shots": SHOTS,
                "expected_output": EXPECTED_OUTPUT,
                "dominant_output": metrics["dominant_output"],
                "success_probability": f"{metrics['success_probability']:.6f}",
                "num_qubits": circuit.num_qubits,
                "original_depth": original_depth,
                "transpiled_depth": transpiled_depth,
                "status": status,
                "notes": (
                    f"Real IBM hardware execution for toy policy input 1,1,1. "
                    f"Mismatch probability={mismatch_probability:.6f}. "
                    "This is not Groth16, not zero-knowledge, and not production access control."
                ),
                "timestamp": utc_timestamp(),
            }
        ],
        [
            "backend_name",
            "job_id",
            "shots",
            "expected_output",
            "dominant_output",
            "success_probability",
            "num_qubits",
            "original_depth",
            "transpiled_depth",
            "status",
            "notes",
            "timestamp",
        ],
    )

    state = json.loads(JOB_STATE_JSON.read_text(encoding="utf-8"))
    state["last_status"] = status
    state["counts_collected"] = True
    state["counts_path"] = str(COUNTS_JSON)
    state["summary_path"] = str(SUMMARY_CSV)
    state["completed_at"] = utc_timestamp()
    write_json(JOB_STATE_JSON, state)
    print(f"IBM hardware toy policy job completed: job_id={job.job_id()} backend={selected_name}")
    print(f"Wrote {SUMMARY_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
