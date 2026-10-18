"""Automatic, finite tessellations of periodic adjacent-XOR dynamics.

Rows use D(w)[i] = w[i] XOR w[i-1], including the cyclic boundary.  The
staggered drawing is the horizontal reflection of the original tessellator's
coordinate convention, so its literal rows now agree with the calculator.
"""

import base64
import io
import math

from PIL import Image, ImageDraw, ImageFont

from shared.algebra import periodic_entry, primitive_root
from shared.http_api import API_VERSION, binary_word


CELL_SIZE = 28
MAX_COLUMNS = 192
MAX_ROWS = 384
# Base64 expansion still leaves ample room for the JSON proxy envelope below
# Lambda's 6 MB synchronous response limit.
MAX_IMAGE_BYTES = 3_500_000


def _bounded_period(word, budget=None):
    """Certify a literal temporal period within a bounded number of steps."""
    for step, row in enumerate(_row_words(word, MAX_ROWS + 1)):
        if budget is not None:
            budget.check()
        if step and row == word:
            return step
    return None


def options(data, budget=None):
    """Choose a bounded, labelled tessellation from the input word alone.

    Former rendering options are ignored so existing callers can still send
    them, but they cannot select a different drawing or disable its labels.
    """
    word = data.get("bitstring", data.get("word", ""))
    word = binary_word({"bitstring": word})
    if "bitstring" in data and "word" in data and data["bitstring"] != data["word"]:
        raise ValueError("word and bitstring must agree when both are supplied.")
    if budget is not None:
        budget.check()
    entry, transient_depth = periodic_entry(word)
    spatial_period = len(primitive_root(entry))
    temporal_period = _bounded_period(entry, budget)
    # The finite image supplies room to pan and zoom. Neither its dimensions
    # nor a short certified period replace the full cyclic word in the rule.
    columns, rows = MAX_COLUMNS, MAX_ROWS
    return {
        "word": word, "first_row_word": entry,
        "periodic_entry_step": transient_depth,
        "spatial_period": spatial_period, "temporal_period": temporal_period,
        "mode": "periodic", "style": "tessellation", "rows": rows,
        "columns": columns, "cell_size": CELL_SIZE, "column_offset": 0,
        "show_bits": True, "start_step": 0,
        "width": columns * CELL_SIZE, "height": rows * CELL_SIZE,
    }


def _row_words(word, count):
    """Yield a bounded number of exact rows, regardless of temporal period."""
    n = len(word)
    value = int(word, 2)
    for _ in range(count):
        yield format(value, f"0{n}b")
        right = (value >> 1) | ((value & 1) << (n - 1))
        value ^= right


def create_image(word, settings, budget=None):
    """Draw exact rows using a fixed palette, with finite viewport clipping."""
    rows, columns = settings["rows"], settings["columns"]
    cell, offset = settings["cell_size"], settings["column_offset"]
    width, height = settings["width"], settings["height"]
    image = Image.new("P", (width, height), 0)
    # Background, edge/one-cell, zero label, one label.
    palette = [208, 208, 208, 64, 64, 64, 0, 136, 255, 255, 136, 0]
    image.putpalette(palette + [0] * (768 - len(palette)))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=round(cell * .55))
    line_width = max(1, round(cell / 8))
    n = len(word)

    # Place lattice rows on both boundaries. Every strip is then filled by
    # its actual edges/triangles, without an unrendered half-cell margin.
    row_words = tuple(_row_words(word, rows + 1))
    for row, bits in enumerate(row_words):
        if budget is not None:
            budget.check()
        shift = -row / 2
        y = height - row * cell
        # Include off-screen neighbors so lines/triangles clip naturally at edges.
        first = math.floor(offset - shift) - 2
        last = math.ceil(offset + columns - shift) + 2
        for i in range(first, last):
            a, b, c = bits[i % n], bits[(i - 1) % n], bits[(i - 2) % n]
            x = (i + shift - offset + .5) * cell
            lower0, lower2 = (x, y), (x - cell, y)
            upper1, upper3 = (x - cell / 2, y - cell), (x - cell * 1.5, y - cell)
            if row < rows:
                if a == "0" and b == "1":
                    if c == "0":
                        draw.polygon((lower2, upper1, upper3), fill=1)
                        draw.line((lower2, upper1, upper3, lower2), fill=1, width=line_width)
                    else:
                        draw.line((lower2, upper1), fill=1, width=line_width)
                elif a == "1" and b == "0":
                    draw.line((lower0, upper1), fill=1, width=line_width)
            if a == b == "1":
                draw.line((lower0, lower2), fill=1, width=line_width)

    # Labels are always drawn, after every edge so no later edge obscures them.
    for row, bits in enumerate(row_words):
        if budget is not None:
            budget.check()
        shift = -row / 2
        y = height - row * cell
        first = math.floor(offset - shift) - 2
        last = math.ceil(offset + columns - shift) + 2
        for i in range(first, last):
            x = (i + shift - offset + .5) * cell
            bit = bits[i % n]
            box = draw.textbbox((x, y), bit, font=font, anchor="mm")
            # Do not show fragments of labels on clipped boundary cells.
            if box[0] >= 0 and box[1] >= 0 and box[2] <= width and box[3] <= height:
                draw.text((x, y), bit, fill=2 + int(bit), font=font, anchor="mm")

    return image


def render(data, budget=None):
    settings = options(data, budget)
    word, first_word = settings["word"], settings["first_row_word"]
    while True:
        if budget is not None:
            budget.check()
        image = create_image(first_word, settings, budget)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=False, compress_level=6)
        raw = buffer.getvalue()
        image.close()
        if budget is not None:
            budget.check()
        if len(raw) <= MAX_IMAGE_BYTES:
            break
        # Bound transmission even for an unusually poorly compressing image.
        # Cropping a smaller exact region preserves the rule and native labels.
        if settings["rows"] == settings["columns"] == 1:
            raise ValueError("The encoded image is too large.")
        settings["rows"] = max(1, settings["rows"] // 2)
        settings["columns"] = max(1, settings["columns"] // 2)
        settings["width"] = settings["columns"] * CELL_SIZE
        settings["height"] = settings["rows"] * CELL_SIZE
    return {
        "api_version": API_VERSION,
        "image": {
            "mime_type": "image/png", "base64": base64.b64encode(raw).decode("ascii"),
            "width": settings["width"], "height": settings["height"],
        },
        "diagram": {
            "n": len(word), "mode": "periodic", "style": "tessellation",
            "rows": settings["rows"], "columns": settings["columns"],
            "cell_size": CELL_SIZE, "show_bits": True,
            "column_offset": 0, "start_step": "0",
            "absolute_start_step": str(settings["periodic_entry_step"]),
            "periodic_entry_step": settings["periodic_entry_step"],
            "first_row_word": first_word,
            "rule": "D(w)[i] = w[i] XOR w[(i-1) mod n]",
            "time_direction": "bottom-to-top",
            "periodic_from_first_row": True,
            "spatial_period": settings["spatial_period"],
            "spatial_period_fits": settings["spatial_period"] <= settings["columns"],
            "temporal_period": settings["temporal_period"],
            "temporal_period_fits": (settings["temporal_period"] is not None
                                     and settings["temporal_period"] <= settings["rows"]),
        },
    }
