#!/usr/bin/env python3
"""Reproducible runner for Phase 3.1 QRNG simulator experiment."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_PYTHON = REPO_ROOT / "quantum-experiments" / "qiskit" / ".venv" / "bin" / "python"
EXPERIMENT = (
    REPO_ROOT
    / "quantum-experiments"
    / "qiskit"
    / "qrng"
    / "qrng_simulator_experiment.py"
)
EXPECTED_OUTPUTS = [
    REPO_ROOT / "results" / "quantum" / "phase3" / "phase3_1_qrng_simulator_detailed.csv",
    REPO_ROOT / "results" / "quantum" / "phase3" / "phase3_1_qrng_simulator_summary.csv",
    REPO_ROOT / "results" / "quantum" / "phase3" / "phase3_1_qrng_counts.json",
]


def main() -> int:
    python_path = Path(sys.executable)
    if python_path.resolve() != VENV_PYTHON.resolve():
        print(f"ERROR: runner must be executed with {VENV_PYTHON}")
        print(f"Current interpreter: {python_path}")
        return 2

    if not EXPERIMENT.exists():
        print(f"ERROR: experiment script not found: {EXPERIMENT}")
        return 3

    completed = subprocess.run([str(VENV_PYTHON), str(EXPERIMENT)], cwd=REPO_ROOT)
    if completed.returncode != 0:
        return completed.returncode

    missing = [str(path) for path in EXPECTED_OUTPUTS if not path.exists()]
    if missing:
        print("ERROR: expected outputs missing:")
        for path in missing:
            print(f"  {path}")
        return 4

    for path in EXPECTED_OUTPUTS:
        if path.stat().st_size == 0:
            print(f"ERROR: output file is empty: {path}")
            return 5

    print("Phase 3.1 QRNG simulator outputs verified.")
    for path in EXPECTED_OUTPUTS:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
