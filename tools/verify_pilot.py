"""Recheck the local pilot exports; no Igor control and no synthetic fallback."""
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from prepare_mapping import prepare, sha256


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    exports = ROOT / 'pilot' / 'exports'
    table = exports / 'original_parameters.tsv'
    if not table.is_file():
        raise FileNotFoundError('Local pilot exports missing; see pilot/export_commands.igor.txt. No data is bundled with Git.')
    confirmation = json.loads((ROOT / 'pilot' / 'angle_confirmation.json').read_text(encoding='utf-8'))
    names = [item['cut'] for item in confirmation['confirmed_angles']]
    before = {p.name: sha256(p) for p in [table, *exports.glob('*.ibw')]}
    checks = []

    result = prepare(table, names, 0, -3, exports, [-.01, .01], confirmation)
    require(len(result['cuts']) == 6, 'Expected six pilot CUTs')
    require(all(x['theta_existing'] == x['theta_proposed'] for x in result['cuts']), 'Angle reconstruction differs')
    require(len(result['issues']) == 6 and all(x['kind'] == 'integration_window_outside_wave' for x in result['issues']), 'Integration warnings were lost')
    require(len(result['resolved_issues']) == 1 and result['resolved_issues'][0]['confirmed_theta'] == -15, 'Angle conflict not resolved with provenance')
    require(result['cuts'][-1]['experimental_note'].endswith(',0'), 'Original note not preserved')
    require(result['ready_for_scientific_mapping'] is False, 'Preflight incorrectly marked scientific mapping ready')
    for cut in result['cuts']:
        require(cut['original']['shape'] == [201, 901], 'Raw grid mismatch')
        require(cut['processed']['shape'] == [201, 642], 'Processed grid mismatch')
    require(result['cuts'][0]['original']['sum'] == 15752892, 'First raw sum differs from recorded Igor WaveStats')
    require(result['cuts'][-1]['original']['sum'] == 8918145, 'Last raw sum differs from recorded Igor WaveStats')
    checks.append('six CUTs, shapes, recorded native sums, resolved conflict, preserved note, retained window warnings')

    unconfirmed = prepare(table, names, 0, -3, exports, [-.01, .01])
    require(len(unconfirmed['issues']) == 7 and not unconfirmed['resolved_issues'], 'Unconfirmed conflict was hidden')
    inside = prepare(table, names, 0, -3, exports, [-.005, .005], confirmation)
    require(not inside['issues'] and len(inside['resolved_issues']) == 1, 'Within-range preflight failed')
    reversed_result = prepare(table, list(reversed(names)), 0, -3, exports)
    require(sum(x['kind'] == 'existing_angle_differs' for x in reversed_result['issues']) == 6, 'Reversed order not detected')
    checks.append('unconfirmed conflict retained, within-range preflight, reversed order detected')

    invalid = []
    for kind in ('hash', 'angle'):
        bad = copy.deepcopy(confirmation)
        if kind == 'hash':
            bad['table_sha256'] = 'stale'
        else:
            bad['confirmed_angles'][-1]['theta'] = 0
        invalid.append((kind, names, -3, bad))
    invalid.extend([('duplicate', [names[0], names[0]], -3, None),
                    ('missing', [names[0], 'missing'], -3, None),
                    ('zero_step', names, 0, None)])
    for label, selected, step, evidence in invalid:
        try:
            prepare(table, selected, 0, step, exports, resolutions=evidence)
        except ValueError:
            checks.append('rejected ' + label)
        else:
            raise AssertionError('Invalid input accepted: ' + label)
    require(before == {p.name: sha256(p) for p in [table, *exports.glob('*.ibw')]}, 'Input files changed')
    checks.append('input parameter table and IBW hashes unchanged')
    output = ROOT / 'pilot' / 'results' / 'verification.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'status': 'passed', 'verified_at_utc': datetime.now(timezone.utc).isoformat(),
                                 'table_sha256': before[table.name], 'checks': checks,
                                 'scope': 'Python preflight only; no Igor processing or Fermi-surface reconstruction executed'},
                                ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'passed', 'checks': len(checks), 'receipt': str(output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
