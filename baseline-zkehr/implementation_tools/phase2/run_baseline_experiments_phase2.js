const fs = require("fs");
const path = require("path");
const { Contract, JsonRpcProvider, Wallet, keccak256, toUtf8Bytes } = require("ethers");
const { performance } = require("perf_hooks");

const { VALID_DEMO_VERIFIER_ARGS } = require("../../lib/demoProofFixture");
const { checkIpfs } = require("./check_ipfs_phase2");

const SHARED_HEADER = [
  "experiment",
  "case_id",
  "status",
  "expected_result",
  "actual_result",
  "passed",
  "latency_ms",
  "gas_estimate",
  "tx_hash",
  "verifier_address",
  "notes",
  "timestamp",
];

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function csvValue(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function writeCsv(filePath, header, rows) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  if (fs.existsSync(filePath)) {
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    fs.copyFileSync(filePath, `${filePath}.bak-${stamp}`);
  }
  const body = [header, ...rows]
    .map((row) => row.map(csvValue).join(","))
    .join("\n");
  fs.writeFileSync(filePath, body + "\n", "utf8");
}

function now() {
  return new Date().toISOString();
}

function latency(start) {
  return (performance.now() - start).toFixed(2);
}

function sharedRow({
  experiment,
  caseId,
  status,
  expected,
  actual,
  passed,
  latencyMs = "",
  gasEstimate = "",
  txHash = "",
  verifierAddress,
  notes = "",
}) {
  return [
    experiment,
    caseId,
    status,
    expected,
    actual,
    passed,
    latencyMs,
    gasEstimate,
    txHash,
    verifierAddress,
    notes,
    now(),
  ];
}

function mutateProofA0(verifierArgs) {
  return {
    ...verifierArgs,
    a: [
      `0x${(BigInt(verifierArgs.a[0]) + 1n).toString(16)}`,
      verifierArgs.a[1],
    ],
  };
}

async function timedCall(fn) {
  const started = performance.now();
  try {
    const value = await fn();
    return {
      ok: true,
      value,
      latencyMs: latency(started),
    };
  } catch (error) {
    return {
      ok: false,
      error,
      latencyMs: latency(started),
    };
  }
}

async function estimateGas(contract, functionName, args) {
  try {
    const gas = await contract[functionName].estimateGas(...args);
    return gas.toString();
  } catch (error) {
    return `ERROR: ${error.message}`;
  }
}

async function sendVerifyProofAndEmit({
  contract,
  provider,
  wallet,
  args,
  recordIdHash,
  nonceState,
}) {
  if (nonceState.next === null) {
    nonceState.next = await provider.getTransactionCount(
      await wallet.getAddress(),
      "pending"
    );
  }
  const nonce = nonceState.next;
  nonceState.next += 1;
  const tx = await contract.verifyProofAndEmit(...args, recordIdHash, {
    gasLimit: 1_000_000n,
    nonce,
  });
  const receipt = await tx.wait();
  return {
    txHash: receipt.hash,
    eventName: findAccessEvent(contract, receipt),
  };
}

function findAccessEvent(contract, receipt) {
  for (const log of receipt.logs || []) {
    try {
      const parsed = contract.interface.parseLog(log);
      if (
        parsed &&
        (parsed.name === "AccessGranted" || parsed.name === "AccessDenied")
      ) {
        return parsed.name;
      }
    } catch (error) {
      // Ignore logs not emitted by the verifier ABI.
    }
  }

  return "";
}

async function runSecureWorkflowIfAvailable({
  config,
  contract,
  verifierArgs,
  outputDir,
  ipfsStatus,
}) {
  const filePath = path.join(outputDir, "secure_workflow_optional.csv");
  const header = [
    "ipfs_available",
    "status",
    "cid",
    "record_id_hash",
    "verification_result",
    "notes",
    "timestamp",
  ];

  if (!config.useIpfs) {
    writeCsv(filePath, header, [
      [
        false,
        "SKIPPED_IPFS_DISABLED",
        "",
        "",
        "",
        "Config useIpfs=false.",
        now(),
      ],
    ]);
    return { status: "SKIPPED_IPFS_DISABLED", passed: true };
  }

  if (ipfsStatus.status !== "AVAILABLE") {
    writeCsv(filePath, header, [
      [
        false,
        "SKIPPED_IPFS_UNAVAILABLE",
        "",
        "",
        "",
        `IPFS API unavailable at ${config.ipfsApiUrl}: ${ipfsStatus.error || ipfsStatus.status}`,
        now(),
      ],
    ]);
    return { status: "SKIPPED_IPFS_UNAVAILABLE", passed: true };
  }

  const { createIpfsClient } = require("../../lib/ipfsClient");
  const { ensureRequesterKeyPair } = require("../../lib/recordCrypto");
  const { runSecureRecordWorkflow } = require("../../lib/secureRecordWorkflow");
  const requesterKeyDir = path.join(outputDir, "secure_workflow_runtime", "requester");
  const runtimeDir = path.join(outputDir, "secure_workflow_runtime");
  const requesterKeys = ensureRequesterKeyPair({
    keyDir: requesterKeyDir,
    forceRegenerate: true,
  });
  const ipfsClient = createIpfsClient(config.ipfsApiUrl);

  try {
    const result = await runSecureRecordWorkflow({
      ipfsClient,
      requesterKeyId: requesterKeys.requesterKeyId,
      requesterPrivateKeyPem: requesterKeys.privateKeyPem,
      requesterPublicKeyPem: requesterKeys.publicKeyPem,
      runtimeDir,
      sourceFilePath: "samples/synthetic_ehr_record.txt",
      verifier: contract,
      verifierArgs,
    });
    writeCsv(filePath, header, [
      [
        true,
        "PASS",
        result.cid,
        result.recordIdHash,
        result.accessDecision.eventName,
        `Round trip verified: ${result.roundTripVerified}`,
        now(),
      ],
    ]);
    return { status: "PASS", passed: true };
  } catch (error) {
    writeCsv(filePath, header, [
      [
        true,
        "FAILED",
        "",
        "",
        "",
        error.message,
        now(),
      ],
    ]);
    return { status: "FAILED", passed: false };
  }
}

async function main() {
  const repoRoot = process.cwd();
  const config = readJson(
    path.join(repoRoot, "implementation_tools", "phase2", "phase2_config.json")
  );
  const outputDir = path.join(repoRoot, config.outputDir);
  const deployment = readJson(path.join(outputDir, "deployment.json"));
  const artifact = readJson(
    path.join(
      repoRoot,
      "artifacts",
      "contracts",
      "Verifier.sol",
      "Groth16Verifier.json"
    )
  );
  const proofFixture = readJson(path.join(repoRoot, "proof.json"));
  const publicSignals = readJson(path.join(repoRoot, "public.json"));
  const provider = new JsonRpcProvider(config.rpcUrl);
  const wallet = new Wallet(config.defaultPrivateKey, provider);
  const verifierAddress = deployment.verifierAddress || config.verifierAddress;
  const contract = new Contract(verifierAddress, artifact.abi, wallet);
  const bytecode = await provider.getCode(verifierAddress);

  if (!bytecode || bytecode === "0x") {
    throw new Error(`No verifier bytecode found at ${verifierAddress}`);
  }

  const valid = VALID_DEMO_VERIFIER_ARGS;
  const tampered = mutateProofA0(valid);
  const recordIdHash = keccak256(toUtf8Bytes("phase2-baseline-record"));
  const invalidRecordIdHash = keccak256(toUtf8Bytes("phase2-invalid-record"));
  const runResults = [];

  const validGas = await estimateGas(contract, "verifyProof", [
    valid.a,
    valid.b,
    valid.c,
    valid.input,
  ]);
  const validCall = await timedCall(() =>
    contract.verifyProof(valid.a, valid.b, valid.c, valid.input)
  );
  const validActual = validCall.ok ? Boolean(validCall.value) : false;
  writeCsv(path.join(outputDir, "verifier_valid_proof.csv"), SHARED_HEADER, [
    sharedRow({
      experiment: "verifier_valid_proof",
      caseId: "valid_fixture",
      status: validCall.ok && validActual ? "PASS" : "FAIL",
      expected: true,
      actual: validCall.ok ? validActual : validCall.error.message,
      passed: validCall.ok && validActual,
      latencyMs: validCall.latencyMs,
      gasEstimate: validGas,
      verifierAddress,
      notes: `Source fixture: lib/demoProofFixture.js; proof.json protocol=${proofFixture.protocol}; publicSignals=${JSON.stringify(publicSignals)}`,
    }),
  ]);
  runResults.push(["verifier_valid_proof", validCall.ok && validActual ? "PASS" : "FAIL"]);

  const tamperCall = await timedCall(() =>
    contract.verifyProof(tampered.a, tampered.b, tampered.c, tampered.input)
  );
  const tamperActual = tamperCall.ok ? Boolean(tamperCall.value) : "ERROR";
  const tamperPassed = tamperCall.ok && tamperActual === false;
  writeCsv(path.join(outputDir, "verifier_tampering.csv"), SHARED_HEADER, [
    sharedRow({
      experiment: "verifier_tampered_proof",
      caseId: "tampered_pA0_plus_one",
      status: tamperPassed ? "PASS" : "FAIL",
      expected: false,
      actual: tamperCall.ok ? tamperActual : tamperCall.error.message,
      passed: tamperPassed,
      latencyMs: tamperCall.latencyMs,
      gasEstimate: await estimateGas(contract, "verifyProof", [
        tampered.a,
        tampered.b,
        tampered.c,
        tampered.input,
      ]),
      verifierAddress,
      notes: "Minimal mutation: pA[0] incremented by one.",
    }),
  ]);
  runResults.push(["verifier_tampering", tamperPassed ? "PASS" : "FAIL"]);

  const corruptInput = ["0x2"];
  const corruptCall = await timedCall(() =>
    contract.verifyProof(valid.a, valid.b, valid.c, corruptInput)
  );
  const corruptActual = corruptCall.ok ? Boolean(corruptCall.value) : "ERROR";
  const corruptPassed = corruptCall.ok && corruptActual === false;
  writeCsv(
    path.join(outputDir, "verifier_corrupted_public_input.csv"),
    SHARED_HEADER,
    [
      sharedRow({
        experiment: "verifier_corrupted_public_input",
        caseId: "public_signal_0x2",
        status: corruptPassed ? "PASS" : "FAIL",
        expected: false,
        actual: corruptCall.ok ? corruptActual : corruptCall.error.message,
        passed: corruptPassed,
        latencyMs: corruptCall.latencyMs,
        gasEstimate: await estimateGas(contract, "verifyProof", [
          valid.a,
          valid.b,
          valid.c,
          corruptInput,
        ]),
        verifierAddress,
        notes: "Valid proof fixture reused with wrong public signal.",
      }),
    ]
  );
  runResults.push([
    "verifier_corrupted_public_input",
    corruptPassed ? "PASS" : "FAIL",
  ]);

  const eventRows = [];
  const nonceState = { next: null };
  const validEventGas = await estimateGas(contract, "verifyProofAndEmit", [
    valid.a,
    valid.b,
    valid.c,
    valid.input,
    recordIdHash,
  ]);
  const validEvent = await timedCall(async () => {
    return sendVerifyProofAndEmit({
      contract,
      provider,
      wallet,
      args: [valid.a, valid.b, valid.c, valid.input],
      recordIdHash,
      nonceState,
    });
  });
  const validEventPassed =
    validEvent.ok && validEvent.value.eventName === "AccessGranted";
  eventRows.push(
    sharedRow({
      experiment: "verifyProofAndEmit_event",
      caseId: "valid_access_granted",
      status: validEventPassed ? "PASS" : "FAIL",
      expected: "AccessGranted",
      actual: validEvent.ok ? validEvent.value.eventName : validEvent.error.message,
      passed: validEventPassed,
      latencyMs: validEvent.latencyMs,
      gasEstimate: validEventGas,
      txHash: validEvent.ok ? validEvent.value.txHash : "",
      verifierAddress,
      notes: "Valid proof should emit AccessGranted.",
    })
  );

  const invalidEventGas = await estimateGas(contract, "verifyProofAndEmit", [
    tampered.a,
    tampered.b,
    tampered.c,
    tampered.input,
    invalidRecordIdHash,
  ]);
  const invalidEvent = await timedCall(async () => {
    return sendVerifyProofAndEmit({
      contract,
      provider,
      wallet,
      args: [tampered.a, tampered.b, tampered.c, tampered.input],
      recordIdHash: invalidRecordIdHash,
      nonceState,
    });
  });
  const invalidEventPassed =
    invalidEvent.ok && invalidEvent.value.eventName === "AccessDenied";
  eventRows.push(
    sharedRow({
      experiment: "verifyProofAndEmit_event",
      caseId: "tampered_access_denied",
      status: invalidEventPassed ? "PASS" : "FAIL",
      expected: "AccessDenied",
      actual: invalidEvent.ok
        ? invalidEvent.value.eventName
        : invalidEvent.error.message,
      passed: invalidEventPassed,
      latencyMs: invalidEvent.latencyMs,
      gasEstimate: invalidEventGas,
      txHash: invalidEvent.ok ? invalidEvent.value.txHash : "",
      verifierAddress,
      notes: "Tampered proof should emit AccessDenied.",
    })
  );
  writeCsv(path.join(outputDir, "verifier_events.csv"), SHARED_HEADER, eventRows);
  runResults.push([
    "verifier_events",
    validEventPassed && invalidEventPassed ? "PASS" : "FAIL",
  ]);

  const batchSize = Number(config.iterations.concurrentBatchSize || 5);
  const concurrentRows = await Promise.all(
    Array.from({ length: batchSize }, async (_, index) => {
      const call = await timedCall(() =>
        contract.verifyProof(valid.a, valid.b, valid.c, valid.input)
      );
      const actual = call.ok ? Boolean(call.value) : false;
      return [
        "concurrent_verification_small",
        batchSize,
        index + 1,
        call.latencyMs,
        call.ok && actual ? "PASS" : "FAIL",
        call.ok && actual,
        call.ok ? "Valid proof accepted." : call.error.message,
        verifierAddress,
        now(),
      ];
    })
  );
  writeCsv(
    path.join(outputDir, "concurrent_verification_small.csv"),
    [
      "experiment",
      "batch_size",
      "request_index",
      "latency_ms",
      "status",
      "passed",
      "notes",
      "verifier_address",
      "timestamp",
    ],
    concurrentRows
  );
  runResults.push([
    "concurrent_verification_small",
    concurrentRows.every((row) => row[5] === true) ? "PASS" : "FAIL",
  ]);

  const ipfsStatus = await checkIpfs(config.ipfsApiUrl);
  fs.writeFileSync(
    path.join(outputDir, "ipfs_status.json"),
    JSON.stringify(ipfsStatus, null, 2) + "\n",
    "utf8"
  );
  const secureWorkflow = await runSecureWorkflowIfAvailable({
    config,
    contract,
    verifierArgs: valid,
    outputDir,
    ipfsStatus,
  });
  runResults.push(["secure_workflow_optional", secureWorkflow.status]);

  writeCsv(
    path.join(outputDir, "phase2_summary.csv"),
    ["category", "artifact_path", "status", "description", "timestamp"],
    [
      [
        "deployment",
        path.join(config.outputDir, "deployment.json"),
        "PASSED",
        `Verifier deployed at ${verifierAddress} on chain ${deployment.chainId}.`,
        now(),
      ],
      [
        "ipfs_availability",
        path.join(config.outputDir, "ipfs_status.json"),
        ipfsStatus.status,
        ipfsStatus.status === "AVAILABLE"
          ? `IPFS version ${ipfsStatus.version}`
          : `IPFS unavailable at ${config.ipfsApiUrl}`,
        now(),
      ],
      ...runResults.map(([name, status]) => [
        "experiment",
        path.join(config.outputDir, `${name}.csv`),
        status,
        `Phase 2 ${name} result.`,
        now(),
      ]),
    ]
  );

  console.log(
    JSON.stringify(
      {
        verifierAddress,
        deployment,
        ipfsStatus,
        runResults,
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
