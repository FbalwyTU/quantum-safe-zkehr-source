const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

const { createIpfsClient } = require("../lib/ipfsClient");
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

  console.log("✅ Verifying proof using patched fixture...");

  const verifierFactory = await hre.ethers.getContractFactory("Groth16Verifier");
  const verifier = await verifierFactory.attach(
    process.env.ZKEHR_VERIFIER_ADDRESS ||
      "0x20e2F410f01733af079A5599c72b03351386F935"
  );

  const verifierArgs = {
    a: [
      "0x1eceb4dd7f1dd45cefd8df0a0dc7f031eb13a0e0fdc110a4306d30615b94e515",
      "0x1ea898c3bf2eae85a2fa979f4971a94f3b5fa5f0828cfbb99f15b6d542365e64",
    ],
    b: [
      [
        "0x03c1c6698fde5dad6b5ba77454f247f3059a2323ab4422dcc6d0812bbb54b814",
        "0x1d54d56c6c8018bfe985a4e0965329b534ca90045684ec575fa038e0a8330de8",
      ],
      [
        "0x2f17ec5862af067532b0a64153917899d50e5772bee2e2e1f4acd7c2a16e9fc1",
        "0x2f82c59dbc18208d1b53d30d0ef6c47cfd8b1cee168959bc0737bc978f697508",
      ],
    ],
    c: [
      "0x17d5519c54308746cadd792f8a5680284e225b70a298974048ef932bbbd8fdfe",
      "0x2f41d450885994a22d3fd9582ca9662a4be91eb9387dcff7faa016b1eb1da27b",
    ],
    input: ["0x1"],
  };

  const accessDecision = await submitProofAndEmit(
    verifier,
    verifierArgs,
    metadata.storage.cid
  );

  if (!accessDecision.accepted) {
    throw new Error("Proof verification failed.");
  }

  const decrypted = await retrieveAndDecryptRecord({
    ipfsClient,
    keyReleasePath: summary.keyReleasePath,
    metadataPath: summary.metadataPath,
    outputDir: path.join(runtimeDir, "retrieved-patched"),
    requesterPrivateKeyPem: requesterKeys.privateKeyPem,
  });

  console.log("✅ File decrypted to:", decrypted.decryptedFilePath);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
