#!/usr/bin/env bash
set -euo pipefail

python3 -m venv quantum-experiments/qiskit/.venv
quantum-experiments/qiskit/.venv/bin/python -m pip install --upgrade pip
quantum-experiments/qiskit/.venv/bin/python -m pip install -r quantum-experiments/requirements-qiskit.txt

python3 -m venv pqc-mlkem-analysis/pqc/.venv
pqc-mlkem-analysis/pqc/.venv/bin/python -m pip install --upgrade pip
pqc-mlkem-analysis/pqc/.venv/bin/python -m pip install -r pqc-mlkem-analysis/requirements-pqc.txt
