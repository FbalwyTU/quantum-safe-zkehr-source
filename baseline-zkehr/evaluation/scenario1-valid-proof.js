const fs = require("fs");
const path = require("path");
const { performance } = require("perf_hooks");
const { JsonRpcProvider, Wallet, Contract } = require("ethers");

const { createIpfsClient } = require("../lib/ipfsClient");
const {
  generateProofAndVerifierArgs,
} = require("../lib/proofUtils");
const { VALID_DEMO_VERIFIER_ARGS } = require("../lib/demoProofFixture");
const { ensureRequesterKeyPair } = require("../lib/recordCrypto");
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
  process.env.ZKEHR_SCENARIO1_RUNTIME_DIR ||
  path.join(process.cwd(), "runtime-data", "scenario1-secure");
const requesterKeyDir =
  process.env.ZKEHR_REQUESTER_KEY_DIR ||
  path.join(runtimeDir, "requester-demo");
const logPath =
  process.env.ZKEHR_SCENARIO1_LOG_PATH ||
  "evaluation/scenario1_secure_logs.csv";

const header =
  "scenario,proof_time_ms,encrypt_upload_time_ms,verification_time_ms,key_release_time_ms,retrieve_decrypt_time_ms,cid,record_id_hash,verifier_event,round_trip_verified,timestamp";

if (!fs.existsSync(logPath)) {
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  fs.writeFileSync(logPath, header + "\n");
}

(async () => {
  const input = JSON.parse(fs.readFileSync("circuits/input.json", "utf8"));
  const wasmPath = "circuits/access_js/access.wasm";
  const zkeyPath = "access_final.zkey";
  const provingArtifactsAvailable =
    fs.existsSync(wasmPath) && fs.existsSync(zkeyPath);
  const requesterKeys = ensureRequesterKeyPair({ keyDir: requesterKeyDir });
  const iterations = Number(process.env.ZKEHR_SCENARIO1_ITERATIONS || 5);

  for (let i = 1; i <= iterations; i += 1) {
    console.log(`\n🔁 Secure Scenario 1 iteration ${i} of ${iterations}`);

    const proofStart = performance.now();
    let verifierArgs;

    if (provingArtifactsAvailable) {
      ({ verifierArgs } = await generateProofAndVerifierArgs({
        input,
        wasmPath,
        zkeyPath,
      }));
    } else {
      verifierArgs = VALID_DEMO_VERIFIER_ARGS;
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
    const verificationTimeMs = performance.now() - verifyStart;

    if (!accessDecision.accepted) {
      throw new Error(`Iteration ${i} failed verification unexpectedly.`);
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

    const line = [
      "scenario1-valid-proof",
      proofTimeMs.toFixed(2),
      encryptUploadTimeMs.toFixed(2),
      verificationTimeMs.toFixed(2),
      keyReleaseTimeMs.toFixed(2),
      retrieveDecryptTimeMs.toFixed(2),
      prepared.cid,
      prepared.recordIdHash,
      accessDecision.eventName,
      roundTripVerified,
      new Date().toISOString(),
    ].join(",");

    fs.appendFileSync(logPath, line + "\n");

    console.log(
      `✅ Iteration ${i} done | CID: ${prepared.cid} | Event: ${accessDecision.eventName} | Round-trip: ${roundTripVerified}`
    );

    await new Promise((resolve) => setTimeout(resolve, 200));
  }

  console.log(`\n🎯 Secure Scenario 1 completed. Results saved in: ${logPath}`);
})().catch((error) => {
  console.error("❌ Secure Scenario 1 failed:", error.message);
  process.exitCode = 1;
});
