"""Resolve bounded GeoTIFF inputs without giving GDAL client-controlled URLs."""

import base64
import binascii
import errno
import fcntl
import ipaddress
import json
import os
import re
import shutil
import socket
import ssl
import threading
import time
from collections.abc import Mapping
from contextlib import contextmanager, suppress
from http.client import HTTPException, HTTPSConnection
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from geo_processes import engine

MAX_ENCODED_BYTES = 4 * ((engine.MAX_INPUT_BYTES + 2) // 3)
MAX_EXECUTION_BYTES = 24 * 1024 * 1024
MAX_URL_LENGTH = 4096
MAX_SCALAR_BYTES = 4096
SCALAR_MEDIA_TYPES = ("application/json", "text/plain")
LINK_METADATA = {"rel", "title", "hreflang"}
FETCH_SECONDS = 10
IO_TIMEOUT = 3
MAX_REDIRECTS = 3
INPUT_SLOTS = 2
MEDIA_TYPES = ("image/tiff", "application/tiff", "application/tiff; application=geotiff")
TIFF_HEADERS = (b"II\x2a\x00", b"MM\x00\x2a", b"II\x2b\x00", b"MM\x00\x2b")


class RasterInputError(ValueError):
    """The supplied raster or input reference is unsupported or invalid."""


class RasterInputTooLargeError(RasterInputError):
    """Encoded or downloaded raster data exceeds the input byte limit."""


class RasterInputBusyError(RuntimeError):
    """All bounded temporary input workspaces are currently occupied."""


class RasterInputStorageError(RuntimeError):
    """Temporary input storage failed independently of the client's data."""


def _url_parts(url):
    if not isinstance(url, str) or not 1 <= len(url) <= MAX_URL_LENGTH:
        raise RasterInputError("source href must be an HTTPS URL of at most 4096 characters")
    if any(ord(char) <= 32 or ord(char) >= 127 for char in url) or "\\" in url:
        raise RasterInputError("source href must be an ASCII URI without whitespace or backslashes")
    try:
        parts = urlsplit(url)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.port not in {None, 443}
            or parts.username is not None
            or parts.password is not None
            or parts.fragment
            or "%" in parts.hostname
        ):
            raise ValueError("unsupported URL")
    except ValueError as error:
        raise RasterInputError("source href must use HTTPS port 443 without credentials or a fragment") from error
    return parts


def validate_source(source):
    """Validate the wire shape without decoding data, accessing disk or fetching."""
    if isinstance(source, str):
        if len(source) > MAX_ENCODED_BYTES:
            raise RasterInputTooLargeError("source exceeds the 16 MiB input limit")
        if len(source) % 4 or re.fullmatch(r"[A-Za-z0-9+/]*={0,2}", source) is None:
            raise RasterInputError("inline source must be a base64 string")
        return
    if not isinstance(source, Mapping):
        raise RasterInputError("source must be an HTTPS reference or an inline base64 GeoTIFF")
    if "href" in source:
        _validate_reference(source, MEDIA_TYPES, "image/tiff")
    elif set(source) == {"value", "mediaType", "encoding"}:
        if source["mediaType"] not in MEDIA_TYPES or source["encoding"] != "base64":
            raise RasterInputError("inline source requires a GeoTIFF mediaType and base64 encoding")
        if not isinstance(source["value"], str):
            raise RasterInputError("inline source value must be a base64 string")
        if len(source["value"]) > MAX_ENCODED_BYTES:
            raise RasterInputTooLargeError("source exceeds the 16 MiB input limit")
    else:
        raise RasterInputError("source must contain href or value/mediaType/encoding")


def _validate_reference(value, media_types, default_type):
    if (
        set(value) - {"href", "type"} - LINK_METADATA
        or value.get("type", default_type) not in media_types
        or any(not isinstance(item, str) for item in value.values())
    ):
        raise RasterInputError("reference requires href, a supported type and optional string link metadata")
    _url_parts(value["href"])


def _public_addresses(host):
    answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
    if not addresses:
        raise RasterInputError("source hostname did not resolve")
    for address in addresses:
        parsed = ipaddress.ip_address(address)
        if (
            not parsed.is_global
            or parsed.is_multicast
            or parsed.is_reserved
            or isinstance(parsed, ipaddress.IPv6Address)
            and (
                parsed.ipv4_mapped is not None
                or parsed.sixtofour is not None
                or parsed.teredo is not None
                or parsed in ipaddress.ip_network("64:ff9b::/96")
                or parsed in ipaddress.ip_network("64:ff9b:1::/48")
            )
        ):
            raise RasterInputError("source hostname must resolve exclusively to public unicast addresses")
    return addresses


class _PinnedHTTPSConnection(HTTPSConnection):
    """Connect to a validated IP while verifying TLS against the original host."""

    def __init__(self, host, address, timeout):
        super().__init__(host, port=443, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        self.sock = socket.create_connection((self.address, 443), self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)
        self.transport = self.sock


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("input fetch deadline reached")
    return min(IO_TIMEOUT, remaining)


def _abort(connection):
    # A deadline must also interrupt a peer that trickles headers or body bytes.
    transport = getattr(connection, "transport", connection.sock)
    if transport is not None:
        with suppress(OSError):
            transport.shutdown(socket.SHUT_RDWR)
    connection.close()


def _fetch(url, destination, *, max_bytes=None, media_types=MEDIA_TYPES):
    """Shared HTTPS transport for raster and scalar references."""
    limit = engine.MAX_INPUT_BYTES if max_bytes is None else max_bytes
    too_large = "source exceeds the 16 MiB input limit" if max_bytes is None else "scalar reference exceeds 4096 bytes"
    deadline = time.monotonic() + FETCH_SECONDS
    for redirect in range(MAX_REDIRECTS + 1):
        parts = _url_parts(url)
        host = parts.hostname.rstrip(".").lower()
        allowed = {
            item.strip().lower().rstrip(".")
            for item in os.environ.get("GEO_INPUT_ALLOWED_HOSTS", "").split(",")
            if item.strip()
        }
        if allowed and host not in allowed:
            raise RasterInputError("source hostname is not allowed by this deployment")
        addresses = _public_addresses(host)
        connection = _PinnedHTTPSConnection(host, addresses[0], _remaining(deadline))
        timer = threading.Timer(max(0, deadline - time.monotonic()), _abort, args=(connection,))
        timer.daemon = True
        timer.start()
        try:
            path = parts.path or "/"
            if parts.query:
                path += "?" + parts.query
            connection.request("GET", path, headers={"Accept": ", ".join(media_types), "Accept-Encoding": "identity"})
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location or redirect == MAX_REDIRECTS:
                    raise RasterInputError("source redirect limit exceeded or Location is missing")
                url = urljoin(url, location)
                continue
            if response.status != 200 or response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise RasterInputError("source must return HTTP 200 without content encoding")
            length = response.getheader("Content-Length")
            expected = int(length) if length is not None else None
            if expected is not None and expected < 0:
                raise RasterInputError("source returned an invalid content length")
            if expected is not None and expected > limit:
                raise RasterInputTooLargeError(too_large)
            count = 0
            with destination.open("wb") as output:
                while True:
                    timeout = _remaining(deadline)
                    if connection.sock is not None:
                        connection.sock.settimeout(timeout)
                    chunk = response.read1(64 * 1024)
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > limit:
                        raise RasterInputTooLargeError(too_large)
                    output.write(chunk)
            _remaining(deadline)
            if expected is not None and count != expected:
                raise RasterInputError("source download was incomplete")
            return response.getheader("Content-Type")
        finally:
            timer.cancel()
            connection.close()


def _download(url, destination, **options):
    """Keep transport failures separate from local storage failures."""
    try:
        return _fetch(url, destination, **options)
    except (HTTPException, OSError, ValueError) as error:
        if isinstance(error, RasterInputError):
            raise
        if isinstance(error, OSError) and error.errno in {
            errno.ENOSPC,
            errno.EDQUOT,
            errno.EIO,
            errno.EACCES,
            errno.EROFS,
            errno.ENOENT,
            errno.ENOTDIR,
            errno.EISDIR,
        }:
            raise RasterInputStorageError("temporary input storage failed") from error
        raise RasterInputError("input HTTPS download failed") from error


def resolve_scalar(value, *, name, choices):
    """Resolve one string input, then validate its value (Core req. 18/24)."""
    if isinstance(value, Mapping):
        if "href" in value:
            _validate_reference(value, SCALAR_MEDIA_TYPES, "application/json")
            with _workspace() as destination:
                content_type = _download(
                    value["href"], destination, max_bytes=MAX_SCALAR_BYTES, media_types=SCALAR_MEDIA_TYPES
                )
                media_type = (content_type or value.get("type", "application/json")).split(";", 1)[0].strip().lower()
                if media_type not in SCALAR_MEDIA_TYPES or value.get("type", media_type) != media_type:
                    raise RasterInputError(f"{name} reference must return its supported JSON or plain-text type")
                try:
                    text = destination.read_bytes().decode("utf-8")
                    value = json.loads(text) if media_type == "application/json" else text.strip()
                except (UnicodeError, ValueError) as error:
                    raise RasterInputError(f"{name} reference is not valid UTF-8 JSON/text") from error
        elif "value" in value and not set(value) - {"value", "mediaType"}:
            if value.get("mediaType", "application/json") not in SCALAR_MEDIA_TYPES:
                raise RasterInputError(f"{name} qualified value has an unsupported media type")
            value = value["value"]
    if not isinstance(value, str) or value not in choices:
        raise RasterInputError(f"{name} must be one of: {', '.join(choices)}")
    return value


@contextmanager
def _workspace():
    root = Path(os.environ.get("GEO_INPUT_TMPDIR", "runtime-data/inputs"))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    for slot in range(INPUT_SLOTS):
        with (root / f".slot-{slot}.lock").open("a+b") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                continue
            workspace = root / f"slot-{slot}"
            try:
                if workspace.exists():
                    shutil.rmtree(workspace)
                workspace.mkdir(mode=0o700)
                yield workspace / "input.tif"
            finally:
                if workspace.exists():
                    shutil.rmtree(workspace)
            return
    raise RasterInputBusyError("temporary raster input capacity is busy; retry later")


@contextmanager
def resolve_source(source, *, require_crs=False):
    """Stage, validate, use and discard one raster, including on handled errors."""
    validate_source(source)
    with _workspace() as destination:
        if isinstance(source, Mapping) and "href" in source:
            _download(source["href"], destination)
        else:
            try:
                data = base64.b64decode(source if isinstance(source, str) else source["value"], validate=True)
            except (ValueError, binascii.Error) as error:
                raise RasterInputError("source value is not valid base64") from error
            if len(data) > engine.MAX_INPUT_BYTES:
                raise RasterInputTooLargeError("source exceeds the 16 MiB input limit")
            destination.write_bytes(data)
        with destination.open("rb") as data:
            if data.read(4) not in TIFF_HEADERS:
                raise RasterInputError("source must contain a self-contained GeoTIFF")
        try:
            engine.validate_raster(destination, require_crs=require_crs)
        except engine.RasterValidationError as error:
            raise RasterInputError(str(error)) from error
        yield destination
