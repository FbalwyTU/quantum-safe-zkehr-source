const fs = require("fs");
const path = require("path");
const { ContractFactory, JsonRpcProvider, Wallet } = require("ethers");

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2) + "\n", "utf8");
}

function parseNetworkName() {
  const index = process.argv.indexOf("--network");
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : "localhost";
}

async function main() {
  const repoRoot = process.cwd();
  const configPath = path.join(
    repoRoot,
    "implementation_tools",
    "phase2",
    "phase2_config.json"
  );
  const artifactPath = path.join(
    repoRoot,
    "artifacts",
    "contracts",
    "Verifier.sol",
    "Groth16Verifier.json"
  );
  const config = readJson(configPath);
  const artifact = readJson(artifactPath);
  const provider = new JsonRpcProvider(config.rpcUrl);
  const wallet = new Wallet(config.defaultPrivateKey, provider);
  const network = await provider.getNetwork();
  const factory = new ContractFactory(artifact.abi, artifact.bytecode, wallet);
  const verifier = await factory.deploy();
  const deployTx = verifier.deploymentTransaction();

  await verifier.waitForDeployment();

  const deployment = {
    network: parseNetworkName(),
    rpcUrl: config.rpcUrl,
    chainId: network.chainId.toString(),
    deployer: await wallet.getAddress(),
    verifierAddress: await verifier.getAddress(),
    txHash: deployTx ? deployTx.hash : "",
    timestamp: new Date().toISOString(),
    notes:
      "Phase 2 local Hardhat deployment. Uses only local development fixture values from phase2_config.json.",
  };

  const deploymentPath = path.join(
    repoRoot,
    config.outputDir,
    "deployment.json"
  );
  writeJson(deploymentPath, deployment);

  console.log(JSON.stringify(deployment, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
