const fs = require("fs");
const snarkjs = require("snarkjs");

async function buildVerifierArgsFromProof(proof, publicSignals) {
  const callData = await snarkjs.groth16.exportSolidityCallData(proof, publicSignals);
  const argv = JSON.parse("[" + callData + "]");

  return {
    a: argv[0],
    b: argv[1],
    c: argv[2],
    input: argv[3],
    proof,
    publicSignals,
  };
}

async function generateProofAndVerifierArgs(options) {
  const { proof, publicSignals } = await snarkjs.groth16.fullProve(
    options.input,
    options.wasmPath,
    options.zkeyPath
  );

  const verifierArgs = await buildVerifierArgsFromProof(proof, publicSignals);

  return {
    proof,
    publicSignals,
    verifierArgs,
  };
}

function loadProofFixture(proofPath, publicSignalsPath) {
  return {
    proof: JSON.parse(fs.readFileSync(proofPath, "utf8")),
    publicSignals: JSON.parse(fs.readFileSync(publicSignalsPath, "utf8")),
  };
}

module.exports = {
  buildVerifierArgsFromProof,
  generateProofAndVerifierArgs,
  loadProofFixture,
};
