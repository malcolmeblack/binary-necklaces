import itertools
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lambda'))
import tools


class CalculatorToolsTest(unittest.TestCase):
    def test_small_words_against_explicit_rotation_classes(self):
        for n in range(1, 9):
            for bits in itertools.product('01', repeat=n):
                word = ''.join(bits)
                least = min(word[i:] + word[:i] for i in range(n))
                self.assertEqual(tools.least_rotation(word), least)
                facts = tools.local_properties(word)
                for preimage in facts['necklace']['preimages']:
                    image = tools.local_properties(preimage)['word']['adjacent_xor']
                    self.assertEqual(tools.least_rotation(image), least)

    def test_fixed_necklace_does_not_require_literal_equality(self):
        facts = tools.local_properties('1100101')
        self.assertTrue(facts['necklace']['fixed'])
        self.assertNotEqual(facts['word']['value'], facts['word']['adjacent_xor'])

    def test_current_response_keeps_deferred_fields_and_integer_strings(self):
        data = tools.local_properties('001')
        data.update(component={'status': 'deferred', 'cycle_length': None},
                    power_set={'words': '8', 'census': {'status': 'deferred'}})
        with patch.object(tools, '_request_calculator', return_value=data):
            result = tools.call_tool('get_properties', {'bitstring': '001'}, timeout_seconds=3)
        self.assertEqual(result['power_set']['words'], '8')
        self.assertEqual(result['component']['status'], 'deferred')
        self.assertIsNone(result['component']['cycle_length'])

    def test_service_failure_returns_only_identified_local_facts(self):
        with patch.object(tools, '_request_calculator', side_effect=RuntimeError('internal details')):
            result = tools.call_tool('get_properties', {'bitstring': '001'}, timeout_seconds=3)
        self.assertEqual(result['word']['value'], '001')
        self.assertEqual(result['component']['status'], 'unavailable')
        self.assertNotIn('internal details', json.dumps(result))

    def test_graph_excerpt_is_explicit_and_counts_retained(self):
        data = tools.local_properties('001')
        data['power_set'] = {'census': {'status': 'exact', 'components': '400',
            'graphs': [{'name': f'G{i}-20'} for i in range(20)],
            'graphs_returned': 20, 'graphs_truncated': False}}
        result = tools._bounded_result(data, tools.local_properties('001'))
        census = result['power_set']['census']
        self.assertEqual(len(census['graphs']), 12)
        self.assertTrue(census['graphs_truncated'])
        self.assertEqual(census['components'], '400')

    def test_maximum_width_local_result_fits_model_tool_allowance(self):
        for word in ('0' * 4096, '01' * 2048, '0' * 4095 + '1'):
            with patch.object(tools, '_request_calculator', side_effect=RuntimeError()):
                result = tools.call_tool('get_properties', {'bitstring': word}, timeout_seconds=1)
            self.assertLess(len(json.dumps(result).encode()), tools.MAX_TOOL_BYTES)
            self.assertEqual(result['word']['value'], word)

    def test_invalid_tool_arguments_never_contact_the_service(self):
        with patch.object(tools, '_request_calculator') as request:
            for args in ({'bitstring': '102'}, {'bitstring': ''},
                         {'bitstring': '0' * 4097}, {'bitstring': 101},
                         {'bitstring': '001', 'url': 'https://example.com'}):
                with self.assertRaises(ValueError):
                    tools.call_tool('get_properties', args, timeout_seconds=1)
            request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
