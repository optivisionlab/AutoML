# Standard Libraries
import os
import sys
import asyncio
import logging
from pathlib import Path

# Ensure PyMapReduce worker daemon uses the current Python interpreter
if "PYTHON_EXECUTABLE" not in os.environ:
    os.environ["PYTHON_EXECUTABLE"] = sys.executable

# Third-party Libraries
import pymapreduce

# Local Libraries
from src.config import settings, MapReduceMode


# Logging
logger = logging.getLogger(__name__)


class MapReduceManager:
    """
    Singleton Manager for PyMapReduce Driver and Cluster connection lifecycle
    """
    _driver: pymapreduce.Driver | None = None
    _is_initialized: bool = False
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    async def get_driver(cls) -> pymapreduce.Driver:
        """
        Get or initialize the singleton PyMapReduce Driver instance
        """
        if cls._driver and cls._is_initialized:
            return cls._driver

        async with cls._lock:
            if cls._driver and cls._is_initialized:
                return cls._driver

            mode = settings.PYMAPREDUCE.MODE
            head_addr = settings.PYMAPREDUCE.HEAD_ADDRESS

            backend_dir = str(Path(__file__).resolve().parent.parent.parent)
            runtime_env = {
                "working_dir": backend_dir,
                "excludes": ["deploy", "tests", "demo", "docs", "MapReduce", "dataset"],
            }

            if mode == MapReduceMode.LOCAL:
                logger.info(f"Initializing PyMapReduce in LOCAL EMBEDDED mode at {head_addr}...")
                # Initialize local HeadNode with retry in case of WAL recovery
                last_err = None
                for attempt in range(1, 4):
                    try:
                        cls._driver = await pymapreduce.init(
                            address=head_addr,
                            runtime_env=runtime_env
                        )
                        break
                    except Exception as err:
                        last_err = err
                        logger.warning(f"PyMapReduce init attempt {attempt}/3 failed: {err}. Retrying in 0.5s...")
                        await asyncio.sleep(0.5)

                if cls._driver is None:
                    raise RuntimeError(f"Failed to initialize PyMapReduce HeadNode after 3 attempts: {last_err}")

                # Start local worker utilizing all available CPU cores automatically
                asyncio.ensure_future(pymapreduce.start_worker(head_addr))
                
                # Allow a short moment for the local worker to register with HeadNode
                await asyncio.sleep(1.0)
                logger.info("PyMapReduce Local Cluster successfully initialized and worker registered")
            else:
                # CLUSTER mode
                logger.info(f"Connecting to PyMapReduce Cluster at HeadNode '{head_addr}' with runtime_env working_dir={backend_dir}...")
                last_err = None
                for attempt in range(1, 4):
                    try:
                        cls._driver = await pymapreduce.connect(
                            head_node=head_addr,
                            runtime_env=runtime_env
                        )
                        break
                    except Exception as err:
                        last_err = err
                        logger.warning(f"PyMapReduce connect attempt {attempt}/3 failed: {err}. Retrying in 0.5s...")
                        await asyncio.sleep(0.5)

                if cls._driver is None:
                    raise RuntimeError(f"Failed to connect to PyMapReduce Cluster after 3 attempts: {last_err}")

                logger.info("Successfully connected to PyMapReduce Cluster")

            cls._is_initialized = True
            return cls._driver

    @classmethod
    async def shutdown(cls) -> None:
        """
        Gracefully shutdown the driver connection.
        """
        async with cls._lock:
            if cls._driver and cls._is_initialized:
                try:
                    mode = settings.PYMAPREDUCE.MODE
                    if mode == MapReduceMode.LOCAL:
                        await cls._driver.shutdown()
                    logger.info("PyMapReduce Driver shutdown completed")
                except Exception as e:
                    logger.warning(f"Error while shutting down PyMapReduce Driver: {e}")
                finally:
                    cls._driver = None
                    cls._is_initialized = False
