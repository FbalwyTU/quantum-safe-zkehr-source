
const fs = require("fs");
const path = require("path");
const { performance } = require("perf_hooks");
const { JsonRpcProvider, Wallet, Contract, getAddress } = require("ethers");

const provider = new JsonRpcProvider(
  process.env.ZKEHR_RPC_URL || "http://127.0.0.1:8545"
);
const PRIVATE_KEY =
  process.env.ZKEHR_ETH_PRIVATE_KEY ||
  "0xaf84bf2b9192e8cce18aa4fdcb95255a08d2447070c016a1114771695213e498";
const wallet = new Wallet(PRIVATE_KEY, provider);

const verifierAddress = getAddress(
  process.env.ZKEHR_VERIFIER_ADDRESS ||
    "0x20e2f410f01733af079a5599c72b03351386f935"
);
const verifierAbi = require("../artifacts/contracts/Verifier.sol/Groth16Verifier.json").abi;
const verifier = new Contract(verifierAddress, verifierAbi, wallet);

const proof = JSON.parse(fs.readFileSync("proof.json"));
const pub = JSON.parse(fs.readFileSync("public.json"));

const scenarios = [
  { id: "3.a", label: "Corrupted public[0]", mutate: (pub) => {
    pub[0] = (BigInt(pub[0]) + 9999n).toString();
    return pub;
  }},
  { id: "3.b", label: "Missing public[1]", mutate: (pub) => {
    return pub.slice(0, 1); // remove second element
  }},
  { id: "3.c", label: "Empty public input", mutate: (_) => {
    return [];
  }},
  { id: "3.d", label: "Valid public input", mutate: (pub) => {
    return pub; // baseline
  }}
];

const outputPath =
  process.env.ZKEHR_SCENARIO3_PUBLIC_INPUT_LOG_PATH ||
  "evaluation/public_input_results.csv";
const header = "scenario,modification,result,verify_time_ms,timestamp\n";
if (!fs.existsSync(outputPath)) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, header);
}

async function run() {
  for (const s of scenarios) {
    console.log(`\n🔍 Scenario ${s.id}: ${s.label}`);
    const a = [proof.pi_a[0], proof.pi_a[1]];
    const b = [
      [proof.pi_b[0][1], proof.pi_b[0][0]],
      [proof.pi_b[1][1], proof.pi_b[1][0]],
    ];
    const c = [proof.pi_c[0], proof.pi_c[1]];
    const input = s.mutate([...pub]);

    const t0 = performance.now();
    let result = false;
    try {
      result = await verifier.verifyProof(a, b, c, input);
    } catch (err) {
      console.error("⛔️ Error:", err.message);
    }
    const t1 = performance.now();
    const verifyTime = (t1 - t0).toFixed(2);
    const timestamp = new Date().toISOString();
    const outcome = result ? "ACCEPTED ❌" : "REJECTED ✅";

    console.log(`📊 Result: ${outcome} | Time: ${verifyTime} ms`);
    fs.appendFileSync(outputPath, `${s.id},${s.label},${outcome},${verifyTime},${timestamp}\n`);
  }
}

run();
