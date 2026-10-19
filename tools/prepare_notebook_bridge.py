"""Prepare an ITX attachment for the user's existing Igor; never launch Igor."""
import sys
import uuid
import argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.igor_bridge import ROOT, igor_path
from app.server import quote_igor


def prepare(directory=None):
    folder=Path(directory or ROOT/'local'/'igor-bridge').resolve()
    folder.mkdir(parents=True,exist_ok=True)
    lines=['IGOR']
    for name in ('MMMomentum.ipf','MMNotebookBridge.ipf'):
        lines.append('X OpenProc/V=0 '+quote_igor(igor_path(ROOT/'igor'/name)))
    lines+=['X Execute/P "COMPILEPROCEDURES "',
            'X Execute/P '+quote_igor('MMMapping#MM_StartBridge('+quote_igor(igor_path(folder)+':')+','+quote_igor(uuid.uuid4().hex)+')')]
    target=folder/'attach.itx'
    target.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return 'LoadWave/T '+quote_igor(igor_path(target))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,help='Same directory as app.server --bridge-dir')
    args=parser.parse_args()
    print('Run this once in the existing 64-bit Igor command line:')
    print(prepare(args.directory))
