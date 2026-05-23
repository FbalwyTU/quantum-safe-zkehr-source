const { expect } = require("chai");
const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");

const {
  decryptFileBuffer,
  encryptFileBuffer,
  ensureRequesterKeyPair,
  generateRecordKey,
  unwrapRecordKeyForRequester,
  wrapRecordKeyForRequester,
} = require("../lib/recordCrypto");

describe("Record Crypto Utilities", function () {
  const fixtureBuffer = fs.readFileSync(
    path.join(process.cwd(), "samples", "synthetic_ehr_record.txt")
  );

  it("encrypts and decrypts a record buffer byte-for-byte", function () {
    const recordKey = generateRecordKey();
    const encrypted = encryptFileBuffer(fixtureBuffer, recordKey);
    const decrypted = decryptFileBuffer(encrypted.ciphertext, recordKey, {
      iv: encrypted.iv,
      authTag: encrypted.authTag,
    });

    expect(Buffer.compare(decrypted, fixtureBuffer)).to.equal(0);
  });

  it("uses unique per-record keys and IVs", function () {
    const firstKey = generateRecordKey();
    const secondKey = generateRecordKey();
    const firstEncrypted = encryptFileBuffer(fixtureBuffer, firstKey);
    const secondEncrypted = encryptFileBuffer(fixtureBuffer, secondKey);

    expect(firstKey.equals(secondKey)).to.equal(false);
    expect(firstEncrypted.iv.equals(secondEncrypted.iv)).to.equal(false);
  });

  it("fails cleanly with a wrong key or tampered ciphertext", function () {
    const recordKey = generateRecordKey();
    const wrongKey = generateRecordKey();
    const encrypted = encryptFileBuffer(fixtureBuffer, recordKey);
    const tamperedCiphertext = Buffer.from(encrypted.ciphertext);
    tamperedCiphertext[0] ^= 0xff;

    expect(() =>
      decryptFileBuffer(encrypted.ciphertext, wrongKey, {
        iv: encrypted.iv,
        authTag: encrypted.authTag,
      })
    ).to.throw(/Failed to decrypt/);

    expect(() =>
      decryptFileBuffer(tamperedCiphertext, recordKey, {
        iv: encrypted.iv,
        authTag: encrypted.authTag,
      })
    ).to.throw(/Failed to decrypt/);
  });

  it("wraps and unwraps the per-record AES key for the requester", function () {
    const tempKeyDir = fs.mkdtempSync(
      path.join(os.tmpdir(), "zk-ehr-requester-keys-")
    );
    const requesterKeys = ensureRequesterKeyPair({
      keyDir: tempKeyDir,
      forceRegenerate: true,
    });
    const recordKey = generateRecordKey();
    const wrappedRecordKey = wrapRecordKeyForRequester(
      recordKey,
      requesterKeys.publicKeyPem
    );
    const unwrappedRecordKey = unwrapRecordKeyForRequester(
      wrappedRecordKey,
      requesterKeys.privateKeyPem
    );

    expect(Buffer.compare(unwrappedRecordKey, recordKey)).to.equal(0);
  });
});
