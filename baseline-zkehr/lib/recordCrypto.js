const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const AES_ALGORITHM = "aes-256-gcm";
const AES_KEY_BYTES = 32;
const AES_IV_BYTES = 12;
const AES_AUTH_TAG_BYTES = 16;
const REQUESTER_KEY_TYPE = "rsa";
const REQUESTER_KEY_BITS = 2048;

function toBuffer(value, label) {
  if (Buffer.isBuffer(value)) {
    return Buffer.from(value);
  }

  if (typeof value === "string") {
    return Buffer.from(value, "base64");
  }

  throw new TypeError(`${label} must be a Buffer or base64 string.`);
}

function assertRecordKey(recordKey) {
  if (!Buffer.isBuffer(recordKey) || recordKey.length !== AES_KEY_BYTES) {
    throw new Error(
      `Record key must be a ${AES_KEY_BYTES}-byte Buffer for ${AES_ALGORITHM}.`
    );
  }
}

function assertIv(iv) {
  if (!Buffer.isBuffer(iv) || iv.length !== AES_IV_BYTES) {
    throw new Error(`IV must be a ${AES_IV_BYTES}-byte Buffer for ${AES_ALGORITHM}.`);
  }
}

function sha256Hex(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function generateRecordKey() {
  return crypto.randomBytes(AES_KEY_BYTES);
}

function generateIv() {
  return crypto.randomBytes(AES_IV_BYTES);
}

function encryptFileBuffer(plaintextBuffer, recordKey, options = {}) {
  const plaintext = Buffer.isBuffer(plaintextBuffer)
    ? plaintextBuffer
    : Buffer.from(plaintextBuffer);
  const aad = options.aad
    ? Buffer.isBuffer(options.aad)
      ? options.aad
      : Buffer.from(options.aad)
    : null;

  assertRecordKey(recordKey);

  const iv = options.iv ? toBuffer(options.iv, "Encryption IV") : generateIv();
  assertIv(iv);

  const cipher = crypto.createCipheriv(AES_ALGORITHM, recordKey, iv, {
    authTagLength: AES_AUTH_TAG_BYTES,
  });

  if (aad) {
    cipher.setAAD(aad);
  }

  const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  const authTag = cipher.getAuthTag();

  return {
    algorithm: AES_ALGORITHM,
    ciphertext,
    iv,
    authTag,
    plaintextSha256: sha256Hex(plaintext),
    ciphertextSha256: sha256Hex(ciphertext),
  };
}

function decryptFileBuffer(ciphertextBuffer, recordKey, options = {}) {
  const ciphertext = Buffer.isBuffer(ciphertextBuffer)
    ? ciphertextBuffer
    : Buffer.from(ciphertextBuffer);
  const aad = options.aad
    ? Buffer.isBuffer(options.aad)
      ? options.aad
      : Buffer.from(options.aad)
    : null;
  const iv = toBuffer(options.iv, "Decryption IV");
  const authTag = toBuffer(options.authTag, "Authentication tag");

  assertRecordKey(recordKey);
  assertIv(iv);

  if (authTag.length !== AES_AUTH_TAG_BYTES) {
    throw new Error(
      `Authentication tag must be ${AES_AUTH_TAG_BYTES} bytes for ${AES_ALGORITHM}.`
    );
  }

  try {
    const decipher = crypto.createDecipheriv(AES_ALGORITHM, recordKey, iv, {
      authTagLength: AES_AUTH_TAG_BYTES,
    });

    if (aad) {
      decipher.setAAD(aad);
    }

    decipher.setAuthTag(authTag);
    return Buffer.concat([decipher.update(ciphertext), decipher.final()]);
  } catch (error) {
    throw new Error(
      `Failed to decrypt record content: ${error.message || "authentication failed"}`
    );
  }
}

function computeRequesterKeyId(publicKeyPem) {
  return sha256Hex(Buffer.from(publicKeyPem, "utf8"));
}

function generateRequesterKeyPair() {
  const { publicKey, privateKey } = crypto.generateKeyPairSync(REQUESTER_KEY_TYPE, {
    modulusLength: REQUESTER_KEY_BITS,
    publicKeyEncoding: {
      type: "spki",
      format: "pem",
    },
    privateKeyEncoding: {
      type: "pkcs8",
      format: "pem",
    },
  });

  return {
    publicKeyPem: publicKey,
    privateKeyPem: privateKey,
    requesterKeyId: computeRequesterKeyId(publicKey),
  };
}

function ensureRequesterKeyPair(options = {}) {
  const keyDir =
    options.keyDir || path.join(process.cwd(), "runtime-data", "requester-keys");
  const publicKeyPath =
    options.publicKeyPath || path.join(keyDir, "requester.public.pem");
  const privateKeyPath =
    options.privateKeyPath || path.join(keyDir, "requester.private.pem");

  const keysExist =
    fs.existsSync(publicKeyPath) && fs.existsSync(privateKeyPath);

  if (!keysExist || options.forceRegenerate) {
    fs.mkdirSync(path.dirname(publicKeyPath), { recursive: true });
    fs.mkdirSync(path.dirname(privateKeyPath), { recursive: true });

    const keyPair = generateRequesterKeyPair();
    fs.writeFileSync(publicKeyPath, keyPair.publicKeyPem, {
      encoding: "utf8",
      mode: 0o644,
    });
    fs.writeFileSync(privateKeyPath, keyPair.privateKeyPem, {
      encoding: "utf8",
      mode: 0o600,
    });
  }

  const publicKeyPem = fs.readFileSync(publicKeyPath, "utf8");
  const privateKeyPem = fs.readFileSync(privateKeyPath, "utf8");

  return {
    publicKeyPath,
    privateKeyPath,
    publicKeyPem,
    privateKeyPem,
    requesterKeyId: computeRequesterKeyId(publicKeyPem),
  };
}

function wrapRecordKeyForRequester(recordKey, requesterPublicKeyPem) {
  assertRecordKey(recordKey);

  return crypto.publicEncrypt(
    {
      key: requesterPublicKeyPem,
      padding: crypto.constants.RSA_PKCS1_OAEP_PADDING,
      oaepHash: "sha256",
    },
    recordKey
  );
}

function unwrapRecordKeyForRequester(wrappedRecordKey, requesterPrivateKeyPem) {
  const wrappedKey = Buffer.isBuffer(wrappedRecordKey)
    ? wrappedRecordKey
    : Buffer.from(wrappedRecordKey, "base64");

  return crypto.privateDecrypt(
    {
      key: requesterPrivateKeyPem,
      padding: crypto.constants.RSA_PKCS1_OAEP_PADDING,
      oaepHash: "sha256",
    },
    wrappedKey
  );
}

module.exports = {
  AES_ALGORITHM,
  AES_AUTH_TAG_BYTES,
  AES_IV_BYTES,
  AES_KEY_BYTES,
  computeRequesterKeyId,
  decryptFileBuffer,
  encryptFileBuffer,
  ensureRequesterKeyPair,
  generateIv,
  generateRecordKey,
  generateRequesterKeyPair,
  sha256Hex,
  unwrapRecordKeyForRequester,
  wrapRecordKeyForRequester,
};
