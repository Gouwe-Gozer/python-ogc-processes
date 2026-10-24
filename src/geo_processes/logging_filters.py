"""Narrow logging compatibility for pygeoapi 0.24.0's metadata locale probes.

Upstream translate_struct() tests data dictionary keys as language tags;
str2locale(silent=True) still warns when Babel rejects them. Keep upstream
translation intact and filter only these known metadata-key diagnostics.
"""

import logging


def _data_keys(value, *, in_data=False):
    if isinstance(value, dict):
        for key, item in value.items():
            if in_data:
                yield key.replace("-", "_").casefold()
            yield from _data_keys(item, in_data=in_data or key in {"schema", "example", "links"})
    elif isinstance(value, list):
        for item in value:
            yield from _data_keys(item, in_data=in_data)


class MetadataLocaleFilter(logging.Filter):
    def __init__(self, metadata):
        super().__init__()
        self.keys = frozenset(key for item in metadata for key in _data_keys(item))

    def filter(self, record):
        # Babel's UnknownLocaleError carries the attempted locale identifier.
        # Only matching metadata-key warnings are filtered; all others pass.
        identifier = getattr(record.msg, "identifier", None)
        return not (
            record.name == "pygeoapi.l10n"
            and record.funcName == "str2locale"
            and record.levelno == logging.WARNING
            and isinstance(identifier, str)
            and identifier.replace("-", "_").casefold() in self.keys
        )


def install_metadata_locale_filter(metadata):
    logger = logging.getLogger("pygeoapi.l10n")
    for installed in tuple(logger.filters):
        if isinstance(installed, MetadataLocaleFilter):
            logger.removeFilter(installed)
    logger.addFilter(MetadataLocaleFilter(metadata))
