const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

const { VALID_DEMO_VERIFIER_ARGS } = require("../../lib/demoProofFixture");

function csvValue(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function writeCsv(filePath, header, rows) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const body = [header, ...rows]
    .map((row) => row.map(csvValue).join(","))
    .join("\n");
  fs.writeFileSync(filePath, body + "\n", "utf8");
}

async function main() {
  const Verifier = await hre.ethers.getContractFactory("Groth16Verifier");
  const verifier = await Verifier.deploy();
  await verifier.waitForDeployment();
  const verifierAddress = await verifier.getAddress();

  const valid = VALID_DEMO_VERIFIER_ARGS;
  const zeroProof = {
    a: ["0x0", "0x0"],
    b: [
      ["0x0", "0x0"],
      ["0x0", "0x0"],
    ],
    c: ["0x0", "0x0"],
    input: ["0x0"],
  };
  const tampered = {
    ...valid,
    a: [
      "0x9999999999999999999999999999999999999999999999999999999999999999",
      valid.a[1],
    ],
  };
  const recordIdHash = hre.ethers.keccak256(
    hre.ethers.toUtf8Bytes("phase1-baseline-record")
  );

  const validAccepted = await verifier.verifyProof(
    valid.a,
    valid.b,
    valid.c,
    valid.input
  );
  const zeroRejected = !(await verifier.verifyProof(
    zeroProof.a,
    zeroProof.b,
    zeroProof.c,
    zeroProof.input
  ));
  const tamperedRejected = !(await verifier.verifyProof(
    tampered.a,
    tampered.b,
    tampered.c,
    tampered.input
  ));
  const invalidPublicRejected = !(await verifier.verifyProof(
    valid.a,
    valid.b,
    valid.c,
    ["0x2"]
  ));

  const gasRows = [];
  try {
    const gas = await verifier.verifyProof.estimateGas(
      valid.a,
      valid.b,
      valid.c,
      valid.input
    );
    gasRows.push([
      "Groth16Verifier",
      "verifyProof",
      gas.toString(),
      "OK",
      "Estimated against valid demo proof fixture on in-process Hardhat network.",
    ]);
  } catch (error) {
    gasRows.push([
      "Groth16Verifier",
      "verifyProof",
      "",
      "FAILED",
      error.message,
    ]);
  }

  try {
    const gas = await verifier.verifyProofAndEmit.estimateGas(
      valid.a,
      valid.b,
      valid.c,
      valid.input,
      recordIdHash
    );
    gasRows.push([
      "Groth16Verifier",
      "verifyProofAndEmit",
      gas.toString(),
      "OK",
      "Estimated against valid demo proof fixture on in-process Hardhat network.",
    ]);
  } catch (error) {
    gasRows.push([
      "Groth16Verifier",
      "verifyProofAndEmit",
      "",
      "FAILED",
      error.message,
    ]);
  }

  writeCsv(
    path.join(process.cwd(), "baseline_results", "baseline_gas_results.csv"),
    ["contract", "function", "gas_estimate", "status", "notes"],
    gasRows
  );

  writeCsv(
    path.join(
      process.cwd(),
      "baseline_results",
      "baseline_proof_fixture_validation.csv"
    ),
    ["check", "status", "expected", "actual", "source", "notes"],
    [
      [
        "valid_fixture_acceptance",
        validAccepted ? "PASS" : "FAIL",
        "true",
        String(validAccepted),
        "lib/demoProofFixture.js",
        `Verifier deployed at ${verifierAddress}.`,
      ],
      [
        "zero_proof_rejection",
        zeroRejected ? "PASS" : "FAIL",
        "true",
        String(zeroRejected),
        "implementation_tools/phase1/phase1_verify_and_gas.js",
        "All-zero proof should be rejected.",
      ],
      [
        "tampered_proof_rejection",
        tamperedRejected ? "PASS" : "FAIL",
        "true",
        String(tamperedRejected),
        "lib/demoProofFixture.js",
        "Tampered pA[0] should be rejected.",
      ],
      [
        "invalid_public_input_rejection",
        invalidPublicRejected ? "PASS" : "FAIL",
        "true",
        String(invalidPublicRejected),
        "lib/demoProofFixture.js",
        "Valid proof with public input 0x2 should be rejected.",
      ],
    ]
  );

  console.log(
    JSON.stringify(
      {
        verifierAddress,
        validAccepted,
        zeroRejected,
        tamperedRejected,
        invalidPublicRejected,
        gasRows,
      },
      null,
      2
    )
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
