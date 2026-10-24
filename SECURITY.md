# Security policy

Use the repository's private GitHub vulnerability reporting when available.
Include the affected version, reproduction and likely impact without secrets.

The public processes accept qualified base64 GeoTIFFs, controlled HTTPS references
and the bundled `demo-dem`. Requests cannot select server paths, CLI arguments,
callbacks or output filenames. HTTPS uses verified TLS, pinned public addresses,
bounded downloads, redirect checks and no ambient proxies. An optional exact-host
allowlist narrows destinations. Private/loopback/link-local addresses, URL
credentials and alternate ports are rejected. GDAL receives private local files;
sidecars/PAM are disabled, the driver is restricted to GTiff and PROJ networking
is disabled. Invalid requests return controlled JSON client errors. Engine
failures return sanitized server errors; detailed errors belong in server logs.

Warp requests select only an approved CRS and nearest/bilinear resampling.
Request bodies are capped at 24 MiB; both info and warp inputs at 16 MiB and
1,048,576 samples including bands. Output dimensions are fixed to the source.
One writer per result volume runs at a time. Outputs have random IDs, bounded
capacity, atomic publication and enforced expiry. Downloads cannot traverse
paths or follow symlinks. A full store rejects new work without evicting
unexpired results. See [result storage](docs/results.md) for lifecycle details.

Two locked, private temporary input slots bound staged files across workers.
Handled requests remove them; slot reuse removes files left by killed workers.
They use the bounded tmpfs independently of persistent output retention. The
[input policy](docs/inputs.md) describes limits and remaining deployment needs.

The release runs non-root, with a read-only root, bounded temporary filesystem,
all capabilities dropped and privilege escalation disabled. The diagnostic
TinyDB/async-echo configuration is for local standards testing only. Authentication,
TLS termination and broader input/resource policies remain deployment decisions.
