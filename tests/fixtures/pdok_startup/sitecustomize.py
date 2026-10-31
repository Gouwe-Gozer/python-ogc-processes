"""Test-only Python startup hook, mounted solely by opt-in container tests.

Mock the supplied algorithm's fixed PDOK transport in API and spawned worker
children. Production configuration/images never enable or copy this hook.
"""

import requests
from terrain_pdok import fake_pdok_get

_original_get = requests.get


def _get(url, *args, **kwargs):
    if url.startswith("https://api.pdok.nl/lv/bgt/ogc/v1/collections/"):
        return fake_pdok_get(url, **kwargs)
    return _original_get(url, *args, **kwargs)


requests.get = _get
