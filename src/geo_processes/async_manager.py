"""Durable PostgreSQL handoff around the existing synchronous execution contract."""

import base64
import json
import os
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pygeoapi.process.base import JobNotFoundError, JobResultNotFoundError, ProcessorExecuteError
from pygeoapi.process.manager.postgresql import PostgreSQLManager
from pygeoapi.util import JobStatus, RequestedProcessExecutionMode, json_serial
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from geo_processes.errors import InputBusyError, InvalidExecutionRequestError, exception_document
from geo_processes.manager import OgcSynchronousManager
from geo_processes.responses import STATUS_HEADER
from geo_processes.storage import ResultStore

ADMISSION_LOCK = 184207011
WORKER_LOCK = 184207012


def job_limits():
    values = {}
    for name, default, maximum in (
        ("GEO_JOB_MAX_COUNT", 16, 1000),
        ("GEO_JOB_MAX_BYTES", 67108864, 1073741824),
        ("GEO_JOB_TIMEOUT", 30, 300),
    ):
        value = int(os.environ.get(name, default))
        if not 1 <= value <= maximum:
            raise ValueError(f"{name} must be between 1 and {maximum}")
        values[name] = value
    return values


class DurableProcessManager(PostgreSQLManager):
    """Reuse upstream registration/job metadata, replacing its ephemeral threads.

    Only async calls create retained jobs. Two application-owned TEXT columns
    keep the request and formatted HTTP result on the upstream jobs row. No
    second queue/table, callbacks or in-API execution threads are introduced.
    """

    durable_async = True
    supports_job_list = True

    def __init__(self, manager_def):
        manager_def = deepcopy(manager_def)
        manager_def.setdefault("options", {}).setdefault("pool_pre_ping", True)
        super().__init__(manager_def)
        self.supports_subscribing = False
        self.result_base_url = ""
        self.limits = job_limits()
        self.retention = ResultStore.from_environment().retention_seconds
        quote = self._engine.dialect.identifier_preparer.quote
        self.table = f"{quote(self.table_model.schema)}.{quote(self.table_model.name)}"
        with self._engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": ADMISSION_LOCK})
            for column in ("request", "response"):
                connection.execute(text(f"ALTER TABLE {self.table} ADD COLUMN IF NOT EXISTS {column} TEXT"))

    def _sql(self, statement):
        # Table/schema identifiers are quoted by SQLAlchemy; all values bind.
        return text(statement.replace("{jobs}", self.table))

    @contextmanager
    def _transaction(self):
        try:
            with self._engine.begin() as connection:
                connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": ADMISSION_LOCK})
                yield connection
        except SQLAlchemyError as error:
            raise InputBusyError(user_msg="job database is unavailable") from error

    def _cleanup(self, connection):
        connection.execute(self._sql("DELETE FROM {jobs} WHERE created < :cutoff"), {"cutoff": self.cutoff()})

    def cutoff(self):
        return datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=self.retention)

    def execute_process(
        self,
        process_id,
        data_dict,
        execution_mode=None,
        requested_outputs=None,
        subscriber=None,
        requested_response="raw",
    ):
        if execution_mode != RequestedProcessExecutionMode.respond_async:
            return OgcSynchronousManager.execute_process(
                self, process_id, data_dict, execution_mode, requested_outputs, subscriber, requested_response
            )
        self.get_processor(process_id)  # retain native process registration/errors
        if (
            subscriber is not None
            or not isinstance(requested_response, str)
            or requested_response not in {"raw", "document"}
        ):
            raise InvalidExecutionRequestError("unsupported subscriber or response")
        if not isinstance(data_dict, dict) or (
            requested_outputs is not None and not isinstance(requested_outputs, dict)
        ):
            raise InvalidExecutionRequestError("inputs and outputs must be objects")
        try:
            request = json.dumps(
                {"inputs": data_dict, "outputs": requested_outputs, "response": requested_response}, allow_nan=False
            )
        except (TypeError, ValueError) as error:
            raise InvalidExecutionRequestError("execution inputs must contain finite JSON values") from error
        identifier = uuid4().hex
        now = datetime.now(UTC).replace(tzinfo=None)
        with self._transaction() as connection:
            self._cleanup(connection)
            count, size = connection.execute(
                self._sql(
                    "SELECT count(*), coalesce(sum(octet_length(request) + "
                    "coalesce(octet_length(response), 0) + 4096), 0) FROM {jobs}"
                )
            ).one()
            if (
                count >= self.limits["GEO_JOB_MAX_COUNT"]
                or size + len(request.encode()) + 4096 > self.limits["GEO_JOB_MAX_BYTES"]
            ):
                raise InputBusyError(user_msg="job storage is full; try again after retained jobs expire")
            connection.execute(
                self._sql(
                    "INSERT INTO {jobs} (identifier, process_id, created, updated, status, progress, message, request) "
                    "VALUES (:id, :process, :now, :now, 'accepted', 0, 'Job accepted', :request)"
                ),
                {"id": identifier, "process": process_id, "now": now, "request": request},
            )
        return (
            identifier,
            "application/json",
            {},
            JobStatus.accepted,
            {"Preference-Applied": "respond-async", "Cache-Control": "no-store"},
        )

    def get_job(self, job_id):
        job = super().get_job(job_id)
        if job["created"] < self.cutoff():
            raise JobNotFoundError()
        return job

    def get_jobs(
        self,
        status=None,
        limit=10,
        offset=0,
        *,
        types=None,
        process_ids=None,
        created_range=None,
        min_duration=None,
        max_duration=None,
        now=None,
    ):
        """Filter/page existing rows without loading private requests or results."""
        clauses = ["created >= :cutoff", "type = 'process'"]
        parameters = {"cutoff": self.cutoff(), "limit": limit or 10, "offset": offset or 0}
        if types is not None and "process" not in types:
            clauses.append("FALSE")
        if isinstance(status, JobStatus):
            status = [status.value]
        elif isinstance(status, str):
            status = [status]
        for name, column, values in (("status", "status", status), ("process", "process_id", process_ids)):
            if values is not None:
                placeholders = []
                for index, value in enumerate(values):
                    key = f"{name}_{index}"
                    parameters[key] = value
                    placeholders.append(":" + key)
                clauses.append(f"{column} IN ({', '.join(placeholders)})" if placeholders else "FALSE")
        if created_range:
            for bound, operator, value in zip(("after", "before"), (">=", "<="), created_range, strict=True):
                if value is not None:
                    clauses.append(f"created {operator} :{bound}")
                    parameters[bound] = value
        if min_duration is not None or max_duration is not None:
            parameters["now"] = now or datetime.now(UTC).replace(tzinfo=None)
            duration = (
                "EXTRACT(EPOCH FROM (CASE WHEN status = 'running' THEN :now - started "
                "WHEN status IN ('successful', 'failed', 'dismissed') THEN finished - started END))"
            )
            clauses.append(f"{duration} IS NOT NULL")
            for name, operator, value in (("minimum", ">=", min_duration), ("maximum", "<=", max_duration)):
                if value is not None:
                    clauses.append(f"{duration} {operator} :{name}")
                    parameters[name] = value
        # Only fixed predicates/placeholder names are interpolated; all client values bind.
        where = " AND ".join(clauses)
        projection = "identifier, process_id, status, message, created, started, finished, updated"
        ordering = "ORDER BY created, identifier LIMIT :limit OFFSET :offset"
        query = f"SELECT {projection} FROM {{jobs}} WHERE {where} {ordering}"  # nosec B608
        with self._engine.connect() as connection:
            count = connection.execute(
                self._sql(f"SELECT count(*) FROM {{jobs}} WHERE {where}"),  # nosec B608
                parameters,
            ).scalar_one()
            rows = (
                connection.execute(
                    self._sql(query),
                    parameters,
                )
                if parameters["offset"] < count
                else []
            )
            return {"jobs": [dict(row._mapping) for row in rows], "numberMatched": count}

    def request(self, job_id):
        with self._engine.connect() as connection:
            value = connection.execute(
                self._sql("SELECT request FROM {jobs} WHERE identifier = :id"), {"id": job_id}
            ).scalar_one()
        return json.loads(value)

    def response(self, job_id):
        with self._engine.connect() as connection:
            value = connection.execute(
                self._sql("SELECT response FROM {jobs} WHERE identifier = :id"), {"id": job_id}
            ).scalar_one()
        return json.loads(value) if value else None

    def get_job_result(self, job_id):
        """Preserve the native manager getter; HTTP also needs stored status/headers."""
        job = self.get_job(job_id)
        value = self.response(job_id)
        if job["status"] != "successful" or value is None:
            raise JobResultNotFoundError()
        body = base64.b64decode(value["body"]) if value["binary"] else value["body"]
        return value["media_type"], body

    def claim(self):
        with self._transaction() as connection:
            self._cleanup(connection)
            identifier = connection.execute(
                self._sql(
                    "SELECT identifier FROM {jobs} WHERE status = 'accepted' "
                    "ORDER BY created LIMIT 1 FOR UPDATE SKIP LOCKED"
                )
            ).scalar_one_or_none()
            if identifier:
                connection.execute(
                    self._sql(
                        "UPDATE {jobs} SET status = 'running', started = :now, updated = :now, "
                        "message = 'Job running' WHERE identifier = :id"
                    ),
                    {"id": identifier, "now": datetime.now(UTC).replace(tzinfo=None)},
                )
        return identifier

    def finish(self, job_id, response, *, failed=False):
        # Match HTTP type conversion while retaining strict persisted JSON.
        encoded = json.dumps(response, default=json_serial, allow_nan=False)
        with self._transaction() as connection:
            size = connection.execute(
                self._sql(
                    "SELECT coalesce(sum(octet_length(request) + coalesce(octet_length(response), 0) + 4096), 0) "
                    "FROM {jobs}"
                )
            ).scalar_one()
            if size + len(encoded.encode()) > self.limits["GEO_JOB_MAX_BYTES"]:
                failed = True
                encoded = json.dumps(self.failure(503, "ServerBusy", "job result storage capacity exceeded"))
            connection.execute(
                self._sql(
                    "UPDATE {jobs} SET status = :status, finished = :now, updated = :now, response = :response, "
                    "message = :message WHERE identifier = :id AND status = 'running'"
                ),
                {
                    "id": job_id,
                    "now": datetime.now(UTC).replace(tzinfo=None),
                    "response": encoded,
                    "status": "failed" if failed else "successful",
                    "message": "Job failed" if failed else "Job completed",
                },
            )

    @staticmethod
    def failure(status, code, message):
        return {
            "status": status,
            "media_type": "application/json",
            "headers": {"Cache-Control": "no-store"},
            "body": exception_document(code, message, status),
            "binary": False,
        }

    def fail_interrupted(self):
        # The worker holds the exclusive session lock before invoking this.
        with self._engine.connect() as connection:
            identifiers = list(
                connection.execute(self._sql("SELECT identifier FROM {jobs} WHERE status = 'running'")).scalars()
            )
        for identifier in identifiers:
            self.finish(
                identifier,
                self.failure(500, "NoApplicableCode", "worker interrupted; submit a new execution"),
                failed=True,
            )

    def perform(self, job_id):
        job = self.get_job(job_id)
        document = self.request(job_id)
        try:
            _, media, body, _, headers = OgcSynchronousManager.execute_process(
                self,
                job["process_id"],
                document["inputs"],
                requested_outputs=document["outputs"],
                requested_response=document["response"],
            )
            binary = isinstance(body, bytes)
            self.finish(
                job_id,
                {
                    "status": int(headers.pop(STATUS_HEADER, "200")),
                    "media_type": media,
                    "headers": headers,
                    "body": base64.b64encode(body).decode() if binary else body,
                    "binary": binary,
                },
            )
        except ProcessorExecuteError as error:
            self.finish(
                job_id, self.failure(error.http_status_code, error.ogc_exception_code, error.message), failed=True
            )
