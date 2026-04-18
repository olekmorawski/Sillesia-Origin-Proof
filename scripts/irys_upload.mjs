/**
 * Irys upload helper — reads provenance JSON from stdin, uploads to Arweave
 * via the new @irys/upload SDK, writes {"id": "<tx_id>"} to stdout.
 *
 * Usage (called by pipeline/arweave.py via subprocess):
 *   echo '{"watermark_id":"..."}' | WALLET_PRIVATE_KEY=0x... node scripts/irys_upload.mjs
 *
 * Exit 0 on success, exit 1 on failure (error on stderr).
 */
import { Uploader } from "@irys/upload";
import { BaseEth } from "@irys/upload-ethereum";

async function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => { data += chunk; });
    process.stdin.on("end", () => resolve(data));
  });
}

async function main() {
  const raw = await readStdin();
  const provenance = JSON.parse(raw);

  const privateKey = process.env.WALLET_PRIVATE_KEY;
  if (!privateKey) {
    process.stderr.write("WALLET_PRIVATE_KEY env var not set\n");
    process.exit(1);
  }

  const uploader = await Uploader(BaseEth).bundlerUrl("https://node1.irys.xyz").withWallet(privateKey);

  const tags = [
    { name: "Content-Type",  value: "application/json" },
    { name: "App-Name",      value: "ProofOfOrigin" },
    { name: "Watermark-Id",  value: provenance.watermark_id ?? "" },
  ];

  let receipt;
  const MAX_RETRIES = 4;
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      receipt = await uploader.upload(JSON.stringify(provenance), { tags });
      break;
    } catch (err) {
      const transient = err.message.includes("ECONNRESET") ||
                        err.message.includes("ETIMEDOUT") ||
                        err.message.includes("ENOTFOUND") ||
                        err.message.includes("socket hang up");
      if (!transient || attempt === MAX_RETRIES) throw err;
      const delay = 1000 * 2 ** (attempt - 1);
      process.stderr.write(`Irys upload attempt ${attempt} failed (${err.message}), retrying in ${delay}ms…\n`);
      await new Promise((r) => setTimeout(r, delay));
    }
  }

  process.stdout.write(JSON.stringify({ id: receipt.id }) + "\n");
}

main().catch((err) => {
  process.stderr.write(`Irys upload error: ${err.message}\n`);
  process.exit(1);
});
