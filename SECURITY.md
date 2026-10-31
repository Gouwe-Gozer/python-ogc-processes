# Security policy

Use the repository's private GitHub vulnerability reporting when available.
Include the affected version, reproduction and likely impact without secrets.

## Input and processing boundary

Public raster inputs are inline base64 or controlled public HTTPS references.
Requests cannot select server paths, CLI arguments, callbacks or output filenames.
HTTPS uses verified TLS, pinned public addresses, bounded downloads, redirect
checks and no ambient proxies. An optional exact-host allowlist narrows destinations.
Private/loopback/link-local addresses, credentials and alternate ports are rejected.
GDAL receives staged local files; only GTiff reads are enabled, sidecars/PAM are
disabled and PROJ networking is off. See [input policy](docs/inputs.md).

Requests are capped at 24 MiB, rasters at 16 MiB and 1,048,576 samples including
bands. Operation-specific bounds cover points, class intervals and polygonization;
warp retains input grid dimensions. Two locked input slots apply per shared input
directory. Compose gives API and worker separate `/tmp` filesystems, so these
slots are per container, not a service-wide two-job quota.

One writer per shared result volume publishes atomically under random IDs.
Quotas/expiry apply without evicting unexpired results. Downloads reject unsafe
paths, symlinks and invalid IDs. Handled failures clean temporary inputs; slot
reuse cleans inputs abandoned by killed processes. See [result storage](docs/results.md).

## Jobs and deployment

The default API/PostgreSQL/worker stack has bounded admission, payload retention
and execution deadlines. Interrupted jobs fail explicitly rather than retrying
automatically. Stored requests can contain input data and signed source URLs;
protect the database and its backups accordingly. See [async lifecycle and
limits](docs/asynchronous-execution.md).

There is **no built-in authentication or per-user authorization**. Job IDs and
status metadata are discoverable through `/jobs`; known job IDs expose their
status/results, and published file links remain accessible until expiry. Protect
all routes consistently if data or metadata must be private. Input SSRF protection
does not provide user access control.

Development and release API/worker services share non-root execution, a read-only
root, bounded tmpfs/memory/CPU/processes, dropped capabilities and disabled
privilege escalation. PostgreSQL uses a separate persistent volume and has no
published host port. Replace the local-only default password before hosted use.
Authentication, TLS termination, egress policy, backups and monitoring remain
deployment responsibilities; see [release deployment](docs/release-image.md).

Custom Python processors are **trusted installed code**. A worker process is not
a sandbox for untrusted code uploads. Keep dataset handles and temporary files
independent per execution, validate resource usage and sanitize unexpected errors.
The TinyDB/async-echo configuration is an isolated compatibility diagnostic,
not the default job deployment.
