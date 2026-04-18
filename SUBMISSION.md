# Proof of Origin

AI-generated images are everywhere and indistinguishable from real ones. Metadata gets stripped, screenshots erase history, and a single re-save cuts the connection to the source. Proof of Origin fixes this: every image generated through the app gets three invisible watermarks woven into its pixels, a zero-knowledge proof registered on a public blockchain, and its full provenance stored permanently on Arweave — so anyone can verify where it came from, even after screenshots, crops, or AI regeneration, without trusting this server.

**How it works.** Generate an image and three watermarks are embedded simultaneously: a frequency-domain fingerprint (survives AI regeneration), a neural steganographic layer (survives JPEG and resizing), and a metadata signature. A zero-knowledge proof binds the watermark ID, image hash, and perceptual hash together and is verified by a smart contract on Base Sepolia — the blockchain itself checks the math, not just stores a hash. The full record (prompt, model, timestamp, hashes) is anchored to Arweave permanently. To verify, upload any version of the image — screenshot, crop, re-encoded JPEG — and the app reads the watermarks, queries the chain, and tells you whether it's the original or a derivative. There's also a trustless verify button that queries the contract directly from the browser, no backend needed.

**Why it matters.** The EU AI Act requires AI-generated content to be machine-detectable as synthetic. Existing solutions break the moment an image is screenshotted. This system is the first to combine watermarks that survive AI regeneration, on-chain ZK proof verification, and permanent decentralized storage into a single compliance-ready pipeline — by design, not convention.

**Innovation.** DINOv2 semantic embeddings as a perceptual hash detect derivatives even after img2img regeneration, something traditional algorithms cannot do. The ezkl ZK proof is verified on-chain at registration time — not stored after the fact — so the chain vouches for honest watermarking. A two-phase registration pattern (placeholder → complete) eliminates the crash window between image generation and blockchain anchoring.

**Secure architecture.** Three independent watermark layers mean an attacker must defeat frequency steganography, neural pixel encoding, and metadata signing simultaneously. The ZK verifier contract is generated from the circuit and deployed independently — a compromised backend cannot fabricate an on-chain proof. Atomic SQLite writes ensure no image can be watermarked but left unregistered after a crash.

**Contract on Base Sepolia:** `0xb723517154096160EFf074263027030Af235cD07`

**License:** GNU General Public License v3.0 (GPLv3)
