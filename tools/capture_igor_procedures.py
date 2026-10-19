"""Prepare an Igor Text script to snapshot loaded buffers; no experiment saves.

Run only after observing the intended Igor UI and exporting its procedure list.
Exports text (including unsaved edits), not experimental waves or credentials.
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory.resolve()
    names = [n for n in (directory / 'procedure-list.txt').read_text().strip().split(';') if n]
    commands = ['IGOR', 'X Variable/G MMRepairRef20261019; String/G MMRepairText20261019']
    for index, name in enumerate(names):
        if any(c in name for c in '\\/:"\r\n'):
            raise ValueError(f'Unexpected procedure title: {name!r}')
        destination = directory / f'{index:03d}.ipf'
        if destination.exists():
            if destination.stat().st_size == 0 and name != 'Procedure':
                raise ValueError(f'Empty previous capture: {destination}')
            continue
        igor_path = str(destination).replace(':\\', ':').replace('\\', ':')
        quoted_name = name.replace('"', '\\"')
        command = (f'MMRepairText20261019=ProcedureText("",0,"{quoted_name}"); '
                   f'Open MMRepairRef20261019 as "{igor_path}"; '
                   'FBinWrite MMRepairRef20261019, MMRepairText20261019; '
                   'Close MMRepairRef20261019')
        commands.append('X ' + command)
    commands.append('X Print "MM_CAPTURE_COMPLETE"')
    script = directory.parent / 'capture.itx'
    script.write_text('\n'.join(commands) + '\n', encoding='utf-8')
    (directory / 'names.json').write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Prepared {len(names)} buffer exports; execute LoadWave/T on {script} and verify MM_CAPTURE_COMPLETE')


if __name__ == '__main__':
    main()
