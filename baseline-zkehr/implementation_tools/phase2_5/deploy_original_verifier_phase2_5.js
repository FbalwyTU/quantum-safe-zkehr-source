const fs = require("fs");
const path = require("path");
const { ContractFactory, JsonRpcProvider, Wallet } = require("ethers");

const repoRoot = path.resolve(__dirname, "../..");
const outputPath = path.join(repoRoot, "baseline_results", "phase2_5", "deployment.json");
const artifactPath = path.join(
  repoRoot,
  "artifacts",
  "contracts",
  "Verifier.sol",
  "Groth16Verifier.json"
);

const rpcUrl = process.env.ZKEHR_RPC_URL || "http://127.0.0.1:8545";
const defaultPrivateKey =
  process.env.ZKEHR_ETH_PRIVATE_KEY ||
  "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80";

async function main() {
  const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));
  const provider = new JsonRpcProvider(rpcUrl);
  const wallet = new Wallet(defaultPrivateKey, provider);
  const network = await provider.getNetwork();
  const factory = new ContractFactory(artifact.abi, artifact.bytecode, wallet);
  const verifier = await factory.deploy();
  const deployTx = verifier.deploymentTransaction();

  await verifier.waitForDeployment();

  const deployment = {
    network: network.name === "unknown" ? "localhost" : network.name,
    rpcUrl,
    chainId: network.chainId.toString(),
    deployer: await wallet.getAddress(),
    verifierAddress: await verifier.getAddress(),
    txHash: deployTx ? deployTx.hash : "",
    timestamp: new Date().toISOString(),
    notes:
      "Phase 2.5 local Hardhat deployment of the original checked-in Groth16Verifier. Uses the public Hardhat development key only.",
  };

  fs.writeFileSync(outputPath, JSON.stringify(deployment, null, 2) + "\n", "utf8");
  console.log(JSON.stringify(deployment, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
