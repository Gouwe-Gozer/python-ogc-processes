# Security policy

Use the repository's private GitHub vulnerability reporting when available.
Include the affected version, reproduction and likely impact without secrets.

The initial public process accepts only the `demo-dem` dataset identifier. It
maps to a fixed bundled GeoTIFF; requests cannot select server paths, remote
URLs, CLI arguments, callbacks or output files. No raster data is fetched over
the network. Invalid requests return controlled JSON client errors. Engine
failures return sanitized server errors; detailed errors belong in server logs.

The release runs non-root, with a read-only root, bounded temporary filesystem,
all capabilities dropped and privilege escalation disabled. The diagnostic
TinyDB/async-echo configuration is for local standards testing only. Authentication,
TLS termination and broader input/resource policies remain deployment decisions.
