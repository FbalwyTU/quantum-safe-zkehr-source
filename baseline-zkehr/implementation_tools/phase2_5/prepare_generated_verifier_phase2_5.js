const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "../..");
const generatedPath = path.join(
  repoRoot,
  "baseline_results",
  "phase2_5",
  "zk_artifacts",
  "GeneratedVerifier.sol"
);
const outputPath = path.join(repoRoot, "contracts", "Groth16VerifierPhase25.sol");

function main() {
  if (!fs.existsSync(generatedPath)) {
    throw new Error(`Generated verifier not found: ${generatedPath}`);
  }

  const source = fs.readFileSync(generatedPath, "utf8");
  if (!source.includes("contract Groth16Verifier")) {
    throw new Error("Generated verifier does not contain contract Groth16Verifier.");
  }

  const renamed = source.replace(
    "contract Groth16Verifier",
    "contract Groth16VerifierPhase25"
  );

  fs.writeFileSync(outputPath, renamed, "utf8");
  console.log(`Wrote ${path.relative(repoRoot, outputPath)}`);
}

main();
