const crypto = require("crypto");
const { create } = require("ipfs-http-client");

function createIpfsClient(url = process.env.IPFS_API_URL || "http://127.0.0.1:5001/api/v0") {
  return create({ url });
}

async function uploadBufferToIpfs(ipfsClient, buffer) {
  const result = await ipfsClient.add(buffer);
  return result.cid.toString();
}

async function downloadBufferFromIpfs(ipfsClient, cid) {
  const chunks = [];

  for await (const chunk of ipfsClient.cat(cid)) {
    chunks.push(Buffer.from(chunk));
  }

  return Buffer.concat(chunks);
}

function createInMemoryIpfsClient() {
  const objects = new Map();

  return {
    async add(buffer) {
      const payload = Buffer.isBuffer(buffer) ? Buffer.from(buffer) : Buffer.from(buffer);
      const cid =
        "mockcid-" + crypto.createHash("sha256").update(payload).digest("hex").slice(0, 32);
      objects.set(cid, payload);
      return {
        cid: {
          toString() {
            return cid;
          },
        },
      };
    },

    async *cat(cid) {
      if (!objects.has(cid)) {
        throw new Error(`No IPFS object found for CID '${cid}'.`);
      }

      yield Buffer.from(objects.get(cid));
    },
  };
}

module.exports = {
  createInMemoryIpfsClient,
  createIpfsClient,
  downloadBufferFromIpfs,
  uploadBufferToIpfs,
};
