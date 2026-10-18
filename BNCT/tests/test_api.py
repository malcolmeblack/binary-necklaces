"""Lossless JSON, API Gateway variants, and useful results under a deadline."""
import base64
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("calculator_main", ROOT / "calculator/main.py")
calculator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calculator)


def invoke(data, post=True, encoded=False, context=None):
    if post:
        body = json.dumps(data)
        if encoded:
            body = base64.b64encode(body.encode()).decode()
        event = {"version": "2.0", "requestContext": {"http": {"method": "POST"}},
                 "body": body, "isBase64Encoded": encoded}
    else:
        event = {"httpMethod": "GET", "queryStringParameters": data}
    result = calculator.handler(event, context)
    return result["statusCode"], json.loads(result["body"])


class ApiTests(unittest.TestCase):
    def test_word_only_request_includes_census(self):
        status, result = invoke({"bitstring": "001"})
        self.assertEqual(status, 200)
        catalogue = result["power_set"]["census"]
        self.assertEqual(catalogue["status"], "exact")
        self.assertEqual(catalogue["components"], "2")
        self.assertTrue(catalogue["graphs"])
        self.assertTrue(all(catalogue["verification"].values()))

    def test_explicit_false_skips_census(self):
        for value in (False, "false"):
            with self.subTest(census=value), patch.object(calculator, "census") as census:
                status, result = invoke({"bitstring": "001", "census": value})
                self.assertEqual(status, 200)
                census.assert_not_called()
                self.assertEqual(result["power_set"]["census"], {"status": "not_requested"})
                self.assertEqual(result["power_set"]["words"], "8")
                self.assertEqual(result["component"]["cycle_length"], "1")

    def test_gateway_v1_v2_and_base64_agree(self):
        values = []
        for post, encoded in ((False, False), (True, False), (True, True)):
            status, result = invoke({"bitstring": "001", "census": "true"}, post, encoded)
            self.assertEqual(status, 200)
            result.pop("elapsed_ms")
            values.append(result)
        self.assertEqual(values[0], values[1])
        self.assertEqual(values[1], values[2])
        self.assertEqual(values[0]["component"]["word_period"], "3")
        self.assertEqual(values[0]["component"]["cycle_length"], "1")
        self.assertTrue(all(values[0]["power_set"]["census"]["verification"].values()))

    def test_counts_are_decimal_strings_beyond_javascript_precision(self):
        status, result = invoke({"bitstring": "1" + "0" * 63, "census": True})
        self.assertEqual(status, 200)
        self.assertEqual(result["power_set"]["words"], "18446744073709551616")
        self.assertEqual(result["component"]["words"], str(2**64))
        self.assertIsInstance(result["word"]["length"], int)
        self.assertIsInstance(result["necklace"]["self_complementary"], bool)
        self.assertIsInstance(result["power_set"]["census"]["graphs"][0]["total_words"], str)

    def test_validation_before_computation(self):
        for word in (None, "", "012", 101, "0" * 4097, "01\n", ["0"], "０１"):
            self.assertEqual(invoke({"bitstring": word})[0], 400)
        for extra in ({"census": "maybe"}, {"preview_limit": 65}, {"preview_limit": True},
                      {"preview_limit": 1.2}):
            self.assertEqual(invoke({"bitstring": "01", **extra})[0], 400)
        for body in ("[]", "null", "{", '{"bitstring":"' + "0" * 33000 + '"}'):
            response = calculator.handler({"httpMethod": "POST", "body": body}, None)
            self.assertEqual(response["statusCode"], 400)

    def test_partial_results_survive_exhausted_budget(self):
        class Deadline:
            def get_remaining_time_in_millis(self):
                return 1500
        status, result = invoke({"bitstring": "001"}, context=Deadline())
        self.assertEqual(status, 200)
        self.assertEqual(result["component"]["status"], "deferred")
        self.assertIsNone(result["component"]["cycle_length"])
        self.assertEqual(result["word"]["adjacent_xor"], "101")
        self.assertEqual(result["tree"]["necklaces"], "2")
        self.assertEqual(result["power_set"]["words"], "8")
        self.assertEqual(result["power_set"]["census"]["status"], "deferred")
        self.assertIsNone(result["power_set"]["census"]["graphs"])

    def test_maximum_width_without_enumerating_the_power_set(self):
        status, result = invoke({"bitstring": "1" + "0" * 4095,
                                 "census": True, "preview_limit": 0})
        self.assertEqual(status, 200)
        self.assertEqual(result["dynamics"]["transient_depth"], 4096)
        self.assertEqual(result["dynamics"]["cycle_entry"], "0" * 4096)
        self.assertEqual(result["power_set"]["words"], str(2**4096))
        self.assertEqual(result["power_set"]["census"]["components"], "1")
        self.assertEqual(result["preview"]["tree"]["items"], [])

    def test_protocol_errors_and_preflight(self):
        self.assertEqual(calculator.handler({"httpMethod": "OPTIONS"}, None)["statusCode"], 204)
        self.assertEqual(calculator.handler({"httpMethod": "DELETE"}, None)["statusCode"], 405)
        response = calculator.handler({"httpMethod": "POST", "isBase64Encoded": True,
                                       "body": "not@base64"}, None)
        self.assertEqual(response["statusCode"], 400)

    def test_large_catalogue_keeps_exact_totals(self):
        with patch.object(calculator, "MAX_CENSUS_BYTES", 1):
            status, result = invoke({"bitstring": "001", "census": True})
        self.assertEqual(status, 200)
        catalogue = result["power_set"]["census"]
        self.assertEqual(catalogue["status"], "summary_only")
        self.assertIsNone(catalogue["graphs"])
        self.assertEqual(catalogue["components"], "2")
        self.assertTrue(all(catalogue["verification"].values()))


if __name__ == "__main__":
    unittest.main()
