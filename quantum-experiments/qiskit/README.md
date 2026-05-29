# Qiskit Quantum-Assisted Layer

## Purpose

This folder contains the Qiskit-side scaffolding for the Quantum-Safe ZK-EHR migration track. It is separate from the stabilized classical ZK-EHR baseline and must not modify baseline contracts, circuits, IPFS workflow code, or original evaluation scripts.

## What Phase 3.0 Does

Phase 3.0 prepares and validates the local Qiskit environment:

- creates a local Python virtual environment under `quantum-experiments/qiskit/.venv/`
- installs/imports `qiskit`, `qiskit-aer`, `qiskit-ibm-runtime`, `numpy`, and `pandas`
- provides a safe non-secret config template
- provides reusable Qiskit environment helper functions
- runs a one-qubit local simulator smoke test
- checks that IBM Runtime imports without authenticating

## What Phase 3.0 Does Not Do

Phase 3.0 does not:

- implement the QRNG experiment
- implement the toy access-policy quantum circuit
- run IBM Quantum hardware
- require or use an IBM Quantum token
- implement post-quantum cryptography
- modify baseline ZK-EHR core code

## Run the Qiskit Smoke Test

From the repository root:

```bash
quantum-experiments/qiskit/.venv/bin/python quantum-experiments/qiskit/smoke_tests/qiskit_smoke_test.py
```

Expected output:

```text
results/quantum/phase3/phase3_0_qiskit_smoke_test.csv
```

The smoke test creates a one-qubit circuit, applies an H gate, measures the qubit, and runs the circuit on the local Aer simulator.

## Future Phase Usage

- Phase 3.1: QRNG simulator experiment using local Qiskit simulation only.
- Phase 3.2: toy access-policy simulator experiment for architecture comparison.
- Phase 3.3: IBM readiness check without mandatory hardware execution.
- Phase 3.4/3.5: optional IBM hardware execution if credentials, backend access, and research protocol are approved.

## Token Safety

Never store IBM Quantum tokens in source code, JSON config files, notebooks, CSV files, or reports.

Use environment variables only, for example:

```bash
export IBM_QUANTUM_TOKEN="..."
```

Phase 3.0 checks only whether token-related environment variables are present. It does not print values and does not authenticate.

## Scientific Framing

The Phase 3.0 Qiskit simulator run is a local classical simulation of a quantum circuit. It is not real quantum hardware execution.

No quantum advantage is claimed. IBM hardware execution remains optional for a later phase and must be reported separately from simulator-only results.
