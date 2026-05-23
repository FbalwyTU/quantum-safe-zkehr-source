#!/usr/bin/env python3
"""Phase 3.3 IBM Runtime readiness check.

This script never prints token values and never submits IBM jobs.
"""

from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "results" / "quantum" / "phase3"
IBM_DIR = REPO_ROOT / "quantum-experiments" / "qiskit" / "ibm"

sys.path.insert(0, str(IBM_DIR))

from ibm_readiness_utils import (
    initialize_ibm_service_if_token_present,
    list_available_backends_if_authenticated,
    select_backend_for_circuit,
    utc_timestamp,
    write_csv,
    write_json,
    check_token_presence,
)


TOKEN_CSV = RESULTS_DIR / "phase3_3_token_check.csv"
SERVICE_CSV = RESULTS_DIR / "phase3_3_ibm_service_check.csv"
BACKENDS_JSON = RESULTS_DIR / "phase3_3_visible_backends.json"


def main() -> int:
    token_rows = check_token_presence()
    write_csv(
        TOKEN_CSV,
        token_rows,
        ["env_var", "present", "value_printed", "status", "notes"],
    )

    try:
        runtime_version = metadata.version("qiskit-ibm-runtime")
        runtime_import_ok = True
    except Exception as error:
        runtime_version = ""
        runtime_import_ok = False
        runtime_error = str(error)
    else:
        runtime_error = ""

    if not runtime_import_ok:
        service_rows = [
            {
                "check": "ibm_runtime_import",
                "status": "IBM_RUNTIME_IMPORT_FAILED",
                "token_present": any(row["present"] for row in token_rows),
                "service_initialized": False,
                "backend_count": 0,
                "selected_backend": "",
                "notes": runtime_error,
                "timestamp": utc_timestamp(),
            }
        ]
        write_csv(
            SERVICE_CSV,
            service_rows,
            [
                "check",
                "status",
                "token_present",
                "service_initialized",
                "backend_count",
                "selected_backend",
                "notes",
                "timestamp",
            ],
        )
        return 1

    service_status = initialize_ibm_service_if_token_present()
    backend_metadata = []
    selected_backend = ""
    safe_backend_payload = {
        "qiskit_ibm_runtime_version": runtime_version,
        "token_present": service_status["token_present"],
        "service_initialized": service_status["service_initialized"],
        "jobs_submitted": False,
        "backends": [],
    }

    if service_status["service_initialized"]:
        backend_metadata = list_available_backends_if_authenticated(service_status["service"])
        qrng_backend = select_backend_for_circuit(backend_metadata, min_qubits=8)
        toy_backend = select_backend_for_circuit(backend_metadata, min_qubits=5)
        selected = qrng_backend or toy_backend
        selected_backend = selected["name"] if selected else ""
        safe_backend_payload["selected_backend_for_qrng"] = (
            qrng_backend["name"] if qrng_backend else ""
        )
        safe_backend_payload["selected_backend_for_toy_policy"] = (
            toy_backend["name"] if toy_backend else ""
        )
        safe_backend_payload["backends"] = [
            {
                key: value
                for key, value in item.items()
                if key != "backend"
            }
            for item in backend_metadata
        ]

    status = service_status["status"]
    service_rows = [
        {
            "check": "ibm_runtime_service",
            "status": status,
            "token_present": service_status["token_present"],
            "service_initialized": service_status["service_initialized"],
            "backend_count": len(backend_metadata),
            "selected_backend": selected_backend,
            "notes": f"qiskit-ibm-runtime={runtime_version}. {service_status['notes']}",
            "timestamp": utc_timestamp(),
        }
    ]
    write_csv(
        SERVICE_CSV,
        service_rows,
        [
            "check",
            "status",
            "token_present",
            "service_initialized",
            "backend_count",
            "selected_backend",
            "notes",
            "timestamp",
        ],
    )
    write_json(BACKENDS_JSON, safe_backend_payload)
    print(f"Wrote {TOKEN_CSV}")
    print(f"Wrote {SERVICE_CSV}")
    print(f"Wrote {BACKENDS_JSON}")
    print(f"IBM readiness status: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
