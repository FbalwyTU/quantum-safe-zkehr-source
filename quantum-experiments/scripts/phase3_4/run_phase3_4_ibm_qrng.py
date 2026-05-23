#!/usr/bin/env python3
"""Phase 3.4 IBM QRNG hardware execution.

This script submits at most one small QRNG circuit job unless an existing
non-secret job state is present. It never prints or stores token values.
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "results" / "quantum" / "phase3"
QRNG_DIR = REPO_ROOT / "quantum-experiments" / "qiskit" / "qrng"
IBM_DIR = REPO_ROOT / "quantum-experiments" / "qiskit" / "ibm"

for path in (QRNG_DIR, IBM_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from qrng_utils import bitstrings_to_bitstream, compute_bit_metrics, counts_to_bitstrings


BACKEND_SELECTION_CSV = RESULTS_DIR / "phase3_4_backend_selection.csv"
TRANSPILATION_JSON = RESULTS_DIR / "phase3_4_transpilation_metadata.json"
COUNTS_JSON = RESULTS_DIR / "phase3_4_ibm_qrng_counts.json"
BACKEND_METADATA_JSON = RESULTS_DIR / "phase3_4_ibm_qrng_backend_metadata.json"
SUMMARY_CSV = RESULTS_DIR / "phase3_4_ibm_qrng_summary.csv"
JOB_STATE_JSON = RESULTS_DIR / "phase3_4_job_state.json"

NUM_QUBITS = 8
SHOTS = 1024
MAX_WAIT_SECONDS = int(os.environ.get("PHASE3_4_MAX_WAIT_SECONDS", "3600"))
POLL_SECONDS = int(os.environ.get("PHASE3_4_POLL_SECONDS", "15"))


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


def load_token_into_process() -> tuple[bool, str]:
    """Require IBM_QUANTUM_TOKEN from the inherited process environment only."""
    return bool(os.environ.get("IBM_QUANTUM_TOKEN")), "environment" if os.environ.get("IBM_QUANTUM_TOKEN") else "missing"


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
        if not isinstance(item["num_qubits"], int) or item["num_qubits"] < NUM_QUBITS:
            continue
        if item["operational"] is False:
            continue
        candidates.append(item)
    if not candidates:
        raise RuntimeError("No operational IBM hardware backend with at least 8 qubits is visible.")

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


def build_qrng_circuit():
    from qrng_utils import build_qrng_circuit as build

    return build(NUM_QUBITS)


def extract_counts_from_result(result: Any, circuit: Any) -> tuple[dict[str, int], list[str]]:
    counts: dict[str, int]
    memory: list[str] = []
    try:
        counts = dict(result.get_counts(circuit))
    except Exception:
        counts = dict(result.get_counts())
    try:
        memory = [str(item).replace(" ", "") for item in result.get_memory(circuit)]
    except Exception:
        try:
            memory = [str(item).replace(" ", "") for item in result.get_memory()]
        except Exception:
            memory = []
    return counts, memory


def extract_counts_from_sampler_result(result: Any) -> tuple[dict[str, int], list[str], dict[str, Any]]:
    """Extract counts from a SamplerV2 PrimitiveResult."""
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


def metrics_from_counts_or_memory(counts: dict[str, int], memory: list[str]) -> tuple[dict[str, Any], str]:
    if memory:
        bitstream = bitstrings_to_bitstream(memory)
        source = "hardware_memory_order"
    else:
        bitstrings = counts_to_bitstrings(counts, max_expanded_shots=100_000)
        bitstream = bitstrings_to_bitstream(bitstrings)
        source = "expanded_counts_sorted_order"
    return compute_bit_metrics(bitstream), source


def job_status_name(job: Any) -> str:
    try:
        status = job.status()
        return getattr(status, "name", str(status))
    except Exception as error:
        return f"STATUS_ERROR: {error}"


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    token_present, token_source = load_token_into_process()
    if not token_present:
        raise RuntimeError("IBM_QUANTUM_TOKEN is not available in the inherited process environment.")

    from qiskit import transpile
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler

    token = os.environ.get("IBM_QUANTUM_TOKEN")
    service = QiskitRuntimeService(channel="ibm_quantum_platform", token=token)
    backends = list_hardware_backends(service)
    selected = select_backend(backends)
    backend = selected["backend"]
    selected_name = selected["backend_name"]
    write_backend_selection(backends, selected_name)

    circuit = build_qrng_circuit()
    original_depth = circuit.depth()
    original_gate_counts = dict(circuit.count_ops())
    transpile_started = time.perf_counter()
    transpiled = transpile(circuit, backend=backend, optimization_level=1, seed_transpiler=3400)
    transpilation_time_ms = (time.perf_counter() - transpile_started) * 1000
    transpiled_depth = transpiled.depth()
    transpiled_gate_counts = dict(transpiled.count_ops())

    transpilation_payload = {
        "backend_name": selected_name,
        "num_qubits": NUM_QUBITS,
        "shots": SHOTS,
        "original_depth": original_depth,
        "transpiled_depth": transpiled_depth,
        "original_gate_counts": original_gate_counts,
        "transpiled_gate_counts": transpiled_gate_counts,
        "transpilation_time_ms": transpilation_time_ms,
        "backend_basis_gates": selected["basis_gates"],
        "backend_num_qubits": selected["num_qubits"],
        "created_at": utc_timestamp(),
    }
    write_json(TRANSPILATION_JSON, transpilation_payload)

    backend_metadata_payload = {
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
    }
    write_json(BACKEND_METADATA_JSON, backend_metadata_payload)

    if JOB_STATE_JSON.exists():
        state = json.loads(JOB_STATE_JSON.read_text(encoding="utf-8"))
        job_id = state.get("job_id")
        if job_id and state.get("counts_collected"):
            print(f"Existing completed Phase 3.4 job state found for job_id={job_id}; no new job submitted.")
            return 0
        if job_id:
            print(f"Existing Phase 3.4 job state found for job_id={job_id}; attempting result retrieval without resubmitting.")
            job = service.job(job_id)
        else:
            raise RuntimeError("Job state exists but does not contain a job_id.")
    else:
        submit_started = time.perf_counter()
        sampler = Sampler(mode=backend)
        job = sampler.run([transpiled], shots=SHOTS)
        job_id = job.job_id()
        state = {
            "job_id": job_id,
            "backend_name": selected_name,
            "shots": SHOTS,
            "submitted_at": utc_timestamp(),
            "submission_count": 1,
            "counts_collected": False,
            "primitive": "SamplerV2",
            "token_value_stored": False,
        }
        write_json(JOB_STATE_JSON, state)
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
    try:
        # Best-effort queue+execution wall clock from submission path.
        runtime_ms = (time.perf_counter() - submit_started) * 1000  # type: ignore[name-defined]
    except Exception:
        runtime_ms = (time.perf_counter() - wait_started) * 1000
    result_fetch_ms = (time.perf_counter() - result_started) * 1000
    counts, memory, sampler_metadata = extract_counts_from_sampler_result(result)
    metrics, metric_source = metrics_from_counts_or_memory(counts, memory)

    status = job_status_name(job)
    counts_payload = {
        "phase": "3.4",
        "experiment": "ibm_qrng_hardware",
        "hardware_used": True,
        "backend_name": selected_name,
        "job_id": job.job_id(),
        "shots": SHOTS,
        "num_qubits": NUM_QUBITS,
        "counts": dict(sorted(counts.items())),
        "memory_sample": memory[:16],
        "memory_count": len(memory),
        "metric_source": metric_source,
        "sampler_metadata": sampler_metadata,
        "primitive": "SamplerV2",
        "job_status": status,
        "result_fetch_ms": result_fetch_ms,
        "token_value_stored": False,
        "created_at": utc_timestamp(),
    }
    write_json(COUNTS_JSON, counts_payload)

    summary_row = {
        "backend_name": selected_name,
        "job_id": job.job_id(),
        "shots": SHOTS,
        "total_bits": metrics["total_bits"],
        "count_0": metrics["count_0"],
        "count_1": metrics["count_1"],
        "zero_ratio": f"{metrics['zero_ratio']:.6f}",
        "one_ratio": f"{metrics['one_ratio']:.6f}",
        "shannon_entropy_per_bit": f"{metrics['shannon_entropy_per_bit']:.6f}",
        "monobit_balance_error": f"{metrics['monobit_balance_error']:.6f}",
        "longest_run_0": metrics["longest_run_0"],
        "longest_run_1": metrics["longest_run_1"],
        "transitions_count": metrics["transitions_count"],
        "transitions_ratio": f"{metrics['transitions_ratio']:.6f}",
        "num_qubits": NUM_QUBITS,
        "original_depth": original_depth,
        "transpiled_depth": transpiled_depth,
        "status": status,
        "notes": f"Real IBM hardware execution. Metrics source={metric_source}. No quantum advantage or production QRNG claim.",
        "timestamp": utc_timestamp(),
    }
    write_csv(
        SUMMARY_CSV,
        [summary_row],
        [
            "backend_name",
            "job_id",
            "shots",
            "total_bits",
            "count_0",
            "count_1",
            "zero_ratio",
            "one_ratio",
            "shannon_entropy_per_bit",
            "monobit_balance_error",
            "longest_run_0",
            "longest_run_1",
            "transitions_count",
            "transitions_ratio",
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
    print(f"IBM hardware QRNG job completed: job_id={job.job_id()} backend={selected_name}")
    print(f"Wrote {SUMMARY_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
