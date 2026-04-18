"""One-time ZK circuit setup for Poseidon commitment circuit.

Run once before starting the server:
    python scripts/setup_zk_circuit.py

Exports a trivial Relu circuit to ONNX (opset 11), sets input_visibility=hashed
so ezkl uses Poseidon hash as the public commitment, calibrates settings,
downloads the SRS, compiles the circuit, and generates proving/verification keys.
All artefacts are written to zk/.
"""

import asyncio
import json
import logging

import numpy as np

from pipeline.zk_proof import (
    ZK_DIR,
    ONNX_PATH,
    COMPILED_PATH,
    SETTINGS_PATH,
    VK_PATH,
    PK_PATH,
    SRS_PATH,
    CALIBRATION_INPUT_PATH,
    EVM_VERIFIER_SOL_PATH,
    EVM_VERIFIER_ABI_PATH,
    INPUT_DIM,
    _get_ezkl,
    is_setup_complete,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Circuit ONNX export
# Architecture: Relu, opset 11 (trivial — real commitment is Poseidon(inputs))
# Input: short_id_bits[64] ++ image_hash_bits[256] ++ phash_bits[64] = 384 floats
# ---------------------------------------------------------------------------

def export_circuit_onnx() -> None:
    """Build and save a trivial Relu circuit as ONNX opset 11.

    The circuit itself does nothing meaningful — the commitment is the
    Poseidon hash of the quantized inputs, computed natively by ezkl
    when input_visibility is set to 'hashed'.
    """
    import onnx
    from onnx import helper, TensorProto

    ZK_DIR.mkdir(exist_ok=True)

    relu = helper.make_node("Relu", inputs=["input"], outputs=["output"])

    graph = helper.make_graph(
        [relu],
        "PoseidonCommitment",
        [helper.make_tensor_value_info("input",  TensorProto.FLOAT, [1, INPUT_DIM])],
        [helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, INPUT_DIM])],
    )

    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 11)])
    onnx.checker.check_model(model)
    onnx.save(model, str(ONNX_PATH))
    logger.info("PoseidonCommitment ONNX exported (opset 11) → %s", ONNX_PATH)


# ---------------------------------------------------------------------------
# Circuit setup
# ---------------------------------------------------------------------------

def setup_circuit_sync() -> None:
    """Run full ezkl setup synchronously.

    ezkl.get_srs uses asyncio.get_running_loop() internally, so all calls
    run inside loop.run_until_complete() to provide a running event loop.
    """
    ezkl = _get_ezkl()
    ZK_DIR.mkdir(exist_ok=True)

    if not ONNX_PATH.exists():
        logger.info("Exporting PoseidonCommitment ONNX...")
        export_circuit_onnx()

    _write_calibration_input()

    async def _run():
        run_args = ezkl.PyRunArgs()
        run_args.input_visibility = "hashed"
        run_args.output_visibility = "private"
        # param_visibility stays "fixed" (default) — no trainable params in circuit

        logger.info("gen_settings (input_visibility=hashed)...")
        ezkl.gen_settings(str(ONNX_PATH), str(SETTINGS_PATH), py_run_args=run_args)

        logger.info("calibrate_settings...")
        ezkl.calibrate_settings(
            str(CALIBRATION_INPUT_PATH), str(ONNX_PATH), str(SETTINGS_PATH), "resources"
        )

        logger.info("get_srs (downloads ~4 MB)...")
        await ezkl.get_srs(str(SETTINGS_PATH), None, str(SRS_PATH))

        logger.info("compile_circuit...")
        ezkl.compile_circuit(str(ONNX_PATH), str(COMPILED_PATH), str(SETTINGS_PATH))

        logger.info("setup (proving + verification keys)...")
        ezkl.setup(str(COMPILED_PATH), str(VK_PATH), str(PK_PATH), str(SRS_PATH), None, False)

        logger.info("create_evm_verifier (Verifier.sol + verifier_abi.json)...")
        ezkl.create_evm_verifier(
            str(VK_PATH),
            str(SETTINGS_PATH),
            str(EVM_VERIFIER_SOL_PATH),
            str(EVM_VERIFIER_ABI_PATH),
        )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()

    logger.info("ZK circuit ready — artefacts in %s/", ZK_DIR)


def _write_calibration_input() -> None:
    calibration = {"input_data": [np.random.choice([0.0, 1.0], size=INPUT_DIM).tolist()]}
    CALIBRATION_INPUT_PATH.write_text(json.dumps(calibration))
