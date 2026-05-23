#!/usr/bin/env python3
"""Record Phase 4.0 PQC package installation and import status."""

from __future__ import annotations

import csv
import importlib
from importlib import metadata
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path


PACKAGES = [
    {
        "package": "liboqs-python",
        "import_name": "oqs",
        "notes": "Python binding used through the oqs module.",
    },
    {
        "package": "oqs",
        "import_name": "oqs",
        "notes": "Requested package name; import resolves through the oqs module.",
    },
    {
        "package": "cmake",
        "import_name": "cmake",
        "notes": "Build helper required for native liboqs installation in this environment.",
    },
    {
        "package": "ninja",
        "import_name": "ninja",
        "notes": "Build helper installed for native liboqs builds.",
    },
]


def find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if (parent / "pqc-mlkem-analysis").exists() and (parent / "results").exists():
            return parent
    return Path.cwd()


def package_version(package_name: str) -> str:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return "NOT_INSTALLED"


def import_status(import_name: str) -> tuple[bool, str]:
    try:
        module = importlib.import_module(import_name)
        module_file = getattr(module, "__file__", "UNKNOWN")
        if import_name == "oqs":
            kem_count = "UNKNOWN"
            try:
                kem_count = str(len(module.get_enabled_kem_mechanisms()))
            except Exception as exc:  # pragma: no cover - diagnostic path
                return False, f"oqs imported but KEM enumeration failed: {type(exc).__name__}: {exc}"
            return True, f"module_file={module_file}; enabled_kem_count={kem_count}"
        return True, f"module_file={module_file}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    repo_root = find_repo_root()
    results_dir = repo_root / "results" / "pqc" / "phase4"
    results_dir.mkdir(parents=True, exist_ok=True)
    output_csv = results_dir / "phase4_0_package_check.csv"

    rows = []
    for item in PACKAGES:
        version = package_version(item["package"])
        installed = version != "NOT_INSTALLED"
        import_success, notes = import_status(item["import_name"])
        if installed and import_success:
            status = "PASS"
        elif installed:
            status = "IMPORT_FAILED"
        else:
            status = "NOT_INSTALLED"
        rows.append(
            {
                "package": item["package"],
                "version": version,
                "installed": str(installed).lower(),
                "import_success": str(import_success).lower(),
                "status": status,
                "notes": f"{item['notes']} {notes}",
            }
        )

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["package", "version", "installed", "import_success", "status", "notes"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"timestamp={datetime.now(timezone.utc).isoformat()}")
    print(f"python={sys.version.split()[0]}")
    print(f"platform={platform.platform()}")
    print(f"machine={platform.machine()}")
    print(f"package_check_csv={output_csv}")
    for row in rows:
        print(
            "package={package} version={version} installed={installed} "
            "import_success={import_success} status={status}".format(**row)
        )
    return 0 if all(row["status"] == "PASS" for row in rows[:2]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
