"""Small HTTP adapter for persisted, already-formatted job responses."""

import base64
from datetime import UTC

from flask import jsonify, make_response
from pygeoapi.process.base import JobNotFoundError
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
        return jsonify(document)
    except JobNotFoundError:
        return jsonify(exception_document("NoSuchJob", "job not found or expired", 404)), 404
    except SQLAlchemyError:
        return jsonify(exception_document("ServerBusy", "job database is unavailable", 503)), 503
