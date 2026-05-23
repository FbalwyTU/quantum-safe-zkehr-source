# Results Inventory

The `results/` directory contains small CSV/JSON summaries copied from the source project and sanitized for public release.

Included:

- `results/baseline/`: baseline test, verifier, gas, Groth16, and Phase 2.5 summary outputs.
- `results/quantum/phase3/`: Qiskit package checks, simulator QRNG outputs, toy access-policy simulator outputs, IBM readiness summaries, and redacted IBM hardware summary/count metadata.
- `results/pqc/phase4/`: Open Quantum Safe package checks, available KEM list, ML-KEM smoke test, RSA-OAEP vs. ML-KEM timing summaries, artifact-size comparison, and raw timing rows that do not contain key bytes.

Excluded:

- Command logs and machine-local paths.
- IBM token-environment result files.
- IBM job-state files.
- Private requester keys and PEM files.
- IPFS repository contents and decrypted runtime records.
- Generated ptau, zkey, witness, wasm, and build artifacts.
- Manuscript, figure, Overleaf, and paper-planning files.

Hardware job identifiers in copied IBM result summaries were redacted. Re-running the IBM scripts may create fresh local job-state files; those are ignored by `.gitignore` and should be reviewed before any commit.
