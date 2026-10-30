"""One independent PostgreSQL-backed worker; no request threads or automatic retries."""

import argparse
import multiprocessing
import signal
import time
from pathlib import Path

from pygeoapi.api import API
from pygeoapi.util import yaml_load
from sqlalchemy import text

from geo_processes.async_manager import WORKER_LOCK, DurableProcessManager
from geo_processes.startup import validate_runtime


def manager_from_config(config):
    api = API(config, {})
    manager = api.manager
    if not isinstance(manager, DurableProcessManager):
        raise ValueError("worker requires DurableProcessManager")
    manager.result_base_url = api.base_url
    return manager


def perform(config, job_id):
    manager = manager_from_config(config)
    try:
        manager.perform(job_id)
    finally:
        manager._engine.dispose()


def serve(config):
    validate_runtime(config)
    manager = manager_from_config(config)
    stopped = False

    def stop(_signum, _frame):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    context = multiprocessing.get_context("spawn")
    with manager._engine.connect().execution_options(isolation_level="AUTOCOMMIT") as lease:
        if not lease.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": WORKER_LOCK}).scalar_one():
            raise RuntimeError("another async worker is already active")
        try:
            manager.fail_interrupted()
            while not stopped:
                # Verify the worker lease connection before claiming another job.
                lease.execute(text("SELECT 1"))
                identifier = manager.claim()
                if identifier is None:
                    time.sleep(0.5)
                    continue
                child = context.Process(target=perform, args=(config, identifier))
                child.start()
                deadline = time.monotonic() + manager.limits["GEO_JOB_TIMEOUT"]
                try:
                    while child.is_alive() and not stopped and time.monotonic() < deadline:
                        lease.execute(text("SELECT 1"))
                        child.join(timeout=0.2)
                    if child.is_alive():
                        child.terminate()
                        child.join(timeout=2)
                        if child.is_alive():
                            child.kill()
                            child.join()
                    job = manager.get_job(identifier)
                    if job["status"] == "running":
                        message = "worker interrupted" if stopped else "job timed out or worker execution failed"
                        manager.finish(identifier, manager.failure(500, "NoApplicableCode", message), failed=True)
                finally:
                    if child.is_alive():
                        child.kill()
                        child.join()
        finally:
            lease.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": WORKER_LOCK})
    manager._engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    with args.config.open() as stream:
        serve(yaml_load(stream))


if __name__ == "__main__":
    main()
