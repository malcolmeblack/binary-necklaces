"""Offline protocol, expiry, deduplication and model-completion regression tests."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lambda"))
import handler
from runtime import IncompleteAnswer, Runtime
from roles import first_responder

SPEC = {"name": "get_properties", "description": "Calculate properties",
        "inputSchema": {"json": {"type": "object"}}}


def model_response(text="A complete answer.", stop="end_turn", tool=None, tokens=1):
    content = [{"toolUse": tool}] if tool else [{"text": text}]
    return {"output": {"message": {"role": "assistant", "content": content}},
            "stopReason": stop, "usage": {"inputTokens": tokens, "outputTokens": 2,
                "cacheReadInputTokens": 3, "cacheWriteInputTokens": 4}}


class FakeStore:
    def __init__(self):
        self.records, self.claimed = {}, set()
        self.lock = threading.Lock()

    def read(self, job_id):
        return copy.deepcopy(self.records.get(job_id))

    def write(self, record, *, create=False):
        with self.lock:
            if create and record["jobId"] in self.records:
                raise AssertionError("Duplicate creation")
            self.records[record["jobId"]] = copy.deepcopy(record)

    def claim(self, job_id):
        with self.lock:
            if job_id in self.claimed:
                return False
            self.claimed.add(job_id)
            return True


def request(method="POST", path=handler.API_PATH, body=None, token=None, origin=True):
    headers = {"X-Api-Origin": "test-origin"} if origin else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    job_id = path[len(handler.API_PATH) + 1:] if path.startswith(handler.API_PATH + "/") else None
    return {"httpMethod": method, "path": path,
            "resource": handler.API_PATH + ("/{jobId}" if job_id else ""),
            "pathParameters": {"jobId": job_id} if job_id else None,
            "requestContext": {"stage": "prod", "httpMethod": method},
            "headers": headers, "multiValueHeaders": {key: [value] for key, value in headers.items()},
            "isBase64Encoded": False,
            "body": json.dumps(body or {"query": "What is a necklace?"})}


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.environment = patch.dict(os.environ, {"ORIGIN_SECRET": "test-origin"})
        self.environment.start()
        self.store_patch = patch.object(handler, "Store", return_value=self.store)
        self.store_patch.start()
        self.dispatch = patch.object(handler, "_invoke_worker")
        self.invoke = self.dispatch.start()

    def tearDown(self):
        self.dispatch.stop()
        self.store_patch.stop()
        self.environment.stop()

    def submit(self):
        response = handler.api_handler(request(), None)
        self.assertEqual(response["statusCode"], 202)
        self.assertEqual(response["headers"]["cache-control"], "no-store, private")
        return json.loads(response["body"])

    def poll(self, job):
        response = handler.api_handler(request("GET", handler.API_PATH + "/" + job["jobId"],
            token=job["token"]), None)
        return response, json.loads(response["body"])

    def test_submit_poll_and_secret_not_exposed(self):
        job = self.submit()
        record = self.store.records[job["jobId"]]
        self.assertNotIn(job["token"], json.dumps(record))
        self.invoke.assert_called_once_with(job["jobId"])
        response, body = self.poll(job)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body, {"status": "queued", "events": [{"seq": 0, "status": "queued"}]})
        bad = dict(job, token="invalid")
        self.assertEqual(self.poll(bad)[0]["statusCode"], 404)

    def test_direct_origin_and_body_limits(self):
        self.assertEqual(handler.api_handler(request(origin=False), None)["statusCode"], 403)
        too_long = request(body={"query": "q" * 12_001})
        self.assertEqual(handler.api_handler(too_long, None)["statusCode"], 413)
        invalid = request(body={"query": "\ud800"})
        self.assertEqual(handler.api_handler(invalid, None)["statusCode"], 400)
        self.invoke.assert_not_called()

    def test_rest_proxy_headers_routes_and_path_parameters(self):
        job = self.submit()
        poll = request("GET", handler.API_PATH + "/" + job["jobId"], token=job["token"])
        poll["headers"] = None
        self.assertEqual(handler.api_handler(poll, None)["statusCode"], 200)
        poll["pathParameters"]["jobId"] = "b" * 32
        self.assertEqual(handler.api_handler(poll, None)["statusCode"], 404)
        poll["pathParameters"]["jobId"] = job["jobId"]
        poll["multiValueHeaders"]["Authorization"].append("Bearer another-token")
        self.assertEqual(handler.api_handler(poll, None)["statusCode"], 404)
        invalid_origin = request()
        invalid_origin["multiValueHeaders"]["X-Api-Origin"].append("another-origin")
        self.assertEqual(handler.api_handler(invalid_origin, None)["statusCode"], 403)
        self.assertEqual(handler.api_handler(request(path="/api/binary-necklaces/chat"), None)["statusCode"], 404)
        self.assertEqual(handler.api_handler(request(path="/api/bnct/calc"), None)["statusCode"], 404)
        self.assertEqual(handler.api_handler(request("GET"), None)["statusCode"], 404)

    def test_expiry_and_stalled_worker(self):
        job = self.submit()
        record = self.store.records[job["jobId"]]
        record["deadlineAt"] = int(time.time()) - 1
        response, body = self.poll(job)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["status"], "error")
        self.assertNotIn("response", body)
        record["expiresAt"] = int(time.time()) - 1
        self.assertEqual(self.poll(job)[0]["statusCode"], 410)

    def test_worker_finishes_only_once_and_discards_question(self):
        job = self.submit()
        def runtime(reference, status, deadline):
            return Runtime(reference, status, deadline, converse=lambda **kw: model_response(),
                           tool=lambda *a, **kw: {}, tool_spec=SPEC)
        with patch.object(handler, "Runtime", side_effect=runtime), \
                patch.object(handler, "bundled_reference", return_value="Test exposition."), \
                patch("builtins.print"):
            result = handler.worker_handler({"jobId": job["jobId"]}, None)
            self.assertEqual(result, {"status": "done"})
            self.assertEqual(handler.worker_handler({"jobId": job["jobId"]}, None), {"status": "ignored"})
        record = self.store.records[job["jobId"]]
        self.assertNotIn("query", record)
        self.assertEqual([event["seq"] for event in record["events"]], list(range(len(record["events"]))))
        self.assertEqual(sum(event["status"] == "arbiter" for event in record["events"]), 2)
        self.assertEqual(self.poll(job)[1]["response"], "A complete answer.")

    def test_queued_job_started_too_late_does_not_call_bedrock(self):
        job = self.submit()
        self.store.records[job["jobId"]]["createdAt"] -= 46
        with patch.object(handler, "Runtime") as runtime, patch("builtins.print"):
            self.assertEqual(handler.worker_handler({"jobId": job["jobId"]}, None), {"status": "error"})
            runtime.assert_not_called()

    def test_duplicate_claim_does_not_call_bedrock(self):
        job = self.submit()
        self.store.claimed.add(job["jobId"])
        with patch.object(handler, "Runtime") as runtime:
            self.assertEqual(handler.worker_handler({"jobId": job["jobId"]}, None), {"status": "duplicate"})
            runtime.assert_not_called()


class RuntimeTests(unittest.TestCase):
    def test_tool_round_usage_and_unknown_tool_error(self):
        replies = [model_response(stop="tool_use", tool={"toolUseId": "t1", "name": "unknown", "input": {}}, tokens=5),
                   model_response(tokens=7)]
        calls = []
        def converse(**kwargs):
            calls.append(copy.deepcopy(kwargs))
            return replies.pop(0)
        runtime = Runtime("Exposition.", lambda status: None, time.monotonic() + 30,
                          converse=converse, tool=lambda *a, **kw: self.fail("Unknown tool dispatched"),
                          tool_spec=SPEC)
        self.assertEqual(runtime.process("Question", first_responder), "A complete answer.")
        self.assertEqual(runtime.usage["inputTokens"], 12)
        self.assertEqual(runtime.usage["cacheReadInputTokens"], 6)
        self.assertEqual(calls[0]["toolConfig"]["tools"], [{"toolSpec": SPEC}])
        self.assertEqual(calls[1]["messages"][-1]["content"][0]["toolResult"]["status"], "error")

    def test_truncated_answer_and_exhausted_tool_rounds_are_not_done(self):
        runtime = Runtime("Exposition.", lambda status: None, time.monotonic() + 30,
            converse=lambda **kw: model_response(stop="max_tokens"), tool=lambda *a, **kw: {}, tool_spec=SPEC)
        with self.assertRaises(IncompleteAnswer):
            runtime.process("Question", first_responder)
        runtime.converse = lambda **kw: model_response(stop="tool_use", tool={
            "name": "get_properties", "toolUseId": "t", "input": {"bitstring": "01"}})
        runtime.max_tool_rounds = 0
        with self.assertRaises(IncompleteAnswer):
            runtime.process("Question", first_responder)

    def test_parallel_analyses_and_judge_usage(self):
        events = []
        runtime = Runtime("Exposition.", events.append, time.monotonic() + 30,
            converse=lambda **kw: model_response(tokens=5), tool=lambda *a, **kw: {}, tool_spec=SPEC)
        self.assertEqual(runtime.answer("Question"), "A complete answer.")
        self.assertEqual(runtime.usage["inputTokens"], 35)
        self.assertEqual(events.count("first_responder"), 2)
        self.assertEqual(events.count("skeptic"), 2)
        self.assertEqual(events.count("arbiter"), 2)
        self.assertEqual(events[-1], "judging")


class S3ClaimTests(unittest.TestCase):
    def test_records_and_claims_share_private_bucket_prefix(self):
        class S3:
            def __init__(self):
                self.objects, self.calls = {}, []
            def put_object(self, **kwargs):
                if kwargs.get("ServerSideEncryption") != "AES256":
                    raise AssertionError("Job records and claims must use S3 encryption")
                self.calls.append(("put", kwargs["Bucket"], kwargs["Key"]))
                self.objects[kwargs["Key"]] = kwargs["Body"]
            def get_object(self, **kwargs):
                self.calls.append(("get", kwargs["Bucket"], kwargs["Key"]))
                return {"Body": io.BytesIO(self.objects[kwargs["Key"]])}
        for configured, prefix in ((None, "binary-necklaces/chatbot/jobs/"),
                                   ("binary-necklaces/chatbot/custom/", "binary-necklaces/chatbot/custom/")):
            with self.subTest(prefix=prefix), patch.dict(os.environ, {"JOBS_BUCKET": "malcolmblack"}):
                if configured is None:
                    os.environ.pop("JOBS_PREFIX", None)
                else:
                    os.environ["JOBS_PREFIX"] = configured
                client = S3()
                store = handler.Store(client)
                record = {"jobId": "a" * 32, "status": "queued"}
                store.write(record, create=True)
                self.assertEqual(store.read(record["jobId"]), record)
                self.assertTrue(store.claim(record["jobId"]))
                self.assertEqual(client.calls, [
                    ("put", "malcolmblack", prefix + record["jobId"] + ".json"),
                    ("get", "malcolmblack", prefix + record["jobId"] + ".json"),
                    ("put", "malcolmblack", prefix + record["jobId"] + ".claim")])

    def test_service_error_logging_never_includes_message_or_request_data(self):
        class ServiceError(Exception):
            response = {"Error": {"Code": "AccessDeniedException", "Message": "private question"},
                        "ResponseMetadata": {"private": "bearer-token"}}
        with patch("builtins.print") as printed:
            handler._log_error("analysis_error", ServiceError("private question"))
        self.assertEqual(json.loads(printed.call_args.args[0]), {
            "event": "analysis_error", "kind": "ServiceError", "code": "AccessDeniedException"})
        exc = ServiceError("private question")
        exc.response = {"Error": {"Code": "private question"}}
        with patch("builtins.print") as printed:
            handler._log_error("api_error", exc)
        self.assertNotIn("code", json.loads(printed.call_args.args[0]))

    def test_conditional_s3_claim_prevents_second_execution(self):
        class Conflict(Exception):
            response = {"Error": {"Code": "PreconditionFailed"}}
        class S3:
            def __init__(self):
                self.keys = set()
            def put_object(self, **kwargs):
                self.assert_conditional = kwargs["IfNoneMatch"] == "*"
                if kwargs["Key"] in self.keys:
                    raise Conflict()
                self.keys.add(kwargs["Key"])
        client = S3()
        with patch.dict(os.environ, {"JOBS_BUCKET": "jobs"}):
            store = handler.Store(client)
        self.assertTrue(store.claim("a" * 32))
        self.assertFalse(store.claim("a" * 32))
        self.assertTrue(client.assert_conditional)


if __name__ == "__main__":
    unittest.main()
