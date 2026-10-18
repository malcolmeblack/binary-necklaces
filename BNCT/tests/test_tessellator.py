"""Automatic, bounded, labelled tessellations and Lambda API regressions."""

import base64
import importlib.util
import io
import json
from pathlib import Path
import random
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tessellator"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SOURCE))

try:
    from PIL import Image
except ImportError:
    Image = None

if Image is not None:
    import tessellate
    SPEC = importlib.util.spec_from_file_location("bnct_tessellator_handler", SOURCE / "main.py")
    api = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(api)


def step(word):
    return "".join("1" if bit != word[i - 1] else "0"
                   for i, bit in enumerate(word))


@unittest.skipIf(Image is None, "Install tessellator/requirements.txt to test rendering.")
class TessellatorTests(unittest.TestCase):
    def request(self, data, method="POST", context=None):
        event = {"httpMethod": method}
        event["body" if method == "POST" else "queryStringParameters"] = (
            json.dumps(data) if method == "POST" else data)
        result = api.handler(event, context)
        return result["statusCode"], json.loads(result["body"])

    def test_rows_agree_with_literal_adjacent_xor(self):
        for n in range(1, 10):
            for value in range(1 << n):
                word = format(value, f"0{n}b")
                expected = word
                for actual in tessellate._row_words(word, 8):
                    self.assertEqual(actual, expected)
                    expected = step(expected)

    def test_labels_follow_full_rows_and_spatial_wrap(self):
        # The visible columns must not become the cyclic boundary for the rule.
        word = "1" + "0" * 30
        settings = tessellate.options({"bitstring": word})
        settings.update(columns=17, rows=12, width=17 * 28, height=12 * 28)
        first = settings["first_row_word"]
        labels = []
        original_text = tessellate.ImageDraw.ImageDraw.text

        def capture(draw, position, text, *args, **kwargs):
            box = draw.textbbox(position, text, font=kwargs["font"], anchor=kwargs["anchor"])
            self.assertGreaterEqual(min(box[0], box[1]), 0)
            self.assertLessEqual(box[2], settings["width"])
            self.assertLessEqual(box[3], settings["height"])
            labels.append((position, text))
            return original_text(draw, position, text, *args, **kwargs)

        with mock.patch.object(tessellate.ImageDraw.ImageDraw, "text", capture):
            image = tessellate.create_image(first, settings)
        self.assertGreaterEqual(len(labels), (settings["rows"] - 1) * (settings["columns"] - 1))
        expected = first
        cell = settings["cell_size"]
        for row in range(settings["rows"] + 1):
            y = image.height - row * cell
            row_labels = [(x, bit) for ((x, label_y), bit) in labels if label_y == y]
            if row in (0, settings["rows"]):
                self.assertFalse(row_labels)
            else:
                self.assertTrue(row_labels)
            for x, bit in row_labels:
                index = round(x / cell + row / 2 - .5)
                self.assertEqual(bit, expected[index % len(word)])
            expected = step(expected)

    def test_get_post_and_image_decode(self):
        for method in ("GET", "POST"):
            with mock.patch.object(tessellate, "MAX_COLUMNS", 24), mock.patch.object(tessellate, "MAX_ROWS", 24):
                status, body = self.request({"bitstring": "00000101101"}, method)
            self.assertEqual(status, 200)
            raw = base64.b64decode(body["image"]["base64"], validate=True)
            with Image.open(io.BytesIO(raw)) as image:
                self.assertEqual(image.size, (body["image"]["width"], body["image"]["height"]))
                self.assertEqual(image.format, "PNG")
                self.assertLessEqual(max(image.size), 672)
                colors = {color for _, color in image.getcolors()}
                self.assertIn(2, colors)  # Blue zero labels.
                self.assertIn(3, colors)  # Orange one labels.
            self.assertEqual(body["diagram"]["mode"], "periodic")
            self.assertEqual(body["diagram"]["style"], "tessellation")
            self.assertTrue(body["diagram"]["show_bits"])

    def test_automatic_size_and_verified_period(self):
        for word in ("0", "011", "01010100000001011", "1" + "0" * 4095):
            settings = tessellate.options({"bitstring": word})
            self.assertEqual((settings["columns"], settings["rows"]), (192, 384))
            self.assertEqual((settings["width"], settings["height"]), (5376, 10752))
        settings = tessellate.options({"bitstring": "011"})
        self.assertEqual(settings["spatial_period"], 3)
        self.assertEqual(settings["temporal_period"], 3)
        self.assertEqual(step(step(step(settings["first_row_word"]))), settings["first_row_word"])

        # A real period of 255 replaces the previous 24-row sample. Rows after
        # that period are derived again, rather than tiling a shorter crop.
        result = tessellate.render({"bitstring": "10011100001110101"})
        diagram = result["diagram"]
        self.assertEqual(diagram["spatial_period"], 17)
        self.assertEqual(diagram["columns"], 192)
        self.assertEqual(diagram["cell_size"], 28)
        self.assertEqual(diagram["temporal_period"], 255)
        self.assertTrue(diagram["temporal_period_fits"])
        self.assertTrue(diagram["periodic_from_first_row"])
        self.assertEqual(diagram["periodic_entry_step"], 1)
        self.assertEqual((result["image"]["width"], result["image"]["height"]), (5376, 10752))
        rows = list(tessellate._row_words(diagram["first_row_word"], 257))
        self.assertEqual(rows[0], rows[255])
        self.assertEqual(rows[1], rows[256])
        with Image.open(io.BytesIO(base64.b64decode(result["image"]["base64"]))) as image:
            # Neither boundary may have the former half-cell empty strip.
            for y in (0, 1, 7, 13, image.height - 14, image.height - 8, image.height - 1):
                colors = image.crop((0, y, image.width, y + 1)).getcolors()
                self.assertIn(1, {color for _, color in colors}, y)

    def test_former_controls_cannot_change_rendering(self):
        word = "01010100000001011"
        defaults = tessellate.options({"bitstring": word})
        legacy = tessellate.options({"bitstring": word, "style": "cells", "mode": "input",
            "rows": 512, "columns": 512, "cell_size": 4, "show_bits": False,
            "start_step": "9" * 100, "column_offset": -100})
        self.assertEqual(legacy, defaults)

    def test_api_gateway_v2_and_base64_json(self):
        payload = json.dumps({"bitstring": "01"})
        with mock.patch.object(tessellate, "MAX_COLUMNS", 24), mock.patch.object(tessellate, "MAX_ROWS", 24):
            result = api.handler({"requestContext": {"http": {"method": "POST"}},
                "body": base64.b64encode(payload.encode()).decode(), "isBase64Encoded": True}, None)
        self.assertEqual(result["statusCode"], 200)
        self.assertFalse(result["isBase64Encoded"])
        self.assertEqual(api.handler({"httpMethod": "OPTIONS"}, None)["statusCode"], 204)
        self.assertEqual(api.handler({"httpMethod": "DELETE"}, None)["statusCode"], 405)

    def test_invalid_words(self):
        invalid = ({"bitstring": ""}, {"bitstring": "0" * 4097}, {"bitstring": "1012"},
            {"bitstring": True}, {"bitstring": "01", "word": "10"})
        for data in invalid:
            status, body = self.request(data)
            self.assertEqual(status, 400, data)
            self.assertIn("error", body)
        result = api.handler({"httpMethod": "POST", "body": "bad!", "isBase64Encoded": True}, None)
        self.assertEqual(result["statusCode"], 400)

    def test_large_word_and_payload_bounds(self):
        # D**4096 is zero at n=4096, so this needs no temporal-order computation.
        rng = random.Random(31)
        dense_word = "".join(rng.choice("01") for _ in range(4095))
        for word in ("1" + "0" * 4095, dense_word):
            status, body = self.request({"bitstring": word})
            self.assertEqual(status, 200)
            self.assertEqual(body["image"]["width"], 5376)
            self.assertEqual(body["image"]["height"], 10752)
            self.assertLessEqual(len(base64.b64decode(body["image"]["base64"])), tessellate.MAX_IMAGE_BYTES)
            self.assertLess(len(json.dumps(api.response(body))), 6_000_000)
            self.assertTrue(body["diagram"]["periodic_from_first_row"])
            if len(word) == 4096:
                self.assertEqual(body["diagram"]["periodic_entry_step"], 4096)
                self.assertEqual(body["diagram"]["first_row_word"], "0" * 4096)
                self.assertEqual(body["diagram"]["absolute_start_step"], "4096")
                self.assertEqual(body["diagram"]["temporal_period"], 1)
            else:
                self.assertFalse(body["diagram"]["spatial_period_fits"])

    def test_encoded_size_fallback_and_final_limit(self):
        with mock.patch.object(tessellate, "MAX_COLUMNS", 24), mock.patch.object(tessellate, "MAX_ROWS", 32):
            with mock.patch.object(tessellate, "MAX_IMAGE_BYTES", 3000):
                result = tessellate.render({"bitstring": "10011100001110101"})
            self.assertLessEqual(len(base64.b64decode(result["image"]["base64"])), 3000)
            self.assertLess(result["diagram"]["columns"], 24)
            self.assertLess(result["diagram"]["rows"], 32)
            self.assertEqual(result["image"]["width"], result["diagram"]["columns"] * 28)
            self.assertEqual(result["image"]["height"], result["diagram"]["rows"] * 28)
        with mock.patch.object(tessellate, "MAX_COLUMNS", 1), mock.patch.object(tessellate, "MAX_ROWS", 1):
            with mock.patch.object(tessellate, "MAX_IMAGE_BYTES", 1):
                with self.assertRaisesRegex(ValueError, "encoded image"):
                    tessellate.render({"bitstring": "011"})

    def test_deadline_and_sanitized_internal_error(self):
        class NoTime:
            def get_remaining_time_in_millis(self):
                return 1000
        self.assertEqual(self.request({"bitstring": "01"}, context=NoTime())[0], 503)
        with mock.patch.object(tessellate, "render", side_effect=RuntimeError("private detail")):
            with self.assertLogs(level="ERROR"):
                status, body = self.request({"bitstring": "01"})
        self.assertEqual(status, 500)
        self.assertNotIn("private detail", body["error"])


if __name__ == "__main__":
    unittest.main()
