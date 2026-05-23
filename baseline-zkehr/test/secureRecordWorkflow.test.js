const { expect } = require("chai");
const fs = require("fs");
const os = require("os");
const path = require("path");
const hre = require("hardhat");

const { createInMemoryIpfsClient } = require("../lib/ipfsClient");
const { ensureRequesterKeyPair } = require("../lib/recordCrypto");
const { runSecureRecordWorkflow } = require("../lib/secureRecordWorkflow");
const { VALID_PROOF_FIXTURE } = require("./helpers/validProofFixture");

describe("Secure Record Workflow", function () {
  let verifier;

  beforeEach(async function () {
    const Verifier = await hre.ethers.getContractFactory("Groth16Verifier");
    verifier = await Verifier.deploy();
    await verifier.waitForDeployment();
  });

  it("encrypts, uploads, verifies, releases a wrapped key, retrieves, and decrypts", async function () {
    const tempRuntimeDir = fs.mkdtempSync(
      path.join(os.tmpdir(), "zk-ehr-secure-workflow-")
    );
    const requesterKeys = ensureRequesterKeyPair({
      keyDir: path.join(tempRuntimeDir, "requester"),
      forceRegenerate: true,
    });
    const ipfsClient = createInMemoryIpfsClient();
    const sourceFilePath = path.join(
      process.cwd(),
      "samples",
      "synthetic_ehr_record.txt"
    );
    const sourceBuffer = fs.readFileSync(sourceFilePath);

    const result = await runSecureRecordWorkflow({
      ipfsClient,
      requesterKeyId: requesterKeys.requesterKeyId,
      requesterPrivateKeyPem: requesterKeys.privateKeyPem,
      requesterPublicKeyPem: requesterKeys.publicKeyPem,
      runtimeDir: tempRuntimeDir,
      sourceFilePath,
      verifier,
      verifierArgs: VALID_PROOF_FIXTURE,
    });

    const decryptedBuffer = fs.readFileSync(result.decryptedFilePath);
    const metadata = JSON.parse(fs.readFileSync(result.metadataPath, "utf8"));
    const keyRelease = JSON.parse(fs.readFileSync(result.keyReleasePath, "utf8"));

    expect(result.roundTripVerified).to.equal(true);
    expect(Buffer.compare(sourceBuffer, decryptedBuffer)).to.equal(0);
    expect(result.accessDecision.eventName).to.equal("AccessGranted");
    expect(metadata.encryption.algorithm).to.equal("aes-256-gcm");
    expect(keyRelease.wrapAlgorithm).to.equal("rsa-oaep-sha256");
    expect(keyRelease.recordIdHash).to.equal(result.recordIdHash);
  });
});
