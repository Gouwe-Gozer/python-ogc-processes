# Security policy

Use the repository's private GitHub vulnerability reporting when available.
Include the affected version, reproduction and likely impact without secrets.

The public raster processes accept only the `demo-dem` dataset identifier. It
maps to a fixed bundled GeoTIFF; requests cannot select server paths, remote
URLs, CLI arguments, callbacks or output filenames. No raster data is fetched over
the network. Invalid requests return controlled JSON client errors. Engine
failures return sanitized server errors; detailed errors belong in server logs.

Warp requests select only an approved CRS and nearest/bilinear resampling.
Request bodies are capped at 16 KiB; both info and warp inputs at 16 MiB and
1,048,576 samples including bands. Output dimensions are fixed to the source.
One writer per result volume runs at a time. Outputs have random IDs, bounded
capacity, atomic publication and enforced expiry. Downloads cannot traverse
paths or follow symlinks. A full store rejects new work without evicting
unexpired results. See [result storage](docs/results.md) for lifecycle details.

The release runs non-root, with a read-only root, bounded temporary filesystem,
all capabilities dropped and privilege escalation disabled. The diagnostic
TinyDB/async-echo configuration is for local standards testing only. Authentication,
TLS termination and broader input/resource policies remain deployment decisions.
