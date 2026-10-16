# ZipVerify

Verify that a previously selected extraction still matches an approved ZIP:
exact file bytes, exact names, expected types, and only the selected files and
their implicit parent directories. Python 3.9+ standard library only, using the
shipped sibling ZipSelect, ZipGate and SafeZip modules. No installation needed.

One command from the repository root shows it working offline:

```sh
python3 -B line-2/tools/zipverify/demo.py
```

Tried here: extracted the historical public IMD OpenAPI capture (23,132 bytes)
with ZipSelect, verified its three-node tree, then changed its first byte without
changing its length. Verification refused the altered hash and left the altered
file untouched. Unselected archive files and empty directories were absent.
The genuine capture and provenance are in `../safezip/imd-openapi.json` and
`../safezip/sample-source.json`; archive packaging is illustrative. This replays
public data offline; it makes no fresh network observation. The demo uses and
removes disposable directories under `test/scratch/`.

## Verify your extraction

First inspect the archive with ZipGate and retain its reviewed `archive_sha256`.
Extract the desired exact files with ZipSelect. Then run:

```sh
python3 -B line-2/tools/zipverify/zipverify.py incoming.zip selected --sha256 APPROVED_DIGEST --file docs/readme.txt --file data/input.csv --seconds 10
```

Replace `APPROVED_DIGEST` with that actual reviewed 64-hex SHA-256 and use the
same exact file selections used for extraction. No globs, directory selection,
renaming or flattening. Case matters. Selection must be nonempty and duplicate
free. A successful JSON report has `exact_selected_tree: true`, the archive
hash, checked node/byte counts, and pre-parser directory counts. The output root
is excluded from the node count. A file omitted from the selection is an extra
path even if it exists in the approved archive. Empty extra directories fail.

Exit 0 means this observed tree matched; exit 2 emits `ok: false` with an error
for policy, corruption, resource or I/O failures. Argument syntax errors use
argparse stderr and exit 2. Python callers can use:

```python
result = verify(archive, tree, ["docs/readme.txt"],
                expected_sha256=approved_digest, seconds=10,
                output_nodes=2, output_bytes=1048576)
```

Import `verify` from `zipverify.py`. Policy failures raise `Rejected`; I/O and
ZIP errors can propagate. No saved extraction report is consumed or trusted:
the reference is rebuilt from the approved archive bytes each time. Every ZIP
payload is checked, including omitted files, through ZipSelect's plan mode and
ZipGate's bounded directory gate. Malicious omitted paths, links or corrupt
payloads refuse verification before tree traversal. The verifier never writes,
repairs, executes or recursively opens archive content.

## Resource limits

All limits are optional positive integers: `--entries` (1000),
`--directory-bytes` (2 MiB), `--archive-bytes` (32 MiB), `--nodes` (32000),
`--file-bytes` (16 MiB), `--total-bytes` (64 MiB), `--ratio` (200),
`--output-nodes` (32000), `--output-bytes` (64 MiB). Full archive limits apply
before selected output limits. Implicit parents count once. A streamed tree
walk refuses its first unexpected child without materializing an unbounded
directory listing. Expected file sizes bound reads, including a one-byte probe
for growth; every accepted file is hashed and checked again.

`--seconds` is an optional finite positive cooperative deadline shared across
archive validation, reference building and tree reads. The API also accepts a
fast side-effect-free `cancelled` callback. No sleep is used. A blocking read,
parser, decompression, sort or traversal call may exceed that deadline; report
serialization is outside it. This is not a hard CPU/RAM sandbox.

Use a cooperative workspace with no concurrent filesystem mutations. All paths
must lie inside the current working directory, with no symlink components.
Observed descendant symlinks and special files are refused. This does not defend
against hostile local rename/symlink races, and hard links are regular files.
A successful observation is not a persistent guarantee about future contents.
Ownership, modes, timestamps, extended attributes and hard-link identity are
not compared. Hash identity does not establish publisher trust or content safety.
Only the classic stored/deflated ZIP layouts accepted by ZipGate are supported;
ZIP64, prefixes and some otherwise valid archives are conservatively refused.

## Checks

```sh
python3 -B line-2/tools/zipverify/selftest.py
```

Observed **28 tests passed**: exact trees with shared parents and empty files;
same-length tampering, shorter/longer content, missing/extra paths and directories;
type changes and symlinks; mandatory hash approval; full and selected budgets;
pre-parser entry rejection; omitted unsafe paths, symlinks and corrupt content;
cancellation, deterministic deadline expiry without sleeps, invalid options,
selection errors, workspace confinement and CLI success/refusal. The inherited
**30 ZipSelect tests** also passed unchanged. These are local worker observations.
