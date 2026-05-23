const fs = require("fs");
const path = require("path");

const {
  AES_ALGORITHM,
  decryptFileBuffer,
  encryptFileBuffer,
  generateRecordKey,
  sha256Hex,
  wrapRecordKeyForRequester,
  unwrapRecordKeyForRequester,
} = require("./recordCrypto");
const { downloadBufferFromIpfs, uploadBufferToIpfs } = require("./ipfsClient");
const { computeRecordIdHash, submitProofAndEmit } = require("./verifierAccess");

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
  return dirPath;
}

function buildRuntimeDirectories(baseDir) {
  return {
    baseDir,
    metadataDir: ensureDir(path.join(baseDir, "record-metadata")),
    keyReleaseDir: ensureDir(path.join(baseDir, "key-releases")),
    decryptedDir: ensureDir(path.join(baseDir, "decrypted-records")),
  };
}

function buildRecordLabel(sourcePath, cid) {
  const sourceName = path.basename(sourcePath, path.extname(sourcePath));
  return `${sourceName}-${cid.slice(0, 16)}`;
}

async function prepareEncryptedRecord(options) {
  const sourceFilePath = options.sourceFilePath;
  const ipfsClient = options.ipfsClient;
  const directories = buildRuntimeDirectories(
    options.runtimeDir || path.join(process.cwd(), "runtime-data", "secure-records")
  );
  const requesterKeyId = options.requesterKeyId;

  const plaintextBuffer = fs.readFileSync(sourceFilePath);
  const recordKey = generateRecordKey();
  const encryptedRecord = encryptFileBuffer(plaintextBuffer, recordKey);
  const cid = await uploadBufferToIpfs(ipfsClient, encryptedRecord.ciphertext);
  const recordIdHash = computeRecordIdHash(cid);
  const recordLabel = buildRecordLabel(sourceFilePath, cid);
  const metadata = {
    schemaVersion: 1,
    recordLabel,
    sourceFileName: path.basename(sourceFilePath),
    sourceFileSha256: encryptedRecord.plaintextSha256,
    encryption: {
      algorithm: AES_ALGORITHM,
      ivBase64: encryptedRecord.iv.toString("base64"),
      authTagBase64: encryptedRecord.authTag.toString("base64"),
      ciphertextSha256: encryptedRecord.ciphertextSha256,
      ciphertextBytes: encryptedRecord.ciphertext.length,
    },
    storage: {
      cid,
      recordIdHash,
    },
    requesterKeyId,
    createdAt: new Date().toISOString(),
  };
  const metadataPath = path.join(directories.metadataDir, `${recordLabel}.json`);

  fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2) + "\n", "utf8");

  return {
    cid,
    directories,
    encryptedRecord,
    metadata,
    metadataPath,
    plaintextBuffer,
    recordIdHash,
    recordKey,
    sourceFilePath,
  };
}

function createKeyReleaseArtifact(options) {
  const wrappedRecordKey = wrapRecordKeyForRequester(
    options.recordKey,
    options.requesterPublicKeyPem
  );
  const artifact = {
    schemaVersion: 1,
    recordIdHash: options.recordIdHash,
    cid: options.cid,
    requesterKeyId: options.requesterKeyId,
    wrappedRecordKeyBase64: wrappedRecordKey.toString("base64"),
    wrapAlgorithm: "rsa-oaep-sha256",
    verificationTxHash: options.verificationTxHash,
    verifierEvent: options.verifierEvent,
    releasedAt: new Date().toISOString(),
  };
  const keyReleasePath = path.join(
    options.keyReleaseDir,
    `${options.recordLabel}-release.json`
  );

  fs.writeFileSync(keyReleasePath, JSON.stringify(artifact, null, 2) + "\n", "utf8");

  return {
    artifact,
    keyReleasePath,
  };
}

async function retrieveAndDecryptRecord(options) {
  const metadata = JSON.parse(fs.readFileSync(options.metadataPath, "utf8"));
  const keyRelease = JSON.parse(fs.readFileSync(options.keyReleasePath, "utf8"));
  const encryptedBuffer = await downloadBufferFromIpfs(
    options.ipfsClient,
    metadata.storage.cid
  );

  if (sha256Hex(encryptedBuffer) !== metadata.encryption.ciphertextSha256) {
    throw new Error("Encrypted payload hash mismatch after IPFS retrieval.");
  }

  const recordKey = unwrapRecordKeyForRequester(
    keyRelease.wrappedRecordKeyBase64,
    options.requesterPrivateKeyPem
  );
  const plaintextBuffer = decryptFileBuffer(encryptedBuffer, recordKey, {
    iv: metadata.encryption.ivBase64,
    authTag: metadata.encryption.authTagBase64,
  });

  if (sha256Hex(plaintextBuffer) !== metadata.sourceFileSha256) {
    throw new Error("Decrypted payload does not match the original record digest.");
  }

  const decryptedFileName =
    options.outputFileName || `decrypted-${metadata.sourceFileName}`;
  const decryptedFilePath = path.join(options.outputDir, decryptedFileName);
  fs.writeFileSync(decryptedFilePath, plaintextBuffer);

  return {
    decryptedBuffer: plaintextBuffer,
    decryptedFilePath,
    metadata,
    keyRelease,
  };
}

async function runSecureRecordWorkflow(options) {
  const prepared = await prepareEncryptedRecord(options);
  const accessDecision = await submitProofAndEmit(
    options.verifier,
    options.verifierArgs,
    prepared.cid
  );

  if (!accessDecision.accepted) {
    throw new Error(
      `Proof verification was denied for record ${prepared.cid}; no key release was produced.`
    );
  }

  const keyRelease = createKeyReleaseArtifact({
    cid: prepared.cid,
    keyReleaseDir: prepared.directories.keyReleaseDir,
    recordIdHash: prepared.recordIdHash,
    recordKey: prepared.recordKey,
    recordLabel: prepared.metadata.recordLabel,
    requesterKeyId: options.requesterKeyId,
    requesterPublicKeyPem: options.requesterPublicKeyPem,
    verificationTxHash: accessDecision.transactionHash,
    verifierEvent: accessDecision.eventName,
  });

  const decrypted = await retrieveAndDecryptRecord({
    ipfsClient: options.ipfsClient,
    keyReleasePath: keyRelease.keyReleasePath,
    metadataPath: prepared.metadataPath,
    outputDir: prepared.directories.decryptedDir,
    requesterPrivateKeyPem: options.requesterPrivateKeyPem,
  });

  const roundTripVerified =
    Buffer.compare(prepared.plaintextBuffer, decrypted.decryptedBuffer) === 0;

  if (!roundTripVerified) {
    throw new Error("Recovered file does not match the original source record.");
  }

  return {
    accessDecision,
    cid: prepared.cid,
    decryptedFilePath: decrypted.decryptedFilePath,
    keyReleasePath: keyRelease.keyReleasePath,
    metadataPath: prepared.metadataPath,
    recordIdHash: prepared.recordIdHash,
    roundTripVerified,
  };
}

module.exports = {
  buildRuntimeDirectories,
  createKeyReleaseArtifact,
  prepareEncryptedRecord,
  retrieveAndDecryptRecord,
  runSecureRecordWorkflow,
};
