"""API Gateway proxy handler for the algebraic binary-necklace tessellator."""

import logging

import tessellate

from shared.http_api import (
    API_VERSION, Budget, check_origin, error_response, method, parameters,
    response,
)


def handler(event, context):
    """GET query parameters and POST JSON share the same validated options."""
    blocked = check_origin(event)
    if blocked:
        return blocked
    verb = method(event)
    if verb == "OPTIONS":
        return response({}, 204)
    if verb not in ("GET", "POST"):
        return error_response("Use GET or POST.", 405)
    budget = Budget(context)
    try:
        result = tessellate.render(parameters(event), budget)
        result["elapsed_ms"] = budget.elapsed_ms()
        return response(result)
    except ValueError as exc:
        return error_response(str(exc))
    except TimeoutError as exc:
        return error_response(str(exc), 503)
    except Exception:
        logging.exception("BNCT tessellation failed")
        return error_response("An internal rendering error occurred.", 500)


lambda_handler = handler
