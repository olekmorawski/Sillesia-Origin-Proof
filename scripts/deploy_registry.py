#!/usr/bin/env python3
import json
import pathlib
import sys

from solcx import compile_source, install_solc
from web3 import Web3

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from settings import settings

DEPLOYMENT_FILE = pathlib.Path(__file__).parent.parent / "deployment.json"
CONTRACT_FILE = pathlib.Path(__file__).parent.parent / "contracts" / "ProofOfOriginRegistry.sol"
CHAIN_ID = 84532


def deploy() -> None:
    if DEPLOYMENT_FILE.exists():
        print(f"deployment.json already exists at {DEPLOYMENT_FILE}")
        print("Delete it manually if you intend to redeploy, then re-run.")
        sys.exit(1)

    print("Installing solc 0.8.20 (no-op if cached)...")
    install_solc("0.8.20")

    solidity_source = CONTRACT_FILE.read_text()
    print("Compiling ProofOfOriginRegistry.sol...")
    compiled = compile_source(solidity_source, solc_version="0.8.20", output_values=["abi", "bin"])

    contract_key = [k for k in compiled if "ProofOfOriginRegistry" in k][0]
    contract_abi = compiled[contract_key]["abi"]
    contract_bytecode = compiled[contract_key]["bin"]
    print(f"Compiled OK — bytecode length: {len(contract_bytecode)} chars")

    w3 = Web3(Web3.HTTPProvider(settings.rpc_url))
    if not w3.is_connected():
        print(f"ERROR: Cannot connect to RPC at {settings.rpc_url}")
        sys.exit(1)
    print(f"Connected to chain ID: {w3.eth.chain_id}")

    account = w3.eth.account.from_key(settings.wallet_private_key)
    print(f"Deploying from: {account.address}")

    balance = w3.eth.get_balance(account.address)
    print(f"Wallet balance: {w3.from_wei(balance, 'ether'):.6f} ETH")
    if balance == 0:
        print("ERROR: Wallet has 0 ETH — fund via Base Sepolia faucet first.")
        sys.exit(1)

    registry = w3.eth.contract(abi=contract_abi, bytecode=contract_bytecode)
    nonce = w3.eth.get_transaction_count(account.address)
    tx = registry.constructor(Web3.to_checksum_address("0x0000000000000000000000000000000000000000")).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "chainId": CHAIN_ID,
        "maxFeePerGas": int(w3.eth.gas_price * 1.2),
        "maxPriorityFeePerGas": w3.eth.max_priority_fee,
    })

    signed = account.sign_transaction(tx)
    print("Sending deployment tx...")
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Tx hash: {tx_hash.hex()}")
    print("Waiting for receipt (up to 120s)...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    contract_address = receipt["contractAddress"]
    print(f"Deployed at: {contract_address}")
    print(f"Block: {receipt['blockNumber']}  Gas used: {receipt['gasUsed']}")
    print(f"BaseScan: https://sepolia.basescan.org/address/{contract_address}")

    deployment = {
        "address": contract_address,
        "abi": contract_abi,
        "tx_hash": receipt["transactionHash"].hex(),
        "block_number": receipt["blockNumber"],
        "chain_id": CHAIN_ID,
    }
    DEPLOYMENT_FILE.write_text(json.dumps(deployment, indent=2))
    print(f"deployment.json written to {DEPLOYMENT_FILE}")
    print("Commit deployment.json to git — judges do not need to redeploy.")


if __name__ == "__main__":
    deploy()
