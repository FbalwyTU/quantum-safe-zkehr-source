#!/usr/bin/env python3
"""Write Phase 3.0 Qiskit package and IBM Runtime import checks."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO_ROOT / "results" / "quantum" / "phase3"
UTILS_DIR = REPO_ROOT / "quantum-experiments" / "qiskit" / "utils"

sys.path.insert(0, str(UTILS_DIR))

from qiskit_environment import (
    any_ibm_token_present,
    check_import,
    detect_qiskit_package_versions,
    write_csv,
)


PACKAGE_MODULES = {
    "qiskit": "qiskit",
    "qiskit-aer": "qiskit_aer",
    "qiskit-ibm-runtime": "qiskit_ibm_runtime",
    "numpy": "numpy",
    "pandas": "pandas",
}


def write_package_check() -> None:
    versions = detect_qiskit_package_versions()
    rows = []

    for package, module in PACKAGE_MODULES.items():
        import_success, error = check_import(module)
        version = versions.get(package, "")
        installed = bool(version)
        status = "PASS" if installed and import_success else "FAIL"
        rows.append(
            {
                "package": package,
                "version": version,
                "installed": installed,
                "import_success": import_success,
                "status": status,
                "notes": error or "Installed and imported successfully.",
            }
        )

    write_csv(
        RESULTS_DIR / "phase3_0_package_check.csv",
        rows,
        ["package", "version", "installed", "import_success", "status", "notes"],
    )


def write_ibm_runtime_check() -> None:
    import_success, error = check_import("qiskit_ibm_runtime")
    version = detect_qiskit_package_versions().get("qiskit-ibm-runtime", "")
    token_present = any_ibm_token_present()

    if not import_success:
        status = "IMPORT_FAILED"
        notes = error
    elif token_present:
        status = "TOKEN_PRESENT_BUT_NOT_USED"
        notes = "qiskit-ibm-runtime imports successfully. Token env var is present but no authentication or service call was attempted."
    else:
        status = "TOKEN_ABSENT_NOT_REQUIRED"
        notes = "qiskit-ibm-runtime imports successfully. Token is absent and was not required for this import-only check."

    write_csv(
        RESULTS_DIR / "phase3_0_ibm_runtime_import_check.csv",
        [
            {
                "component": "qiskit-ibm-runtime",
                "import_success": import_success,
                "version": version,
                "token_env_present": token_present,
                "status": status,
                "notes": notes,
            }
        ],
        [
            "component",
            "import_success",
            "version",
            "token_env_present",
            "status",
            "notes",
        ],
    )


def main() -> int:
    write_package_check()
    write_ibm_runtime_check()
    print("Wrote Phase 3.0 package and IBM Runtime import checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
