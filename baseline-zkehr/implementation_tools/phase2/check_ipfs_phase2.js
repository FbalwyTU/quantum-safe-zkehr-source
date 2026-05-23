const fs = require("fs");
const path = require("path");

function loadConfig() {
  const configPath = path.join(__dirname, "phase2_config.json");
  return JSON.parse(fs.readFileSync(configPath, "utf8"));
}

function buildVersionUrl(ipfsApiUrl) {
  const trimmed = ipfsApiUrl.replace(/\/+$/, "");
  return trimmed.endsWith("/version") ? trimmed : `${trimmed}/version`;
}

async function checkIpfs(ipfsApiUrl, options = {}) {
  const timeoutMs = options.timeoutMs || 2500;
  const versionUrl = buildVersionUrl(ipfsApiUrl);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(versionUrl, {
      method: "POST",
      signal: controller.signal,
    });

    if (!response.ok) {
      return {
        status: "ERROR",
        ipfsApiUrl,
        versionUrl,
        httpStatus: response.status,
        error: `IPFS API returned HTTP ${response.status}`,
      };
    }

    const text = await response.text();
    let parsed = null;
    try {
      parsed = JSON.parse(text);
    } catch (error) {
      parsed = { raw: text };
    }

    return {
      status: "AVAILABLE",
      ipfsApiUrl,
      versionUrl,
      version: parsed.Version || parsed.version || parsed.raw || "",
      response: parsed,
    };
  } catch (error) {
    const status = error.name === "AbortError" ? "UNAVAILABLE" : "UNAVAILABLE";
    return {
      status,
      ipfsApiUrl,
      versionUrl,
      error: error.message,
    };
  } finally {
    clearTimeout(timeout);
  }
}

async function main() {
  const config = loadConfig();
  const result = await checkIpfs(config.ipfsApiUrl);
  console.log(JSON.stringify(result, null, 2));
}

if (require.main === module) {
  main().catch((error) => {
    console.error(
      JSON.stringify(
        {
          status: "ERROR",
          error: error.message,
        },
        null,
        2
      )
    );
    process.exitCode = 1;
  });
}

module.exports = {
  buildVersionUrl,
  checkIpfs,
};
