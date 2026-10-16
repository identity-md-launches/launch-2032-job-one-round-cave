# BoundAudit

BoundAudit independently checks saved **RewardBounds** allocations of ZTO. It solves exact capped discretionary quotas by integrating active weight between sorted cap/weight thresholds. It then checks the reported rounding winners against the winner/loser boundary, including ASCII ID ties. It never calls RewardBounds' allocator or verifier, RewardSplit's allocator, or RewardReceipt's verifier.

From the repository root, with Python 3.9+ and only its standard library:

```sh
python3 -B line-3/tools/boundaudit/boundaudit.py demo
```

Tried here: exit **0**, auditing exactly **1000000000000000000 atomic ZTO units (1 ZTO)** among four illustrative address-free roles. The frozen request/report are the RewardBounds demo: build receives 0.4 ZTO at its cap, research and review receive 0.25 each, and zero-weight support receives its 0.1 floor. The inherited real Ethereum ZTO metadata capture supplies 18 decimals. No recipient is invented. The demo reads a saved report rather than generating one with the allocator.

For a saved bounded allocation and its original request:

```sh
python3 -B line-3/tools/boundaudit/boundaudit.py audit \
  --request line-3/tools/boundaudit/request.json \
  --report line-3/tools/boundaudit/report.json
```

Use your own paths for a real allocation. `--metadata PATH` selects the exact historical token capture used to allocate; the default is the sibling RewardSplit ZTO capture. Optional `--output PATH` creates a new workspace JSON receipt and refuses overwrites. The receipt binds the complete request, metadata and report with unsigned canonical SHA-256 hashes. JSON object order and whitespace do not change those hashes; value types and array order do.

The audit checks every header and allocation field, unknown/missing fields, exact canonical rational strings, minima, maxima, zero weights, formatted amounts, rounding flags and ties, contributor order, token capture, and conservation. It accepts the RewardBounds v1 schema only, not RewardSplit reports or bounded verification receipts. Its threshold sweep takes O(n log n) comparisons; integer and rational operations remain exact. No floating point is used in the audit.

**Independence is limited to arithmetic.** Request syntax, decimal conversion, token/address validation, JSON I/O and canonical hashing are shared with the inherited tools. Keep the sibling `line-3/tools/` tree together. The inherited input limits apply: 1–1000 contributors, uint256 budget/bounds, weights with at most 18 whole and 18 fractional decimal digits, 256-KiB workspace-only input files, duplicate JSON keys refused. RewardBounds may refuse large reports before they reach this tool. This does not independently attest metadata, identify recipients, establish entitlement, check a live balance, authorize payment, or prove code free of bugs. Largest remainder can still reverse shares when budgets change.

Exits: **0** complete audit passed; **2** invalid input, failed arithmetic/type/field check, limit violation or I/O failure. Failures emit no success receipt. Nothing reads environment variables, accesses wallets or secrets, signs, sends, posts, pays or uses the network.

```sh
python3 -B line-3/tools/boundaudit/selftest.py
```

All **12 tests** passed here: more than 550 feasible seeded policies with exhaustive rounding-subset checks, multiple/duplicate cap thresholds, fully saturated budgets, minima-only and zero-weight cases, wrong conserved rounding winners, tampered fields/types/order/metadata, uint256 and fractional-weight precision, address propagation, 750-row compact reports, CLI refusals and overwrite protection. The demo also passes with all inherited allocators/verifiers patched to raise if called. Address syntax tests use the real public token contract identifiers solely as validation fixtures, never as suggested payees.
