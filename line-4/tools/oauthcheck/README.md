# OAuthCheck

Identify potential OAuth acquisition breaks before updating an OpenAPI integration. Python 3.9+, standard library only; offline and no installation. From the repository root:

```sh
python3 -B line-4/tools/oauthcheck/oauthcheck.py demo
```

This uses the bundled real public IMD OpenAPI capture, adds an explicitly hypothetical OAuth declaration in memory, and changes its token URL. It compares five operations and reports one potential OAuth acquisition break plus the retained document review. The illustrative `example.invalid` URLs are never contacted. The actual captured service does not declare this illustrative scheme. Successful demo exit: 0.

Compare two JSON descriptions in your current workspace:

```sh
python3 -B line-4/tools/oauthcheck/oauthcheck.py compare line-4/tools/apidelta/imd-openapi.json line-4/tools/apidelta/imd-openapi.json
```

Replace both paths with your descriptions. Output is deterministic JSON, including exact input-byte SHA-256 hashes. Compare exits: 0 no detected break, 1 potential break, 2 refused/error, 3 unresolved review. Keep all sibling tool folders from `apidelta` through `schemecheck`: OAuthCheck imports their bounded loaders and analyzers and retains their findings. There are no external packages, environment/configuration reads, remote-reference fetches, authorization calls, credentials, signatures or transactions. ZTO/IMD are unnecessary for this static analysis.

## Rule and limits

Checks effective security declarations on common operations, including root inheritance, operation overrides, local scheme aliases, AND requirements and OR alternatives. For each old alternative, at least one new alternative must preserve its symbolic obligations and transport identity, then retain **every old OAuth flow that declared all of that old requirement's scopes**. Required authorization/token URL references must match exactly. An old declared refresh URL must remain identical; adding one where none was declared is harmless to this rule. Required scopes must remain available in those old flows. Added flows, additional scopes and changed scope descriptions do not themselves trigger an OAuth break, although inherited review findings remain.

The four modeled flow kinds are implicit, password, clientCredentials and authorizationCode. An effective OAuth requirement must have at least one flow declaring all its scopes, on both sides; otherwise comparison refuses with exit 2 rather than silently reporting compatibility. Required URL fields must be nonempty strings without whitespace; scopes must be a map of at most 256 string descriptions. Unknown non-extension flow names refuse. Empty flows are therefore refused when used. Unused declarations and new-only operations are outside this validation. This is not a full OpenAPI or URL validator; relative references are allowed and compared literally, not resolved against servers or normalized.

Preserving all old acquisition choices is deliberately conservative: a person might have used any declared grant kind. A surviving different grant kind cannot rescue a removed one. A separately surviving security alternative can rescue the old alternative, following the inherited symbolic model. Server redirects, changed relative-URL bases, actual issuer trust, discovery/OpenID Connect, PKCE, OAuth extensions, runtime permission meanings and credential acceptance remain unresolved. A `breaking` finding is a potential integration failure, not proof that a real caller fails; a clean report is not a compatibility guarantee.

Limits inherited from the pipeline: 1 MiB per input, 50,000 nodes, depth 80, 20,000 schema visits, 2,000 findings, 64 security alternatives, 32 schemes and 64 requirement labels per alternative. OAuth adds a separate 100,000 alternative-pair budget and caches effective definitions. Budget exhaustion refuses without a partial pass. The base JSON float parser's numeric precision limitation still applies to schema checks. OAuth strings are compared exactly.

## Tried

- `python3 -B line-4/tools/oauthcheck/selftest.py`: 16 tests passed, including 36 independent finite acquisition-choice comparisons, all four flows, URL changes, flow removal/addition, scope availability, refresh addition/removal, irrelevant flows, surviving alternatives, anonymous overrides, references, pointer escaping, malformed identical declarations, budget refusal, inherited findings, deterministic nonmutation, and CLI exits 0/1/2/3.
- `python3 -B line-4/tools/schemecheck/selftest.py`: all 11 existing regression tests passed unchanged.
- Demo: five operations, one OAuth potential break and one document review, exit 0.
- Bundled public capture compared with itself: five operations, no findings, exit 0. This is an offline reproducibility check, not a fresh service observation.

The capture source is `https://api.imd.fun/openapi.json`, SHA-256 `be142840c010710cb2a5b9e5c73e71d8e79ec4054c15661699d60bfa627be96a`. Round evidence is in `line-4/check-results-29.json`.
