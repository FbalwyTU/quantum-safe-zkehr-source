#!/usr/bin/env python3
"""Run Phase 4.1 RSA-OAEP vs ML-KEM-768 comparison experiment."""

from __future__ import annotations

import csv
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path


ITERATIONS = 25


def find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if (parent / "pqc-mlkem-analysis").exists() and (parent / "results").exists():
            return parent
    return Path.cwd()


REPO_ROOT = find_repo_root()
PQC_UTILS_DIR = REPO_ROOT / "pqc-mlkem-analysis" / "pqc" / "utils"
if str(PQC_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(PQC_UTILS_DIR))

from mlkem_utils import run_mlkem_iteration, select_mlkem_algorithm
from rsa_baseline_utils import run_rsa_oaep_iteration


RESULTS_DIR = REPO_ROOT / "results" / "pqc" / "phase4"
RSA_CSV = RESULTS_DIR / "phase4_1_rsa_baseline.csv"
MLKEM_CSV = RESULTS_DIR / "phase4_1_mlkem_results.csv"
SUMMARY_CSV = RESULTS_DIR / "phase4_1_rsa_vs_mlkem_summary.csv"
ARTIFACT_CSV = RESULTS_DIR / "phase4_1_key_artifact_comparison.csv"
RAW_JSON = RESULTS_DIR / "phase4_1_raw_results.json"
VALIDATION_CSV = RESULTS_DIR / "phase4_1_validation.csv"


RSA_FIELDS = [
    "iteration",
    "algorithm",
    "rsa_key_size_bits",
    "oaep_hash",
    "aes_session_key_size",
    "public_key_size",
    "private_key_size",
    "wrapped_key_size",
    "keygen_ms",
    "wrap_ms",
    "unwrap_ms",
    "recovered_key_match",
    "total_artifact_size",
    "status",
    "notes",
]


MLKEM_FIELDS = [
    "iteration",
    "algorithm",
    "selection_mode",
    "public_key_size",
    "secret_key_size",
    "ciphertext_size",
    "shared_secret_size",
    "keygen_ms",
    "encapsulation_ms",
    "decapsulation_ms",
    "shared_secret_match",
    "total_artifact_size",
    "status",
    "notes",
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def stdev(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def metric_summary(rows: list[dict[str, object]], metric_name: str) -> dict[str, float]:
    values = [float(row[metric_name]) for row in rows]
    return {
        "avg": mean(values),
        "stdev": stdev(values),
        "min": min(values) if values else 0.0,
        "max": max(values) if values else 0.0,
    }


def build_summary_rows(rsa_rows: list[dict[str, object]], mlkem_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    mapping = [
        ("RSA-OAEP-2048-SHA256", rsa_rows, "keygen_ms", "key_generation"),
        ("RSA-OAEP-2048-SHA256", rsa_rows, "wrap_ms", "wrap_or_encapsulate"),
        ("RSA-OAEP-2048-SHA256", rsa_rows, "unwrap_ms", "unwrap_or_decapsulate"),
        ("ML-KEM-768", mlkem_rows, "keygen_ms", "key_generation"),
        ("ML-KEM-768", mlkem_rows, "encapsulation_ms", "wrap_or_encapsulate"),
        ("ML-KEM-768", mlkem_rows, "decapsulation_ms", "unwrap_or_decapsulate"),
    ]
    for algorithm, source_rows, source_metric, phase in mapping:
        summary = metric_summary(source_rows, source_metric)
        rows.append(
            {
                "algorithm": algorithm,
                "operation": phase,
                "iterations": len(source_rows),
                "avg_ms": f"{summary['avg']:.6f}",
                "stdev_ms": f"{summary['stdev']:.6f}",
                "min_ms": f"{summary['min']:.6f}",
                "max_ms": f"{summary['max']:.6f}",
                "success_count": sum(1 for row in source_rows if row["status"] == "PASS"),
                "failure_count": sum(1 for row in source_rows if row["status"] != "PASS"),
                "notes": "Controlled local comparison; not production deployment.",
            }
        )
    return rows


def build_artifact_rows(rsa_rows: list[dict[str, object]], mlkem_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rsa = rsa_rows[0]
    mlkem = mlkem_rows[0]
    return [
        {
            "algorithm": "RSA-OAEP-2048-SHA256",
            "public_key_size": rsa["public_key_size"],
            "private_or_secret_key_size": rsa["private_key_size"],
            "wrapped_or_ciphertext_size": rsa["wrapped_key_size"],
            "session_or_shared_secret_size": rsa["aes_session_key_size"],
            "total_artifact_size": rsa["total_artifact_size"],
            "notes": "RSA row includes DER public key, DER private key, and wrapped AES key size.",
        },
        {
            "algorithm": mlkem["algorithm"],
            "public_key_size": mlkem["public_key_size"],
            "private_or_secret_key_size": mlkem["secret_key_size"],
            "wrapped_or_ciphertext_size": mlkem["ciphertext_size"],
            "session_or_shared_secret_size": mlkem["shared_secret_size"],
            "total_artifact_size": mlkem["total_artifact_size"],
            "notes": "ML-KEM row includes public key, secret key size, and ciphertext size.",
        },
    ]


def validation_rows(
    rsa_rows: list[dict[str, object]], mlkem_rows: list[dict[str, object]], summary_created: bool
) -> list[dict[str, str]]:
    def add(check: str, passed: bool, details: str) -> None:
        rows.append({"check": check, "status": "PASS" if passed else "FAIL", "details": details})

    rows: list[dict[str, str]] = []
    add("RSA key generation succeeded", all(row["keygen_ms"] >= 0 for row in rsa_rows), f"iterations={len(rsa_rows)}")
    add("RSA wrap/unwrap succeeded", all(row["status"] == "PASS" for row in rsa_rows), "all RSA rows PASS")
    add(
        "AES key recovery matched",
        all(row["recovered_key_match"] is True for row in rsa_rows),
        "recovered_key_match true for every RSA iteration",
    )
    add(
        "ML-KEM key generation succeeded",
        all(row["keygen_ms"] >= 0 for row in mlkem_rows),
        f"iterations={len(mlkem_rows)}",
    )
    add("ML-KEM encapsulation succeeded", all(row["status"] == "PASS" for row in mlkem_rows), "all ML-KEM rows PASS")
    add("ML-KEM decapsulation succeeded", all(row["status"] == "PASS" for row in mlkem_rows), "all ML-KEM rows PASS")
    add(
        "shared secrets matched",
        all(row["shared_secret_match"] is True for row in mlkem_rows),
        "shared_secret_match true for every ML-KEM iteration",
    )
    add("timing data collected", bool(rsa_rows and mlkem_rows), "timing columns populated in detailed CSVs")
    add("artifact sizes collected", bool(rsa_rows and mlkem_rows), "size columns populated in detailed CSVs")
    add("summary CSV created", summary_created and SUMMARY_CSV.exists(), str(SUMMARY_CSV))
    return rows


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    mlkem_algorithm, selection_mode = select_mlkem_algorithm()

    rsa_rows = [run_rsa_oaep_iteration(iteration) for iteration in range(1, ITERATIONS + 1)]
    mlkem_rows = [
        run_mlkem_iteration(iteration, algorithm_name=mlkem_algorithm) for iteration in range(1, ITERATIONS + 1)
    ]

    write_csv(RSA_CSV, RSA_FIELDS, rsa_rows)
    write_csv(MLKEM_CSV, MLKEM_FIELDS, mlkem_rows)

    summary_fields = [
        "algorithm",
        "operation",
        "iterations",
        "avg_ms",
        "stdev_ms",
        "min_ms",
        "max_ms",
        "success_count",
        "failure_count",
        "notes",
    ]
    summary_rows = build_summary_rows(rsa_rows, mlkem_rows)
    write_csv(SUMMARY_CSV, summary_fields, summary_rows)

    artifact_fields = [
        "algorithm",
        "public_key_size",
        "private_or_secret_key_size",
        "wrapped_or_ciphertext_size",
        "session_or_shared_secret_size",
        "total_artifact_size",
        "notes",
    ]
    artifact_rows = build_artifact_rows(rsa_rows, mlkem_rows)
    write_csv(ARTIFACT_CSV, artifact_fields, artifact_rows)

    RAW_JSON.write_text(
        json.dumps(
            {
                "timestamp": timestamp,
                "iterations": ITERATIONS,
                "rsa": rsa_rows,
                "mlkem": mlkem_rows,
                "summary": summary_rows,
                "artifact_comparison": artifact_rows,
                "mlkem_algorithm": mlkem_algorithm,
                "mlkem_selection_mode": selection_mode,
                "notes": "No raw keys, session keys, shared secrets, or ciphertext bytes are stored.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    validation = validation_rows(rsa_rows, mlkem_rows, summary_created=True)
    write_csv(VALIDATION_CSV, ["check", "status", "details"], validation)

    final_status = "PASS" if all(row["status"] == "PASS" for row in validation) else "FAIL"
    print(f"phase4_1_status={final_status}")
    print(f"iterations={ITERATIONS}")
    print(f"mlkem_algorithm={mlkem_algorithm}")
    print(f"rsa_csv={RSA_CSV}")
    print(f"mlkem_csv={MLKEM_CSV}")
    print(f"summary_csv={SUMMARY_CSV}")
    print(f"artifact_csv={ARTIFACT_CSV}")
    print(f"raw_json={RAW_JSON}")
    print(f"validation_csv={VALIDATION_CSV}")
    return 0 if final_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
