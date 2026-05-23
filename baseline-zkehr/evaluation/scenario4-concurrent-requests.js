
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

const a = [proof.pi_a[0], proof.pi_a[1]];
const b = [
  [proof.pi_b[0][1], proof.pi_b[0][0]],
  [proof.pi_b[1][1], proof.pi_b[1][0]],
];
const c = [proof.pi_c[0], proof.pi_c[1]];
const input = pub;

const outputPath =
  process.env.ZKEHR_SCENARIO4_CONCURRENT_LOG_PATH ||
  "evaluation/concurrent_results.csv";
const header = "request_id,result,verify_time_ms,timestamp\n";
if (!fs.existsSync(outputPath)) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, header);
}

async function verifyInstance(id) {
  const t0 = performance.now();
  let result = false;
  try {
    result = await verifier.verifyProof(a, b, c, input);
  } catch (err) {
    console.error(`⛔️ [${id}] Error:`, err.message);
  }
  const t1 = performance.now();
  const verifyTime = (t1 - t0).toFixed(2);
  const timestamp = new Date().toISOString();
  const outcome = result ? "ACCEPTED ✅" : "REJECTED ❌";
  console.log(`🔁 Request ${id}: ${outcome} | Time: ${verifyTime} ms`);
  fs.appendFileSync(outputPath, `${id},${outcome},${verifyTime},${timestamp}\n`);
}

async function runConcurrentVerifications() {
  const concurrentTasks = [];
  const totalRequests = Number(process.env.ZKEHR_SCENARIO4_TOTAL_REQUESTS || 50);
  for (let i = 1; i <= totalRequests; i++) {
    concurrentTasks.push(verifyInstance(i));
  }
  await Promise.all(concurrentTasks);
  console.log("\n📊 All results saved to:", outputPath);
}

runConcurrentVerifications();
