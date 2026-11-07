"""python -m dvm: start ingest, the Tiger Data writer and the API in one process."""
import logging

import uvicorn

from dvm import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
uvicorn.run("dvm.app:app", host=config.HOST, port=config.PORT, log_level="info")
