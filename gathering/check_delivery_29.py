#!/usr/bin/env python3
"""Verify gathering 29's paths, bytes, inherited pixels and local evidence."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

from check_delivery import jpeg_dimensions, png


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    root = Path(__file__).resolve().parent.parent
    assert Path.cwd().resolve() == root
    expected_lines = json.loads(Path('gathering/line-integrity-29.json').read_text())
    actual_lines = {str(p): digest(p.read_bytes()) for n in range(1, 5)
                    for folder in (Path(f'line-{n}'), Path(f'dist/line-{n}'))
                    for p in folder.rglob('*') if p.is_file()}
    assert actual_lines == expected_lines
    line_status = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=all',
                                  '--', 'line-1', 'line-2', 'line-3', 'line-4',
                                  'dist/line-1', 'dist/line-2', 'dist/line-3',
                                  'dist/line-4'], capture_output=True, text=True, check=True)
    assert not line_status.stdout, 'line folder or line record changed'

    before = Path('artifacts/gathering/wall-v9.png').read_bytes()
    wall = Path('artifacts/gathering/wall-v10.png').read_bytes()
    old_size, old_pixels = png(before)
    size, pixels = png(wall)
    assert old_size == size == (1254, 1254)
    assert Path('artifacts/gathering/wall.png').is_symlink()
    assert Path('artifacts/gathering/wall.png').readlink() == Path('wall-v10.png')
    assert Path('artifacts/gathering/wall.png').read_bytes() == wall
    preserved = json.loads(Path('gathering/preservation-29.json').read_text())
    assert preserved['inherited_wall_sha256'] == digest(before)
    assert preserved['output_sha256'] == digest(wall)
    box = preserved['mark_rectangle']
    assert box == [925, 135, 220, 205]
    changed = outside = 0
    protected = hashlib.sha256()
    for y in range(1254):
        for x in range(1254):
            i = (y * 1254 + x) * 3
            old, new = old_pixels[i:i + 3], pixels[i:i + 3]
            if box[0] <= x < box[0] + box[2] and box[1] <= y < box[1] + box[3]:
                changed += old != new
            else:
                outside += old != new
                protected.update(new)
    assert changed == preserved['changed_pixels_inside'] == 5762
    assert outside == preserved['pixels_changed_outside'] == 0
    assert protected.hexdigest() == preserved['protected_rgb_sha256']

    preview = Path('dist/gathering/29.jpg').read_bytes()
    assert jpeg_dimensions(preview) == (512, 512) and len(preview) < 100000
    record = json.loads(Path('dist/gathering/29.json').read_text())
    assert set(record) == {'name', 'image', 'attributes'}
    assert record['image'] == 'https://api.imd.fun/artifacts/' + digest(wall)
    traits = {row['trait_type']: row['value'] for row in record['attributes']}
    assert len(record['attributes']) == len(traits) == 6
    assert set(traits) == {'Cave', 'Wall', 'Number', 'Left behind', 'Meaning', 'One thing'}
    assert traits['Cave'] == 'Lava' and traits['Wall'] == traits['One thing'] == 'Gathering'
    assert type(traits['Number']) is int and traits['Number'] == 29
    review = json.loads(Path('gathering/review-29.json').read_text())
    assert review['wall_dimensions'] == [1254, 1254] and review['wall_format'] == 'PNG'
    assert review['preview_dimensions'] == [512, 512] and review['preview_format'] == 'JPEG'
    assert review['wall_sha256'] == digest(wall) and review['preview_sha256'] == digest(preview)
    assert review['visual_requirements_unmet'] == []

    goals = [{'line': n, 'goal': Path(f'line-{n}/GOAL.md').read_text().strip()}
             for n in range(1, 5)]
    assert json.loads(Path('dist/goals.json').read_text()) == goals
    page = Path('dist/index.html').read_text()
    assert '<script' not in page and '<style>' in page
    folders = [f'line-{n}' for n in range(1, 5)] + ['gathering']
    total = placeholders = painted = 0
    bare = 'https://api.imd.fun/artifacts/09ee8caaf2f2f23c437db97f072627760da64d33dbd2b3409379a24a4a38d26a'
    for folder in folders:
        positions = []
        for path in Path('dist', folder).glob('*.json'):
            assert re.fullmatch(r'\d{2}\.json', path.name)
            assert f'href="{folder}/{path.name}"' in page
            record = json.loads(path.read_text())
            total += 1
            if record['name'] == 'Not painted yet':
                assert record == {'name': 'Not painted yet', 'image': bare,
                                  'attributes': [{'trait_type': 'Cave', 'value': 'Lava'}]}
                assert not path.with_suffix('.jpg').exists()
                placeholders += 1
            else:
                assert jpeg_dimensions(path.with_suffix('.jpg').read_bytes()) == (512, 512)
                painted += 1
        for n in range(2, 22):
            assert json.loads(Path('dist', folder, f'{n:02}.json').read_text())['name'] == 'Not painted yet'
        for n in (29, 28, 27, 26, 25, 24, 23, 22, 1):
            positions.append(page.index(f'href="{folder}/{n:02}.json"'))
        assert positions == sorted(positions)
    assert (total, placeholders, painted) == (145, 100, 45)

    sources = json.loads(Path('shared/api_bundle/SOURCES.json').read_text())
    assert len(sources) == 11
    for destination, entry in sources.items():
        assert digest(Path(entry['source']).read_bytes()) == entry['source_sha256']
        assert digest(Path('shared/api_bundle', destination).read_bytes()) == entry['sha256']
    checks = json.loads(Path('gathering/check-results-29.json').read_text())
    assert len(checks) == 76 and all(row['passed'] and row['exit'] == row['expected_exit'] for row in checks)
    assert sum(row['unittest_cases'] for row in checks) == 489
    shared = json.loads(Path('gathering/shared-check-results-29.json').read_text())
    assert shared['isolated_copy'] and all(row['passed'] for row in shared['results'])
    assert shared['results'][0]['tests'] == 49
    assert Path('gathering/COINS.md').read_text().startswith('none\n')
    assert not Path('gathering/coin-order.json').exists()
    assert not Path('gathering/deploy-order.json').exists()

    status = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=all'],
                            capture_output=True, text=True, check=True).stdout
    for line in status.splitlines():
        path = line[3:]
        assert path.startswith(('gathering/', 'shared/', 'artifacts/gathering/', 'dist/',
                                'test/scratch/')), path
        assert not path.startswith(tuple(f'dist/line-{n}/' for n in range(1, 5)))
        item = Path(path)
        if item.is_file() and not path.startswith(('artifacts/', 'test/scratch/')):
            assert item.stat().st_size <= 100000, path
    tracked = subprocess.run(['git', 'ls-files', '--error-unmatch',
                              'artifacts/gathering/wall-v10.png'], capture_output=True)
    assert tracked.returncode == 1
    result = {'passed': True, 'line_files_unchanged': len(actual_lines),
              'line_commands_passed': len(checks), 'line_unittest_cases': 489,
              'shared_tests_passed_in_isolation': 49, 'gallery_records': total,
              'painted_records': painted, 'placeholders': placeholders,
              'wall_dimensions': list(size), 'wall_format': 'PNG',
              'preview_dimensions': [512, 512], 'preview_format': 'JPEG',
              'preview_bytes': len(preview), 'wall_sha256': digest(wall),
              'pixels_changed_inside': changed, 'pixels_changed_outside': outside,
              'visual_requirements_unmet': review['visual_requirements_unmet'],
              'limitation': 'Local byte/path checks do not independently certify behavior or visual quality.'}
    Path('gathering/delivery-check-29.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
