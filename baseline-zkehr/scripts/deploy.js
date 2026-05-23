const hre = require("hardhat");

async function main() {
  console.log("⏳ Deploying Verifier contract...");

  const Verifier = await hre.ethers.getContractFactory("Groth16Verifier");
  const verifier = await Verifier.deploy();

  console.log(`✅ Verifier deployed at: ${verifier.target}`);
}

main().catch((error) => {
  console.error("❌ Deployment failed:", error);
  process.exitCode = 1;
});
