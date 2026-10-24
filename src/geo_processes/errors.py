"""JSON exception catalogue; retain legacy codes alongside stable type URIs."""

from dataclasses import dataclass

OGC_EXCEPTIONS = "http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0"
SERVICE_EXCEPTIONS = "https://github.com/Gouwe-Gozer/terrio-processes/blob/main/docs/errors.md"


@dataclass(frozen=True)
class ExceptionType:
    uri: str
    title: str


# Part 1 specifies no-such-process explicitly. The other types describe our
# application policy; do not invent OGC registry entries for these extensions.
EXCEPTIONS = {
    "NoSuchProcess": ExceptionType(f"{OGC_EXCEPTIONS}/no-such-process", "Process not found"),
    "InvalidParameterValue": ExceptionType(f"{SERVICE_EXCEPTIONS}#invalid-parameter-value", "Invalid request"),
    "RequestTooLarge": ExceptionType(f"{SERVICE_EXCEPTIONS}#request-too-large", "Input too large"),
    "ServerBusy": ExceptionType(f"{SERVICE_EXCEPTIONS}#server-busy", "Processing capacity unavailable"),
    "NoSuchResult": ExceptionType(f"{SERVICE_EXCEPTIONS}#no-such-result", "Result not found or expired"),
    "NoApplicableCode": ExceptionType(f"{SERVICE_EXCEPTIONS}#processing-failed", "Processing failed"),
}


def exception_document(code, description, status):
    """Build an OGC exception with RFC problem fields and compatible extras."""
    exception = EXCEPTIONS[code]
    return {
        "type": exception.uri,
        "title": exception.title,
        "status": status,
        "detail": description,
        "code": code,
        "description": description,
    }
