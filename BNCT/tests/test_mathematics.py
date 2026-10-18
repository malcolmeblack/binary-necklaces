"""Independent finite-state oracles and saved-output regression checks.

The oracle uses strings, explicit rotations, and graph traversal. It does not
use the calculator's polynomial arithmetic, order finding, or census formulas.
Run: python -m unittest discover -s tests -v
Optional larger reference checks: BNCT_LARGE_TESTS=1 python -m unittest discover -s tests -v
"""

import functools
import csv
import io
import itertools
import os
from pathlib import Path
import random
import sys
import time
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@functools.lru_cache(maxsize=1)
def reference_census():
    """Independent saved results for n=1..1024; never imported at runtime."""
    with zipfile.ZipFile(Path(__file__).with_name("reference-census.zip")) as archive:
        with archive.open("powersets.csv") as raw:
            result = {row["n"]: {"powerset": row, "graphs": []}
                      for row in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"))}
        with archive.open("graphs.csv") as raw:
            for row in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8")):
                result[row["n"]]["graphs"].append(row)
    return result


def rotations(word):
    return [word[i:] + word[:i] for i in range(len(word))]


def canonical(word):
    return min(rotations(word))


def step(word):
    return "".join("1" if ch != word[i - 1] else "0"
                   for i, ch in enumerate(word))


def trajectory(word, necklace=False):
    seen, path = {}, []
    while word not in seen:
        seen[word] = len(path)
        path.append(word)
        word = step(word)
        if necklace:
            word = canonical(word)
    return path, seen[word]


def spatial_period(word):
    return len(set(rotations(word)))


@functools.lru_cache(maxsize=12)
def oracle(n):
    words = ["".join(chars) for chars in itertools.product("01", repeat=n)]
    vertices = sorted({canonical(word) for word in words})
    edges = {word: canonical(step(word)) for word in vertices}
    incoming = {word: [] for word in vertices}
    for word, target in edges.items():
        incoming[target].append(word)

    component_for = {}
    entry_for = {}
    depth_for = {}
    components = {}
    for vertex in vertices:
        path, start = trajectory(vertex, necklace=True)
        cycle = tuple(sorted(path[start:]))
        component_for[vertex] = cycle
        entry_for[vertex] = path[start]
        depth_for[vertex] = start
        components.setdefault(cycle, []).append(vertex)

    tree_for = {}
    graph_rows = {}
    component_info = {}
    for cycle, members in components.items():
        cycle_set = set(cycle)
        trees = []
        for root in cycle:
            levels, seen = [[root]], {root}
            while True:
                next_level = []
                for vertex in levels[-1]:
                    for source in incoming[vertex]:
                        if source not in cycle_set and source not in seen:
                            seen.add(source)
                            next_level.append(source)
                if not next_level:
                    break
                levels.append(sorted(next_level))
            branching = []
            for level in levels:
                indegrees = {len(incoming[vertex]) for vertex in level}
                assert len(indegrees) == 1, (n, root, level, indegrees)
                branching.append(str(indegrees.pop()))
            tree = {
                "root": root,
                "depth": len(levels) - 1,
                "levels": len(levels),
                "branching_sequence": "".join(branching),
                "necklaces": len(seen),
                "words": sum(spatial_period(vertex) for vertex in seen),
                "members": seen,
                "level_members": levels,
            }
            tree_for[root] = tree
            trees.append(tree)
        shape = {(t["depth"], t["branching_sequence"], t["necklaces"])
                 for t in trees}
        assert len(shape) == 1, (n, cycle, shape)
        tree = trees[0]
        name = "G{}-{}".format(len(cycle), tree["branching_sequence"])
        info = {
            "name": name,
            "cycle_length": len(cycle),
            "branching_sequence": tree["branching_sequence"],
            "depth": tree["depth"],
            "necklaces": len(members),
            "words": sum(spatial_period(vertex) for vertex in members),
            "primitive_necklaces": sum(spatial_period(vertex) == n
                                       for vertex in members),
        }
        component_info[cycle] = info
        if name not in graph_rows:
            graph_rows[name] = {
                key: info[key] for key in
                ("name", "cycle_length", "branching_sequence", "depth", "necklaces")
            }
            graph_rows[name].update(components=0, total_words=0,
                                    total_necklaces=0, total_primitive_necklaces=0)
        row = graph_rows[name]
        assert row["necklaces"] == len(members)
        row["components"] += 1
        row["total_words"] += info["words"]
        row["total_necklaces"] += info["necklaces"]
        row["total_primitive_necklaces"] += info["primitive_necklaces"]

    return {
        "words": words, "vertices": vertices, "edges": edges,
        "incoming": incoming, "component_for": component_for,
        "component_info": component_info, "entry_for": entry_for,
        "depth_for": depth_for, "tree_for": tree_for,
        "graphs": graph_rows, "components": len(components),
        "primitive_necklaces": sum(spatial_period(word) == n for word in vertices),
    }


class WordAlgebraTests(unittest.TestCase):
    def test_every_word_through_width_ten(self):
        from shared.algebra import analyze_word

        for n in range(1, 11):
            expected = oracle(n)
            for word in expected["words"]:
                with self.subTest(n=n, word=word):
                    actual = analyze_word(word, preview_limit=0)
                    properties = actual["word"]
                    self.assertEqual(properties["length"], n)
                    self.assertEqual(properties["weight"], word.count("1"))
                    self.assertEqual(properties["parity"],
                                     "odd" if word.count("1") % 2 else "even")
                    self.assertEqual(properties["complement"],
                                     word.translate(str.maketrans("01", "10")))
                    self.assertEqual(properties["reversal"], word[::-1])
                    self.assertEqual(properties["palindrome"], word == word[::-1])
                    self.assertEqual(properties["adjacent_xor"], step(word))
                    period = spatial_period(word)
                    self.assertEqual(properties["spatial_period"], period)
                    self.assertEqual(properties["primitive_root"], word[:period])
                    necklace = actual["necklace"]
                    representative = canonical(word)
                    self.assertEqual(necklace["least_rotation"], representative)
                    self.assertEqual(necklace["chirality"], "achiral"
                                     if canonical(word[::-1]) == representative else "chiral")
                    self.assertEqual(necklace["self_complementary"],
                                     canonical(properties["complement"]) == representative)
                    self.assertEqual(sorted(necklace["preimages"]),
                                     sorted(expected["incoming"][representative]))

                    path, start = trajectory(word)
                    entry = path[start]
                    self.assertEqual(actual["dynamics"]["transient_depth"], start)
                    self.assertEqual(actual["dynamics"]["cycle_entry"], entry)
                    self.assertEqual(actual["dynamics"]["periodic_spatial_period"],
                                     spatial_period(entry))
                    root = canonical(entry)
                    tree = expected["tree_for"][root]
                    for key in ("root", "depth", "levels", "branching_sequence",
                                "necklaces", "words"):
                        self.assertEqual(actual["tree"][key], tree[key], key)
                    component = expected["component_info"][expected["component_for"][root]]
                    measured = actual["component"]
                    self.assertEqual(measured["status"], "exact")
                    self.assertEqual(measured["cycle_length"], component["cycle_length"])
                    self.assertEqual(measured["word_period"], len(path) - start)
                    self.assertEqual(measured["graph_name"], component["name"])
                    self.assertEqual(measured["necklaces"], component["necklaces"])
                    self.assertEqual(measured["words"], component["words"])

    def test_shift_uses_right_rotation(self):
        from shared.algebra import analyze_word

        for word in ("1001011", "010011", "110000111", "10100100101"):
            with self.subTest(word=word):
                result = analyze_word(word, preview_limit=0)
                entry = result["dynamics"]["cycle_entry"]
                after = entry
                for _ in range(result["component"]["cycle_length"]):
                    after = step(after)
                shift = result["component"]["rotation_shift"]
                self.assertGreaterEqual(shift, 0)
                self.assertLess(shift, spatial_period(entry))
                self.assertEqual(after, entry[-shift:] + entry[:-shift] if shift else entry)

    def test_achiral_need_not_be_palindromic(self):
        from shared.algebra import analyze_word

        result = analyze_word("01")
        self.assertFalse(result["word"]["palindrome"])
        self.assertEqual(result["necklace"]["chirality"], "achiral")

    def test_explicit_previews_are_exact_and_bounded(self):
        from shared.algebra import analyze_word

        for n in range(1, 9):
            expected = oracle(n)
            for word in expected["vertices"]:
                with self.subTest(n=n, word=word):
                    actual = analyze_word(word, preview_limit=64)
                    root = canonical(actual["dynamics"]["cycle_entry"])
                    tree = expected["tree_for"][root]
                    preview = actual["preview"]["tree"]
                    self.assertFalse(preview["truncated"])
                    self.assertEqual(preview["total"], tree["necklaces"])
                    self.assertEqual(len(preview["items"]), tree["necklaces"])
                    self.assertEqual({item["word"] for item in preview["items"]}, tree["members"])
                    for item in preview["items"]:
                        self.assertIn(item["word"], tree["level_members"][item["depth"]])
                    cycle = actual["preview"]["cycle"]
                    path, start = trajectory(root, necklace=True)
                    self.assertEqual(start, 0)
                    self.assertEqual(cycle["items"], path)
                    self.assertEqual(cycle["total"], len(path))
                    self.assertFalse(cycle["truncated"])
        limited = analyze_word("10000000", preview_limit=3)
        self.assertEqual(len(limited["preview"]["tree"]["items"]), 3)
        self.assertTrue(limited["preview"]["tree"]["truncated"])

    def test_sampled_larger_word_orbits(self):
        from shared.algebra import analyze_word

        rng = random.Random(12031)
        for n in (11, 12, 14, 15, 16, 18, 20, 21, 24, 28, 30, 32, 48, 64):
            for _ in range(4):
                word = "".join(rng.choice("01") for _ in range(n))
                with self.subTest(n=n, word=word):
                    actual = analyze_word(word, preview_limit=0)
                    path, start = trajectory(word)
                    self.assertEqual(actual["dynamics"]["transient_depth"], start)
                    self.assertEqual(actual["dynamics"]["cycle_entry"], path[start])
                    self.assertEqual(actual["component"]["word_period"], len(path) - start)
                    necklace_path, necklace_start = trajectory(canonical(word), necklace=True)
                    self.assertEqual(actual["component"]["cycle_length"],
                                     len(necklace_path) - necklace_start)

    def test_fast_jump_matches_iterated_adjacent_xor(self):
        from shared.algebra import xor_jump

        rng = random.Random(901)
        for n in range(1, 26):
            word = "".join(rng.choice("01") for _ in range(n))
            after = word
            for steps in range(129):
                self.assertEqual(xor_jump(word, steps), after, (n, steps))
                after = step(after)


class CensusTests(unittest.TestCase):
    def test_enumerated_components_through_width_twelve(self):
        from shared.census import census

        for n in range(1, 13):
            with self.subTest(n=n):
                expected = oracle(n)
                actual = census(n)
                self.assertEqual(actual["status"], "exact")
                self.assertEqual(actual["n"], n)
                self.assertEqual(actual["words"], len(expected["words"]))
                self.assertEqual(actual["necklaces"], len(expected["vertices"]))
                self.assertEqual(actual["primitive_necklaces"], expected["primitive_necklaces"])
                self.assertEqual(actual["components"], expected["components"])
                self.assertEqual(actual["graph_types"], len(expected["graphs"]))
                rows = {row["name"]: row for row in actual["graphs"]}
                self.assertEqual(set(rows), set(expected["graphs"]))
                for name, expected_row in expected["graphs"].items():
                    for key, value in expected_row.items():
                        self.assertEqual(rows[name][key], value, (name, key))
                self.assertTrue(all(actual["verification"].values()))

    def test_equal_shapes_can_have_unequal_word_masses(self):
        from shared.census import census

        result = census(3)
        self.assertEqual(result["graph_types"], 1)
        row = result["graphs"][0]
        self.assertEqual(row["name"], "G1-20")
        self.assertEqual(row["components"], 2)
        self.assertEqual(row["total_words"], 8)
        masses = sorted(component["words"] for component in oracle(3)["component_info"].values())
        self.assertEqual(masses, [2, 6])

    def check_saved_width(self, n, seconds):
        from shared.census import census

        expected = reference_census()[str(n)]
        deadline = time.monotonic() + seconds

        def check():
            if time.monotonic() > deadline:
                raise TimeoutError("Reference check exceeded {} seconds for n={}".format(seconds, n))

        actual = census(n, check=check)
        powerset_fields = {
            "words": "bitstrings", "necklaces": "bitloops",
            "primitive_necklaces": "factors", "components": "chains",
            "graph_types": "graphs",
        }
        for key, old_key in powerset_fields.items():
            self.assertEqual(actual[key], int(expected["powerset"][old_key]), (n, key))
        actual_graphs = {graph["name"]: graph for graph in actual["graphs"]}
        expected_graphs = {graph["name"]: graph for graph in expected["graphs"]}
        self.assertEqual(set(actual_graphs), set(expected_graphs))
        fields = {
            "cycle_length": "cycle-order", "depth": "tree-depth",
            "necklaces": "bitloops-per-chain", "components": "chains",
            "total_words": "bitstrings", "total_necklaces": "bitloops",
            "total_primitive_necklaces": "factors",
        }
        for name, expected_row in expected_graphs.items():
            self.assertEqual(actual_graphs[name]["branching_sequence"], expected_row["signature"])
            for key, old_key in fields.items():
                self.assertEqual(actual_graphs[name][key], int(expected_row[old_key]), (n, name, key))

    def test_selected_supplied_results(self):
        for n in (14, 24, 31, 43, 48, 49, 50, 63, 64, 96, 127, 128):
            with self.subTest(n=n):
                self.check_saved_width(n, seconds=8)

    @unittest.skipUnless(os.getenv("BNCT_LARGE_TESTS") == "1", "optional larger census regression")
    def test_larger_supplied_results(self):
        for n in (255, 256, 511, 512, 1023, 1024):
            with self.subTest(n=n):
                self.check_saved_width(n, seconds=15)


if __name__ == "__main__":
    unittest.main()
