const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

const { VALID_DEMO_VERIFIER_ARGS } = require("../../lib/demoProofFixture");

const repoRoot = path.resolve(__dirname, "../..");
const outputPath = path.join(
  repoRoot,
  "baseline_results",
  "phase2_5",
  "existing_fixture_validation.csv"
);

function csvValue(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function writeCsv(rows) {
  const header = [
    "case_id",
    "verifier",
    "proof_source",
    "expected",
    "actual",
    "status",
    "gas_estimate",
    "notes",
  ];
  const body = [header, ...rows]
    .map((row) => row.map(csvValue).join(","))
    .join("\n");
  fs.writeFileSync(outputPath, body + "\n", "utf8");
}

function mutateProofA0(args) {
  return {
    ...args,
    a: [
      "0x9999999999999999999999999999999999999999999999999999999999999999",
      args.a[1],
    ],
  };
}

function mutatePublicInput(args) {
  return {
    ...args,
    input: ["0x2"],
  };
}

async function accessEventName(verifier, receipt) {
  for (const log of receipt.logs || []) {
    try {
      const parsed = verifier.interface.parseLog(log);
      if (
        parsed &&
        (parsed.name === "AccessGranted" || parsed.name === "AccessDenied")
      ) {
        return parsed.name;
      }
    } catch (error) {
      // Ignore logs that do not belong to this ABI.
    }
  }
  return "";
}

async function estimate(contractMethod, args) {
  try {
    return (await contractMethod.estimateGas(...args)).toString();
  } catch (error) {
    return `ERROR: ${error.message}`;
  }
}

async function main() {
  const Verifier = await hre.ethers.getContractFactory("Groth16Verifier");
  const verifier = await Verifier.deploy();
  await verifier.waitForDeployment();

  const rows = [];
  const valid = VALID_DEMO_VERIFIER_ARGS;
  const tampered = mutateProofA0(valid);
  const corrupted = mutatePublicInput(valid);
  const recordIdHash = hre.ethers.keccak256(
    hre.ethers.toUtf8Bytes("phase2_5-existing-fixture")
  );

  const proofCases = [
    ["valid_verifyProof", valid, true],
    ["tampered_proof", tampered, false],
    ["corrupted_public_input", corrupted, false],
  ];

  for (const [caseId, args, expected] of proofCases) {
    let actual = "";
    let status = "FAIL";
    let notes = "";
    const gasEstimate = await estimate(verifier.verifyProof, [
      args.a,
      args.b,
      args.c,
      args.input,
    ]);
    try {
      actual = await verifier.verifyProof(args.a, args.b, args.c, args.input);
      status = actual === expected ? "PASS" : "FAIL";
    } catch (error) {
      notes = error.message;
      actual = "ERROR";
    }
    rows.push([
      caseId,
      "contracts/Verifier.sol::Groth16Verifier",
      "lib/demoProofFixture.js",
      expected,
      actual,
      status,
      gasEstimate,
      notes,
    ]);
  }

  const eventCases = [
    ["verifyProofAndEmit_valid", valid, "AccessGranted"],
    ["verifyProofAndEmit_invalid", tampered, "AccessDenied"],
  ];

  for (const [caseId, args, expected] of eventCases) {
    let actual = "";
    let status = "FAIL";
    let notes = "";
    const gasEstimate = await estimate(verifier.verifyProofAndEmit, [
      args.a,
      args.b,
      args.c,
      args.input,
      recordIdHash,
    ]);
    try {
      const tx = await verifier.verifyProofAndEmit(
        args.a,
        args.b,
        args.c,
        args.input,
        recordIdHash,
        { gasLimit: 1_000_000n }
      );
      const receipt = await tx.wait();
      actual = await accessEventName(verifier, receipt);
      status = actual === expected ? "PASS" : "FAIL";
      notes = `tx=${receipt.hash}`;
    } catch (error) {
      actual = "ERROR";
      notes = error.message;
    }
    rows.push([
      caseId,
      "contracts/Verifier.sol::Groth16Verifier",
      "lib/demoProofFixture.js",
      expected,
      actual,
      status,
      gasEstimate,
      notes,
    ]);
  }

  writeCsv(rows);

  if (rows.some((row) => row[5] !== "PASS")) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  writeCsv([
    [
      "script_error",
      "contracts/Verifier.sol::Groth16Verifier",
      "lib/demoProofFixture.js",
      "PASS",
      "ERROR",
      "ERROR",
      "",
      error.message,
    ],
  ]);
  process.exitCode = 1;
});
