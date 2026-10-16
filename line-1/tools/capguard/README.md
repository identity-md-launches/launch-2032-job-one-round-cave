# Capguard

Check whether a complete offline work plan still meets a deadline if several
task durations reach their upper bounds at the same time. Python 3.9+ and
standard library only. The unchanged sibling Plancheck source is its one
runtime dependency.

Run from the repository root:

    python3 -B line-1/tools/capguard/capguard.py --demo

Observed here: the checked two-worker plan takes 9 minutes at its estimates.
With build capped at 6 and fixtures capped at 5, the earliest finish under
both caps is 10 minutes. It meets the 10-minute deadline with zero margin;
the witness path is read, build, check.

For your own job:

    python3 -B line-1/tools/capguard/capguard.py --tasks line-1/tools/plancheck/tasks.json --plan line-1/tools/plancheck/plan.json --caps line-1/tools/capguard/caps.json --workers 2 --budget 7

The task and plan schemas are Plancheck's. Caps is a JSON object with one
maximum_minutes map from task ID to numeric upper duration. Omitted tasks
keep their estimated duration; each supplied cap must be at least its
estimate. All three files must be ordinary workspace-local JSON files of
at most 100 KB. Duplicate keys, unknown tasks, invalid numbers, cycles,
incomplete or infeasible original plans, and caps below estimates are
refused. Worker count and deadline come from the command line.

Capguard keeps the input plan's worker assignment and each worker's task
order. It schedules tasks as soon as dependencies and prior work on that
worker allow, first at estimates and then at all caps. It removes idle
gaps in the supplied plan. For fixed order and continuously available
workers, finish time cannot decrease when a duration increases. Thus the
all-caps finish is the worst case within the independent duration bounds.
This does not search for a better order, handle release times or calendars,
or establish that actual durations obey the caps.

The report gives input finish, earliest baseline and capped finish, task
timing shifts, deadline margin, one longest path and the capped earliest
plan. Report measures are exact decimal strings. The embedded plan has
exact JSON numbers and can be checked against the capped task graph by
Plancheck. Exit 0 means this fixed-order all-caps finish fits the deadline;
exit 2 means it misses; exit 1 means invalid input. The CLI writes only
stdout/stderr and never executes task labels, waits, reads environment
variables, reaches a network, or handles keys, wallets or payments.

Run the local checks with:

    python3 -B line-1/tools/capguard/selftest.py

Observed: 9 tests passed, covering the deadline boundary, exact decimal
arithmetic, invalid inputs, idle-gap removal, a worker-order constraint,
CLI exits and all 24 duration combinations in a four-task example. These
checks do not certify future duration estimates. The 15 unchanged
Plancheck tests also passed.
