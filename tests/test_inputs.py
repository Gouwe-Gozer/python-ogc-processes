"""User rasters, real HTTPS transport, destination policy and input cleanup."""

import base64
import errno
import socket
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest
import rasterio
from jsonschema import Draft202012Validator
from rasterio.io import MemoryFile

from geo_processes import engine, inputs
from geo_processes.contracts.info import INFO_SCHEMA
from geo_processes.contracts.sources import SOURCE_EXECUTE_SCHEMA


@pytest.fixture(scope="module")
def raster_payload():
    values = np.arange(2 * 48 * 64, dtype="uint16").reshape(2, 48, 64)
    values[0, 0, 0] = 65535
    with MemoryFile() as memory:
        with memory.open(
            driver="GTiff",
            width=64,
            height=48,
            count=2,
            dtype="uint16",
            crs="EPSG:28992",
            transform=rasterio.Affine(10, 0, 155000, 0, -10, 463000),
            nodata=65535,
        ) as raster:
            raster.write(values)
        return memory.read()


def inline(data):
    return {"value": base64.b64encode(data).decode("ascii"), "mediaType": "image/tiff", "encoding": "base64"}


@pytest.fixture(autouse=True)
def input_directory(monkeypatch, tmp_path):
    root = tmp_path / "inputs"
    monkeypatch.setenv("GEO_INPUT_TMPDIR", str(root))
    monkeypatch.delenv("GEO_INPUT_ALLOWED_HOSTS", raising=False)
    return root


@pytest.fixture(scope="module")
def tls_origin(raster_payload):
    seen = {"hosts": [], "sni": [], "paths": []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            try:
                seen["paths"].append(self.path)
                seen["hosts"].append(self.headers.get("Host"))
                if self.path in {"/redirect", "/loop", "/private", "/other-host"}:
                    self.send_response(302)
                    location = {
                        "/redirect": "/dem.tif",
                        "/loop": "/loop",
                        "/private": "https://127.0.0.1/dem.tif",
                        "/other-host": "https://unlisted.test/dem.tif",
                    }
                    self.send_header("Location", location[self.path])
                    self.end_headers()
                    return
                if self.path == "/slow-header":
                    time.sleep(2)
                if self.path == "/missing":
                    self.send_error(404)
                    return
                self.send_response(200)
                if self.path == "/chunked":
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    for start in range(0, len(raster_payload), 257):
                        chunk = raster_payload[start : start + 257]
                        self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                    self.wfile.write(b"0\r\n\r\n")
                    return
                if self.path == "/encoded":
                    self.send_header("Content-Encoding", "gzip")
                length = len(raster_payload)
                if self.path == "/too-large":
                    length = engine.MAX_INPUT_BYTES + 1
                elif self.path == "/truncated":
                    length += 100
                elif self.path == "/invalid-length":
                    length = "invalid"
                self.send_header("Content-Length", str(length))
                self.end_headers()
                if self.path == "/slow-body":
                    for value in raster_payload:
                        self.wfile.write(bytes([value]))
                        self.wfile.flush()
                        time.sleep(0.01)
                elif self.path != "/too-large":
                    self.wfile.write(raster_payload)
            except OSError:
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain("tests/fixtures/tls/source.cert.pem", "tests/fixtures/tls/source.key.pem")
    context.set_servername_callback(lambda _socket, name, _context: seen["sni"].append(name))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_port, seen
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


@pytest.fixture()
def https_origin(tls_origin, monkeypatch):
    port, seen = tls_origin
    dns = socket.getaddrinfo
    connect = socket.create_connection
    create_context = ssl.create_default_context

    def lookup(host, requested_port, *args, **kwargs):
        if host == "raster-source.test":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", requested_port))]
        return dns(host, requested_port, *args, **kwargs)

    def pinned_connection(address, *args, **kwargs):
        if address == ("93.184.216.34", 443):
            return connect(("127.0.0.1", port), *args, **kwargs)
        return connect(address, *args, **kwargs)

    # Only tests map the approved public address to a local TLS fixture. The
    # production resolver has no private-destination bypass or TLS-disable flag.
    monkeypatch.setattr(inputs.socket, "getaddrinfo", lookup)
    monkeypatch.setattr(inputs.socket, "create_connection", pinned_connection)
    monkeypatch.setattr(
        inputs.ssl, "create_default_context", lambda: create_context(cafile="tests/fixtures/tls/source.cert.pem")
    )
    return "https://raster-source.test", seen


@pytest.mark.parametrize(
    "source",
    [
        None,
        True,
        [],
        "https://example.com/a.tif",
        "/etc/passwd",
        {},
        {"href": "file:///etc/passwd"},
        {"href": "http://example.com/a.tif"},
        {"href": "https://user:password@example.com/a.tif"},
        {"href": "https://example.com:8443/a.tif"},
        {"href": "https://example.com/a.tif#part"},
        {"href": "https://example.com/a\nb.tif"},
        {"href": "https://example.com\\@localhost/a.tif"},
        {"href": "https://example.com/a.tif", "value": "anything"},
        {"href": "https://example.com/a.tif", "type": "application/json"},
        {"value": "abcd", "mediaType": "image/tiff"},
        {"value": [], "mediaType": "image/tiff", "encoding": "base64"},
        {"value": "abcd", "mediaType": "image/tiff", "encoding": "gzip"},
    ],
)
def test_unsupported_sources_are_rejected_without_io(source):
    with pytest.raises(inputs.RasterInputError):
        inputs.validate_source(source)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "240.0.0.1",
        "::1",
        "fe80::1",
        "fc00::1",
        "ff02::1",
        "::ffff:127.0.0.1",
        "2002:7f00:0001::",
        "64:ff9b::7f00:1",
    ],
)
def test_nonpublic_or_translated_destinations_are_blocked(monkeypatch, address):
    monkeypatch.setattr(inputs.socket, "getaddrinfo", lambda *_a, **_k: [(0, 0, 0, "", (address, 443))])
    with pytest.raises(inputs.RasterInputError, match="public unicast"):
        inputs._public_addresses("example.test")


def test_mixed_public_private_dns_answers_are_rejected(monkeypatch):
    monkeypatch.setattr(
        inputs.socket,
        "getaddrinfo",
        lambda *_a, **_k: [(0, 0, 0, "", (host, 443)) for host in ("93.184.216.34", "127.0.0.1")],
    )
    with pytest.raises(inputs.RasterInputError):
        inputs._public_addresses("example.test")


@pytest.mark.parametrize("address", ["93.184.216.34", "2606:4700:4700::1111"])
def test_public_addresses_can_be_selected(monkeypatch, address):
    monkeypatch.setattr(inputs.socket, "getaddrinfo", lambda *_a, **_k: [(0, 0, 0, "", (address, 443))])
    assert inputs._public_addresses("example.test") == [address]


def test_inline_source_is_private_and_deleted_after_use(raster_payload, input_directory):
    with inputs.resolve_source(inline(raster_payload)) as path:
        assert path.read_bytes() == raster_payload
        assert path.parent.stat().st_mode & 0o777 == 0o700
        saved = path
    assert not saved.exists()
    assert not list(input_directory.glob("slot-*"))


def test_input_cleanup_on_processing_error(raster_payload, input_directory):
    with pytest.raises(RuntimeError, match="processing failed"), inputs.resolve_source(inline(raster_payload)) as path:
        assert path.exists()
        raise RuntimeError("processing failed")
    assert not list(input_directory.glob("slot-*"))


@pytest.mark.parametrize(
    "data", [b"", b"not a raster", b"II\x2a\x00broken", b'<VRTDataset rasterXSize="2" rasterYSize="2"/>']
)
def test_malformed_inline_files_are_rejected_and_removed(data, input_directory):
    with pytest.raises(inputs.RasterInputError), inputs.resolve_source(inline(data)):
        pytest.fail("invalid raster was accepted")
    assert not list(input_directory.glob("slot-*"))


def test_noncanonical_base64_is_rejected(input_directory):
    with (
        pytest.raises(inputs.RasterInputError, match="base64"),
        inputs.resolve_source(inline(b"data") | {"value": "!!!"}),
    ):
        pytest.fail("invalid base64 was accepted")


def test_encoded_and_decoded_limits_are_enforced(monkeypatch, raster_payload):
    monkeypatch.setattr(inputs, "MAX_ENCODED_BYTES", 3)
    with pytest.raises(inputs.RasterInputTooLargeError):
        inputs.validate_source(inline(raster_payload))
    monkeypatch.setattr(inputs, "MAX_ENCODED_BYTES", 100000)
    monkeypatch.setattr(engine, "MAX_INPUT_BYTES", len(raster_payload) - 1)
    with pytest.raises(inputs.RasterInputTooLargeError), inputs.resolve_source(inline(raster_payload)):
        pytest.fail("oversized decoded input was accepted")


def test_workspace_capacity_and_crash_recovery(input_directory):
    input_directory.mkdir()
    orphan = input_directory / "slot-0"
    orphan.mkdir()
    (orphan / "stale.tif").write_bytes(b"interrupted upload")
    with inputs._workspace() as first, inputs._workspace() as second:
        assert first.parent != second.parent
        assert not (first.parent / "stale.tif").exists()
        with pytest.raises(inputs.RasterInputBusyError), inputs._workspace():
            pytest.fail("third active input was accepted")
    assert not list(input_directory.glob("slot-*"))


def test_https_uses_pinned_address_and_original_tls_host(https_origin, raster_payload):
    origin, seen = https_origin
    source = {"href": origin + "/redirect", "type": "image/tiff"}
    with inputs.resolve_source(source) as path:
        assert path.read_bytes() == raster_payload
    assert seen["hosts"][-1] == "raster-source.test"
    assert seen["sni"][-1] == "raster-source.test"
    assert seen["paths"][-2:] == ["/redirect", "/dem.tif"]


@pytest.mark.parametrize(
    "path, error",
    [
        ("/private", inputs.RasterInputError),
        ("/loop", inputs.RasterInputError),
        ("/missing", inputs.RasterInputError),
        ("/encoded", inputs.RasterInputError),
        ("/truncated", inputs.RasterInputError),
        ("/too-large", inputs.RasterInputTooLargeError),
        ("/invalid-length", inputs.RasterInputError),
    ],
)
def test_https_failures_and_redirect_policies(https_origin, input_directory, path, error):
    origin, _seen = https_origin
    with pytest.raises(error), inputs.resolve_source({"href": origin + path}):
        pytest.fail("invalid source response was accepted")
    assert not list(input_directory.glob("slot-*"))


def test_chunked_https_and_streamed_byte_limit(https_origin, raster_payload, input_directory, monkeypatch):
    origin, _seen = https_origin
    source = {"href": origin + "/chunked"}
    with inputs.resolve_source(source) as path:
        assert path.read_bytes() == raster_payload
    monkeypatch.setattr(engine, "MAX_INPUT_BYTES", len(raster_payload) - 1)
    with pytest.raises(inputs.RasterInputTooLargeError), inputs.resolve_source(source):
        pytest.fail("chunked body exceeded the streaming byte limit")
    assert not list(input_directory.glob("slot-*"))


@pytest.mark.parametrize("path", ["/slow-header", "/slow-body"])
def test_fetch_deadline_interrupts_trickling_peer(https_origin, monkeypatch, path):
    origin, _seen = https_origin
    monkeypatch.setattr(inputs, "FETCH_SECONDS", 0.15)
    started = time.monotonic()
    with pytest.raises(inputs.RasterInputError), inputs.resolve_source({"href": origin + path}):
        pytest.fail("slow input was accepted")
    assert time.monotonic() - started < 1


def test_host_allowlist_is_checked_before_dns(https_origin, monkeypatch):
    origin, _seen = https_origin
    monkeypatch.setenv("GEO_INPUT_ALLOWED_HOSTS", "other.test")
    with (
        pytest.raises(inputs.RasterInputError, match="not allowed"),
        inputs.resolve_source({"href": origin + "/dem.tif"}),
    ):
        pytest.fail("unlisted host was accepted")
    monkeypatch.setenv("GEO_INPUT_ALLOWED_HOSTS", "raster-source.test")
    with inputs.resolve_source({"href": origin + "/dem.tif"}) as path:
        assert path.exists()
    with (
        pytest.raises(inputs.RasterInputError, match="not allowed"),
        inputs.resolve_source({"href": origin + "/other-host"}),
    ):
        pytest.fail("redirect bypassed the deployment hostname allowlist")


def test_certificate_validation_cannot_be_disabled_by_the_client(https_origin, monkeypatch):
    origin, _seen = https_origin
    monkeypatch.setattr(inputs.ssl, "create_default_context", lambda: ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT))
    with pytest.raises(inputs.RasterInputError), inputs.resolve_source({"href": origin + "/dem.tif"}):
        pytest.fail("untrusted TLS certificate was accepted")


@pytest.mark.parametrize("method", ["inline", "href"])
@pytest.mark.parametrize("mode", ["raw", "document"])
def test_user_raster_info_http_contract(http_client, raster_payload, https_origin, method, mode):
    origin, _seen = https_origin
    source = inline(raster_payload) if method == "inline" else {"href": origin + "/dem.tif"}
    Draft202012Validator(SOURCE_EXECUTE_SCHEMA).validate(source)
    response = http_client.post(
        "/processes/raster-info/execution", json={"inputs": {"source": source}, "response": mode}
    )
    assert response.status_code == 200
    info = response.get_json() if mode == "raw" else response.get_json()["info"]["value"]
    Draft202012Validator(INFO_SCHEMA).validate(info)
    assert info["size"] == [64, 48] and info["band_count"] == 2
    assert info["bands"][0]["statistics"]["valid_count"] == 3071
    assert info["crs"]["epsg"] == 28992


@pytest.mark.parametrize("method", ["inline", "href"])
@pytest.mark.parametrize("mode", ["raw", "document"])
@pytest.mark.parametrize("transmission", ["value", "reference"])
def test_user_raster_warp_preserves_response_modes(
    http_client, raster_payload, https_origin, method, mode, transmission
):
    origin, _seen = https_origin
    source = inline(raster_payload) if method == "inline" else {"href": origin + "/dem.tif"}
    response = http_client.post(
        "/processes/raster-warp/execution",
        json={
            "inputs": {"source": source, "target_crs": "EPSG:4326"},
            "response": mode,
            "outputs": {"result": {"transmissionMode": transmission}},
        },
    )
    assert response.status_code == (204 if mode == "raw" and transmission == "reference" else 200)
    if transmission == "reference":
        href = (
            response.headers["Link"].split("<", 1)[1].split(">", 1)[0]
            if mode == "raw"
            else response.get_json()["result"]["href"]
        )
        from urllib.parse import urlsplit

        data = http_client.get(urlsplit(href).path).data
    elif mode == "document":
        data = base64.b64decode(response.get_json()["result"]["value"], validate=True)
    else:
        data = response.data
    with MemoryFile(data) as memory, memory.open() as raster:
        assert raster.shape == (48, 64) and raster.count == 2
        assert raster.crs.to_epsg() == 4326 and raster.nodata == 65535
        assert raster.read(masked=True).count() > 0


@pytest.mark.parametrize("process", ["raster-info", "raster-warp"])
def test_input_errors_are_typed_http_responses(http_client, raster_payload, monkeypatch, process):
    payload = (
        {"inputs": {"source": inline(b"invalid"), "target_crs": "EPSG:4326"}}
        if process == "raster-warp"
        else {"inputs": {"source": inline(b"invalid")}}
    )
    response = http_client.post(f"/processes/{process}/execution", json=payload)
    assert response.status_code == 400 and response.is_json
    payload["inputs"]["source"] = inline(raster_payload)
    with inputs._workspace(), inputs._workspace():
        assert http_client.post(f"/processes/{process}/execution", json=payload).status_code == 503
    monkeypatch.setattr(engine, "MAX_INPUT_BYTES", 10)
    assert http_client.post(f"/processes/{process}/execution", json=payload).status_code == 413


def test_fetch_storage_fault_is_a_server_failure(monkeypatch, http_client):
    def fail(*_args):
        raise OSError(errno.ENOSPC, "/private/input/storage")

    monkeypatch.setattr(inputs, "_fetch", fail)
    response = http_client.post(
        "/processes/raster-info/execution", json={"inputs": {"source": {"href": "https://example.com/a.tif"}}}
    )
    assert response.status_code == 500
    assert "private" not in response.text


def test_invalid_output_options_never_fetch_rasters(monkeypatch, http_client):
    def forbidden(*_args, **_kwargs):
        pytest.fail("invalid outputs must be rejected before fetching")

    monkeypatch.setattr(inputs, "_fetch", forbidden)
    response = http_client.post(
        "/processes/raster-info/execution",
        json={"inputs": {"source": {"href": "https://example.com/a.tif"}}, "outputs": {"bad": {}}},
    )
    assert response.status_code == 400


def test_source_schema_describes_values_separately_from_wire_wrappers(http_client):
    description = http_client.get("/processes/raster-info?f=json").get_json()
    assert description["inputs"]["source"]["schema"]["anyOf"][1]["contentMediaType"] == "image/tiff"
    operation = http_client.get("/openapi?f=json").get_json()["paths"]["/processes/raster-info/execution"]["post"]
    assert "503" in operation["responses"]
    wire = operation["requestBody"]["content"]["application/json"]["schema"]
    assert len(wire["properties"]["inputs"]["properties"]["source"]["oneOf"]) == 3


def test_engine_driver_restriction_prevents_vrt_dispatch(tmp_path):
    source = tmp_path / "fake.tif"
    source.write_text(
        '<VRTDataset rasterXSize="2" rasterYSize="2"><VRTRasterBand dataType="Byte" band="1"/></VRTDataset>'
    )
    with pytest.raises(engine.RasterValidationError):
        engine.validate_raster(source)


def test_block_decode_budget_is_checked_before_pixel_read(monkeypatch, raster_payload):
    monkeypatch.setattr(engine, "MAX_BLOCK_BYTES", 1)
    with pytest.raises(inputs.RasterInputError), inputs.resolve_source(inline(raster_payload)):
        pytest.fail("oversized raster blocks were accepted")


def test_dns_host_is_not_resolved_again_when_connecting(https_origin, monkeypatch):
    origin, _seen = https_origin
    original = inputs.socket.getaddrinfo
    lookups = []

    def rebind(host, port, *args, **kwargs):
        if host == "raster-source.test":
            lookups.append(host)
            address = "93.184.216.34" if len(lookups) == 1 else "127.0.0.1"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]
        return original(host, port, *args, **kwargs)

    monkeypatch.setattr(inputs.socket, "getaddrinfo", rebind)
    with inputs.resolve_source({"href": origin + "/dem.tif"}) as path:
        assert path.exists()
    assert len(lookups) == 1


def test_ambient_proxy_variables_do_not_bypass_the_connection_policy(https_origin, monkeypatch):
    origin, _seen = https_origin
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")
    with inputs.resolve_source({"href": origin + "/dem.tif"}) as path:
        assert path.exists()


def test_missing_crs_is_a_client_error_for_user_warp(http_client):
    with MemoryFile() as memory:
        with memory.open(
            driver="GTiff", width=2, height=2, count=1, dtype="uint8", transform=rasterio.Affine(10, 0, 1, 0, -10, 1)
        ) as raster:
            raster.write(np.ones((1, 2, 2), dtype="uint8"))
        source = inline(memory.read())
    info = http_client.post("/processes/raster-info/execution", json={"inputs": {"source": source}})
    assert info.status_code == 200 and info.get_json()["crs"] is None
    warp = http_client.post(
        "/processes/raster-warp/execution", json={"inputs": {"source": source, "target_crs": "EPSG:4326"}}
    )
    assert warp.status_code == 400 and "CRS" in warp.get_json()["description"]
