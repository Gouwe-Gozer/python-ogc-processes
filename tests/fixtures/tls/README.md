# HTTPS test fixture

`source.cert.pem` and `source.key.pem` are a public, self-signed certificate/key
pair for the reserved test hostname `raster-source.test`. The key is test data,
not a deployment credential. Never use this certificate/key for a live service.

The tests trust this certificate only in their own SSL context, map a simulated
public address to a loopback TLS server, and verify original-host SNI and Host
headers. Production has no TLS-verification or private-address bypass flag.
The fixtures were generated for this repository on 2026-10-24 with OpenSSL and
are valid for ten years; they contain no third-party raster data.
