"""Independent OAuth flow witnesses, refusals, alternatives and CLI checks."""
import copy
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import oauthcheck as o


def flow(kind='authorizationCode', scopes=('read',)):
    f = {'scopes': {s: s for s in scopes}}
    for field in o.FIELDS[kind]:
        f[field] = 'https://example.invalid/' + field
    return f


def doc():
    return {'openapi': '3.1.0', 'paths': {'/a~b/c': {'get': {
        'security': [{'auth': ['read']}], 'responses': {'200': {'description': 'ok'}}}}},
        'components': {'securitySchemes': {'auth': {'type': 'oauth2', 'flows': {
            'authorizationCode': flow()}}}}}


def fs(d):
    return d['components']['securitySchemes']['auth']['flows']


def hits(a, b):
    return [f for f in o.compare(a, b)['findings'] if f['code'] == 'oauth_acquisition_incompatible']


class Tests(unittest.TestCase):
    def test_endpoints(self):
        for kind, fields in o.FIELDS.items():
            for field in fields:
                a = doc()
                fs(a).clear()
                fs(a)[kind] = flow(kind)
                b = copy.deepcopy(a)
                fs(b)[kind][field] += '-v2'
                self.assertTrue(hits(a, b), (kind, field))

    def test_flow_removal(self):
        a = doc()
        fs(a)['clientCredentials'] = flow('clientCredentials')
        b = copy.deepcopy(a)
        del fs(b)['authorizationCode']
        self.assertTrue(hits(a, b))
        self.assertFalse(hits(b, a))

    def test_irrelevant_flow(self):
        a = doc()
        fs(a)['clientCredentials'] = flow('clientCredentials', ('write',))
        b = copy.deepcopy(a)
        del fs(b)['clientCredentials']
        self.assertFalse(hits(a, b))

    def test_refresh(self):
        a = doc()
        b = copy.deepcopy(a)
        fs(b)['authorizationCode']['refreshUrl'] = '/refresh'
        self.assertFalse(hits(a, b))
        self.assertTrue(hits(b, a))
        a = copy.deepcopy(b)
        fs(b)['authorizationCode']['refreshUrl'] = '/refresh-v2'
        self.assertTrue(hits(a, b))

    def test_scope_description_and_unrequired_removal(self):
        a = doc()
        fs(a)['authorizationCode']['scopes']['write'] = 'write'
        b = copy.deepcopy(a)
        del fs(b)['authorizationCode']['scopes']['write']
        fs(b)['authorizationCode']['scopes']['read'] = 'Read things'
        self.assertFalse(hits(a, b))
        self.assertEqual(o.compare(a, b)['status'], 'review_required')

    def test_missing_required_scope_refuses(self):
        a = doc()
        b = copy.deepcopy(a)
        fs(b)['authorizationCode']['scopes'].clear()
        with self.assertRaisesRegex(o.api.Invalid, 'no flow declaring'):
            o.compare(a, b)

    def test_alternative_survives(self):
        a = doc()
        a['components']['securitySchemes']['key'] = {'type': 'http', 'scheme': 'bearer'}
        a['paths']['/a~b/c']['get']['security'] = [{'auth': ['read'], 'key': []}]
        b = copy.deepcopy(a)
        b['paths']['/a~b/c']['get']['security'] = [{'auth': ['read']}, {'key': []}]
        fs(b)['authorizationCode']['tokenUrl'] += '-v2'
        self.assertFalse(hits(a, b))
        b['paths']['/a~b/c']['get']['security'].pop()
        self.assertTrue(hits(a, b))

    def test_anonymous_and_root_override(self):
        a = doc()
        a['security'] = a['paths']['/a~b/c']['get'].pop('security')
        b = copy.deepcopy(a)
        fs(b)['authorizationCode']['tokenUrl'] += '-v2'
        self.assertTrue(hits(a, b))
        b['paths']['/a~b/c']['get']['security'] = []
        self.assertFalse(hits(a, b))

    def test_refs_determinism_location_no_mutation(self):
        a = doc()
        definitions = a['components']['securitySchemes']
        definitions['alias/~'] = definitions['auth']
        definitions['auth'] = {'$ref': '#/components/securitySchemes/alias~1~0'}
        b = copy.deepcopy(a)
        b['components']['securitySchemes']['alias/~']['flows']['authorizationCode']['tokenUrl'] += '-v2'
        saved = copy.deepcopy((a, b))
        self.assertEqual(hits(a, b)[0]['location'], '/paths/~1a~0b~1c/get/security')
        self.assertEqual(o.compare(a, b), o.compare(a, b))
        self.assertEqual((a, b), saved)

    def test_invalid_identical(self):
        for value in (None, [], {'unknown': {}}, {'authorizationCode': []},
                      {'authorizationCode': {}},
                      {'authorizationCode': {**flow(), 'tokenUrl': 'bad url'}},
                      {'authorizationCode': {**flow(), 'scopes': []}},
                      {'authorizationCode': {**flow(), 'scopes': {'read': False}}},
                      {'authorizationCode': {**flow(), 'scopes': {str(i): '' for i in range(257)}}}):
            a = doc()
            a['components']['securitySchemes']['auth']['flows'] = value
            with self.subTest(value=value), self.assertRaises(o.api.Invalid):
                o.compare(a, a)

    def test_finite_flow_oracle(self):
        # Enumerate actual old acquisition choices independently: token URL and
        # grant kind are a client's fixed construction, not interchangeable flows.
        variants = []
        for mask in range(1, 4):
            for suffix in ('', '-v2'):
                a = doc()
                fs(a).clear()
                for bit, kind in enumerate(('authorizationCode', 'clientCredentials')):
                    if mask & (1 << bit):
                        fs(a)[kind] = flow(kind)
                        fs(a)[kind]['tokenUrl'] += suffix
                variants.append(a)
        for a, b in itertools.product(variants, repeat=2):
            old_choices = {(kind, f['tokenUrl']) for kind, f in fs(a).items()}
            new_choices = {(kind, f['tokenUrl']) for kind, f in fs(b).items()}
            self.assertEqual(bool(hits(a, b)), not old_choices <= new_choices)

    def test_comparison_limit(self):
        a = doc()
        a['paths']['/a~b/c']['get']['security'] *= 64
        b = copy.deepcopy(a)
        fs(b)['authorizationCode']['tokenUrl'] += '-v2'
        limit = o.scheme.auth.MAX_COMPARISONS
        try:
            o.scheme.auth.MAX_COMPARISONS = 1000
            with self.assertRaisesRegex(o.api.Invalid, 'OAuth comparison limit'):
                o.compare(a, b)
        finally:
            o.scheme.auth.MAX_COMPARISONS = limit

    def test_capture_demo(self):
        self.assertTrue(any(f['code'] == 'oauth_acquisition_incompatible' for f in o.demo()['findings']))
        capture = o.scheme.auth.depend.unique.const.multiple.bound.BASE.with_name('imd-openapi.json')
        a, _ = o.api.load(capture)
        self.assertEqual(o.compare(a, a)['findings'], [])

    def test_inherited_findings_preserved(self):
        a = doc()
        a['paths']['/a~b/c']['get']['requestBody'] = {'content': {'application/json': {
            'schema': {'type': 'string', 'maxLength': 20}}}}
        b = copy.deepcopy(a)
        b['paths']['/a~b/c']['get']['requestBody']['content']['application/json']['schema']['maxLength'] = 10
        before = o.scheme.compare(a, b)['findings']
        after = o.compare(a, b)['findings']
        self.assertTrue(any(f['code'] == 'size_bound_incompatible' for f in after))
        self.assertTrue(all(f in after for f in before))

    def test_transport_type_break_not_duplicated(self):
        a = doc()
        b = copy.deepcopy(a)
        b['components']['securitySchemes']['auth'] = {'type': 'http', 'scheme': 'bearer'}
        b['paths']['/a~b/c']['get']['security'] = [{'auth': []}]
        result = o.compare(a, b)
        self.assertTrue(any(f['code'] == 'security_transport_incompatible' for f in result['findings']))
        self.assertFalse(hits(a, b))

    def test_cli(self):
        root = Path('test/scratch')
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as tmp:
            a, b = Path(tmp)/'a.json', Path(tmp)/'b.json'
            old = doc()
            a.write_text(json.dumps(old))
            changed = copy.deepcopy(old)
            fs(changed)['authorizationCode']['tokenUrl'] += '-v2'
            review = copy.deepcopy(old)
            fs(review)['authorizationCode']['scopes']['read'] = 'Changed description'
            invalid = copy.deepcopy(old)
            fs(invalid).clear()
            for new, code in ((old, 0), (changed, 1), (review, 3), (invalid, 2)):
                b.write_text(json.dumps(new))
                run = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('oauthcheck.py')),
                                      'compare', str(a), str(b)], capture_output=True, text=True, timeout=10)
                self.assertEqual(run.returncode, code, run.stderr)
                if code != 2:
                    self.assertEqual(len(json.loads(run.stdout)['old_sha256']), 64)


if __name__ == '__main__':
    unittest.main()
