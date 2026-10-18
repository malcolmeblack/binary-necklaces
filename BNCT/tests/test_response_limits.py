"""Endpoint-size, deadline and certificate limits without large enumerations."""
import copy
import json
import unittest
from unittest.mock import patch

from test_api import calculator, invoke
from shared import algebra, numbertheory as nt
from shared.census import _order


class ResponseLimitTests(unittest.TestCase):
    def test_maximum_width_maximum_preview_and_odd_width(self):
        for word in ('1' + '0' * 4095, '0' * 4095):
            with self.subTest(n=len(word)):
                event = {'httpMethod': 'POST', 'body': json.dumps({
                    'bitstring': word, 'preview_limit': 64, 'census': len(word) == 4096})}
                packed = calculator.handler(event, None)
                self.assertEqual(packed['statusCode'], 200)
                self.assertLessEqual(len(json.dumps(packed).encode()), calculator.MAX_RESPONSE_BYTES)
                data = json.loads(packed['body'])
                self.assertEqual(data['power_set']['words'], str(1 << len(word)))
                self.assertLessEqual(len(data['necklace']['preimages']), 2)
                for preview in data['preview'].values():
                    self.assertLessEqual(len(preview['items']), 64)
                    self.assertEqual(preview['returned'], len(preview['items']))
                    self.assertEqual(preview['limit'], 64)
                    self.assertEqual(preview['truncated'], preview['status'] == 'truncated')
                if len(word) == 4096:
                    self.assertEqual(data['preview']['tree']['returned'], 64)
                    self.assertEqual(data['preview']['tree']['reason'], 'item_limit')
                    self.assertEqual(len(data['tree']['branching_sequence']), 4097)
                    self.assertTrue(all(data['power_set']['census']['verification'].values()))

    def test_preview_deadline_preserves_valid_prefix_and_total(self):
        ticks = 0

        def stop_after_three():
            nonlocal ticks
            ticks += 1
            if ticks > 3:
                raise TimeoutError('test cutoff')

        full = algebra.analyze_word('1' + '0' * 15, preview_limit=64)
        tree = full['tree']
        preview = algebra._tree_preview(tree['root'], tree['necklaces'], 64, stop_after_three)
        self.assertEqual(preview['items'], full['preview']['tree']['items'][:3])
        self.assertEqual(preview['returned'], 3)
        self.assertEqual(preview['total'], tree['necklaces'])
        self.assertEqual(preview['reason'], 'time_limit')
        self.assertEqual(preview['status'], 'truncated')
        closed = algebra._cycle_preview('011', None, 1)
        self.assertEqual(closed['total'], 1)
        self.assertEqual(closed['status'], 'complete')

    def test_expired_request_skips_optional_lists(self):
        class Deadline:
            def get_remaining_time_in_millis(self):
                return 3000

        status, result = invoke({'bitstring': '1001011', 'census': True}, context=Deadline())
        self.assertEqual(status, 200)
        self.assertEqual(result['component']['status'], 'deferred')
        self.assertEqual(result['power_set']['census']['status'], 'deferred')
        self.assertEqual(result['power_set']['words'], '128')
        for preview in result['preview'].values():
            self.assertEqual(preview['returned'], 0)
            self.assertEqual(preview['reason'], 'time_limit')
        self.assertLessEqual(len(result['necklace']['preimages']), 2)

    def test_total_payload_fallback_keeps_exact_scalar_results(self):
        original = calculator.calculate({'bitstring': '1' + '0' * 127,
                                         'census': True, 'preview_limit': 64})
        with patch.object(calculator, 'MAX_RESPONSE_BYTES', 10000):
            packed = calculator.bounded_response(copy.deepcopy(original))
        self.assertLessEqual(len(json.dumps(packed).encode()), 10000)
        result = json.loads(packed['body'])
        for key in ('word', 'necklace', 'dynamics', 'tree', 'component'):
            self.assertEqual(result[key], original[key])
        census = result['power_set']['census']
        self.assertEqual(census['status'], 'summary_only')
        self.assertIsNone(census['graphs'])
        self.assertEqual(census['components'], original['power_set']['census']['components'])
        self.assertTrue(all(census['verification'].values()))
        self.assertEqual(result['preview']['tree']['reason'], 'response_size')
        self.assertEqual(result['preview']['tree']['total'], original['preview']['tree']['total'])

    def test_proxy_escaping_is_included_in_size_limit(self):
        # The inner body fits this allowance, but escaping it as the Lambda
        # proxy body's string does not. Headers and envelope also count.
        with patch.object(calculator, 'MAX_RESPONSE_BYTES', 3500):
            self.assertIsNone(calculator._pack_response({'x': '\\' * 1000}))

    def test_certificate_depth_defers_instead_of_overflowing(self):
        # This proven prime needs a recursive n-1 certificate.
        factorer = nt._Factorer(None)
        with patch.object(nt, 'MAX_FACTOR_DEPTH', 1):
            with self.assertRaisesRegex(nt.ComputationLimit, 'certificate-depth'):
                factorer.factor((1 << 89) - 1)
        self.assertEqual(factorer.depth, 0)
        with patch.object(nt, 'MAX_FACTOR_DEPTH', 0):
            status, result = invoke({'bitstring': '001', 'census': True})
        self.assertEqual(status, 200)
        self.assertEqual(result['component']['status'], 'deferred')
        self.assertEqual(result['power_set']['census']['status'], 'deferred')
        self.assertEqual(result['power_set']['words'], '8')

    def test_large_order_bound_is_allowed_but_cancellable(self):
        # No huge factorization is performed: verify that a bound fitting an
        # accepted width reaches the cancellable factorer, not the old cap.
        with patch('shared.census.ff.pow_mod', return_value=1), \
                patch('shared.census.factor_integer', side_effect=TimeoutError('test deadline')) as factor:
            with self.assertRaisesRegex(TimeoutError, 'test deadline'):
                _order(3, 7, (1 << 4092) - 1, None, {})
            factor.assert_called_once()
        with self.assertRaises(ValueError):
            algebra.analyze_word('0' * 4097)


if __name__ == '__main__':
    unittest.main()
