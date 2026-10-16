#!/usr/bin/env python3
"""Independent bounded-report audit checks, standard library only."""

import copy
from fractions import Fraction
import itertools
import json
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest.mock import patch

import boundaudit as ba


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata = ba.rs.read_json(ba.rr.ROOT / 'zto-mainnet.json')
        cls.root = Path(__file__).resolve().parent

    def request(self, rows, budget):
        return {'budget': ba.rs.display_units(budget, 18), 'contributors': [
            {'id': name, 'weight': str(weight), 'minimum': ba.rs.display_units(low, 18),
             'maximum': ba.rs.display_units(high, 18)} for name, weight, low, high in rows]}

    def check(self, request):
        report = ba.rb.allocate(request, self.metadata)
        receipt = ba.audit(request, report, self.metadata)
        self.assertEqual(receipt['report_sha256'], ba.rr.digest(report))
        return report

    def test_demo_without_allocator_or_verifier(self):
        with patch.object(ba.rb, 'allocate', side_effect=AssertionError('allocator called')), \
             patch.object(ba.rb, 'verify', side_effect=AssertionError('verifier called')), \
             patch.object(ba.rs, 'allocate', side_effect=AssertionError('ordinary allocator called')), \
             patch.object(ba.rr, 'verify', side_effect=AssertionError('receipt verifier called')):
            result = ba.demo()
        self.assertEqual(result['budget_units'], str(10**18))
        self.assertEqual(result['contributors'], 4)

    def test_seeded_feasible_policies_and_exhaustive_awards(self):
        rng = random.Random(2903)
        checked = 0
        for _ in range(600):
            rows = []
            for i in range(rng.randrange(1, 8)):
                low = rng.randrange(5)
                rows.append(('r%02d' % i, rng.randrange(8), low, low + rng.randrange(12)))
            if not any(row[1] > 0 for row in rows):
                continue
            reserved = sum(row[2] for row in rows)
            cap = sum(row[3] - row[2] for row in rows if row[1] > 0)
            if reserved + cap == 0:
                continue
            budget = rng.randrange(max(1, reserved), reserved + cap + 1)
            request = self.request(rows, budget)
            report = self.check(request)
            # A third check: enumerate award subsets and maximize remainder sum,
            # using a membership bit vector to break ties. No winner sort here.
            _, _, _, parsed = ba.rb.parse_request(request, self.metadata)
            level, quotas = ba.sweep(parsed, budget - reserved)
            floors = [q.numerator // q.denominator for q in quotas]
            left = budget - reserved - sum(floors)
            best = max(itertools.combinations(range(len(rows)), left), key=lambda chosen: (
                sum((quotas[i] - floors[i] for i in chosen), Fraction(0)),
                tuple(i in chosen for i in range(len(rows)))))
            self.assertEqual([r['rounding_unit_awarded'] for r in report['allocations']],
                             [i in best for i in range(len(rows))])
            self.assertEqual(report['waterfill_level_fraction'], str(level))
            checked += 1
        self.assertGreater(checked, 550)

    def test_multiple_caps_exact_levels_and_ties(self):
        request = self.request([('a', 100, 0, 1), ('b', 10, 0, 2),
                                ('c', 1, 0, 10), ('d', 1, 0, 10)], 10)
        report = self.check(request)
        self.assertEqual(report['waterfill_level_fraction'], '7/2')
        self.assertEqual([r['units'] for r in report['allocations']], ['1','2','4','3'])
        # Conserved, bounded units with the wrong equal-remainder winner.
        bad = copy.deepcopy(report)
        for i, units, flag in [(2, 3, False), (3, 4, True)]:
            bad['allocations'][i].update(units=str(units), amount=ba.rs.display_units(units, 18),
                                          rounding_unit_awarded=flag)
        with self.assertRaisesRegex(ba.rs.Invalid, 'ASCII tie'):
            ba.audit(request, bad, self.metadata)

    def test_non_tied_wrong_winner(self):
        request = self.request([('a', 1, 0, 10), ('b', 2, 0, 10)], 2)
        report = self.check(request)
        bad = copy.deepcopy(report)
        for i, units, flag in [(0, 0, False), (1, 2, True)]:
            bad['allocations'][i].update(units=str(units), amount=ba.rs.display_units(units, 18),
                                          at_minimum=units == 0, rounding_unit_awarded=flag)
        with self.assertRaisesRegex(ba.rs.Invalid, 'remainder'):
            ba.audit(request, bad, self.metadata)

    def test_minima_only_zero_weight_and_zero_capacity(self):
        report = self.check(self.request([('a', 2, 3, 3), ('b', 0, 4, 100)], 7))
        self.assertEqual(report['waterfill_level_fraction'], '0')
        self.assertEqual([r['units'] for r in report['allocations']], ['3', '4'])

    def test_all_caps_and_duplicate_thresholds(self):
        for budget in (2, 4, 6):
            report = self.check(self.request([('a', 1, 0, 2), ('b', 2, 0, 4), ('c', 0, 0, 90)], budget))
            self.assertEqual(report['waterfill_level_fraction'], str(Fraction(budget, 3)))
        report = self.check(self.request([('a', 1, 0, 1), ('b', 1, 0, 9)], 10))
        self.assertEqual(report['waterfill_level_fraction'], '9')

    def test_every_header_and_row_field_tampering(self):
        request = ba.rs.read_json(self.root / 'request.json')
        report = ba.rs.read_json(self.root / 'report.json')
        for key in report:
            altered = copy.deepcopy(report)
            altered.pop(key)
            with self.subTest(missing=key), self.assertRaises(ba.rs.Invalid):
                ba.audit(request, altered, self.metadata)
        for key in report['allocations'][0]:
            altered = copy.deepcopy(report)
            altered['allocations'][0].pop(key)
            with self.subTest(row_missing=key), self.assertRaises(ba.rs.Invalid):
                ba.audit(request, altered, self.metadata)
        changes = [lambda r: r.update(extra=True),
                   lambda r: r['allocations'][0].update(extra=True),
                   lambda r: r.update(rounding_units_distributed=False),
                   lambda r: r['allocations'][0].update(rounding_unit_awarded=0),
                   lambda r: r['allocations'][0].update(at_minimum=0),
                   lambda r: r['allocations'][0].update(discretionary_quota_fraction='1/2'),
                   lambda r: r.update(waterfill_level_fraction='0'),
                   lambda r: r['token'].update(block_number=1),
                   lambda r: r['allocations'].reverse()]
        for change in changes:
            altered = copy.deepcopy(report)
            change(altered)
            with self.assertRaises(ba.rs.Invalid):
                ba.audit(request, altered, self.metadata)

    def test_uint256_fractional_weights_and_permutation(self):
        maximum = ba.rs.UINT256_MAX
        request = self.request([('a', 1, maximum - 10, maximum), ('b', 1, 0, maximum)], maximum)
        request['contributors'][0]['weight'] = '0.000000000000000001'
        request['contributors'][1]['weight'] = '999999999999999999.999999999999999999'
        report = self.check(request)
        request['contributors'].reverse()
        ba.audit(request, report, self.metadata)
        self.assertEqual([r['units'] for r in report['allocations']], [str(maximum - 10), '10'])

    def test_addresses_are_propagated_and_bound(self):
        # Real public token contract strings exercise validation only, not payees.
        request = self.request([('a', 1, 0, 10), ('b', 1, 0, 10)], 5)
        request['contributors'][0]['address'] = ba.rs.TOKENS['zto']
        request['contributors'][1]['address'] = ba.rs.TOKENS['imd']
        report = self.check(request)
        self.assertTrue(report['all_recipients_supplied'])
        request['contributors'][0]['address'] = ba.rs.TOKENS['imd']
        with self.assertRaises(ba.rs.Invalid):
            ba.audit(request, report, self.metadata)

    def test_invalid_requests_metadata_and_json(self):
        request = self.request([('a', 1, 0, 1)], 2)
        with self.assertRaises(ba.rs.Invalid):
            ba.audit(request, {}, self.metadata)
        request['budget'] = '0'
        with self.assertRaises(ba.rs.Invalid):
            ba.audit(request, {}, self.metadata)
        with self.assertRaises(ba.rs.Invalid):
            ba.rs.parse_json('{"budget":"1","budget":"2"}')
        with self.assertRaises(ba.rs.Invalid):
            ba.rs.read_json(Path.cwd().parent / 'not-read.json')
        with self.assertRaises(ba.rs.Invalid):
            ba.audit(ba.rs.read_json(self.root / 'request.json'), {}, dict(self.metadata, decimals=True))

    def test_large_compact_report(self):
        request = {'budget': '1', 'contributors': [{'id': 'r%04d' % i, 'weight': '1'} for i in range(750)]}
        self.check(request)

    def test_cli_success_errors_and_overwrite_refusal(self):
        command = [sys.executable, '-B', str(self.root / 'boundaudit.py')]
        run = lambda args: subprocess.run(command + args, capture_output=True, text=True)
        self.assertEqual(run(['demo']).returncode, 0)
        args = ['audit', '--request', str(self.root / 'request.json'), '--report', str(self.root / 'report.json')]
        result = run(args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['schema'], 'boundaudit-v1')
        original = (self.root / 'report.json').read_bytes()
        self.assertEqual(run(args + ['--output', str(self.root / 'report.json')]).returncode, 2)
        self.assertEqual((self.root / 'report.json').read_bytes(), original)
        self.assertEqual(run(['audit', '--request', str(self.root / 'request.json'),
                              '--report', str(self.root / 'request.json')]).returncode, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
