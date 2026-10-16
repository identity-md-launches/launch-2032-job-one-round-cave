#!/usr/bin/env python3
"""Independently audit RewardBounds arithmetic using a sorted threshold sweep."""

import argparse
from fractions import Fraction
import importlib.util
from pathlib import Path
import sys

SPEC = importlib.util.spec_from_file_location(
    "rewardbounds", Path(__file__).resolve().parents[1] / "rewardbounds" / "rewardbounds.py")
rb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rb)
rs, rr = rb.rs, rb.rr


def same(actual, expected, label):
    """Canonical JSON comparison rejects bool/int substitutions and extra fields."""
    rs.require(rr.canonical_bytes(actual) == rr.canonical_bytes(expected),
               label + " disagrees with independently checked arithmetic")


def sweep(rows, residual):
    """Integrate available weight between sorted cap/weight breakpoints.

    This does not call RewardBounds.allocate or reproduce its repeated removal
    of saturated contributors. Every positive-capacity weight is visited once
    after sorting. The level is zero for no discretionary budget, otherwise
    the first level at which the piecewise-linear filled volume reaches it.
    """
    if residual == 0:
        return Fraction(0), [Fraction(0) for _ in rows]
    events = sorted((Fraction(row["maximum"] - row["minimum"], row["weight"]),
                     row["id"], row["weight"])
                    for row in rows if row["weight"] > 0 and row["maximum"] > row["minimum"])
    active_weight = sum((event[2] for event in events), Fraction(0))
    previous, remaining = Fraction(0), Fraction(residual)
    for threshold, _, weight in events:
        volume = (threshold - previous) * active_weight
        if remaining <= volume:
            level = previous + remaining / active_weight
            quotas = [min(Fraction(row["maximum"] - row["minimum"]), level * row["weight"])
                      for row in rows]
            rs.require(sum(quotas) == residual, "swept quotas do not conserve discretionary units")
            return level, quotas
        remaining -= volume
        previous = threshold
        active_weight -= weight
    raise rs.Invalid("discretionary budget exceeds swept capacity")


def audit(request, report, metadata):
    """Check the entire bounded report without calling either allocator/verifier.

    Input syntax/metadata validation is shared with RewardBounds; arithmetic,
    quota construction and rounding acceptance are independent.
    """
    budget, decimals, reserved, rows = rb.parse_request(request, metadata)
    rs.require(isinstance(report, dict), "report must be an object")
    residual = budget - reserved
    level, quotas = sweep(rows, residual)
    allocations = report.get("allocations")
    rs.require(isinstance(allocations, list) and len(allocations) == len(rows),
               "allocation roster size differs from request")
    floors = [q.numerator // q.denominator for q in quotas]
    remainders = [q - floor for q, floor in zip(quotas, floors)]
    leftover = residual - sum(floors)
    awarded, unawarded, actual_total = [], [], 0
    for i, (row, actual) in enumerate(zip(rows, allocations)):
        rs.require(isinstance(actual, dict), "each allocation must be an object")
        flag = actual.get("rounding_unit_awarded")
        rs.require(type(flag) is bool, "rounding flag must be a boolean")
        # Higher remainder wins; lexically earlier ASCII ID wins a tie.
        # Check the selected/unselected boundary, rather than select winners
        # with the allocator's sorting-and-slicing implementation.
        key = (-remainders[i], row["id"])
        (awarded if flag else unawarded).append(key)
        units = row["minimum"] + floors[i] + int(flag)
        rs.require(row["minimum"] <= units <= row["maximum"], "allocation exceeds its bounds")
        expected = {
            "id": row["id"], "weight_fraction": str(row["weight"]),
            "minimum_units": str(row["minimum"]), "maximum_units": str(row["maximum"]),
            "discretionary_quota_fraction": str(quotas[i]),
            "rounding_unit_awarded": flag, "units": str(units),
            "amount": rs.display_units(units, decimals),
            "at_minimum": units == row["minimum"], "at_maximum": units == row["maximum"],
        }
        if row["address"] is not None:
            expected["address"] = row["address"]
        same(actual, expected, "allocation " + row["id"])
        actual_total += units
    rs.require(len(awarded) == leftover, "incorrect number of rounding winners")
    rs.require(not awarded or not unawarded or max(awarded) < min(unawarded),
               "rounding winner loses a remainder or ASCII tie comparison")
    rs.require(actual_total == budget, "allocations do not conserve budget")
    expected_header = {
        "schema": "rewardbounds-allocation-v1",
        "purpose": "bounded allocation only; no transaction, balance check, or promise of payment",
        "token": {key: metadata[key] for key in
                  ("chain_id", "address", "symbol", "decimals", "block_number", "block_hash")},
        "budget_units": str(budget), "budget_amount": rs.display_units(budget, decimals),
        "minimum_units_reserved": str(reserved), "discretionary_units": str(residual),
        "method": "reserve minima; cap-weighted discretionary water filling; largest remainder; ASCII id ties",
        "waterfill_level_fraction": str(level), "rounding_units_distributed": leftover,
        "unallocated_units": "0", "all_recipients_supplied": all(row["address"] is not None for row in rows),
    }
    same({key: value for key, value in report.items() if key != "allocations"}, expected_header, "report header")
    return {
        "schema": "boundaudit-v1", "result": "passed independent bounded-allocation arithmetic audit",
        "budget_units": str(budget), "contributors": len(rows),
        "waterfill_level_fraction": str(level), "rounding_units_distributed": leftover,
        "checks": ["sorted cap-threshold integration", "exact rational quotas and floors",
                   "rounding winner/loser boundary and ASCII ties", "bounds and budget conservation",
                   "complete report fields and JSON types"],
        "request_sha256": rr.digest(request), "metadata_sha256": rr.digest(metadata),
        "report_sha256": rr.digest(report),
        "scope": "arithmetic only; shared input validation; historical metadata; no entitlement, identity, balance or payment proof",
    }


def demo():
    # A frozen example, not generated by the allocator in this command.
    root = Path(__file__).resolve().parent
    return audit(rs.read_json(root / "request.json"), rs.read_json(root / "report.json"),
                 rs.read_json(rr.ROOT / "zto-mainnet.json"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="audit the bundled address-free 1-ZTO bounded allocation")
    check = sub.add_parser("audit", help="independently audit a saved RewardBounds allocation")
    check.add_argument("--request", required=True)
    check.add_argument("--report", required=True)
    check.add_argument("--metadata", default=str(rr.ROOT / "zto-mainnet.json"))
    check.add_argument("--output", help="new workspace JSON receipt; refuses overwrites")
    args = parser.parse_args(argv)
    try:
        result = demo() if args.command == "demo" else audit(
            rs.read_json(args.request), rs.read_json(args.report), rs.read_json(args.metadata))
        rs.write_json(result, getattr(args, "output", None))
    except (rs.Invalid, OSError, ValueError, OverflowError, RecursionError) as exc:
        print("boundaudit: " + (str(exc) if isinstance(exc, rs.Invalid) else type(exc).__name__), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
