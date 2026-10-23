"""Bounded local raster delivery with atomic publication and lazy expiry.

The service runs on Linux (including local development through Docker).
An advisory file lock serializes writers across Gunicorn processes sharing
the volume; downloads remain available while another process is warping.
"""

import argparse
import errno
import fcntl
import os
import re
import shutil
import stat
import tempfile
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

RESULT_ID = re.compile(r"[0-9a-f]{32}")
MAX_RESULT_BYTES = 16 * 1024 * 1024


class ResultStoreError(RuntimeError):
    """Local result storage failed."""


class ResultStoreBusyError(ResultStoreError):
    """Another writer currently holds the volume lock."""


class ResultStoreFullError(ResultStoreError):
    """Publishing a new output would exceed a configured bound."""


class ResultNotFoundError(ResultStoreError):
    """The result is invalid, missing, or expired."""


@dataclass(frozen=True)
class StoredResult:
    identifier: str
    expires_at: float


@dataclass(frozen=True)
class ResultStore:
    root: Path
    retention_seconds: int = 86400
    max_bytes: int = 64 * 1024 * 1024
    max_results: int = 256

    def __post_init__(self):
        if not 1 <= self.retention_seconds <= 604800:
            raise ValueError("retention must be between 1 second and 7 days")
        if not 1 <= self.max_bytes <= 1024 * 1024 * 1024:
            raise ValueError("result capacity must be between 1 byte and 1 GiB")
        if not 1 <= self.max_results <= 10000:
            raise ValueError("result count must be between 1 and 10000")

    @classmethod
    def from_environment(cls):
        return cls(
            Path(os.environ.get("TERRIO_OUTPUT_DIR", "runtime-data/results")).resolve(),
            retention_seconds=int(os.environ.get("TERRIO_RESULT_RETENTION_SECONDS", "86400")),
            max_bytes=int(os.environ.get("TERRIO_RESULT_MAX_BYTES", str(64 * 1024 * 1024))),
            max_results=int(os.environ.get("TERRIO_RESULT_MAX_COUNT", "256")),
        )

    @contextmanager
    def _writer(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.root / ".lock").open("a+b") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ResultStoreBusyError("another raster operation is running") from error
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _cleanup(self):
        now = time.time()
        for path in self.root.iterdir():
            if path.name.startswith(".work-") and path.is_dir() and not path.is_symlink():
                # Holding the writer lock proves these are abandoned workspaces.
                shutil.rmtree(path)
            elif (
                RESULT_ID.fullmatch(path.stem)
                and path.suffix == ".tif"
                and now - path.lstat().st_mtime >= self.retention_seconds
            ):
                path.unlink()

    def cleanup(self):
        """Remove expired results and workspaces left by interrupted workers."""
        with self._writer():
            self._cleanup()

    def publish(self, write: Callable[[Path], None]) -> StoredResult:
        """Run one bounded writer, then atomically make its complete file visible."""
        with self._writer():
            self._cleanup()
            results = [path for path in self.root.glob("*.tif") if RESULT_ID.fullmatch(path.stem)]
            used_bytes = sum(path.lstat().st_size for path in results)
            if len(results) >= self.max_results or used_bytes >= self.max_bytes:
                raise ResultStoreFullError("result storage is full; retry after results expire")
            with tempfile.TemporaryDirectory(prefix=".work-", dir=self.root) as directory:
                output = Path(directory) / "output.tif"
                write(output)
                size = output.stat().st_size
                if size > MAX_RESULT_BYTES or size + used_bytes > self.max_bytes:
                    raise ResultStoreFullError("output exceeds the available result capacity")
                if size == 0:
                    raise ResultStoreError("raster output is empty")
                identifier = uuid4().hex
                created_at = time.time()
                os.utime(output, (created_at, created_at))
                output.replace(self.root / f"{identifier}.tif")
                return StoredResult(identifier, created_at + self.retention_seconds)

    def read(self, identifier: str) -> tuple[bytes, float]:
        """Read only a bounded, unexpired, regular result file; never follow links."""
        if not RESULT_ID.fullmatch(identifier):
            raise ResultNotFoundError("result not found or expired")
        path = self.root / f"{identifier}.tif"
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as result:
                metadata = os.fstat(result.fileno())
                expires_at = metadata.st_mtime + self.retention_seconds
                if not stat.S_ISREG(metadata.st_mode) or expires_at <= time.time():
                    raise ResultNotFoundError("result not found or expired")
                if metadata.st_size > MAX_RESULT_BYTES:
                    raise ResultStoreError("stored result exceeds the size limit")
                return result.read(MAX_RESULT_BYTES + 1), expires_at
        except OSError as error:
            if error.errno in {errno.ENOENT, errno.ENOTDIR, errno.ELOOP}:
                raise ResultNotFoundError("result not found or expired") from error
            raise ResultStoreError("result could not be read") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["cleanup"])
    parser.parse_args()
    ResultStore.from_environment().cleanup()


if __name__ == "__main__":
    main()
