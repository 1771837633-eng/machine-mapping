"""Build an isolated, UTF-8 legacy procedure tree from captured Igor buffers.

Inputs and generated third-party code remain under local/. Installation files are
never written. Explicit include paths prevent accidental selection of old copies.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path


def igor_path(path):
    return str(path.resolve()).replace(':\\', ':').replace('\\', ':')


def build(capture, output):
    names = json.loads((capture / 'names.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    mapping = {name.lower(): output / f'MMR{i:03d}_{name}'
               for i, name in enumerate(names) if name != 'Procedure'}
    manifest = []
    missing = set()
    for index, name in enumerate(names):
        if name == 'Procedure':
            continue
        source = capture / f'{index:03d}.ipf'
        text = source.read_text(encoding='utf-8')
        text = re.sub(r'(?im)^#pragma TextEncoding\s*=.*$', '#pragma TextEncoding = "UTF-8"', text)
        if not re.search(r'(?im)^#pragma TextEncoding', text):
            text = '#pragma TextEncoding = "UTF-8"\n' + text

        def include(match):
            requested = match[2]
            key = requested.lower().removesuffix('.ipf') + '.ipf'
            if key in mapping:
                return match[1] + '"' + igor_path(mapping[key]).removesuffix('.ipf') + '"'
            missing.add(requested)
            return match[0]

        text = re.sub(r'(?im)^(\s*#include\s+)"([^"\n]+)"', include, text)
        # Both tools expose a FitFL button callback. Rename only the linear
        # background tool, including its proc= callback reference.
        if name.lower() == 'fermilevelfit_linearbackground.ipf':
            text = re.sub(r'\bFitFL\b', 'MMR_LinearBackgroundFitFL', text, flags=re.I)
        if name.lower() == 'image_tool3.ipf':
            # OffsetStack builds commands from trace names; w is never used.
            # The old WAVE w=wn incorrectly assigns a string as a wave reference.
            text = text.replace('WAVE w=wn', '// Removed unused invalid wave reference: WAVE w=wn')
        if name.lower() == 'wav_util.ipf':
            # The runtime smoke test reproduced [1,1,1] for a scaled [1,2,3]
            # wave: tmp(np-1-p) used x coordinates rather than point indices.
            replacement = ('Function JEG_ReverseLegacy(w)\n\tWave w\n'
                           '\tVariable np=numpnts(w)\n'
                           '\tDuplicate/FREE w, MMRReverseCopy\n'
                           '\tw=MMRReverseCopy[np-1-p]\n\treturn np\nEnd')
            text, count = re.subn(r'(?ims)^Function JEG_ReverseLegacy\(w\).*?^End\s*$', replacement, text)
            if count != 1:
                raise ValueError('Expected the captured renamed Reverse function')
        if name.lower() != 'commonfunction2.ipf':
            # These helpers are static in #pragma ModuleName=CmnFunc.
            text = re.sub(r'(?<![#\w])\b(wavefromlistbox2?)\s*(?=\()',
                          r'CmnFunc#\1', text, flags=re.I)
        if name.lower() == 'lc_arpesprocess_2020.ipf':
            # The supplied library has neither BCS helper. Preserve its code
            # conditionally; fail before modifying waves when a helper is absent.
            for function, dependency in [('WDS_convFunc_BCSfit', 'BCSEDC'),
                                         ('WDS_convFunc_BCSfit2', 'BCSEDC_Direct')]:
                pattern = rf'(?ims)^Function {function}\(w,yw,xw\)\s*:\s*FitFunc\s*\n.*?^End\s*$'
                def guard(match, function=function, dependency=dependency):
                    return (f'#if exists("{dependency}")\n' + match[0] + '\n#else\n'
                            f'Function {function}(w,yw,xw) : FitFunc\n'
                            '\tWave w,yw,xw\n'
                            f'\tAbort "Missing {dependency}: obtain the original BCS procedure/plugin before using this fit."\n'
                            'End\n#endif\n')
                text, count = re.subn(pattern, guard, text)
                if count != 1:
                    raise ValueError(f'Expected exactly one {function}, found {count}')
        destination = mapping[name.lower()]
        destination.write_text(text, encoding='utf-8', newline='\r\n')
        manifest.append({'title': name, 'captured_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                         'output': destination.name, 'output_sha256': hashlib.sha256(destination.read_bytes()).hexdigest()})
    entry = mapping['00bxjzhers_ses2002.ipf']
    if missing:
        raise ValueError(f'Unresolved includes: {sorted(missing)}')
    report = {'capture': str(capture.resolve()), 'entry': str(entry.resolve()),
              'files': manifest, 'unresolved_quoted_includes': sorted(missing),
              'unavailable_science_dependencies': ['BCSEDC', 'BCSEDC_Direct']}
    (output.parent / 'build-manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    launch = ('IGOR\n'
              f'X OpenProc "{igor_path(entry)}"\n'
              'X Execute/P "COMPILEPROCEDURES "\n'
              'X Execute/P "Load_SES2002_Data()"\n'
              'X Execute/P "FLfit()"\n'
              'X Execute/P "SetDataFolder root:"\n'
              'X Execute/P "Print \\"MM_LEGACY_STARTUP_READY\\""\n')
    (output.parent / 'launch.itx').write_text(launch, encoding='utf-8')
    print(json.dumps({'entry': str(entry), 'files': len(manifest), 'unresolved': sorted(missing)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, default=Path('local/igor-repair/session-before'))
    parser.add_argument('--output', type=Path, default=Path('local/igor-repair/runtime'))
    args = parser.parse_args()
    build(args.capture, args.output)
