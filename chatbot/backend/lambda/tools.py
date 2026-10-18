"""Bounded, read-only calculator tool using the current BNCT JSON contract."""
import json
import os
import re
import urllib.error
import urllib.request

MAX_WORD_LENGTH = 4096
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TOOL_BYTES = 60_000
CALCULATOR_URL = "https://malcolmblack.org/api/bnct/calc"
TOOL_SPEC = {
    "name": "get_properties",
    "description": (
        "Calculate properties of a binary word and its binary necklace, incoming tree, "
        "component, and ambient power set using BNCT. Preserve leading zeros. "
        "Distinguish word equality from necklace equality. Some expensive component "
        "or census fields may be deferred; do not infer missing values. "
        "Graph census counts actual components, not reflected pairs."
    ),
    "inputSchema": {"json": {
        "type": "object", "properties": {"bitstring": {
            "type": "string", "pattern": "^[01]+$", "minLength": 1,
            "maxLength": MAX_WORD_LENGTH,
            "description": "A binary word, with leading zeros preserved."
        }}, "required": ["bitstring"], "additionalProperties": False
    }}
}


def least_rotation(word):
    """Booth's algorithm; never enumerate all rotations."""
    doubled, n = word + word, len(word)
    i, j, k = 0, 1, 0
    while i < n and j < n and k < n:
        a, b = doubled[i + k], doubled[j + k]
        if a == b:
            k += 1
            continue
        if a > b:
            i += k + 1
            if i <= j:
                i = j + 1
        else:
            j += k + 1
            if j <= i:
                j = i + 1
        k = 0
    start = min(i, j)
    return doubled[start:start + n]


def local_properties(word):
    """Exact elementary facts remain available when the BNCT service is down."""
    n = len(word)
    image = ''.join(str(int(word[i]) ^ int(word[i - 1])) for i in range(n))
    complement = word.translate(str.maketrans('01', '10'))
    least = least_rotation(word)
    image_least = least_rotation(image)
    preimages = []
    if word.count('1') % 2 == 0:
        bits = ['0']
        for bit in word[1:]:
            bits.append(str(int(bits[-1]) ^ int(bit)))
        preimage = ''.join(bits)
        preimages = sorted({least_rotation(preimage),
                            least_rotation(preimage.translate(str.maketrans('01', '10')))})
    period = (word + word).find(word, 1)
    return {
        "word": {"value": word, "length": n, "weight": word.count('1'),
                 "parity": "odd" if word.count('1') % 2 else "even",
                 "complement": complement, "reversal": word[::-1],
                 "palindrome": word == word[::-1], "adjacent_xor": image,
                 "primitive_root": word[:period], "spatial_period": period},
        "necklace": {"least_rotation": least, "image": image_least,
                     "fixed": image_least == least,
                     "chirality": "achiral" if word[::-1] in word + word else "chiral",
                     "self_complementary": complement in word + word,
                     "spatial_period": period, "preimages": preimages}
    }


def _json_body(raw):
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("Calculator response exceeds the size limit.")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise RuntimeError("The calculator returned an invalid response.")
    return result


def _request_calculator(word, timeout_seconds):
    body = json.dumps({"bitstring": word, "census": True, "preview_limit": 4}).encode()
    timeout = max(0.1, min(25.0, timeout_seconds))
    function_arn = os.environ.get("CALCULATOR_FUNCTION_ARN", "")
    if function_arn:
        import boto3
        from botocore.config import Config
        client = boto3.session.Session().client("lambda", config=Config(
            connect_timeout=min(2, timeout), read_timeout=timeout,
            retries={"total_max_attempts": 1}))
        event = {"requestContext": {"http": {"method": "POST"}},
                 "headers": {"content-type": "application/json"},
                 "body": body.decode()}
        try:
            response = client.invoke(FunctionName=function_arn, InvocationType="RequestResponse",
                                     Payload=json.dumps(event).encode())
            stream = response["Payload"]
            try:
                envelope = _json_body(stream.read(MAX_RESPONSE_BYTES + 1))
            finally:
                stream.close()
        finally:
            client.close()
        if response.get("FunctionError") or envelope.get("statusCode") != 200:
            raise RuntimeError("The calculator request failed.")
        result = _json_body(envelope["body"].encode())
    else:
        request = urllib.request.Request(CALCULATOR_URL, data=body, method="POST", headers={
            "Content-Type": "application/json", "Accept": "application/json",
            "User-Agent": "binary-necklaces-chatbot/2"})
        # The model cannot provide a URL or change the endpoint.
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = _json_body(response.read(MAX_RESPONSE_BYTES + 1))
    if result.get("error") or not isinstance(result.get("word"), dict):
        raise RuntimeError("The calculator response does not use the BNCT schema.")
    if result["word"].get("value") != word:
        raise RuntimeError("The calculator response belongs to a different word.")
    return result


def _bounded_result(result, local):
    """Keep exact scalar fields and explicitly mark omitted lists; never clip a word."""
    result = dict(result)
    result.pop("limits", None)
    result.pop("elapsed_ms", None)
    result["necklace"] = dict(result.get("necklace") or local["necklace"])
    result["necklace"]["fixed"] = local["necklace"]["fixed"]
    result["conventions"] = (
        "D(w) = w XOR right_rotation(w). A fixed necklace has D(w) rotation-equivalent "
        "to w. Census components are actual weakly connected components; reflected "
        "pairs are not counted as single components. Deferred and truncated fields "
        "do not establish missing values."
    )
    census = result.get("power_set", {}).get("census", {})
    graphs = census.get("graphs")
    if isinstance(graphs, list) and len(graphs) > 12:
        census["graphs"] = graphs[:12]
        census["graphs_returned"] = 12
        census["graphs_truncated"] = True
        census["tool_note"] = "Only the first 12 graph rows are included for the language model."
    encoded = lambda: json.dumps(result, ensure_ascii=True, separators=(',', ':')).encode()
    if len(encoded()) > MAX_TOOL_BYTES:
        if census.get("graphs") is not None:
            census.update(graphs=None, graphs_returned=0, graphs_truncated=True,
                          tool_note="Graph rows omitted to bound the tool response; census totals are retained.")
        if "preview" in result:
            result["preview"] = {"status": "omitted", "reason": "tool_response_size"}
    if len(encoded()) > MAX_TOOL_BYTES:
        # Elementary fields at n<=4096 fit the cap; do not forward an oversized
        # algebraic polynomial or branching sequence to the language model.
        result = dict(local)
        result.update(status="partial", component={"status": "unavailable"},
                      warning="The calculator's detailed result exceeded the tool response limit. Only exact elementary facts are included.")
    return result


def call_tool(name, arguments, *, timeout_seconds):
    if name != "get_properties":
        raise ValueError("Unknown calculator tool.")
    if not isinstance(arguments, dict) or set(arguments) != {"bitstring"}:
        raise ValueError("Supply only bitstring, a binary word preserving leading zeros.")
    word = arguments["bitstring"]
    if not isinstance(word, str) or re.fullmatch(r"[01]{1,4096}", word) is None:
        raise ValueError("Provide a binary word of length 1 to 4096, preserving leading zeros.")
    local = local_properties(word)
    try:
        result = _request_calculator(word, timeout_seconds)
    except Exception:
        # Never expose service internals or confuse local facts with a census.
        local.update(status="partial", component={"status": "unavailable"},
                     power_set={"census": {"status": "unavailable"}},
                     warning="The BNCT calculator is unavailable. Only exact elementary word and necklace properties were calculated locally.")
        return local
    return _bounded_result(result, local)
