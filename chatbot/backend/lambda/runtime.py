"""Bounded Bedrock orchestration, independent of HTTP and Lambda invocation."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import threading
import time

from roles import first_responder, skeptic, arbiter, judge

TOKEN_KEYS = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheWriteInputTokens")
MAX_TOOL_RESULT_BYTES = 65_536
MAX_MODEL_INPUT_BYTES = 180_000


class IncompleteAnswer(RuntimeError):
    """The model stopped before producing a complete answer."""


def bounded_int(name, default, low, high):
    value = int(os.environ.get(name, str(default)))
    if not low <= value <= high:
        raise ValueError(f"Invalid {name} configuration")
    return value


class Runtime:
    def __init__(self, reference, status, deadline, *, converse=None, tool=None, tool_spec=None):
        if not reference.strip():
            raise RuntimeError("The bundled exposition is empty")
        if tool is None or tool_spec is None:
            from tools import TOOL_SPEC, call_tool
            tool = tool or call_tool
            tool_spec = tool_spec or TOOL_SPEC
        self.reference = reference
        self.status = status
        self.deadline = deadline
        self.tool = tool
        self.tool_spec = tool_spec
        self.converse = converse or self._converse
        self.usage = dict.fromkeys(TOKEN_KEYS, 0)
        self.usage_lock = threading.Lock()
        self.cancelled = threading.Event()
        self.model_id = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
        self.max_tokens = bounded_int("MAX_OUTPUT_TOKENS", 1000, 128, 4096)
        self.max_tool_rounds = bounded_int("MAX_TOOL_ROUNDS", 3, 0, 5)

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if self.cancelled.is_set() or remaining < 3:
            raise TimeoutError("The answer exceeded its time limit")
        return remaining

    def _converse(self, **kwargs):
        # No automatic model retries: a timed-out request may already be billed.
        import boto3
        from botocore.config import Config
        remaining = self.remaining()
        client = boto3.session.Session().client("bedrock-runtime", config=Config(
            connect_timeout=min(3, remaining / 4),
            read_timeout=min(45, max(1, remaining - 4)),
            retries={"total_max_attempts": 1},
        ))
        try:
            return client.converse(**kwargs)
        finally:
            client.close()

    def process(self, query, role):
        messages = [{"role": "user", "content": [{"text": query}]}]
        for round_index in range(self.max_tool_rounds + 1):
            self.remaining()
            system = [{"text": self.reference}]
            if os.environ.get("USE_PROMPT_CACHE", "true").lower() not in ("false", "0", "no"):
                system.append({"cachePoint": {"type": "default"}})
            system.append({"text": role.prompt_template})
            size = len(json.dumps([system, messages], ensure_ascii=False).encode("utf-8"))
            if size > MAX_MODEL_INPUT_BYTES:
                raise IncompleteAnswer("The question requires too much intermediate material")
            response = self.converse(
                modelId=self.model_id,
                inferenceConfig={"maxTokens": self.max_tokens, "temperature": 0.5},
                system=system,
                messages=messages,
                toolConfig={"tools": [{"toolSpec": self.tool_spec}]},
            )
            with self.usage_lock:
                for key in TOKEN_KEYS:
                    self.usage[key] += response.get("usage", {}).get(key, 0)
            self.remaining()
            content = response.get("output", {}).get("message", {}).get("content", [])
            uses = [block["toolUse"] for block in content if "toolUse" in block]
            stop = response.get("stopReason")
            if uses:
                if stop != "tool_use" or round_index == self.max_tool_rounds:
                    raise IncompleteAnswer("The answer exhausted its calculation rounds")
                if len(uses) > 4:
                    raise IncompleteAnswer("The answer requested too many calculations")
                messages.append({"role": "assistant", "content": content})
                results = []
                for use in uses:
                    self.status("calculating")
                    try:
                        if use.get("name") != "get_properties":
                            raise ValueError("Unknown tool")
                        value = self.tool(use["name"], use.get("input", {}),
                                          timeout_seconds=min(25, self.remaining() - 2))
                        text = json.dumps(value, ensure_ascii=False)
                        if len(text.encode("utf-8")) > MAX_TOOL_RESULT_BYTES:
                            raise ValueError("The calculator result exceeded the response limit")
                        result_status = "success"
                    except (ValueError, RuntimeError, TimeoutError) as exc:
                        # Tools expose safe, user-readable failures. Never serialize SDK errors.
                        text = str(exc)[:500]
                        result_status = "error"
                    results.append({"toolResult": {
                        "toolUseId": use["toolUseId"],
                        "content": [{"text": text}], "status": result_status,
                    }})
                messages.append({"role": "user", "content": results})
                continue
            if stop not in ("end_turn", "stop_sequence"):
                raise IncompleteAnswer("The model did not finish its answer")
            text = "\n".join(block["text"] for block in content if "text" in block).strip()
            if not text or len(text.encode("utf-8")) > 48_000:
                raise IncompleteAnswer("The model did not return a usable answer")
            return text
        raise IncompleteAnswer("The answer exhausted its calculation rounds")

    def analysis(self, query):
        self.status("first_responder")
        first = self.process(first_responder.query_template.format(query=query), first_responder)
        self.status("skeptic")
        critique = self.process(skeptic.query_template.format(
            query=query, first_response=first), skeptic)
        self.status("arbiter")
        return self.process(arbiter.query_template.format(
            query=query, first_response=first, skeptic_response=critique), arbiter)

    def answer(self, query):
        self.status("running_parallel_analyses")
        # Preserve the two independent analyses and final judge from the EC2 service.
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {pool.submit(self.analysis, query): i for i in range(2)}
            results = [None, None]
            try:
                for future in as_completed(futures):
                    results[futures[future]] = future.result()
            except Exception:
                self.cancelled.set()
                raise
        self.status("judging")
        return self.process(judge.query_template.format(
            query=query, arbiter_response_1=results[0], arbiter_response_2=results[1]), judge)


def bundled_reference():
    return (Path(__file__).parent / "knowledge" / "binary-necklaces.yml").read_text(encoding="utf-8")
