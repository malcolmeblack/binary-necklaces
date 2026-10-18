"""API Gateway job endpoint and asynchronous analysis worker.

Only API Gateway invokes api_handler. Only the API role may invoke worker_handler.
The browser never receives the S3 key, question, token hash, or model context.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
import uuid

from runtime import Runtime, IncompleteAnswer, bounded_int, bundled_reference

JOB_ID = re.compile(r"[a-f0-9]{32}\Z")
API_PATH = "/api/chatbot"
MAX_REQUEST_BYTES = 16_384
MAX_RECORD_BYTES = 196_608


def _client(service, *, api=False):
    import boto3
    from botocore.config import Config
    return boto3.client(service, config=Config(
        connect_timeout=1 if api else 3,
        read_timeout=2 if api else 8,
        retries={"total_max_attempts": 1 if api else 2}))


def _log_error(event, exc):
    fields = {"event": event, "kind": type(exc).__name__}
    code = getattr(exc, "response", {}).get("Error", {}).get("Code")
    if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", code):
        fields["code"] = code
    # SDK error messages and request metadata can contain user input. Only retain
    # the service's bounded identifier (for example AccessDeniedException).
    print(json.dumps(fields))


class Store:
    def __init__(self, client=None, *, api=False):
        self.client = client or _client("s3", api=api)
        self.bucket = os.environ["JOBS_BUCKET"]
        self.prefix = os.environ.get("JOBS_PREFIX", "binary-necklaces/chatbot/jobs/").strip("/")
        if not self.prefix:
            raise ValueError("JOBS_PREFIX must not be empty")
        self.prefix += "/"

    def read(self, job_id):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=f"{self.prefix}{job_id}.json")
        except Exception as exc:
            if getattr(exc, "response", {}).get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise
        stream = response["Body"]
        try:
            raw = stream.read(MAX_RECORD_BYTES + 1)
        finally:
            stream.close()
        if len(raw) > MAX_RECORD_BYTES:
            raise RuntimeError("The stored job exceeded its limit")
        return json.loads(raw)

    def write(self, record, *, create=False):
        raw = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(raw) > MAX_RECORD_BYTES:
            raise RuntimeError("The job exceeded its storage limit")
        options = {"IfNoneMatch": "*"} if create else {}
        self.client.put_object(Bucket=self.bucket, Key=f"{self.prefix}{record['jobId']}.json",
                               Body=raw, ContentType="application/json", ServerSideEncryption="AES256", **options)

    def claim(self, job_id):
        try:
            self.client.put_object(Bucket=self.bucket, Key=f"{self.prefix}{job_id}.claim",
                                   Body=b"{}", ContentType="application/json", ServerSideEncryption="AES256",
                                   IfNoneMatch="*")
            return True
        except Exception as exc:
            if getattr(exc, "response", {}).get("Error", {}).get("Code") in (
                    "PreconditionFailed", "ConditionalRequestConflict", "412", "409"):
                return False
            raise


class Progress:
    def __init__(self, store, record):
        self.store, self.record = store, record
        self.lock = threading.Lock()

    def emit(self, event_status, **fields):
        # Both analyses write through this lock, so sequences and object replacements
        # cannot race. Only this worker owns the claimed job.
        with self.lock:
            events = self.record["events"]
            if len(events) >= 200:
                raise RuntimeError("The analysis exceeded its event limit")
            events.append({"seq": len(events), "status": event_status})
            self.record.update(fields)
            self.record["updatedAt"] = int(time.time())
            self.store.write(self.record)


def _response(code, body):
    return {"statusCode": code, "headers": {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "no-store, private", "pragma": "no-cache",
        "x-content-type-options": "nosniff",
    }, "body": json.dumps(body, ensure_ascii=False, separators=(",", ":"))}


def _headers(event):
    headers = {str(key).lower(): str(value)
               for key, value in (event.get("headers") or {}).items() if value is not None}
    # REST API proxy integrations may put headers in both maps. The multi-value
    # map is authoritative; joining duplicates prevents accepting ambiguous secrets
    # or bearer tokens while still supporting the ordinary single-header form.
    for key, values in (event.get("multiValueHeaders") or {}).items():
        headers[str(key).lower()] = ",".join(str(value) for value in (values or []))
    return headers


def _origin_ok(headers):
    expected = os.environ.get("ORIGIN_SECRET", "")
    supplied = headers.get("x-api-origin", "")
    return bool(expected) and hmac.compare_digest(supplied.encode(), expected.encode())


def _invoke_worker(job_id):
    # Asynchronous Lambda delivery may happen more than once; S3 claims deduplicate it.
    response = _client("lambda", api=True).invoke(
        FunctionName=os.environ["WORKER_FUNCTION_NAME"], InvocationType="Event",
        Payload=json.dumps({"jobId": job_id}).encode())
    if response.get("StatusCode") != 202:
        raise RuntimeError("Worker dispatch failed")


def _post(event, store):
    raw = event.get("body") or ""
    if not isinstance(raw, str) or len(raw) > MAX_REQUEST_BYTES * 2:
        return _response(413, {"error": "The question is too long."})
    try:
        raw = base64.b64decode(raw, validate=True) if event.get("isBase64Encoded") else raw.encode("utf-8")
        if len(raw) > MAX_REQUEST_BYTES:
            return _response(413, {"error": "The question is too long."})
        body = json.loads(raw)
    except (ValueError, UnicodeError):
        return _response(400, {"error": "Provide a JSON object containing a question."})
    query = body.get("query") if isinstance(body, dict) else None
    if not isinstance(query, str) or not query.strip():
        return _response(400, {"error": "Enter a question."})
    query = query.strip()
    try:
        query_size = len(query.encode("utf-8"))
    except UnicodeError:
        return _response(400, {"error": "The question contains invalid characters."})
    if query_size > bounded_int("MAX_QUERY_BYTES", 12_000, 100, 12_000):
        return _response(413, {"error": "The question is too long."})
    now = int(time.time())
    token = secrets.token_urlsafe(32)
    job_id = uuid.uuid4().hex
    expires = now + bounded_int("JOB_TTL_SECONDS", 900, 300, 3600)
    record = {"jobId": job_id, "query": query,
              "tokenHash": hashlib.sha256(token.encode()).hexdigest(),
              "createdAt": now, "updatedAt": now, "expiresAt": expires,
              "deadlineAt": now + 270,
              "status": "queued", "events": [{"seq": 0, "status": "queued"}]}
    store.write(record, create=True)
    try:
        _invoke_worker(job_id)
    except Exception as exc:
        # Do not replace the record: an ambiguous dispatch response may have already
        # started the worker. It is still safe for the client to poll this job.
        _log_error("dispatch_error", exc)
        return _response(202, {"jobId": job_id, "token": token, "expiresAt": expires})
    return _response(202, {"jobId": job_id, "token": token, "expiresAt": expires})


def _get(job_id, headers, store):
    bearer = headers.get("authorization", "")
    if not bearer.startswith("Bearer ") or len(bearer) > 128:
        return _response(401, {"error": "The request is not authorized."})
    record = store.read(job_id)
    token_hash = hashlib.sha256(bearer[7:].encode()).hexdigest()
    expected = record.get("tokenHash", "") if record else "0" * 64
    if not hmac.compare_digest(token_hash, expected):
        return _response(404, {"error": "The requested answer was not found."})
    now = int(time.time())
    if now >= record["expiresAt"]:
        return _response(410, {"error": "This answer has expired. Submit the question again."})
    public = {key: record[key] for key in ("status", "events")}
    if record["status"] not in ("done", "error") and now >= record.get("deadlineAt", record["expiresAt"]):
        public = {"status": "error", "events": record["events"] + [
            {"seq": len(record["events"]), "status": "error"}],
            "error": "The answer exceeded its time limit. Please try a shorter question."}
    elif record["status"] == "done":
        public["response"] = record["response"]
    elif record["status"] == "error":
        public["error"] = record["error"]
    return _response(200, public)


def api_handler(event, context):
    headers = _headers(event)
    if not _origin_ok(headers):
        return _response(403, {"error": "The request is not authorized."})
    http = event.get("requestContext", {}).get("http", {})
    method = event.get("httpMethod") or http.get("method", "")
    path = event.get("path") or event.get("rawPath", "")
    try:
        if method == "POST" and path == API_PATH:
            return _post(event, Store(api=True))
        if method == "GET" and path.startswith(API_PATH + "/"):
            job_id = path[len(API_PATH) + 1:]
            path_job_id = (event.get("pathParameters") or {}).get("jobId", job_id)
            if JOB_ID.fullmatch(job_id) and path_job_id == job_id:
                return _get(job_id, headers, Store(api=True))
        return _response(404, {"error": "The requested route was not found."})
    except Exception as exc:
        _log_error("api_error", exc)
        return _response(503, {"error": "The chatbot is temporarily unavailable. Please try again."})


def worker_handler(event, context):
    job_id = event.get("jobId") if isinstance(event, dict) else None
    if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id):
        return {"status": "ignored"}
    store = Store()
    record = store.read(job_id)
    if not record or record["expiresAt"] <= time.time() or record["status"] != "queued":
        return {"status": "ignored"}
    if not store.claim(job_id):
        return {"status": "duplicate"}
    budget = bounded_int("WORKER_BUDGET_SECONDS", 225, 30, 225)
    if context and hasattr(context, "get_remaining_time_in_millis"):
        budget = min(budget, context.get_remaining_time_in_millis() / 1000 - 10)
    budget = min(budget, record["deadlineAt"] - time.time() - 5)
    deadline = time.monotonic() + budget
    progress = Progress(store, record)
    runtime = None
    try:
        if time.time() - record["createdAt"] > 45 or budget < 3:
            raise TimeoutError("The job was not started within its time limit")
        progress.emit("running", status="running", deadlineAt=int(time.time() + budget + 5))
        runtime = Runtime(bundled_reference(), progress.emit, deadline)
        answer = runtime.answer(record["query"])
        runtime.remaining()
        # Keep a pollable terminal result, but discard the private question early.
        record.pop("query", None)
        progress.emit("done", status="done", response=answer)
    except Exception as exc:
        record.pop("query", None)
        if isinstance(exc, TimeoutError):
            message = "The answer exceeded its time limit. Please try a shorter question."
        elif isinstance(exc, IncompleteAnswer):
            message = "The analysis did not finish. Please try a more focused question."
        else:
            message = "The chatbot could not complete the answer. Please try again."
        progress.emit("error", status="error", error=message)
        _log_error("analysis_error", exc)
    finally:
        if runtime:
            # Aggregate metrics only; questions, answers and bearer tokens are never logged.
            print(json.dumps({"_aws": {"Timestamp": int(time.time() * 1000),
                "CloudWatchMetrics": [{"Namespace": "BinaryNecklacesChatbot", "Dimensions": [[]],
                    "Metrics": [{"Name": key, "Unit": "Count"} for key in runtime.usage]}]},
                **runtime.usage}))
    return {"status": record["status"]}
