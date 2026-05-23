#!/usr/bin/env python3
"""TEMPLATE ONLY: IBM Quantum QRNG hardware execution for a later phase.

Do not run this template unless Phase 3.3 reports IBM_SERVICE_READY and the
user explicitly approves hardware execution. Running a real job can consume
IBM Quantum queue/QPU resources.

Safety rules:
- read tokens only from environment variables
- never print token values
- never store token values
- never submit jobs without explicit user approval
"""

from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def get_token_from_environment() -> str:
    token = os.environ.get("IBM_QUANTUM_TOKEN") or os.environ.get("QISKIT_IBM_TOKEN")
    if not token:
        raise RuntimeError("IBM Quantum token is not set in the environment.")
    return token


def build_qrng_circuit_for_hardware(num_qubits: int = 1):
    import sys

    qrng_dir = REPO_ROOT / "quantum-experiments" / "qiskit" / "qrng"
    sys.path.insert(0, str(qrng_dir))
    from qrng_utils import build_qrng_circuit

    return build_qrng_circuit(num_qubits)


def submit_qrng_hardware_job_TEMPLATE(explicit_user_approval: bool = False):
    """Template placeholder for Phase 3.4.

    This function intentionally refuses to submit unless a future phase passes
    explicit_user_approval=True after user confirmation.
    """
    if not explicit_user_approval:
        raise RuntimeError("Hardware submission blocked: explicit user approval is required.")

    # Future Phase 3.4 adaptation point:
    # from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
    # token = get_token_from_environment()
    # service = QiskitRuntimeService(channel="ibm_quantum", token=token)
    # backend = service.least_busy(operational=True, simulator=False, min_num_qubits=1)
    # circuit = build_qrng_circuit_for_hardware(num_qubits=1)
    # sampler = Sampler(mode=backend)
    # job = sampler.run([circuit], shots=1024)
    # return job.job_id()

    raise NotImplementedError("Adapt this template in Phase 3.4 before hardware execution.")


if __name__ == "__main__":
    print("TEMPLATE ONLY: no IBM job was submitted.")
    print("Use this file only after Phase 3.3 reports IBM_SERVICE_READY and the user approves Phase 3.4 hardware execution.")
