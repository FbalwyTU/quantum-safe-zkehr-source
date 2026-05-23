const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

const { buildVerifierArgsFromProof } = require("../../lib/proofUtils");

const repoRoot = path.resolve(__dirname, "../..");
const outputPath = path.join(
  repoRoot,
  "baseline_results",
  "phase2_5",
  "fresh_verifier_validation.csv"
);
const proofPath = path.join(
  repoRoot,
  "baseline_results",
  "phase2_5",
  "zk_artifacts",
  "proof.generated.json"
);
const publicPath = path.join(
  repoRoot,
  "baseline_results",
  "phase2_5",
  "zk_artifacts",
  "public.generated.json"
);

function csvValue(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function writeCsv(rows) {
  const header = [
    "verifier_contract",
    "proof_source",
    "public_source",
    "status",
    "gas_estimate",
    "notes",
  ];
  const body = [header, ...rows]
    .map((row) => row.map(csvValue).join(","))
    .join("\n");
  fs.writeFileSync(outputPath, body + "\n", "utf8");
}

async function main() {
  const proof = JSON.parse(fs.readFileSync(proofPath, "utf8"));
  const publicSignals = JSON.parse(fs.readFileSync(publicPath, "utf8"));
  const verifierArgs = await buildVerifierArgsFromProof(proof, publicSignals);

  const Verifier = await hre.ethers.getContractFactory("Groth16VerifierPhase25");
  const verifier = await Verifier.deploy();
  await verifier.waitForDeployment();

  let status = "FAIL";
  let gasEstimate = "";
  let notes = "";

  try {
    gasEstimate = (
      await verifier.verifyProof.estimateGas(
        verifierArgs.a,
        verifierArgs.b,
        verifierArgs.c,
        verifierArgs.input
      )
    ).toString();
    const accepted = await verifier.verifyProof(
      verifierArgs.a,
      verifierArgs.b,
      verifierArgs.c,
      verifierArgs.input
    );
    status = accepted ? "PASS" : "FAIL";
    notes = accepted
      ? `Fresh proof accepted by generated verifier at ${await verifier.getAddress()}.`
      : "Fresh proof was rejected by generated verifier.";
  } catch (error) {
    notes = error.message;
  }

  writeCsv([
    [
      "Groth16VerifierPhase25",
      "baseline_results/phase2_5/zk_artifacts/proof.generated.json",
      "baseline_results/phase2_5/zk_artifacts/public.generated.json",
      status,
      gasEstimate,
      notes,
    ],
  ]);

  if (status !== "PASS") {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  writeCsv([
    [
      "Groth16VerifierPhase25",
      "baseline_results/phase2_5/zk_artifacts/proof.generated.json",
      "baseline_results/phase2_5/zk_artifacts/public.generated.json",
      "ERROR",
      "",
      error.message,
    ],
  ]);
  process.exitCode = 1;
});
