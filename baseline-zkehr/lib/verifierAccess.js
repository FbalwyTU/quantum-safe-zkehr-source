const { keccak256, toUtf8Bytes } = require("ethers");

function computeRecordIdHash(recordLocator) {
  if (typeof recordLocator !== "string" || recordLocator.length === 0) {
    throw new Error("recordLocator must be a non-empty string.");
  }

  return /^0x[0-9a-fA-F]{64}$/.test(recordLocator)
    ? recordLocator
    : keccak256(toUtf8Bytes(recordLocator));
}

async function getContractAddress(contract) {
  if (typeof contract.getAddress === "function") {
    return contract.getAddress();
  }

  if (contract.target) {
    return contract.target;
  }

  if (contract.address) {
    return contract.address;
  }

  throw new Error("Unable to determine verifier contract address.");
}

async function extractAccessDecisionFromReceipt(verifier, receipt) {
  const verifierAddress = (await getContractAddress(verifier)).toLowerCase();

  for (const log of receipt.logs || []) {
    if (!log.address || log.address.toLowerCase() !== verifierAddress) {
      continue;
    }

    try {
      const parsedLog = verifier.interface.parseLog(log);

      if (
        parsedLog &&
        (parsedLog.name === "AccessGranted" || parsedLog.name === "AccessDenied")
      ) {
        return {
          eventName: parsedLog.name,
          accepted: parsedLog.name === "AccessGranted",
          requester: parsedLog.args.requester,
          recordIdHash: parsedLog.args.recordIdHash,
        };
      }
    } catch (error) {
      // Ignore unrelated logs from the same receipt.
    }
  }

  return null;
}

async function submitProofAndEmit(verifier, verifierArgs, recordLocator, options = {}) {
  const recordIdHash = computeRecordIdHash(recordLocator);
  const gasLimit = options.gasLimit || 1_000_000n;
  const tx = await verifier.verifyProofAndEmit(
    verifierArgs.a,
    verifierArgs.b,
    verifierArgs.c,
    verifierArgs.input,
    recordIdHash,
    { gasLimit }
  );
  const receipt = await tx.wait();
  const decision = await extractAccessDecisionFromReceipt(verifier, receipt);

  if (!decision) {
    throw new Error("Verifier transaction completed without an access decision event.");
  }

  return {
    ...decision,
    recordIdHash,
    receipt,
    transactionHash: receipt.hash,
  };
}

module.exports = {
  computeRecordIdHash,
  extractAccessDecisionFromReceipt,
  submitProofAndEmit,
};
