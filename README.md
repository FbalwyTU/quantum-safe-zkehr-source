# Quantum-Safe ZK-EHR Research Artefacts Repository

This repository contains the source-code and reproducibility artefacts for the manuscript:

"A Quantum-Safe ML-KEM Key-Release Migration and Coexistence Architecture for Groth16-Based ZK-EHR Systems"

The repository supports a reproduced ZK-EHR baseline workflow, Groth16/Circom/Solidity verification workflows, encrypted-record/IPFS workflow code, Qiskit/Aer simulator experiments, IBM Quantum hardware execution scripts, QRNG and toy access-policy circuits, RSA-OAEP vs. ML-KEM-768 migration-analysis code, and non-sensitive reproducibility artefacts.

This is a research prototype for reproducibility. It is not a production clinical system.

## Scope Boundary

- Not a production EHR system.
- Not a clinical deployment.
- Not a production QRNG.
- Not a Groth16 replacement.
- Not a full post-quantum migration.
- IBM Quantum scripts require user credentials, backend availability, queue access, and current calibration conditions.
- No real patient data, production keys, IBM Quantum tokens, or private deployment credentials are included.

## Repository Layout

| Path | Purpose |
|---|---|
| `baseline-zkehr/` | Reproduced ZK-EHR baseline: Circom circuit, Solidity verifier/contracts, Hardhat tests, proof fixtures, AES-GCM/IPFS/RSA-OAEP workflow code, and baseline experiment scripts. |
| `quantum-experiments/` | Qiskit/Aer simulator code, QRNG experiment, toy access-policy circuit, IBM readiness checks, and IBM hardware execution scripts. |
| `pqc-mlkem-analysis/` | Open Quantum Safe/liboqs ML-KEM utilities, KEM smoke test, and RSA-OAEP vs. ML-KEM-768 comparison harness. |
| `scripts/` | Convenience scripts for local environment creation and repository artifact checks. |
| `results/` | Small, non-sensitive, sanitized CSV/JSON summaries useful for validating the manuscript experiments. |
| `docs/` | Manuscript-to-code mapping and packaged result inventory. |

## Requirements

Baseline Node/Hardhat environment:

- Node.js: observed project environment `v22.10.0`.
- npm: observed project environment `10.9.0`.
- Hardhat: `^2.24.3` in `baseline-zkehr/package.json`; observed Phase 2.5 run used `2.28.6`.
- Solidity: `0.8.28` in `baseline-zkehr/hardhat.config.js`.
- Circom: observed project environment `2.2.2`.
- snarkjs: `^0.7.5` in `package.json`; observed Phase 2.5 run used `0.7.6`.
- Kubo/IPFS: observed Phase 2.5 run used `0.18.1`.

Quantum/Qiskit environment:

- Python: observed project environment `3.12.4`.
- Qiskit: `2.4.1`.
- qiskit-aer: `0.17.2`.
- qiskit-ibm-runtime: `0.47.0`.
- numpy: `2.4.5`.
- pandas: `3.0.3`.
- See `quantum-experiments/requirements-qiskit.txt`.

PQC/ML-KEM environment:

- Python: observed project environment `3.12.4`.
- liboqs-python: `0.15.0`.
- oqs: `0.10.2`.
- cmake: `4.3.2`.
- ninja: `1.13.0`.
- cryptography: `48.0.0`.
- See `pqc-mlkem-analysis/requirements-pqc.txt`.

## Installation

Clone and enter the repository:

```bash
git clone https://github.com/FbalwyTU/quantum-safe-zkehr-source.git
cd quantum-safe-zkehr-source
```

Install the baseline Node dependencies:

```bash
cd baseline-zkehr
npm ci
cd ..
```

Create Python environments for the quantum and PQC components:

```bash
scripts/create_python_envs.sh
```

If native `liboqs` build tooling is not already available, ensure `cmake` and `ninja` from the PQC virtual environment are on `PATH` before importing `oqs`.

## Reproducing the Experiments

### 1. Baseline ZK-EHR reproduction

```bash
cd baseline-zkehr
npm test
npx hardhat compile
```

Groth16/Circom workflow, regenerated locally:

```bash
mkdir -p baseline_results/phase2_5/zk_artifacts
circom circuits/access.circom --r1cs --wasm --sym -o baseline_results/phase2_5/zk_artifacts
npx snarkjs r1cs info baseline_results/phase2_5/zk_artifacts/access.r1cs
```

The full trusted-setup, witness, proof, verifier-export, and validation sequence is listed in `REPRODUCIBILITY.md`.

For the encrypted-record/IPFS workflow, run a local Hardhat node and Kubo/IPFS daemon, deploy the verifier, then run:

```bash
node scripts/retrieveRecord.js
```

The public artifact includes a tiny synthetic record fixture at `baseline-zkehr/samples/synthetic_ehr_record.txt`; no real patient data are included.

### 2. Qiskit/Aer simulator experiments

```bash
quantum-experiments/qiskit/.venv/bin/python quantum-experiments/qiskit/smoke_tests/qiskit_smoke_test.py
quantum-experiments/qiskit/.venv/bin/python quantum-experiments/scripts/phase3_1/run_phase3_1_qrng.py
quantum-experiments/qiskit/.venv/bin/python quantum-experiments/scripts/phase3_2/run_phase3_2_toy_access_policy.py
```

Outputs are written under `results/quantum/phase3/`.

### 3. IBM Quantum hardware runs

IBM hardware execution is optional and should be run only with explicit user intent. Configure your own IBM Quantum credentials through an environment variable. Do not commit tokens.

```bash
export IBM_QUANTUM_TOKEN="your-token-here"
quantum-experiments/qiskit/.venv/bin/python quantum-experiments/scripts/phase3_3/check_ibm_readiness.py
```

If readiness succeeds and a suitable backend is visible:

```bash
quantum-experiments/qiskit/.venv/bin/python quantum-experiments/scripts/phase3_4/run_phase3_4_ibm_qrng.py
quantum-experiments/qiskit/.venv/bin/python quantum-experiments/scripts/phase3_5/run_phase3_5_toy_policy_hardware.py
```

Hardware results may vary by backend, calibration date, queue status, shot count, transpilation, and account access.

### 4. RSA-OAEP vs. ML-KEM-768 comparison

```bash
pqc-mlkem-analysis/pqc/.venv/bin/python pqc-mlkem-analysis/scripts/phase4_0/check_pqc_packages.py
pqc-mlkem-analysis/pqc/.venv/bin/python pqc-mlkem-analysis/pqc/utils/list_available_kems.py
pqc-mlkem-analysis/pqc/.venv/bin/python pqc-mlkem-analysis/pqc/smoke_tests/pqc_kem_smoke_test.py
pqc-mlkem-analysis/pqc/.venv/bin/python pqc-mlkem-analysis/scripts/phase4_1/run_phase4_1_rsa_vs_mlkem.py
```

Outputs are written under `results/pqc/phase4/`.

## Expected Outputs

Expected high-level output categories:

- Baseline Hardhat tests pass.
- Groth16 verifier fixture accepts valid proof inputs and rejects tampered inputs.
- Optional Circom/snarkjs commands regenerate local proving artifacts and verify a fresh proof.
- QRNG simulator writes local Aer bit-count and summary CSV/JSON outputs.
- Toy access-policy simulator writes all eight input combinations and expected truth-table outputs.
- IBM hardware scripts write backend, transpilation, count, and summary outputs if rerun with valid credentials.
- ML-KEM smoke test passes when Open Quantum Safe/liboqs is available.
- RSA-OAEP vs. ML-KEM comparison writes latency and artifact-size summaries.

## Mapping to Manuscript

| Manuscript component | Repository location | Main command |
|---|---|---|
| Baseline reproduction | `baseline-zkehr/` | `cd baseline-zkehr && npm test` |
| QRNG simulation | `quantum-experiments/qiskit/qrng` | `quantum-experiments/qiskit/.venv/bin/python quantum-experiments/scripts/phase3_1/run_phase3_1_qrng.py` |
| Toy access-policy simulation | `quantum-experiments/qiskit/toy_access_policy` | `quantum-experiments/qiskit/.venv/bin/python quantum-experiments/scripts/phase3_2/run_phase3_2_toy_access_policy.py` |
| IBM Quantum hardware execution | `quantum-experiments/scripts/phase3_4`, `quantum-experiments/scripts/phase3_5` | `export IBM_QUANTUM_TOKEN=...` then run the selected hardware script |
| RSA-OAEP vs. ML-KEM comparison | `pqc-mlkem-analysis/pqc/comparison` | `pqc-mlkem-analysis/pqc/.venv/bin/python pqc-mlkem-analysis/scripts/phase4_1/run_phase4_1_rsa_vs_mlkem.py` |
| ML-KEM environment validation | `pqc-mlkem-analysis/pqc/smoke_tests` | `pqc-mlkem-analysis/pqc/.venv/bin/python pqc-mlkem-analysis/pqc/smoke_tests/pqc_kem_smoke_test.py` |

## Citation

If you use this repository, please cite the manuscript:

Albalwy, F. A Quantum-Safe ML-KEM Key-Release Migration and Coexistence Architecture for Groth16-Based ZK-EHR Systems. Manuscript submitted to Systems, 2026.

Also cite the baseline paper:

Albalwy, F. Zero-Knowledge-Based Policy Enforcement for Privacy-Preserving Cross-Institutional Health Data Sharing on Blockchain. Systems 2026, 14, 385. https://doi.org/10.3390/systems14040385.

## License

This repository is released under the MIT License. See `LICENSE`.

## Security and Privacy Note

No real patient data are included. No production keys are included. No credentials are included. Generated cryptographic keys in examples are for demonstration only. Users must not commit secrets, `.env` files, IBM Quantum API tokens, wallet files, or private keys.

## Reproducibility Limitations

- IBM Quantum hardware outcomes are backend- and calibration-dependent.
- QPU queues and backend availability vary.
- ML-KEM timings are environment-specific.
- Local trusted-setup artifacts generated by the Circom/snarkjs commands are for reproducibility only.
- The repository supports research reproducibility, not certified security.
