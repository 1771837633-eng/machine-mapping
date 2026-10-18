"""Read-only Igor export audit and explicit ordered-CUT angle plan.

Does not modify PXP/IBW files or infer instrument geometry.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from igor2 import binarywave


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def wave_summary(path, expected_name):
    wave = binarywave.load(str(path))['wave']
    header, data = wave['wave_header'], wave['wData']
    name = header['bname'].decode('utf-8')
    if name != expected_name or data.ndim != 2:
        raise ValueError(f'Unexpected wave name or dimensions: {path}')
    if not np.isfinite(data).all():
        raise ValueError(f'Non-finite intensity: {path}')
    axes = []
    for dim, count in enumerate(data.shape):
        start, step = float(header['sfB'][dim]), float(header['sfA'][dim])
        if not math.isfinite(start) or not math.isfinite(step) or step == 0:
            raise ValueError(f'Invalid axis: {path}')
        axes.append({'start': start, 'step': step, 'end': start + step * (count - 1)})
    note = wave['note'].decode('utf-8', errors='replace')
    return {'file': str(path.resolve()), 'sha256': sha256(path), 'name': name,
            'shape': list(data.shape), 'axes': axes, 'sum': float(data.sum(dtype=np.float64)),
            'minimum': float(data.min()), 'maximum': float(data.max()), 'note': note}


def prepare(table, names, start, step, export_dir, energy_window=None, resolutions=None):
    if len(names) < 2 or len(set(names)) != len(names):
        raise ValueError('Specify at least two distinct CUT names in acquisition order.')
    if not all(math.isfinite(v) for v in (start, step)) or step == 0:
        raise ValueError('Start and nonzero step must be finite.')
    if energy_window and (not all(math.isfinite(v) for v in energy_window)
                          or energy_window[0] >= energy_window[1]):
        raise ValueError('Energy window must be finite and increasing.')
    with table.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    by_name = {}
    for index, row in enumerate(rows):
        name = row['OriginalImage']
        if name in by_name:
            raise ValueError(f'Duplicate OriginalImage: {name}')
        by_name[name] = (index, row)
    table_hash = sha256(table)
    confirmations = {}
    if resolutions is not None:
        if resolutions.get('table_sha256') != table_hash:
            raise ValueError('Confirmation belongs to a different parameter table.')
        if not resolutions.get('user_statement') or not resolutions.get('confirmed_on'):
            raise ValueError('Confirmation must retain user statement and date.')
        for item in resolutions.get('confirmed_angles', []):
            name, angle = item['cut'], item['theta']
            if name not in names or name not in by_name or name in confirmations or not math.isfinite(angle):
                raise ValueError(f'Unknown, duplicate, or invalid angle confirmation: {name}')
            if not math.isclose(float(by_name[name][1]['Theta_Angle']), angle, abs_tol=1e-8):
                raise ValueError(f'Confirmed angle differs from current table: {name}')
            confirmations[name] = angle
    plan, issues, resolved_issues = [], [], []
    reference_axes = None
    for order, name in enumerate(names):
        if name not in by_name or Path(name).name != name or any(c in name for c in ':\\/'):
            raise ValueError(f'Unknown or invalid CUT: {name}')
        index, row = by_name[name]
        proposed, existing = start + order * step, float(row['Theta_Angle'])
        if not math.isfinite(existing):
            raise ValueError(f'Non-finite existing angle: {name}')
        original = wave_summary(export_dir / f'{name}.ibw', name)
        processed_name = row['ProcessedImage']
        if Path(processed_name).name != processed_name or any(c in processed_name for c in ':\\/'):
            raise ValueError('Invalid processed wave name')
        processed = wave_summary(export_dir / f'{processed_name}.ibw', processed_name)
        if not math.isclose(existing, proposed, abs_tol=1e-8):
            issues.append({'cut': name, 'kind': 'existing_angle_differs', 'existing': existing, 'proposed': proposed})
        # This field convention is specific to this pilot's FineMapping notes.
        note = row['ExperimentalNote']
        note_angle = None
        if note.startswith('FineMapping,'):
            try:
                note_angle = float(note.rsplit(',', 1)[-1])
            except ValueError:
                pass
            if note_angle is not None and (not math.isfinite(note_angle)
                    or not math.isclose(note_angle, existing, abs_tol=1e-8)):
                issue = {'cut': name, 'kind': 'note_table_conflict', 'note_value': note_angle, 'table_value': existing}
                if name in confirmations:
                    issue.update({'resolution': 'user_confirmed_table_angle', 'confirmed_theta': confirmations[name]})
                    resolved_issues.append(issue)
                else:
                    issues.append(issue)
        if energy_window:
            low, high = sorted([processed['axes'][0]['start'], processed['axes'][0]['end']])
            if energy_window[0] < low - 1e-8 or energy_window[1] > high + 1e-8:
                issues.append({'cut': name, 'kind': 'integration_window_outside_wave',
                               'requested': energy_window, 'available': [low, high]})
        axis_signature = [processed['shape'], processed['axes']]
        if reference_axes is not None and axis_signature != reference_axes:
            issues.append({'cut': name, 'kind': 'processed_grid_differs'})
        reference_axes = axis_signature
        plan.append({'order': order, 'source_row': index, 'cut': name, 'theta_existing': existing,
                     'theta_proposed': proposed, 'note_angle_candidate': note_angle,
                     'angle_authority': 'user_confirmation' if name in confirmations else 'unconfirmed_table',
                     'phi': float(row['Phi_Angle']), 'omega': float(row['Omega_Angle']),
                     'process_flag': float(row['ProcessFlag']), 'experimental_note': note,
                     'original': original, 'processed': processed})
    return {'mode': 'preview_only', 'angle_rule': {'start': start, 'step': step,
            'authority': 'explicit command arguments; not independently established acquisition metadata'},
            'table': str(table.resolve()), 'table_sha256': table_hash, 'cuts': plan, 'issues': issues,
            'resolved_issues': resolved_issues, 'confirmation': resolutions,
            'ready_for_scientific_mapping': False,
            'limitations': ['Physical calibration and scan identity require validation.',
                           'FineMapping final-note token is a pilot-specific angle candidate.',
                           'No source Wave or experiment was modified.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--table', type=Path, required=True)
    parser.add_argument('--exports', type=Path, required=True)
    parser.add_argument('--cuts', nargs='+', required=True, help='Explicit acquisition order; never sorted implicitly')
    parser.add_argument('--start', type=float, required=True)
    parser.add_argument('--step', type=float, required=True)
    parser.add_argument('--energy-window', nargs=2, type=float)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resolutions', type=Path, help='User confirmation tied to the exact exported table')
    args = parser.parse_args()
    resolutions = json.loads(args.resolutions.read_text(encoding='utf-8')) if args.resolutions else None
    result = prepare(args.table, args.cuts, args.start, args.step, args.exports, args.energy_window, resolutions)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    with (args.output / 'angle_preview.tsv').open('w', encoding='utf-8-sig', newline='') as stream:
        fields = ['order', 'source_row', 'cut', 'theta_existing', 'theta_proposed', 'note_angle_candidate', 'angle_authority', 'phi', 'omega', 'process_flag', 'experimental_note']
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter='\t', extrasaction='ignore')
        writer.writeheader()
        writer.writerows(result['cuts'])
    print(json.dumps({'cuts': len(result['cuts']), 'issues': result['issues'], 'output': str(args.output.resolve())}, ensure_ascii=False))


if __name__ == '__main__':
    main()
