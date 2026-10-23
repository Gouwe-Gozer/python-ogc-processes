"""Atomic publication, bounded capacity, expiry and safe local retrieval."""

import os
import time

import pytest

from geo_processes.storage import (
    MAX_RESULT_BYTES,
    ResultNotFoundError,
    ResultStore,
    ResultStoreBusyError,
    ResultStoreError,
    ResultStoreFullError,
)


def publish(store, data=b"TIFF"):
    return store.publish(lambda output: output.write_bytes(data))


def test_result_survives_new_store_instance_and_uses_generated_name(tmp_path):
    store = ResultStore(tmp_path, retention_seconds=60)
    result = publish(store)
    assert len(result.identifier) == 32
    assert (tmp_path / f"{result.identifier}.tif").is_file()
    assert ResultStore(tmp_path, retention_seconds=60).read(result.identifier)[0] == b"TIFF"
    assert 59 <= result.expires_at - time.time() <= 60
    assert not list(tmp_path.glob(".work-*"))


def test_quota_never_evicts_unexpired_results(tmp_path):
    store = ResultStore(tmp_path, max_results=1)
    first = publish(store)
    with pytest.raises(ResultStoreFullError):
        publish(store)
    assert store.read(first.identifier)[0] == b"TIFF"


def test_byte_capacity_is_checked_before_and_after_writing(tmp_path):
    store = ResultStore(tmp_path, max_bytes=4)
    result = publish(store)
    with pytest.raises(ResultStoreFullError):
        publish(store)
    assert store.read(result.identifier)[0] == b"TIFF"
    other = ResultStore(tmp_path / "other", max_bytes=3)
    with pytest.raises(ResultStoreFullError):
        publish(other)
    assert not list(other.root.glob("*.tif"))
    assert not list(other.root.glob(".work-*"))


def test_single_file_limit_and_empty_output(tmp_path):
    store = ResultStore(tmp_path)

    def oversize(path):
        with path.open("wb") as stream:
            stream.truncate(MAX_RESULT_BYTES + 1)

    with pytest.raises(ResultStoreFullError):
        store.publish(oversize)
    with pytest.raises(ResultStoreError, match="empty"):
        publish(store, b"")


def test_interrupted_writer_does_not_publish_partial_output(tmp_path):
    store = ResultStore(tmp_path)

    def broken(output):
        output.write_bytes(b"partial")
        raise RuntimeError("engine stopped")

    with pytest.raises(RuntimeError):
        store.publish(broken)
    assert not list(tmp_path.glob("*.tif"))
    assert not list(tmp_path.glob(".work-*"))


def test_expiration_is_enforced_and_cleanup_recovers_capacity(tmp_path):
    store = ResultStore(tmp_path, retention_seconds=60, max_results=1)
    result = publish(store)
    path = tmp_path / f"{result.identifier}.tif"
    then = time.time() - 61
    os.utime(path, (then, then))
    with pytest.raises(ResultNotFoundError):
        store.read(result.identifier)
    new = publish(store)
    assert not path.exists()
    assert store.read(new.identifier)[0] == b"TIFF"


def test_cleanup_removes_abandoned_work_but_preserves_unexpired_and_unrelated_files(tmp_path):
    store = ResultStore(tmp_path)
    result = publish(store)
    work = tmp_path / ".work-interrupted"
    work.mkdir()
    (work / "output.tif").write_bytes(b"partial")
    unrelated = tmp_path / "operator-note.txt"
    unrelated.write_text("keep")
    store.cleanup()
    assert not work.exists()
    assert unrelated.read_text() == "keep"
    assert store.read(result.identifier)[0] == b"TIFF"


def test_writer_lock_serializes_workers_without_blocking_downloads(tmp_path):
    first, second = ResultStore(tmp_path), ResultStore(tmp_path)
    result = publish(first)
    with first._writer():
        assert second.read(result.identifier)[0] == b"TIFF"
        with pytest.raises(ResultStoreBusyError):
            publish(second)
    publish(second)


@pytest.mark.parametrize("identifier", ["../secret", "/etc/passwd", "", "a" * 31, "A" * 32, "a" * 32])
def test_invalid_or_missing_results_are_not_found(tmp_path, identifier):
    with pytest.raises(ResultNotFoundError):
        ResultStore(tmp_path).read(identifier)


def test_symlinks_and_special_files_cannot_be_downloaded(tmp_path):
    secret = tmp_path / "secret"
    secret.write_text("private")
    (tmp_path / f"{'a' * 32}.tif").symlink_to(secret)
    store = ResultStore(tmp_path)
    with pytest.raises(ResultNotFoundError):
        store.read("a" * 32)
    os.mkfifo(tmp_path / f"{'b' * 32}.tif")
    with pytest.raises(ResultNotFoundError):
        store.read("b" * 32)


def test_oversized_stored_file_is_not_read(tmp_path):
    path = tmp_path / f"{'a' * 32}.tif"
    with path.open("wb") as stream:
        stream.truncate(MAX_RESULT_BYTES + 1)
    with pytest.raises(ResultStoreError, match="size limit"):
        ResultStore(tmp_path).read("a" * 32)


@pytest.mark.parametrize(
    "settings", [{"retention_seconds": 0}, {"retention_seconds": 604801}, {"max_bytes": 0}, {"max_results": 10001}]
)
def test_invalid_storage_bounds_fail_configuration(tmp_path, settings):
    with pytest.raises(ValueError):
        ResultStore(tmp_path, **settings)


def test_environment_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("GEO_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("GEO_RESULT_RETENTION_SECONDS", "123")
    monkeypatch.setenv("GEO_RESULT_MAX_BYTES", "456")
    monkeypatch.setenv("GEO_RESULT_MAX_COUNT", "7")
    assert ResultStore.from_environment() == ResultStore(tmp_path, 123, 456, 7)


def test_io_failure_is_not_misreported_as_a_missing_result(tmp_path, monkeypatch):
    import errno

    def denied(*args, **kwargs):
        raise PermissionError(errno.EACCES, "/secret/internal/path")

    monkeypatch.setattr("geo_processes.storage.os.open", denied)
    with pytest.raises(ResultStoreError, match="result could not be read") as error:
        ResultStore(tmp_path).read("a" * 32)
    assert not isinstance(error.value, ResultNotFoundError)
    assert "secret" not in str(error.value)
