#!/usr/bin/env python3
"""Run the Phase 4.1 RSA-OAEP vs ML-KEM comparison harness."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if (parent / "pqc-mlkem-analysis").exists() and (parent / "results").exists():
            return parent
    return Path.cwd()


def main() -> int:
    repo_root = find_repo_root()
    venv_python = repo_root / "pqc-mlkem-analysis" / "pqc" / ".venv" / "bin" / "python"
    script = repo_root / "pqc-mlkem-analysis" / "pqc" / "comparison" / "rsa_vs_mlkem_experiment.py"
    expected_outputs = [
        repo_root / "results" / "pqc" / "phase4" / "phase4_1_rsa_baseline.csv",
        repo_root / "results" / "pqc" / "phase4" / "phase4_1_mlkem_results.csv",
        repo_root / "results" / "pqc" / "phase4" / "phase4_1_rsa_vs_mlkem_summary.csv",
        repo_root / "results" / "pqc" / "phase4" / "phase4_1_key_artifact_comparison.csv",
        repo_root / "results" / "pqc" / "phase4" / "phase4_1_raw_results.json",
        repo_root / "results" / "pqc" / "phase4" / "phase4_1_validation.csv",
    ]

    if not venv_python.exists():
        print(f"missing_pqc_venv_python={venv_python}", file=sys.stderr)
        return 1

    completed = subprocess.run([str(venv_python), str(script)], cwd=repo_root, check=False)
    if completed.returncode != 0:
        return completed.returncode

    missing = [str(path) for path in expected_outputs if not path.exists() or path.stat().st_size == 0]
    if missing:
        print("missing_or_empty_outputs=" + ",".join(missing), file=sys.stderr)
        return 1

    print("phase4_1_runner_status=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
