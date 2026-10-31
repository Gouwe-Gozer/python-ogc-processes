"""Small HTTP adapter for persisted, already-formatted job responses."""

import base64
import re
from datetime import UTC, datetime
from urllib.parse import urlencode

from flask import jsonify, make_response
from pygeoapi.api import evaluate_limit
from pygeoapi.process.base import JobNotFoundError
from pygeoapi.util import render_j2_template
from sqlalchemy.exc import SQLAlchemyError

from geo_processes.errors import exception_document
from geo_processes.responses import htmlsafe_json


def job_response(api, identifier, *, results=False):
    manager = api.manager
    try:
        job = manager.get_job(identifier)
        if results:
            if job["status"] in {"accepted", "running"}:
                return jsonify(exception_document("ResultNotReady", "job results are not ready", 404)), 404
            stored = manager.response(identifier)
            if stored is None:
                return jsonify(exception_document("NoApplicableCode", "stored job response is unavailable", 500)), 500
            body = base64.b64decode(stored["body"]) if stored["binary"] else stored["body"]
            # Match synchronous rendering: native strings pass through; JSON values are encoded.
            if not stored["binary"] and (stored["media_type"] == "application/json" or not isinstance(body, str)):
                body = htmlsafe_json(body)
            response = make_response(body, stored["status"])
            response.headers.update(stored["headers"])
            if stored["status"] == 204:
                response.headers.pop("Content-Type", None)
            else:
                response.headers["Content-Type"] = stored["media_type"]
            return response
        return jsonify(status_document(api, job))
    except JobNotFoundError:
        return jsonify(exception_document("NoSuchJob", "job not found or expired", 404)), 404
    except SQLAlchemyError:
        return jsonify(exception_document("ServerBusy", "job database is unavailable", 503)), 503


def status_document(api, job):
    """Public status fields only; never serialize persisted requests or results."""
    identifier = job["identifier"]
    document = {
        "jobID": identifier,
        "processID": job["process_id"],
        "type": "process",
        "status": job["status"],
        "message": job["message"],
    }
    for field in ("created", "started", "finished", "updated"):
        if job[field] is not None:
            document[field] = job[field].replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
    document["links"] = [{"rel": "self", "href": f"{api.base_url}/jobs/{identifier}", "type": "application/json"}]
    if job["status"] in {"accepted", "running"}:
        document["links"].append(
            {"rel": "monitor", "href": f"{api.base_url}/jobs/{identifier}", "type": "application/json"}
        )
    if job["status"] in {"successful", "failed"}:
        document["links"].append(
            {
                "rel": "http://www.opengis.net/def/rel/ogc/1.0/results",
                "href": f"{api.base_url}/jobs/{identifier}/results",
            }
        )
    return document


def job_filters(parameters):
    """Decode Section 11 query parameters; SQL values remain bound by the manager."""
    allowed = {"f", "limit", "offset", "type", "processID", "status", "datetime", "minDuration", "maxDuration"}
    if set(parameters) - allowed:
        raise ValueError("unsupported job-list query parameter")
    for name in ("f", "limit", "offset", "datetime"):
        if len(parameters.getlist(name)) > 1:
            raise ValueError(f"{name} must occur once")
    for name in ("limit", "offset"):
        if name in parameters and re.fullmatch(r"[0-9]+", parameters[name]) is None:
            raise ValueError(f"{name} must be a nonnegative integer")

    def values(name, *, integers=False):
        if name not in parameters:
            return None
        items = [part.strip() for value in parameters.getlist(name) for part in value.split(",")]
        if any(not item or (integers and re.fullmatch(r"[+-]?[0-9]+", item) is None) for item in items):
            raise ValueError(f"{name} must contain {'integer seconds' if integers else 'nonempty values'}")
        return [int(item) for item in items] if integers else items

    minimum = values("minDuration", integers=True)
    maximum = values("maxDuration", integers=True)
    return {
        "types": values("type"),
        "process_ids": values("processID"),
        "status": values("status"),
        "created_range": datetime_range(parameters["datetime"]) if "datetime" in parameters else None,
        # Every supplied bound applies: strongest minimum and strongest maximum.
        "min_duration": max(minimum) if minimum else None,
        "max_duration": min(maximum) if maximum else None,
    }


def datetime_range(value):
    """RFC 3339 instant or closed/open interval, normalized to the UTC job table."""

    def instant(text):
        if (
            re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})",
                text,
            )
            is None
        ):
            raise ValueError("datetime must contain RFC 3339 timestamps with a timezone")
        return datetime.fromisoformat(text.upper()).astimezone(UTC).replace(tzinfo=None)

    parts = value.split("/")
    if len(parts) == 1:
        start = end = instant(parts[0])
    elif len(parts) == 2:
        start, end = (None if part in {"", ".."} else instant(part) for part in parts)
        if start is None and end is None:
            raise ValueError("datetime interval requires at least one timestamp")
    else:
        raise ValueError("datetime must be an instant or interval")
    if start is not None and end is not None and start > end:
        raise ValueError("datetime interval starts after it ends")
    return start, end


def job_list(api, request):
    """List retained jobs through the existing API formats and HTML template."""
    headers = request.get_response_headers(**api.api_headers)
    headers["Cache-Control"] = "no-store"
    if request.format not in {None, "json", "html"}:
        return api.get_format_exception(request)
    try:
        filters = job_filters(request.params)
        limit = evaluate_limit(request.params.get("limit"), api.config["server"].get("limits", {}), {})
        offset = int(request.params.get("offset", 0))
        if offset < 0:
            raise ValueError("offset must be nonnegative")
        result = api.manager.get_jobs(limit=limit, offset=offset, now=datetime.now(UTC).replace(tzinfo=None), **filters)
    except (ValueError, OverflowError) as error:
        return api.get_exception(400, headers, request.format, "InvalidParameterValue", str(error))
    except SQLAlchemyError:
        return api.get_exception(503, headers, request.format, "ServerBusy", "job database is unavailable")
    format_ = request.format or "json"

    def link(encoding, relation, page_offset=offset):
        arguments = [
            (key, value) for key, value in request.params.items(multi=True) if key not in {"f", "limit", "offset"}
        ]
        arguments += [("f", encoding), ("limit", limit), ("offset", page_offset)]
        return {
            "rel": relation,
            "type": "text/html" if encoding == "html" else "application/json",
            "href": f"{api.base_url}/jobs?{urlencode(arguments)}",
        }

    links = [link(format_, "self"), link("html" if format_ == "json" else "json", "alternate")]
    if offset + limit < result["numberMatched"]:
        links.append(link(format_, "next", offset + limit))
    if offset:
        links.append(link(format_, "prev", max(0, offset - limit)))
    document = {"jobs": [status_document(api, row) for row in result["jobs"]], "links": links}
    if format_ == "html":
        # The upstream template requires progress; it is not part of our JSON contract.
        body = render_j2_template(
            api.tpl_config,
            api.config["server"]["templates"],
            "jobs/index.html",
            {
                "jobs": {**document, "jobs": [{**job, "progress": 0} for job in document["jobs"]]},
                "links": links,
                "offset": offset,
                "now": datetime.now(UTC).isoformat(),
            },
            request.locale,
        )
    else:
        body = htmlsafe_json(document, pretty=api.pretty_print)
    headers["Link"] = ", ".join(f'<{item["href"]}>; rel="{item["rel"]}"; type="{item["type"]}"' for item in links)
    return headers, 200, body
