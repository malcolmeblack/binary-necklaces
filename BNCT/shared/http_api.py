"""Small API Gateway v1/v2 adapter; no AWS SDK or network access required."""
import base64
import hmac
import json
import os
import re
import time

API_VERSION = "BNCT-a1"
MAX_N = 4096
MAX_BODY = 32768
HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Cache-Control": "no-store",
}


class InputError(ValueError):
    pass


def method(event):
    return (event.get("requestContext", {}).get("http", {}).get("method")
            or event.get("httpMethod") or "GET").upper()


def parameters(event):
    """Read either a GET query or a JSON POST, including base64 proxy bodies."""
    verb = method(event)
    if verb not in ("GET", "POST", "OPTIONS"):
        raise InputError("Use GET or POST.")
    if verb == "POST":
        body = event.get("body") or "{}"
        if not isinstance(body, str) or len(body) > MAX_BODY * 2:
            raise InputError("The request body is too large.")
        if event.get("isBase64Encoded"):
            try:
                body = base64.b64decode(body, validate=True).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                raise InputError("The request body is not valid base64 UTF-8.") from None
        if len(body.encode("utf-8")) > MAX_BODY:
            raise InputError("The request body is too large.")
        try:
            data = json.loads(body)
        except (ValueError, RecursionError):
            raise InputError("The request body must contain valid JSON.") from None
    else:
        data = event.get("queryStringParameters") or {}
    if not isinstance(data, dict):
        raise InputError("Supply a JSON object or query parameters.")
    return data


def binary_word(data):
    word = data.get("bitstring", "")
    if not isinstance(word, str) or re.fullmatch(r"[01]{1,4096}", word) is None:
        raise InputError(f"Enter a binary word of length 1 to {MAX_N:,}.")
    return word


def boolean(data, key, default=False):
    value = data.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in ("true", "false", "1", "0"):
        return value.lower() in ("true", "1")
    raise InputError(f"{key} must be true or false.")


def integer(data, key, default, low, high):
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise InputError(f"{key} must be an integer from {low} to {high}.")
    if isinstance(value, str) and (len(value) > 40 or re.fullmatch(r"[0-9]+", value) is None):
        raise InputError(f"{key} must be an integer from {low} to {high}.")
    result = int(value)
    if not low <= result <= high:
        raise InputError(f"{key} must be an integer from {low} to {high}.")
    return result


class Budget:
    """Cooperative deadline, bounded by the Lambda invocation's remaining time."""
    def __init__(self, context=None, seconds=None):
        if seconds is None:
            try:
                seconds = float(os.environ.get("BNCT_SECONDS", "20"))
            except ValueError:
                seconds = 20.0
        # Leave time to serialize a response before the usual HTTP deadline.
        if not 0 < seconds <= 25:
            seconds = 20.0
        if context is not None and hasattr(context, "get_remaining_time_in_millis"):
            seconds = min(seconds, max(0, context.get_remaining_time_in_millis() / 1000 - 3.0))
        self.started = time.monotonic()
        self.deadline = self.started + seconds

    def check(self):
        if time.monotonic() >= self.deadline:
            raise TimeoutError("The request's computation time limit was reached.")

    def elapsed_ms(self):
        return round(1000 * (time.monotonic() - self.started))


def response(data, status=200):
    return {"statusCode": status, "headers": dict(HEADERS),
            "isBase64Encoded": False,
            "body": json.dumps(data, separators=(",", ":"), ensure_ascii=True)}


def error_response(message, status=400):
    return response({"api_version": API_VERSION, "error": message}, status)


def check_origin(event):
    """Return a 403 response if the configured origin secret is missing or wrong.

    Returns None when the check passes or when no secret is configured.
    """
    expected = os.environ.get("ORIGIN_SECRET", "")
    if not expected:
        return None
    headers = {str(k).lower(): str(v) for k, v in (event.get("headers") or {}).items()}
    supplied = headers.get("x-api-origin", "")
    if hmac.compare_digest(supplied.encode(), expected.encode()):
        return None
    return error_response("The request is not authorized.", 403)
