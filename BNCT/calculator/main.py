"""Calculator Lambda: exact algebra, bounded work, JSON-safe integer counts."""
import json
import logging
import time

from shared.algebra import analyze_word
from shared.census import census, power_set_totals
from shared.numbertheory import ComputationLimit
from shared.http_api import (API_VERSION, MAX_N, Budget, InputError, binary_word,
                             boolean, check_origin, error_response, integer,
                             method, parameters, response)

# These values are dimensions/indices bounded by the accepted word length.
# All mathematical counts and periods are decimal strings, even when small.
SMALL_FIELDS = frozenset({
    "n", "q", "length", "weight", "spatial_period", "periodic_spatial_period",
    "transient_depth", "depth", "levels", "rotation_shift", "elapsed_ms",
    "returned", "limit", "max_word_length", "preview_limit", "degree", "exponent",
    "graphs_returned", "max_census_rows", "max_census_bytes", "max_response_bytes",
})
MAX_CENSUS_BYTES = 1024 * 1024
MAX_CENSUS_ROWS = 1000
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def wire_integers(value, key=""):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value if key in SMALL_FIELDS else str(value)
    if isinstance(value, dict):
        return {k: wire_integers(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [wire_integers(v, key) for v in value]
    return value


def calculate(data, context=None):
    word = binary_word(data)
    include_census = boolean(data, "census", True)
    preview_limit = integer(data, "preview_limit", 16, 0, 64)
    budget = Budget(context)
    # If a census is requested, reserve some of the request for that independent
    # calculation. Neither result's failure suppresses the other exact fields.
    word_deadline = min(budget.deadline, time.monotonic() + (10 if include_census else 20))

    def word_check():
        budget.check()
        if time.monotonic() >= word_deadline:
            raise TimeoutError("The component calculation's time limit was reached.")

    result = analyze_word(word, check=word_check, preview_limit=preview_limit)
    totals = power_set_totals(len(word))
    if include_census:
        try:
            catalogue = census(len(word), check=budget.check, max_states=10000,
                               max_graphs=MAX_CENSUS_ROWS, max_graph_bytes=MAX_CENSUS_BYTES)
            totals["census"] = catalogue
        except (ComputationLimit, TimeoutError) as exc:
            totals["census"] = {"status": "deferred", "reason": str(exc),
                                "graphs": None, "components": None, "graph_types": None,
                                "graphs_returned": 0, "graphs_truncated": None}
    else:
        totals["census"] = {"status": "not_requested"}
    result.update({
        "api_version": API_VERSION,
        "power_set": totals,
        "limits": {"max_word_length": MAX_N, "preview_limit": preview_limit,
                   "max_census_rows": MAX_CENSUS_ROWS,
                   "max_census_bytes": MAX_CENSUS_BYTES,
                   "max_response_bytes": MAX_RESPONSE_BYTES},
        "elapsed_ms": budget.elapsed_ms(),
    })
    return wire_integers(result)


def _pack_response(data):
    """Bound both the JSON body and the escaped Lambda proxy envelope.

    The graph collector already bounds intermediate allocation. This final
    guard also covers previews, scalar fields, headers and JSON escaping.
    ASCII encoding makes character counts equal byte counts.
    """
    chunks, size = [], 0
    for chunk in json.JSONEncoder(separators=(",", ":"), ensure_ascii=True).iterencode(data):
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            return None
        chunks.append(chunk)
    packed = response({})
    packed["body"] = ''.join(chunks)
    size = 0
    # Include the ordinary JSON encoder's spaces as a conservative allowance.
    for chunk in json.JSONEncoder(ensure_ascii=True).iterencode(packed):
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            return None
    return packed


def bounded_response(result):
    packed = _pack_response(result)
    if packed is not None:
        return packed
    catalogue = result["power_set"]["census"]
    if catalogue.get("graphs") is not None:
        catalogue.update(status="summary_only", graphs=None, graphs_returned=0,
                         graphs_truncated=True,
                         reason="The graph table exceeds the complete response size limit; exact census totals are retained.")
        packed = _pack_response(result)
        if packed is not None:
            return packed
    # This fallback is normally unnecessary under the current input/table caps,
    # but keeps future response additions from overflowing Lambda's payload.
    for preview in sorted(result["preview"].values(), key=lambda p: len(p["items"]), reverse=True):
        if not preview["items"]:
            continue
        preview.update(items=[], returned=0, truncated=True, status="truncated", reason="response_size")
        packed = _pack_response(result)
        if packed is not None:
            return packed
    # Core fields at n<=4096 are far below the allowance; never silently cut a
    # binary word, count or branching sequence if a future change violates it.
    raise ArithmeticError("Core calculator fields exceed the response allowance")


def handler(event, context):
    blocked = check_origin(event)
    if blocked:
        return blocked
    if method(event) == "OPTIONS":
        return response({}, 204)
    if method(event) not in ("GET", "POST"):
        return error_response("Use GET or POST.", 405)
    try:
        return bounded_response(calculate(parameters(event), context))
    except InputError as exc:
        return error_response(str(exc))
    except Exception:
        logging.exception("BNCT calculation failed")
        return error_response("An internal calculation error occurred.", 500)
