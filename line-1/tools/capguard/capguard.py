#!/usr/bin/env python3
"""Check a deadline against simultaneous task-duration caps for a fixed plan."""

import argparse
from decimal import Decimal, localcontext
from fractions import Fraction
import heapq
import importlib.util
import json
from pathlib import Path
import sys

_spec = importlib.util.spec_from_file_location(
    'capguard_plancheck', Path(__file__).resolve().parents[1] / 'plancheck/plancheck.py')
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)


def exact(value):
    """Render bounded terminating decimal arithmetic without float rounding."""
    with localcontext() as context:
        context.prec = 512
        rendered = format(Decimal(value.numerator) / Decimal(value.denominator), 'f')
    return rendered.rstrip('0').rstrip('.') if '.' in rendered else rendered


def render_json(value):
    """Keep plan times as exact JSON numbers; other report measures are strings."""
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError('nonfinite output number')
        return format(value, 'f')
    if isinstance(value, dict):
        return '{' + ','.join(json.dumps(key) + ':' + render_json(item)
                              for key, item in value.items()) + '}'
    if isinstance(value, list):
        return '[' + ','.join(render_json(item) for item in value) + ']'
    return json.dumps(value, allow_nan=False)


def _fixed_graph(tasks, plan):
    parents = {name: set(deps) for name, (_, deps) in tasks.items()}
    workers = {name: row['worker'] for row in plan['schedule'] for name in [row['task']]}
    groups = {}
    for row in plan['schedule']:
        groups.setdefault(row['worker'], []).append(
            (pc.number(row['start'], 'start'), row['task']))
    for group in groups.values():
        ordered = sorted(group)
        for (_, before), (_, after) in zip(ordered, ordered[1:]):
            parents[after].add(before)
    children = {name: set() for name in tasks}
    for name, deps in parents.items():
        for dep in deps:
            children[dep].add(name)
    degree = {name: len(deps) for name, deps in parents.items()}
    ready = [name for name, count in degree.items() if count == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        name = heapq.heappop(ready)
        order.append(name)
        for child in sorted(children[name]):
            degree[child] -= 1
            if degree[child] == 0:
                heapq.heappush(ready, child)
    if len(order) != len(tasks):
        raise ValueError('dependency and worker order form a cycle')
    return parents, workers, order


def _earliest(durations, parents, workers, order):
    starts, finishes, predecessor = {}, {}, {}
    for name in order:
        deps = sorted(parents[name])
        leading = min(deps, key=lambda dep: (-finishes[dep], dep)) if deps else None
        predecessor[name] = leading
        starts[name] = finishes[leading] if leading is not None else Fraction(0)
        finishes[name] = starts[name] + durations[name]
    last = min(order, key=lambda name: (-finishes[name], name))
    path = []
    while last is not None:
        path.append(last)
        last = predecessor[last]
    rows = [{'task': name, 'worker': workers[name], 'start': exact(starts[name]),
             'finish': exact(finishes[name])}
            for name in sorted(order, key=lambda item: (starts[item], workers[item], item))]
    return starts, finishes, list(reversed(path)), rows


def analyze(data, plan, caps, workers, budget):
    """Return the exact worst finish under independent upper duration bounds.

    Assignment and per-worker order are fixed. All tasks can start as soon as
    their prerequisites and preceding work on that worker have finished.
    """
    if budget is None:
        raise ValueError('an external budget is required')
    deadline = pc.number(budget, 'budget')
    if deadline < 0:
        raise ValueError('budget must be nonnegative')
    tasks = pc.graph(data)
    checked = pc.check(data, plan, workers)
    if not checked['valid']:
        raise ValueError('invalid input plan: ' + ', '.join(checked['violations']))
    pc.keys(caps, ('maximum_minutes',))
    overrides = caps['maximum_minutes']
    if not isinstance(overrides, dict) or len(overrides) > 500:
        raise ValueError('maximum_minutes must be an object of at most 500 entries')
    durations = {name: duration for name, (duration, _) in tasks.items()}
    maximum = dict(durations)
    for name, raw in overrides.items():
        if name not in tasks:
            raise ValueError('unknown cap task: ' + str(name))
        bound = pc.number(raw, 'maximum_minutes for ' + name)
        if bound < durations[name]:
            raise ValueError('cap is below estimate: ' + name)
        maximum[name] = bound
    parents, assignment, order = _fixed_graph(tasks, plan)
    baseline_start, baseline_end, _, _ = _earliest(durations, parents, assignment, order)
    upper_start, upper_end, path, schedule = _earliest(maximum, parents, assignment, order)
    baseline_finish, upper_finish = max(baseline_end.values()), max(upper_end.values())
    revised = {'workers': workers, 'units': 'minutes',
               'finish': Decimal(exact(upper_finish)),
               'schedule': [dict(row, start=Decimal(row['start']),
                                 finish=Decimal(row['finish'])) for row in schedule]}
    revised_data = {'tasks': [
        {'id': name, 'minutes': Decimal(exact(maximum[name])), 'after': sorted(deps)}
        for name, (_, deps) in sorted(tasks.items())]}
    verified = pc.check(revised_data, revised, workers)
    if not verified['valid']:
        raise AssertionError('internal schedule check failed: ' + str(verified['violations']))
    changes = [{'task': name, 'estimate': exact(durations[name]),
                'cap': exact(maximum[name]),
                'baseline_start': exact(baseline_start[name]),
                'capped_start': exact(upper_start[name]),
                'start_shift': exact(upper_start[name] - baseline_start[name]),
                'finish_shift': exact(upper_end[name] - baseline_end[name])}
               for name in sorted(tasks)]
    return {'units': 'minutes', 'workers': workers, 'deadline': exact(deadline),
            'input_plan_finish': exact(pc.number(plan['finish'], 'finish')),
            'baseline_fixed_order_finish': exact(baseline_finish),
            'capped_fixed_order_finish': exact(upper_finish),
            'increase_from_baseline': exact(upper_finish - baseline_finish),
            'deadline_margin_under_caps': exact(deadline - upper_finish),
            'safe_under_caps': upper_finish <= deadline,
            'one_worst_case_path': path, 'tasks': changes,
            'capped_earliest_plan': revised,
            'scope': ('All durations may reach their caps simultaneously; fixed worker '
                      'assignment and order, continuously available workers, no release '
                      'dates. Input idle gaps are removed. Estimates/caps are assumptions.')}


def demo():
    tasks = {'tasks': [
        {'id': 'read', 'minutes': 2},
        {'id': 'build', 'minutes': 5, 'after': ['read']},
        {'id': 'fixtures', 'minutes': 3, 'after': ['read']},
        {'id': 'check', 'minutes': 2, 'after': ['build', 'fixtures']}]}
    plan = {'workers': 2, 'finish': 9, 'schedule': [
        {'task': 'read', 'worker': 1, 'start': 0, 'finish': 2},
        {'task': 'build', 'worker': 1, 'start': 2, 'finish': 7},
        {'task': 'fixtures', 'worker': 2, 'start': 2, 'finish': 5},
        {'task': 'check', 'worker': 1, 'start': 7, 'finish': 9}]}
    caps = {'maximum_minutes': {'build': 6, 'fixtures': 5}}
    return tasks, plan, caps, 2, Decimal('10')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--tasks')
    parser.add_argument('--plan')
    parser.add_argument('--caps')
    parser.add_argument('--workers', type=int)
    parser.add_argument('--budget', type=Decimal)
    args = parser.parse_args()
    try:
        if args.demo:
            if any(value is not None for value in
                   (args.tasks, args.plan, args.caps, args.workers, args.budget)):
                raise ValueError('--demo cannot be combined with file options')
            inputs = demo()
        else:
            if any(value is None for value in
                   (args.tasks, args.plan, args.caps, args.workers, args.budget)):
                raise ValueError('--tasks, --plan, --caps, --workers and --budget are required')
            inputs = (pc.read_json(args.tasks), pc.read_json(args.plan),
                      pc.read_json(args.caps), args.workers, args.budget)
        report = analyze(*inputs)
        print(render_json(report))
        return 0 if report['safe_under_caps'] else 2
    except (ValueError, OSError, OverflowError, RecursionError) as exc:
        print('capguard: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
