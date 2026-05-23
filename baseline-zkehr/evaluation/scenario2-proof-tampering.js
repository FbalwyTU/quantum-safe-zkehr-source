const fs = require("fs");
const path = require("path");
const { performance } = require("perf_hooks");
const { JsonRpcProvider, Wallet, Contract } = require("ethers");

// إعدادات الاتصال بالعقد
const provider = new JsonRpcProvider(
  process.env.ZKEHR_RPC_URL || "http://127.0.0.1:8545"
); // استخدم IPv4 فقط
const PRIVATE_KEY =
  process.env.ZKEHR_ETH_PRIVATE_KEY ||
  "0xaf84bf2b9192e8cce18aa4fdcb95255a08d2447070c016a1114771695213e498";
const wallet = new Wallet(PRIVATE_KEY, provider);

// تحميل ABI من Hardhat artifacts
const verifierAbi =
  require("../artifacts/contracts/Verifier.sol/Groth16Verifier.json").abi;
const verifierAddress =
  process.env.ZKEHR_VERIFIER_ADDRESS ||
  "0x20e2F410f01733af079A5599c72b03351386F935";
const verifier = new Contract(verifierAddress, verifierAbi, wallet);

// تحميل الإثبات والبيانات العامة
const proof = JSON.parse(fs.readFileSync("proof.json"));
const pub = JSON.parse(fs.readFileSync("public.json"));

// التلاعب بالإثبات (Tampering)
const a = [
  (BigInt(proof.pi_a[0]) + 123456789n).toString(), // تغيير مقصود لكسر الإثبات
  proof.pi_a[1],
];
const b = [
  [proof.pi_b[0][1], proof.pi_b[0][0]],
  [proof.pi_b[1][1], proof.pi_b[1][0]],
];
const c = [proof.pi_c[0], proof.pi_c[1]];
const input = pub.map((n) => n);

// ملف النتائج
const outputPath =
  process.env.ZKEHR_SCENARIO2_LOG_PATH || "evaluation/evaluation_logs.csv";
const header = "scenario,result,verify_time_ms,timestamp\n";
if (!fs.existsSync(outputPath)) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, header);
}

async function run() {
  console.log("\n🔒 Scenario 2: Proof Tampering");

  const t0 = performance.now();
  let result = false;

  try {
    result = await verifier.verifyProof(a, b, c, input);
  } catch (err) {
    console.error("⛔️ Error during verification:", err.message);
  }

  const t1 = performance.now();
  const verifyTime = (t1 - t0).toFixed(2);
  const timestamp = new Date().toISOString();
  const outcome = result ? "ACCEPTED ❌" : "REJECTED ✅";

  console.log(`📊 Result: ${outcome} | Time: ${verifyTime} ms`);
  fs.appendFileSync(
    outputPath,
    `Proof Tampering,${outcome},${verifyTime},${timestamp}\n`
  );
}

run();
