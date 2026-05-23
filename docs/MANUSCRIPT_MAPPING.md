# Manuscript Mapping

| Manuscript component | Repository location | Main command |
|---|---|---|
| Baseline reproduction | `baseline-zkehr/` | `cd baseline-zkehr && npm test` |
| Groth16/Circom verifier workflow | `baseline-zkehr/circuits`, `baseline-zkehr/contracts`, `baseline-zkehr/implementation_tools/phase2_5` | See `REPRODUCIBILITY.md` Groth16 commands |
| Encrypted record/IPFS workflow | `baseline-zkehr/lib`, `baseline-zkehr/scripts/retrieveRecord.js` | `cd baseline-zkehr && node scripts/retrieveRecord.js` |
| QRNG simulation | `quantum-experiments/qiskit/qrng` | `quantum-experiments/qiskit/.venv/bin/python quantum-experiments/scripts/phase3_1/run_phase3_1_qrng.py` |
| Toy access-policy simulation | `quantum-experiments/qiskit/toy_access_policy` | `quantum-experiments/qiskit/.venv/bin/python quantum-experiments/scripts/phase3_2/run_phase3_2_toy_access_policy.py` |
| IBM Quantum hardware execution | `quantum-experiments/scripts/phase3_4`, `quantum-experiments/scripts/phase3_5` | Configure `IBM_QUANTUM_TOKEN`, then run the selected hardware script |
| RSA-OAEP vs. ML-KEM comparison | `pqc-mlkem-analysis/pqc/comparison` | `pqc-mlkem-analysis/pqc/.venv/bin/python pqc-mlkem-analysis/scripts/phase4_1/run_phase4_1_rsa_vs_mlkem.py` |
| ML-KEM environment validation | `pqc-mlkem-analysis/pqc/smoke_tests`, `pqc-mlkem-analysis/pqc/utils` | `pqc-mlkem-analysis/pqc/.venv/bin/python pqc-mlkem-analysis/pqc/smoke_tests/pqc_kem_smoke_test.py` |
