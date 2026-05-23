const fs = require("fs");
const path = require("path");
const { ethers } = require("hardhat");

const { createIpfsClient } = require("../lib/ipfsClient");
const { buildVerifierArgsFromProof, loadProofFixture } = require("../lib/proofUtils");
const { ensureRequesterKeyPair } = require("../lib/recordCrypto");
const { submitProofAndEmit } = require("../lib/verifierAccess");
const { retrieveAndDecryptRecord } = require("../lib/secureRecordWorkflow");

const runtimeDir =
  process.env.ZKEHR_RUNTIME_DIR ||
  path.join(process.cwd(), "runtime-data", "secure-records");
const summaryPath =
  process.env.ZKEHR_SECURE_SUMMARY_PATH ||
  path.join(runtimeDir, "latest-secure-workflow-summary.json");
const requesterKeyDir =
  process.env.ZKEHR_REQUESTER_KEY_DIR ||
  path.join(runtimeDir, "requester-demo");

async function main() {
  if (!fs.existsSync(summaryPath)) {
    throw new Error(`Secure workflow summary not found: ${summaryPath}`);
  }

  const summary = JSON.parse(fs.readFileSync(summaryPath, "utf8"));
  const metadata = JSON.parse(fs.readFileSync(summary.metadataPath, "utf8"));
  const requesterKeys = ensureRequesterKeyPair({ keyDir: requesterKeyDir });
  const ipfsClient = createIpfsClient();
  const { proof, publicSignals } = loadProofFixture("proof.json", "public.json");
  const verifierArgs = await buildVerifierArgsFromProof(proof, publicSignals);

  console.log("✅ Verifying proof and replaying secure retrieval...");

  const verifierArtifact = await ethers.getContractFactory("Groth16Verifier");
  const verifier = await verifierArtifact.attach(
    process.env.ZKEHR_VERIFIER_ADDRESS ||
      "0x20e2F410f01733af079A5599c72b03351386F935"
  );

  const accessDecision = await submitProofAndEmit(
    verifier,
    verifierArgs,
    metadata.storage.cid
  );

  if (!accessDecision.accepted) {
    throw new Error("Proof verification was denied; secure retrieval aborted.");
  }

  const decrypted = await retrieveAndDecryptRecord({
    ipfsClient,
    keyReleasePath: summary.keyReleasePath,
    metadataPath: summary.metadataPath,
    outputDir: path.join(runtimeDir, "retrieved-v3"),
    requesterPrivateKeyPem: requesterKeys.privateKeyPem,
  });

  console.log("📥 File decrypted successfully to:", decrypted.decryptedFilePath);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
