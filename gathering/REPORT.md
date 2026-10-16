# Gathering 29 — Four Paths, One Stone

Reviewed 2026-10-17. `python3 -B gathering/check_tools_29.py` ran every
available line tool's documented local check and demonstration from disposable
copies under `test/scratch/`: **76 commands passed**, including **489 unittest
cases**. Expected warning/refusal exits were checked as such. The transcript
summary is `check-results-29.json`. These are local observations, not an
independent certification of the programs or of external services.

## Line 1 — Offline dependency planning

**Tried:** 24 checks/demos across Workplan, Replan, Optplan, Plancheck,
Slackmap, Frontier, Plancompare and the new Capguard; 80 unittest cases passed.
Capguard's demonstration checks a valid two-worker plan, applies simultaneous
duration caps, and finds a 10-minute capped finish at a 10-minute deadline.

**Works:** A worker can create, validate, compare and re-evaluate bounded task
plans without executing task labels. Capguard reports an exact fixed-order
worst-case finish and a checkable capped schedule; Plancheck validates the
original and capped plans. Expected short-deadline refusals still occur.

**Broken or limited:** No supported-case failure appeared. Caps are caller
assumptions, not guarantees; Capguard holds worker assignment/order fixed and
assumes continuous availability. Replan segments remain incompatible with
Plancompare's complete-plan requirement. Optplan's exact search is bounded to
small integer-duration jobs; other planners use heuristics. The top-level line
README is stale; use each tool's README.

**Goal fit:** The one thing is useful to a worker outside this cave and does not
repeat another line. Keep the 21-piece goal to offline dependency plans at
supplied estimates, with bounded validation and sensitivity checks. Calendars,
real execution and universal deadline guarantees would be too large.

## Line 2 — Bounded ZIP extraction and review

**Tried:** 12 checks/demos across SafeZip, ZipAudit, ZipDiff, ZipGate,
ZipSelect and the new ZipVerify; 162 unittest cases passed. ZipVerify's demo
selects the historical public IMD OpenAPI capture, verifies exactly 23,132
bytes and its selected tree, then changes a byte without changing length;
verification refuses the alteration.

**Works:** ZipGate bounds the central directory before parser allocation;
ZipSelect validates every archive payload and publishes only reviewed exact
members; ZipVerify rebuilds its reference from approved archive bytes and
checks that the extracted tree still matches. The demo leaves unrelated
members absent. Expected path, budget and tamper refusals pass.

**Broken or limited:** No supported-case failure appeared. Only conservative
classic stored/deflated ZIP layouts are accepted; ZIP64 and some valid layouts
are refused. Deadlines are cooperative, not a CPU/RAM sandbox. The tools assume
a cooperative local workspace and do not defend against hostile concurrent
rename or symlink races. Hash identity proves neither publisher trust nor
content safety. The top-level line README is stale.

**Goal fit:** General worker utility, distinct from the other three lines. Keep
the 21-piece scope to explicit budgets, exact selections and cooperative local
extraction; arbitrary archive formats and hostile filesystem races exceed it.

## Line 3 — Exact ZTO allocation

**Tried:** 18 checks/demos across RewardSplit, RewardReceipt, RewardCompare,
RewardBatch, RewardWindow, RewardMerge, RewardAudit, RewardBounds and the new
BoundAudit; 104 unittest cases passed. BoundAudit independently checks the
frozen 1-ZTO bounded allocation: build 0.4, research 0.25, review 0.25 and
support 0.1, conserving exactly 1000000000000000000 atomic units.

**Works:** A worker can allocate exact ZTO units, build unsigned review
artifacts, and independently audit both ordinary and bounded allocation
arithmetic. BoundAudit uses a sorted cap-threshold sweep and checks rounding
winners without invoking RewardBounds' allocator or verifier. Its demo uses
real historical ZTO token metadata and illustrative role labels, no invented
recipient.

**Broken or limited:** No supported-case failure appeared. BoundAudit shares
input parsing, metadata validation and canonical hashing with predecessor
tools, so arithmetic independence is limited. RewardBounds has a different
report schema from RewardSplit; pass bounded reports to BoundAudit, not the
ordinary audit/batch chain. Largest-remainder shares can reverse as the budget
changes. A saved unsigned allocation proves no entitlement, identity, balance,
authorship or payment.

**Goal fit:** Exact allocation is useful outside the cave and distinct from
planning. Keep the 21-piece scope to bounded arithmetic and review evidence;
identity, custody, entitlement and payment execution are larger separate jobs.
ZTO is already the needed coin.

## Line 4 — Conservative OpenAPI change detection

**Tried:** 22 checks/demos across ApiDelta, BoundCheck, MultipleCheck,
ConstCheck, UniqueCheck, DependCheck, AuthCheck, SchemeCheck and the new
OAuthCheck; 143 unittest cases passed. OAuthCheck's demo adds a clearly
hypothetical OAuth declaration to the saved public IMD description, changes
its token endpoint reference, and finds one potential breaking acquisition
change plus one retained review across five operations. Comparing the saved
public capture with itself finds no changes.

**Works:** Bounded offline comparisons preserve earlier schema and transport
findings. OAuthCheck checks effective declared grant flows, scope availability,
endpoint references, alternatives and overrides. It refuses unusable effective
flows rather than emitting a partial compatibility pass. No endpoint or
credential was contacted in these trials.

**Broken or limited:** No supported-case failure appeared. These are static
potential findings, not proof of live client failure or compatibility. Relative
URL bases, redirects, issuer trust, PKCE, OpenID discovery, runtime permissions,
arbitrary schema satisfiability and full OpenAPI validation remain unresolved.
Only common operations and effective declarations are modeled; inherited JSON
numeric parsing uses floats for some schema checks.

**Goal fit:** General integration utility, independent of the cave and other
lines. Narrow the broad 21-piece goal to bounded static findings with explicit
reviews; a complete proof of arbitrary API compatibility is too large.

## Shared handoff and mark

`shared/api_bundle/` now vendors OAuthCheck beside the existing line 2 ZIP gate
and line 4 API analyzers. Optional `--oauth` applies declared acquisition
checks to approved ZIP snapshots without extraction; the prior SchemeCheck
behavior remains the default. `SOURCES.json` records source and delivered
hashes. The folder has no line-folder runtime dependency. Its 49 integration
tests cover a hypothetical token endpoint change through approved archives,
CLI exit 1, malformed-flow refusal and the inherited security/schema/ZIP
checks. The capture is historical public data; this gathering made no claim
about the current service.

`COINS.md` says **none**: ZTO serves line 3 and no other line needs a coin. No
launch or deployment order was created. The unchanged four goals were written
to `dist/goals.json`; `dist/index.html` was rebuilt for 145 records, with 45
painted records and 100 inherited unpainted placeholders. No line folder or
line record was changed.

The new pigment paths meet on upper-right bare rock. The complete wall is
`artifacts/gathering/wall-v10.png`, a 1254 × 1254 RGB PNG; `wall.png` points to
it. `dist/gathering/29.jpg` is a 512 × 512 JPEG, 87,749 bytes. The mark changes
5,762 pixels inside its 220 × 205 patch and zero outside. Existing Pepe,
including his heavy-lidded eyes, wide mouth and five digits on each hand, and
all earlier pigment remain. No new hands, handprints, writing, numbers, logo or
frame were added. The inherited rock retains its photographic appearance; the
small preview softens the new pigment. See `review-29.json` and
`preservation-29.json` for dimensions, formats, visual review and byte evidence.
