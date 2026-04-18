#!/usr/bin/env python3

import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("setup_zk_circuit")


def main() -> None:
    force = "--force" in sys.argv

    from pipeline.zk_proof import ZK_DIR, is_setup_complete
    from pipeline.zk_setup import setup_circuit_sync

    if is_setup_complete() and not force:
        logger.info("Circuit already set up at %s/", ZK_DIR)
        logger.info("Pass --force to regenerate from scratch.")
        return

    if force:
        import shutil
        if ZK_DIR.exists():
            shutil.rmtree(ZK_DIR)
            logger.info("--force: removed %s/", ZK_DIR)

    logger.info("Starting ZK circuit setup...")
    setup_circuit_sync()
    logger.info("Done. You can now start the server: uvicorn main:app --reload")


if __name__ == "__main__":
    main()
