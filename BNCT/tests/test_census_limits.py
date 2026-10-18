"""Output bounds must not weaken the exact census accounting."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.census import census, graph_shape
from shared.numbertheory import ComputationLimit


class CensusOutputLimitTests(unittest.TestCase):
    def assert_summary_matches(self, summary, full):
        self.assertEqual(summary["status"], "summary_only")
        self.assertIsNone(summary["graphs"])
        self.assertEqual(summary["graphs_returned"], 0)
        self.assertTrue(summary["graphs_truncated"])
        self.assertTrue(summary["reason"])
        for key in ("n", "words", "necklaces", "primitive_necklaces", "components",
                    "graph_types", "verification", "relation_states", "component_convention"):
            self.assertEqual(summary[key], full[key], key)
        self.assertTrue(all(summary["verification"].values()))

    def test_row_and_byte_caps_preserve_exact_summary(self):
        full = census(14)
        self.assertEqual(full["status"], "exact")
        self.assertEqual(full["graphs_returned"], len(full["graphs"]))
        self.assertFalse(full["graphs_truncated"])
        for limits in ({"max_graphs": 1}, {"max_graph_bytes": 1}):
            with self.subTest(limits=limits):
                self.assert_summary_matches(census(14, **limits), full)

    def test_exact_bound_includes_duplicate_updates_and_json_delimiters(self):
        # Several relations coalesce into a row, increasing its decimal counts.
        full = census(31)
        self.assertGreater(full["relation_states"], full["graph_types"])
        quoted_rows = [{key: str(value) for key, value in row.items()}
                       for row in full["graphs"]]
        bound = len(json.dumps(quoted_rows, separators=(",", ":")).encode("ascii"))
        at_bound = census(31, max_graphs=full["graph_types"], max_graph_bytes=bound)
        self.assertEqual(at_bound, full)
        self.assert_summary_matches(census(31, max_graph_bytes=bound - 1), full)

    def test_output_limits_do_not_hide_computation_failure(self):
        with self.assertRaises(ComputationLimit):
            census(14, max_states=1, max_graphs=1)

        visited = False

        def measured_shape(*args):
            nonlocal visited
            visited = True
            return graph_shape(*args)

        def deadline():
            if visited:
                raise TimeoutError("test deadline")

        # The first row is already too large, but summary totals are not yet
        # complete. A later deadline must escape, rather than return them.
        with patch("shared.census.graph_shape", side_effect=measured_shape):
            with self.assertRaises(TimeoutError):
                census(14, check=deadline, max_graph_bytes=1)

    def test_output_limit_validation(self):
        for name in ("max_graphs", "max_graph_bytes"):
            for value in (0, -1, True, False, 1.5, "1"):
                with self.subTest(name=name, value=value):
                    with self.assertRaisesRegex(ValueError, name):
                        census(1, **{name: value})
        self.assertEqual(census(3), census(3, max_graphs=None, max_graph_bytes=None))


if __name__ == "__main__":
    unittest.main()
