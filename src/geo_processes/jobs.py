"""Small HTTP adapter for persisted, already-formatted job responses."""

import base64
from datetime import UTC

from flask import jsonify, make_response
from pygeoapi.process.base import JobNotFoundError
from sqlalchemy.exc import SQLAlchemyError

from geo_processes.errors import exception_document


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
            response = make_response(jsonify(body) if not stored["binary"] else body, stored["status"])
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
        response = jsonify(document)
        response.headers["Cache-Control"] = "no-store"
        return response
    except JobNotFoundError:
        return jsonify(exception_document("NoSuchJob", "job not found or expired", 404)), 404
    except SQLAlchemyError:
        return jsonify(exception_document("ServerBusy", "job database is unavailable", 503)), 503
