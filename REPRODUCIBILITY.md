# Reproducibility Protocol

This protocol gives a clean path for regenerating the main source-code outputs. Commands assume the repository root is the current directory unless a `cd` command is shown.

## 1. Environment Setup

Baseline:

```bash
cd baseline-zkehr
npm ci
npx hardhat compile
cd ..
```

Python environments:

```bash
scripts/create_python_envs.sh
```

Do not place IBM Quantum tokens in files. Use shell environment variables only.

## 2. Baseline Reproduction Checklist

Run baseline tests:

```bash
cd baseline-zkehr
npm test
```

Compile the Circom circuit:

```bash
mkdir -p baseline_results/phase2_5/zk_artifacts
circom circuits/access.circom --r1cs --wasm --sym -o baseline_results/phase2_5/zk_artifacts
npx snarkjs r1cs info baseline_results/phase2_5/zk_artifacts/access.r1cs
```

Regenerate a local Groth16 setup and proof:

```bash
npx snarkjs powersoftau new bn128 12 baseline_results/phase2_5/zk_artifacts/pot12_0000.ptau -v
npx snarkjs powersoftau contribute baseline_results/phase2_5/zk_artifacts/pot12_0000.ptau baseline_results/phase2_5/zk_artifacts/pot12_0001.ptau --name="local reproducibility contribution" -v -e="local_reproducibility_entropy"
npx snarkjs powersoftau prepare phase2 baseline_results/phase2_5/zk_artifacts/pot12_0001.ptau baseline_results/phase2_5/zk_artifacts/pot12_final.ptau -v
npx snarkjs powersoftau verify baseline_results/phase2_5/zk_artifacts/pot12_final.ptau
npx snarkjs groth16 setup baseline_results/phase2_5/zk_artifacts/access.r1cs baseline_results/phase2_5/zk_artifacts/pot12_final.ptau baseline_results/phase2_5/zk_artifacts/access_0000.zkey
npx snarkjs zkey contribute baseline_results/phase2_5/zk_artifacts/access_0000.zkey baseline_results/phase2_5/zk_artifacts/access_final.zkey --name="local zkey contribution" -v -e="local_zkey_entropy"
npx snarkjs zkey export verificationkey baseline_results/phase2_5/zk_artifacts/access_final.zkey baseline_results/phase2_5/zk_artifacts/verification_key.generated.json
npx snarkjs wtns calculate baseline_results/phase2_5/zk_artifacts/access_js/access.wasm circuits/input.json baseline_results/phase2_5/zk_artifacts/witness.wtns
npx snarkjs groth16 prove baseline_results/phase2_5/zk_artifacts/access_final.zkey baseline_results/phase2_5/zk_artifacts/witness.wtns baseline_results/phase2_5/zk_artifacts/proof.generated.json baseline_results/phase2_5/zk_artifacts/public.generated.json
npx snarkjs groth16 verify baseline_results/phase2_5/zk_artifacts/verification_key.generated.json baseline_results/phase2_5/zk_artifacts/public.generated.json baseline_results/phase2_5/zk_artifacts/proof.generated.json
```

Expected verifier output: `OK!`

Optional encrypted-record/IPFS workflow:

```bash
IPFS_PATH="$PWD/baseline_results/phase2_5/ipfs_repo" ipfs init
IPFS_PATH="$PWD/baseline_results/phase2_5/ipfs_repo" ipfs daemon
npx hardhat node
node implementation_tools/phase2_5/deploy_original_verifier_phase2_5.js
export ZKEHR_VERIFIER_ADDRESS="$(node -e 'console.log(require("./baseline_results/phase2_5/deployment.json").verifierAddress)')"
export ZKEHR_ETH_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
node scripts/retrieveRecord.js
```

The final two services should run in separate terminals. The included default source record is synthetic.

## 3. Qiskit/Aer Simulation Checklist

```bash
quantum-experiments/qiskit/.venv/bin/python quantum-experiments/qiskit/smoke_tests/qiskit_smoke_test.py
quantum-experiments/qiskit/.venv/bin/python quantum-experiments/scripts/phase3_1/run_phase3_1_qrng.py
quantum-experiments/qiskit/.venv/bin/python quantum-experiments/scripts/phase3_1/validate_phase3_1_outputs.py
quantum-experiments/qiskit/.venv/bin/python quantum-experiments/scripts/phase3_2/run_phase3_2_toy_access_policy.py
quantum-experiments/qiskit/.venv/bin/python quantum-experiments/scripts/phase3_2/validate_phase3_2_outputs.py
```

Expected outputs:

- `results/quantum/phase3/phase3_1_qrng_simulator_summary.csv`
- `results/quantum/phase3/phase3_1_qrng_counts.json`
- `results/quantum/phase3/phase3_2_toy_access_policy_summary.csv`
- `results/quantum/phase3/phase3_2_toy_access_policy_counts.json`

## 4. IBM Quantum Hardware Rerun Checklist

Do not run these commands unless you intend to submit IBM Quantum hardware jobs.

```bash
export IBM_QUANTUM_TOKEN="your-token-here"
quantum-experiments/qiskit/.venv/bin/python quantum-experiments/scripts/phase3_3/check_ibm_readiness.py
```

If readiness indicates an available backend:

```bash
quantum-experiments/qiskit/.venv/bin/python quantum-experiments/scripts/phase3_4/run_phase3_4_ibm_qrng.py
quantum-experiments/qiskit/.venv/bin/python quantum-experiments/scripts/phase3_5/run_phase3_5_toy_policy_hardware.py
```

Review generated `results/quantum/phase3/*job_state*.json` before committing. `.gitignore` excludes these files because they may contain account-specific job identifiers.

## 5. ML-KEM Validation Checklist

```bash
pqc-mlkem-analysis/pqc/.venv/bin/python pqc-mlkem-analysis/scripts/phase4_0/check_pqc_packages.py
pqc-mlkem-analysis/pqc/.venv/bin/python pqc-mlkem-analysis/pqc/utils/list_available_kems.py
pqc-mlkem-analysis/pqc/.venv/bin/python pqc-mlkem-analysis/pqc/smoke_tests/pqc_kem_smoke_test.py
pqc-mlkem-analysis/pqc/.venv/bin/python pqc-mlkem-analysis/scripts/phase4_0/validate_phase4_0_outputs.py
```

Expected category: `ML-KEM-768` or a documented ML-KEM/Kyber-family fallback is available, and encapsulation/decapsulation produces matching shared secrets.

## 6. RSA-OAEP vs. ML-KEM Comparison Checklist

```bash
pqc-mlkem-analysis/pqc/.venv/bin/python pqc-mlkem-analysis/scripts/phase4_1/run_phase4_1_rsa_vs_mlkem.py
```

Expected outputs:

- `results/pqc/phase4/phase4_1_rsa_baseline.csv`
- `results/pqc/phase4/phase4_1_mlkem_results.csv`
- `results/pqc/phase4/phase4_1_rsa_vs_mlkem_summary.csv`
- `results/pqc/phase4/phase4_1_key_artifact_comparison.csv`

No private keys, AES session keys, shared secrets, or ciphertext bytes should be written to result files.

## 7. Expected Result Categories

- Baseline contract tests and proof-fixture checks.
- Local Groth16 proof generation and verification if snarkjs/Circom are installed.
- Local Qiskit/Aer QRNG summaries.
- Local Qiskit/Aer toy access-policy truth table.
- Optional IBM hardware count summaries.
- OQS KEM enumeration and ML-KEM smoke test.
- RSA-OAEP and ML-KEM timing and artifact-size comparison summaries.

## 8. Troubleshooting

- If `npm ci` fails, check Node/npm compatibility and use `npm install` as a fallback.
- If `circom` is missing, install Circom separately and ensure it is on `PATH`.
- If `snarkjs` commands fail, run them through `npx snarkjs` from `baseline-zkehr/`.
- If IPFS upload fails, confirm a local Kubo daemon is listening at `127.0.0.1:5001`.
- If `qiskit-aer` import fails, recreate `quantum-experiments/qiskit/.venv`.
- If `oqs` import triggers a native build failure, ensure `cmake` and `ninja` are installed and visible on `PATH`.
- If IBM readiness reports no backend, check account access, token validity, backend availability, and queue status.

## 9. Known Limitations

- IBM hardware measurements are not deterministic across time or backends.
- Local simulator experiments do not establish quantum advantage.
- The toy access-policy circuit is not zero-knowledge and does not replace Groth16.
- ML-KEM is evaluated as a local KEM migration harness only; it is not a complete post-quantum EHR migration.
- Timings are environment-specific.
- This artifact supports research reproducibility, not production certification.
