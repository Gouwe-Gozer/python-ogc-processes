"""OGC exception catalogue and JSON/HTML rendering with compatible legacy codes."""

from dataclasses import dataclass

OGC_EXCEPTIONS = "http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0"
SERVICE_EXCEPTIONS = "https://github.com/Gouwe-Gozer/raster-processes/blob/main/docs/errors.md"


@dataclass(frozen=True)
class ExceptionType:
    uri: str
    title: str


# Use the three prescribed Core URIs; other types describe application policy.
# Do not invent OGC registry entries for those extensions.
EXCEPTIONS = {
    "NoSuchProcess": ExceptionType(f"{OGC_EXCEPTIONS}/no-such-process", "Process not found"),
    "NoSuchJob": ExceptionType(f"{OGC_EXCEPTIONS}/no-such-job", "Job not found"),
    "ResultNotReady": ExceptionType(f"{OGC_EXCEPTIONS}/result-not-ready", "Job results not ready"),
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


def install_exception_renderer(api):
    """Adapt this API instance's errors for JSON/HTML, with any job manager.

    Do not patch upstream classes or infer that an unknown job requires a new
    job store. The same renderer applies to the existing TinyDB diagnostic.
    """
    import json
    import logging

    from flask import has_request_context, render_template_string, request

    upstream = api.get_exception

    def render(status, headers, format_, code, description):
        # pygeoapi 0.24.0 mislabels unknown job status as InvalidParameterValue.
        if (
            status == 404
            and code == "InvalidParameterValue"
            and has_request_context()
            and request.endpoint == "pygeoapi.get_jobs"
            and (request.view_args or {}).get("job_id") is not None
        ):
            code = "NoSuchJob"
        if code not in EXCEPTIONS:
            return upstream(status, headers, format_, code, description)
        logging.getLogger(__name__).error("%s", description)
        document = exception_document(code, description, int(status))
        headers = dict(headers)
        if format_ == "html":
            headers["Content-Type"] = "text/html"
            content = render_template_string(
                '<!doctype html><html lang="en"><head><title>{{ title }}</title></head>'
                "<body><h1>{{ title }}</h1><p>{{ detail }}</p><dl>"
                '<dt>Type</dt><dd><a href="{{ type }}">{{ type }}</a></dd>'
                "<dt>Status</dt><dd>{{ status }}</dd><dt>Code</dt><dd>{{ code }}</dd>"
                "</dl></body></html>",
                **document,
            )
        else:
            headers["Content-Type"] = "application/json"
            content = json.dumps(document, indent=2 if api.pretty_print else None)
        return headers, status, content

    api.get_exception = render
