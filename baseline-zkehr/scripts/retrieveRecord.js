const fs = require("fs");
const path = require("path");
const { performance } = require("perf_hooks");
const { JsonRpcProvider, Wallet, Contract } = require("ethers");

const { createIpfsClient } = require("../lib/ipfsClient");
const {
  generateProofAndVerifierArgs,
} = require("../lib/proofUtils");
const { VALID_DEMO_VERIFIER_ARGS } = require("../lib/demoProofFixture");
const {
  ensureRequesterKeyPair,
  sha256Hex,
} = require("../lib/recordCrypto");
const { submitProofAndEmit } = require("../lib/verifierAccess");
const {
  createKeyReleaseArtifact,
  prepareEncryptedRecord,
  retrieveAndDecryptRecord,
} = require("../lib/secureRecordWorkflow");

const DEV_PRIVATE_KEY =
  process.env.ZKEHR_ETH_PRIVATE_KEY ||
  "0xaf84bf2b9192e8cce18aa4fdcb95255a08d2447070c016a1114771695213e498"; // Local Ganache key only.
const verifierAddress =
  process.env.ZKEHR_VERIFIER_ADDRESS ||
  "0x20e2F410f01733af079A5599c72b03351386F935";
const provider = new JsonRpcProvider(
  process.env.ZKEHR_RPC_URL || "http://localhost:8545"
);
const wallet = new Wallet(DEV_PRIVATE_KEY, provider);
const verifierAbi =
  require("../artifacts/contracts/Verifier.sol/Groth16Verifier.json").abi;
const verifier = new Contract(verifierAddress, verifierAbi, wallet);
const ipfsClient = createIpfsClient();

const sourceFilePath =
  process.env.ZKEHR_SOURCE_RECORD_PATH || "samples/synthetic_ehr_record.txt";
const runtimeDir =
  process.env.ZKEHR_RUNTIME_DIR ||
  path.join(process.cwd(), "runtime-data", "secure-records");
const requesterKeyDir =
  process.env.ZKEHR_REQUESTER_KEY_DIR ||
  path.join(runtimeDir, "requester-demo");

async function main() {
  if (!fs.existsSync(sourceFilePath)) {
    throw new Error(`Source record not found: ${sourceFilePath}`);
  }

  const requesterKeys = ensureRequesterKeyPair({ keyDir: requesterKeyDir });
  const input = JSON.parse(fs.readFileSync("circuits/input.json", "utf8"));
  const wasmPath = "circuits/access_js/access.wasm";
  const zkeyPath = "access_final.zkey";
  const provingArtifactsAvailable =
    fs.existsSync(wasmPath) && fs.existsSync(zkeyPath);

  console.log("🔐 Starting secure ZK-EHR record workflow...");
  console.log(`📄 Source record: ${sourceFilePath}`);
  console.log(`🗂️ Runtime directory: ${runtimeDir}`);

  const proofStart = performance.now();
  let verifierArgs;

  if (provingArtifactsAvailable) {
    ({ verifierArgs } = await generateProofAndVerifierArgs({
      input,
      wasmPath,
      zkeyPath,
    }));
    console.log("🧮 Proof generated from local circuit artifacts.");
  } else {
    verifierArgs = VALID_DEMO_VERIFIER_ARGS;
    console.log(
      "🧮 Local proving artifacts are missing; using the repository's known-good verifier fixture."
    );
  }

  const proofTimeMs = performance.now() - proofStart;

  const encryptUploadStart = performance.now();
  const prepared = await prepareEncryptedRecord({
    ipfsClient,
    requesterKeyId: requesterKeys.requesterKeyId,
    runtimeDir,
    sourceFilePath,
  });
  const encryptUploadTimeMs = performance.now() - encryptUploadStart;

  const verifyStart = performance.now();
  const accessDecision = await submitProofAndEmit(
    verifier,
    verifierArgs,
    prepared.cid
  );
  const verifyTimeMs = performance.now() - verifyStart;

  if (!accessDecision.accepted) {
    throw new Error("Proof verification was denied; key release aborted.");
  }

  const keyReleaseStart = performance.now();
  const keyRelease = createKeyReleaseArtifact({
    cid: prepared.cid,
    keyReleaseDir: prepared.directories.keyReleaseDir,
    recordIdHash: prepared.recordIdHash,
    recordKey: prepared.recordKey,
    recordLabel: prepared.metadata.recordLabel,
    requesterKeyId: requesterKeys.requesterKeyId,
    requesterPublicKeyPem: requesterKeys.publicKeyPem,
    verificationTxHash: accessDecision.transactionHash,
    verifierEvent: accessDecision.eventName,
  });
  const keyReleaseTimeMs = performance.now() - keyReleaseStart;

  const retrieveDecryptStart = performance.now();
  const decrypted = await retrieveAndDecryptRecord({
    ipfsClient,
    keyReleasePath: keyRelease.keyReleasePath,
    metadataPath: prepared.metadataPath,
    outputDir: prepared.directories.decryptedDir,
    requesterPrivateKeyPem: requesterKeys.privateKeyPem,
  });
  const retrieveDecryptTimeMs = performance.now() - retrieveDecryptStart;

  const roundTripVerified =
    Buffer.compare(prepared.plaintextBuffer, decrypted.decryptedBuffer) === 0;

  if (!roundTripVerified) {
    throw new Error("Round-trip integrity check failed after decryption.");
  }

  const summary = {
    sourceFilePath,
    sourceFileSha256: sha256Hex(prepared.plaintextBuffer),
    encryptedCid: prepared.cid,
    encryptedCiphertextSha256: prepared.metadata.encryption.ciphertextSha256,
    metadataPath: prepared.metadataPath,
    keyReleasePath: keyRelease.keyReleasePath,
    decryptedFilePath: decrypted.decryptedFilePath,
    proofTimeMs: Number(proofTimeMs.toFixed(2)),
    encryptUploadTimeMs: Number(encryptUploadTimeMs.toFixed(2)),
    verifyTimeMs: Number(verifyTimeMs.toFixed(2)),
    keyReleaseTimeMs: Number(keyReleaseTimeMs.toFixed(2)),
    retrieveDecryptTimeMs: Number(retrieveDecryptTimeMs.toFixed(2)),
    verifierEvent: accessDecision.eventName,
    verificationTxHash: accessDecision.transactionHash,
    roundTripVerified,
    completedAt: new Date().toISOString(),
  };

  const summaryPath = path.join(runtimeDir, "latest-secure-workflow-summary.json");
  fs.mkdirSync(path.dirname(summaryPath), { recursive: true });
  fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2) + "\n", "utf8");

  console.log("✅ Secure workflow completed successfully.");
  console.log(`   CID: ${summary.encryptedCid}`);
  console.log(`   Event: ${summary.verifierEvent}`);
  console.log(`   Metadata: ${summary.metadataPath}`);
  console.log(`   Key release: ${summary.keyReleasePath}`);
  console.log(`   Decrypted file: ${summary.decryptedFilePath}`);
  console.log(
    `   Timings (ms) => proof: ${summary.proofTimeMs}, encrypt+upload: ${summary.encryptUploadTimeMs}, verify: ${summary.verifyTimeMs}, release: ${summary.keyReleaseTimeMs}, retrieve+decrypt: ${summary.retrieveDecryptTimeMs}`
  );
}

main().catch((error) => {
  console.error("❌ Secure workflow failed:", error.message);
  process.exitCode = 1;
});
