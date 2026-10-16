#!/usr/bin/env python3
"""Behavioral checks for fixed-order capped schedules."""

from decimal import Decimal
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(__file__).with_name('capguard.py')
spec = importlib.util.spec_from_file_location('capguard_under_test', SCRIPT)
capguard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capguard)


class CapguardTests(unittest.TestCase):
    def test_demo(self):
        result = capguard.analyze(*capguard.demo())
        self.assertEqual(result['baseline_fixed_order_finish'], '9')
        self.assertEqual(result['capped_fixed_order_finish'], '10')
        self.assertEqual(result['deadline_margin_under_caps'], '0')
        self.assertEqual(result['one_worst_case_path'], ['read', 'build', 'check'])

    def test_deadline_boundary(self):
        args = list(capguard.demo())
        args[-1] = Decimal('9.999')
        result = capguard.analyze(*args)
        self.assertFalse(result['safe_under_caps'])
        self.assertEqual(result['deadline_margin_under_caps'], '-0.001')

    def test_idle_gaps_are_removed(self):
        tasks, plan, caps, workers, budget = capguard.demo()
        plan = json.loads(json.dumps(plan))
        plan['schedule'][-1].update(start=9, finish=11)
        plan['finish'] = 11
        result = capguard.analyze(tasks, plan, caps, workers, budget)
        self.assertEqual(result['input_plan_finish'], '11')
        self.assertEqual(result['baseline_fixed_order_finish'], '9')
        self.assertEqual(result['capped_fixed_order_finish'], '10')

    def test_exact_decimal_plan_json(self):
        tasks = {'tasks': [{'id': 'a', 'minutes': Decimal('0.1')},
                           {'id': 'b', 'minutes': Decimal('0.2'), 'after': ['a']}]}
        plan = {'workers': 1, 'finish': Decimal('0.3'), 'schedule': [
            {'task': 'a', 'worker': 1, 'start': 0, 'finish': Decimal('0.1')},
            {'task': 'b', 'worker': 1, 'start': Decimal('0.1'), 'finish': Decimal('0.3')}]}
        result = capguard.analyze(tasks, plan,
                                  {'maximum_minutes': {'a': Decimal('0.2')}},
                                  1, Decimal('0.4'))
        packed = capguard.render_json(result)
        parsed = json.loads(packed, parse_float=Decimal)
        self.assertEqual(parsed['capped_earliest_plan']['finish'], Decimal('0.4'))
        self.assertEqual(parsed['capped_earliest_plan']['schedule'][1]['start'],
                         Decimal('0.2'))

    def test_invalid_caps(self):
        tasks, plan, _, workers, budget = capguard.demo()
        for bad in ({'maximum_minutes': {'build': 4}},
                    {'maximum_minutes': {'ghost': 7}},
                    {'maximum_minutes': {'build': '6'}},
                    {'maximum_minutes': {}, 'extra': 1}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                capguard.analyze(tasks, plan, bad, workers, budget)

    def test_invalid_plan(self):
        tasks, plan, caps, workers, budget = capguard.demo()
        plan = json.loads(json.dumps(plan))
        plan['schedule'][1]['start'] = 1
        with self.assertRaisesRegex(ValueError, 'invalid input plan'):
            capguard.analyze(tasks, plan, caps, workers, budget)

    def test_all_duration_combinations(self):
        tasks, plan, _, workers, _ = capguard.demo()
        maximum = {'read': 3, 'build': 6, 'fixtures': 5, 'check': 3}
        result = capguard.analyze(tasks, plan, {'maximum_minutes': maximum},
                                  workers, 12)
        originals = {'read': 2, 'build': 5, 'fixtures': 3, 'check': 2}
        edges = {'read': [], 'build': ['read'], 'fixtures': ['read'],
                 'check': ['build', 'fixtures']}
        highest = 0
        combinations = 0
        # Separate forward calculation, repeated for all integer vectors.
        for values in itertools.product(*(range(originals[k], maximum[k] + 1)
                                          for k in originals)):
            combinations += 1
            lengths = dict(zip(originals, values))
            finish = {}
            for name in ('read', 'build', 'fixtures', 'check'):
                finish[name] = max((finish[d] for d in edges[name]), default=0) + lengths[name]
            highest = max(highest, max(finish.values()))
        self.assertEqual(combinations, 24)
        self.assertEqual(highest, 12)
        self.assertEqual(result['capped_fixed_order_finish'], str(highest))

    def test_worker_order_creates_path(self):
        tasks = {'tasks': [{'id': 'a', 'minutes': 2},
                           {'id': 'b', 'minutes': 2},
                           {'id': 'c', 'minutes': 1, 'after': ['b']}]}
        plan = {'workers': 2, 'finish': 5, 'schedule': [
            {'task': 'a', 'worker': 1, 'start': 0, 'finish': 2},
            {'task': 'b', 'worker': 1, 'start': 2, 'finish': 4},
            {'task': 'c', 'worker': 2, 'start': 4, 'finish': 5}]}
        report = capguard.analyze(tasks, plan,
                                  {'maximum_minutes': {'a': 3, 'b': 4}}, 2, 8)
        self.assertEqual(report['capped_fixed_order_finish'], '8')
        self.assertEqual(report['one_worst_case_path'], ['a', 'b', 'c'])
        self.assertEqual([r['start'] for r in report['capped_earliest_plan']['schedule']],
                         [Decimal(0), Decimal(3), Decimal(7)])

    def test_cli_exits(self):
        good = subprocess.run([sys.executable, '-B', str(SCRIPT), '--demo'],
                              cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertTrue(json.loads(good.stdout)['safe_under_caps'])
        missed = subprocess.run([
            sys.executable, '-B', str(SCRIPT),
            '--tasks', 'line-1/tools/plancheck/tasks.json',
            '--plan', 'line-1/tools/plancheck/plan.json',
            '--caps', 'line-1/tools/capguard/caps.json',
            '--workers', '2', '--budget', '6'],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(missed.returncode, 2, missed.stderr)
        self.assertFalse(json.loads(missed.stdout)['safe_under_caps'])


if __name__ == '__main__':
    unittest.main()
