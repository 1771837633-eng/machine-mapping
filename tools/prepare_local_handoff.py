"""Prepare a consistent handoff checkpoint inside this shared project, without Git writes.

Copies source/docs and uses SQLite's online backup API. Experimental input and
legacy captures stay in place and are inventoried. Live queue/locks are never
copied into a runnable bridge. No Igor calls or scientific data saves.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.records import Store


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def inside(path):
    path=path.resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('Handoff inputs and output must stay inside the project')
    return path


def entry(path):
    path=inside(path)
    return {'path':path.relative_to(ROOT).as_posix(), 'bytes':path.stat().st_size,
            'sha256':digest(path)}


def source_files():
    for directory,dirs,files in os.walk(ROOT):
        parent=Path(directory)
        dirs[:]=[d for d in dirs if d not in {'.git','local','__pycache__','.agents','.codex','.aws'}
                 and not (parent==ROOT/'pilot' and d in {'input','exports','results'})
                 and not (parent/d).is_symlink()]
        for name in sorted(files):
            path=parent/name
            if path.suffix.lower() in {'.py','.ipf','.itx','.txt','.md','.json','.cmd'} or name in {'.gitignore','.gitattributes'}:
                if not path.is_symlink():
                    yield inside(path)


def prepare(db,bridge):
    db,bridge=inside(db),inside(bridge)
    stamp=datetime.now().astimezone().strftime('%Y%m%d-%H%M%S-%f')
    folder=ROOT/'local'/'handoff'/stamp
    folder.mkdir(parents=True,exist_ok=False)
    checkpoint={'created_utc':datetime.now(timezone.utc).isoformat(), 'host':socket.gethostname(),
                'project_root_at_capture':str(ROOT), 'artifacts':[], 'in_place_dependencies':[],
                'missing_dependencies':[], 'notes':[
                    'Source backup is a point-in-time copy; use the main project root for execution.',
                    'PXP and legacy captures remain inside the shared project and are not duplicated.',
                    'Igor memory-only science results do not move with this folder.',
                    'No live request, lock, session attachment or heartbeat is included for replay.'
                ]}
    for source in source_files():
        target=folder/'source'/source.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        if digest(source)!=digest(target):
            raise RuntimeError(f'Source changed while copying: {source}')
    if db.is_file():
        target=folder/'state'/'notebook.sqlite3'
        target.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as original:
            with sqlite3.connect(target) as backup:
                original.backup(backup)
                if backup.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise RuntimeError('SQLite snapshot integrity check failed')
        store=Store(target)
        records,session,jobs=store.records(),store.metadata(),store.jobs()
        (folder/'state'/'records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
        (folder/'state'/'session.json').write_text(json.dumps(session,ensure_ascii=False,indent=2),encoding='utf-8')
        (folder/'state'/'jobs.json').write_text(json.dumps(jobs,ensure_ascii=False,indent=2),encoding='utf-8')
        checkpoint['database']={'source':db.relative_to(ROOT).as_posix(), 'integrity_check':'ok',
                                'records':len(records), 'jobs':len(jobs)}
    else:
        checkpoint['missing_dependencies'].append(str(db.relative_to(ROOT)))
    for receipt in sorted(bridge.glob('*.receipt.txt')):
        content=receipt.read_text(encoding='utf-8')
        if content.splitlines()[-1:]!=['END']:
            raise RuntimeError(f'Incomplete receipt: {receipt}')
        target=folder/'state'/'receipts'/receipt.name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(receipt,target)
    for relative in ['pilot/input/FeSe20211118_JJJ_current.pxp',
                     'local/igor-repair/session-before','local/igor-repair/runtime',
                     'local/igor-repair/build-manifest.json','local/igor-repair/validation-history.txt',
                     'local/qa-export-current.xlsx']:
        path=ROOT/relative
        if path.is_file():
            checkpoint['in_place_dependencies'].append(entry(path))
        elif path.is_dir():
            checkpoint['in_place_dependencies'] += [entry(p) for p in sorted(path.rglob('*')) if p.is_file() and not p.is_symlink()]
        else:
            checkpoint['missing_dependencies'].append(relative)
    # Git is optional and read-only here. Failed Git approval does not block this checkpoint.
    try:
        env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')
        for name,args in [('git-status.txt',['status','--short','--branch']),
                          ('tracked-changes.patch',['diff','--binary','--no-ext-diff'])]:
            result=subprocess.run(['git',*args],cwd=ROOT,env=env,capture_output=True,timeout=15)
            if result.returncode:
                raise RuntimeError(result.stderr.decode('utf-8','replace'))
            (folder/name).write_bytes(result.stdout)
    except (OSError,RuntimeError,subprocess.TimeoutExpired) as error:
        checkpoint['git_read_note']=str(error)
    (folder/'START_HERE.txt').write_text(
        'Shared-folder handoff checkpoint. Read the main project 首先阅读_接手说明.txt and HANDOFF.txt.\n'
        'source/ contains the code/docs checkpoint, including untracked files.\n'
        'state/ contains a consistent SQLite backup, readable JSON and terminal receipts.\n'
        'manifest.json inventories this checkpoint and project-local dependencies.\n'
        'Do not replay old jobs or copy old live bridge files to another computer.\n'
        'Science data/results were not saved from Igor memory.\n',encoding='utf-8')
    for path in sorted(folder.rglob('*')):
        if path.is_file():
            info=entry(path)
            info['path']=path.relative_to(folder).as_posix()
            checkpoint['artifacts'].append(info)
    (folder/'manifest.json').write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2),encoding='utf-8')
    for info in checkpoint['artifacts']:
        if digest(folder/info['path'])!=info['sha256']:
            raise RuntimeError('Checkpoint hash verification failed: '+info['path'])
    (folder.parent/'LATEST.txt').write_text(folder.relative_to(ROOT).as_posix()+'\n',encoding='utf-8')
    return {'folder':folder.relative_to(ROOT).as_posix(), 'artifacts_verified':len(checkpoint['artifacts']),
            'dependency_files':len(checkpoint['in_place_dependencies']),
            'database':checkpoint.get('database'), 'missing_dependencies':checkpoint['missing_dependencies']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,default=ROOT/'local'/'trial-notebook.sqlite3')
    parser.add_argument('--bridge-dir',type=Path,default=ROOT/'local'/'igor-bridge')
    args=parser.parse_args()
    print(json.dumps(prepare(args.db,args.bridge_dir),ensure_ascii=False,indent=2))
