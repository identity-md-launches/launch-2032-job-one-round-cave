#!/usr/bin/env python3
"""Bounded offline OAuth flow continuity checks for OpenAPI 3 descriptions."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys

PREVIOUS = Path(__file__).with_name('schemecheck.py')
spec = importlib.util.spec_from_file_location('oauthcheck_scheme', PREVIOUS)
scheme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scheme)
api = scheme.api
FIELDS = {
    'implicit': ('authorizationUrl',),
    'password': ('tokenUrl',),
    'clientCredentials': ('tokenUrl',),
    'authorizationCode': ('authorizationUrl', 'tokenUrl'),
}


def flows(document, name):
    definition = document.resolve(document.obj['components']['securitySchemes'][name])
    if definition['type'] != 'oauth2':
        return None
    raw = definition.get('flows')
    api.require(isinstance(raw, dict), 'OAuth flows must be an object')
    api.require(all(k in FIELDS or k.startswith('x-') for k in raw), 'unknown OAuth flow')
    result = {}
    for kind, fields in FIELDS.items():
        if kind not in raw:
            continue
        flow = raw[kind]
        api.require(isinstance(flow, dict), 'OAuth flow must be an object')
        for field in fields + (('refreshUrl',) if 'refreshUrl' in flow else ()):
            api.require(isinstance(flow.get(field), str) and bool(flow[field])
                        and not any(c.isspace() for c in flow[field]),
                        'OAuth ' + field + ' must be a nonempty URL reference without whitespace')
        scopes = flow.get('scopes')
        api.require(isinstance(scopes, dict) and len(scopes) <= 256,
                    'OAuth scopes must be an object of at most 256 entries')
        api.require(all(isinstance(k, str) and isinstance(v, str) for k, v in scopes.items()),
                    'OAuth scope descriptions must be strings')
        result[kind] = (tuple((f, flow.get(f)) for f in fields + ('refreshUrl',)),
                        frozenset(scopes))
    return result


def preserves(before, after, labels):
    """All old acquisition flows offering required labels must remain usable."""
    for kind, (urls, scopes) in before.items():
        if not labels <= scopes:
            continue
        if kind not in after:
            return False
        next_urls, next_scopes = after[kind]
        next_urls = dict(next_urls)
        if any(value is not None and next_urls[field] != value for field, value in urls) or not labels <= next_scopes:
            return False
    return True


class Analyzer(scheme.Analyzer):
    def __init__(self, old, new):
        super().__init__(old, new)
        self.flow_cache = {}
        self.oauth_comparisons = 0

    def acquisition(self, side, name):
        key = side, name
        if key not in self.flow_cache:
            self.flow_cache[key] = flows(self.old if side == 'old' else self.new, name)
        return self.flow_cache[key]

    def operation(self, path, method, old_item, new_item):
        super().operation(path, method, old_item, new_item)
        before = scheme.auth.policy(self.old, old_item[method])
        after = scheme.auth.policy(self.new, new_item[method])
        for side, policies in (('old', before), ('new', after)):
            for _, _, option in policies:
                for name, labels in option.items():
                    available = self.acquisition(side, name)
                    if available is not None:
                        api.require(any(set(labels) <= scopes for _, scopes in available.values()),
                                    'effective OAuth requirement has no flow declaring all its scopes: ' + name)
        loc = api.pointer('/paths', path) + '/' + method + '/security'
        for index, source, old_option in before:
            transport_cover = False
            oauth_cover = False
            for _, target, option in after:
                self.oauth_comparisons += 1
                api.require(self.oauth_comparisons <= scheme.auth.MAX_COMPARISONS,
                            'OAuth comparison limit exceeded (100000)')
                if not target <= source or not all(
                        self.identity('old', n) == self.identity('new', n) for n in option):
                    continue
                transport_cover = True
                compatible = True
                for name in option:
                    old_flows = self.acquisition('old', name)
                    if old_flows is not None and not preserves(
                            old_flows, self.acquisition('new', name), set(old_option[name])):
                        compatible = False
                        break
                if compatible:
                    oauth_cover = True
                    break
            if transport_cover and not oauth_cover:
                self.emit('breaking', 'oauth_acquisition_incompatible', loc,
                          'Old effective alternative ' + str(index) +
                          ' has no transport-compatible new alternative retaining every old OAuth '
                          'flow that offered its required scopes, with identical declared endpoint '
                          'URLs and those scopes. Existing acquisition or refresh integrations may fail; '
                          'no endpoint or credential was tested.')


def compare(old, new):
    analyzer = Analyzer(old, new)
    result = analyzer.run()
    result['extension'] = 'oauthcheck-v1 (includes schemecheck and earlier line 4 analyzers)'
    result['oauth_alternative_comparisons'] = analyzer.oauth_comparisons
    return result


def demo():
    capture = Path(__file__).resolve().parents[1] / 'imd-openapi.json'
    old, digest = api.load(capture)
    old = copy.deepcopy(old)
    # Explicitly hypothetical declaration; these URLs are illustrative and never fetched.
    old['components']['securitySchemes']['illustrativeOAuth29'] = {
        'type': 'oauth2', 'flows': {'authorizationCode': {
            'authorizationUrl': 'https://example.invalid/authorize',
            'tokenUrl': 'https://example.invalid/token', 'scopes': {'read': 'Read'}}}}
    old['paths']['/requests/quote']['post']['security'] = [{'illustrativeOAuth29': ['read']}]
    new = copy.deepcopy(old)
    new['components']['securitySchemes']['illustrativeOAuth29']['flows']['authorizationCode']['tokenUrl'] += '-v2'
    result = compare(old, new)
    api.require(any(f['code'] == 'oauth_acquisition_incompatible' for f in result['findings']),
                'demo failed to detect hypothetical endpoint change')
    result.update(capture_sha256=digest, baseline_source='https://api.imd.fun/openapi.json',
                  demo='Hypothetical OAuth token URL migration added to the bundled public description; no endpoint called.')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('demo')
    diff = commands.add_parser('compare')
    diff.add_argument('old')
    diff.add_argument('new')
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            result = demo()
        else:
            old, oh = api.load(args.old)
            new, nh = api.load(args.new)
            result = compare(old, new)
            result.update(old_sha256=oh, new_sha256=nh)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if args.command == 'demo' else {
            'breaking': 1, 'review_required': 3, 'no_detected_breakage': 0}[result['status']]
    except (api.Invalid, OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        print('oauthcheck: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
