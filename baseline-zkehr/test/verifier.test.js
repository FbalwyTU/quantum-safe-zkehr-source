const { expect } = require("chai");
const hre = require("hardhat");
const { VALID_PROOF_FIXTURE } = require("./helpers/validProofFixture");

describe("Verifier Contract - ZK-EHR", function () {
  let verifier;

  before(async function () {
    const Verifier = await hre.ethers.getContractFactory("Groth16Verifier");
    verifier = await Verifier.deploy();
    await verifier.waitForDeployment();
  });

  it("Should verify a valid zk-SNARK proof", async function () {
    const result = await verifier.verifyProof(
      VALID_PROOF_FIXTURE.a,
      VALID_PROOF_FIXTURE.b,
      VALID_PROOF_FIXTURE.c,
      VALID_PROOF_FIXTURE.input
    );
    expect(result).to.be.true;
  });

  it("Should reject an invalid zk-SNARK proof (all zero)", async function () {
    const a = ["0x0", "0x0"];
    const b = [
      ["0x0", "0x0"],
      ["0x0", "0x0"],
    ];
    const c = ["0x0", "0x0"];
    const input = ["0x0"];

    const result = await verifier.verifyProof(a, b, c, input);
    expect(result).to.be.false;
  });

  it("Should reject a proof with tampered a[0]", async function () {
    const a = [
      "0x9999999999999999999999999999999999999999999999999999999999999999", // tampered
      VALID_PROOF_FIXTURE.a[1],
    ];

    const result = await verifier.verifyProof(
      a,
      VALID_PROOF_FIXTURE.b,
      VALID_PROOF_FIXTURE.c,
      VALID_PROOF_FIXTURE.input
    );
    expect(result).to.be.false;
  });

  it("Should reject a valid proof with invalid public input", async function () {
    const input = ["0x2"];

    const result = await verifier.verifyProof(
      VALID_PROOF_FIXTURE.a,
      VALID_PROOF_FIXTURE.b,
      VALID_PROOF_FIXTURE.c,
      input
    );
    expect(result).to.be.false;
  });

  it("Should reject execution with invalid public input size at the ABI level", async function () {
    const input = []; // intentionally invalid input size

    await expect(
      verifier.verifyProof(
        VALID_PROOF_FIXTURE.a,
        VALID_PROOF_FIXTURE.b,
        VALID_PROOF_FIXTURE.c,
        input
      )
    ).to.be.rejectedWith(
      Error,
      /wrong length/i
    );
  });

  it("Should emit AccessGranted for a valid proof without breaking verifyProof", async function () {
    const [signer] = await hre.ethers.getSigners();
    const recordIdHash = hre.ethers.keccak256(
      hre.ethers.toUtf8Bytes("cid:valid-record")
    );

    await expect(
      verifier.verifyProofAndEmit(
        VALID_PROOF_FIXTURE.a,
        VALID_PROOF_FIXTURE.b,
        VALID_PROOF_FIXTURE.c,
        VALID_PROOF_FIXTURE.input,
        recordIdHash
      )
    )
      .to.emit(verifier, "AccessGranted")
      .withArgs(await signer.getAddress(), recordIdHash);
  });

  it("Should emit AccessDenied for an invalid proof", async function () {
    const [signer] = await hre.ethers.getSigners();
    const recordIdHash = hre.ethers.keccak256(
      hre.ethers.toUtf8Bytes("cid:invalid-record")
    );
    const tamperedA = [
      "0x9999999999999999999999999999999999999999999999999999999999999999",
      VALID_PROOF_FIXTURE.a[1],
    ];

    await expect(
      verifier.verifyProofAndEmit(
        tamperedA,
        VALID_PROOF_FIXTURE.b,
        VALID_PROOF_FIXTURE.c,
        VALID_PROOF_FIXTURE.input,
        recordIdHash
      )
    )
      .to.emit(verifier, "AccessDenied")
      .withArgs(await signer.getAddress(), recordIdHash);
  });
});
