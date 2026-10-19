"""Data-only file bridge to the explicitly attached, existing 64-bit Igor.

No executable launch and no evaluation of request strings. A persistent slot
prevents a timeout or server restart from overlapping an unacknowledged job.
"""
import datetime
from contextlib import contextmanager
import json
import math
import os
import re
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def igor_path(path):
    return str(Path(path).resolve()).replace('\\', ':').replace('/', ':').replace('::', ':')


class IgorBridge:
    def __init__(self, directory=None):
        self.directory = Path(directory or ROOT/'local'/'igor-bridge')
        self.lock = threading.Lock()

    @contextmanager
    def submission_lock(self):
        # Serialize old-slot retirement and publication across server processes.
        # A crash leaves a guard for explicit inspection instead of guessing idle.
        with self.lock:
            guard=self.directory/'submission.guard'
            try:
                guard.mkdir()
            except FileExistsError:
                raise ValueError('另一服务正在提交任务；若服务异常退出，请检查连接目录') from None
            try:
                yield
            finally:
                guard.rmdir()

    def state(self):
        try:
            lines=(self.directory/'ready.txt').read_text(encoding='utf-8').splitlines()
            if len(lines)!=4 or lines[0]!='MM1' or not re.fullmatch('[a-f0-9]{32}',lines[1]):
                raise ValueError('Incomplete heartbeat')
            clock=(datetime.datetime.now()-datetime.datetime(1904,1,1)).total_seconds()
            age=clock-float(lines[2])
            connected=math.isfinite(age) and -3<=age<=15 and lines[3]!='stopped'
            return {'connected':connected,'session':lines[1],'busy':lines[3],
                    'message':'Igor 已连接' if connected else 'Igor 暂未响应，请检查当前会话'}
        except (OSError,ValueError):
            return {'connected':False,'message':'请在当前 64 位 Igor 加载项目连接模块'}

    def receipt(self, job_id):
        if not re.fullmatch('[a-f0-9]{16}',job_id):
            return None
        try:
            lines=(self.directory/(job_id+'.receipt.txt')).read_text(encoding='utf-8').splitlines()
            if len(lines)!=12 or lines[0]!='MM1' or lines[1]!=job_id or lines[-1]!='END':
                return None
            if lines[2] not in ('memory_complete','failed'):
                return None
            result={'status':lines[2]}
            if lines[2]=='failed':
                result['error']=lines[4]
                result['message']='Igor 已停止此任务；实验记录仍可正常保存和导出。'
            else:
                shape=[int(v) for v in lines[5:8]]
                finite,nans=int(lines[8]),int(lines[9])
                residual=float(lines[10])
                if shape[0]<2 or min(shape[1:])<3 or finite<=0 or finite+nans!=math.prod(shape) or not math.isfinite(residual):
                    return None
                result.update(result_folder=lines[3],shape=shape,finite=finite,nans=nans,roundtrip_max_abs=residual,
                              message='Igor 内存试跑完成；费米面和三维动量数据已生成，物理标定尚待确认。')
            return result
        except (OSError,ValueError,OverflowError):
            return None

    def submit(self, manifest, job_id):
        if not re.fullmatch('[a-f0-9]{16}',job_id):
            raise ValueError('Invalid job ID')
        ready=self.state()
        if not ready['connected']:
            raise ValueError(ready['message'])
        with self.submission_lock():
            # Re-read after obtaining the guard, as another process may reconnect.
            ready=self.state()
            if not ready['connected'] or ready['busy']:
                raise ValueError('Igor 未就绪或仍在处理任务，普通记录可继续')
            slot=self.directory/'active.lock'
            # A complete old receipt is the only automatic reason to free a slot.
            if slot.exists():
                try:
                    active=json.loads(slot.read_text(encoding='utf-8'))
                except (ValueError,OSError):
                    raise ValueError('Igor 任务占用记录异常，请先检查；普通记录可继续') from None
                if self.receipt(active.get('id','')):
                    slot.unlink()
            try:
                with slot.open('x',encoding='utf-8') as f:
                    json.dump({'id':job_id,'session':ready['session']},f)
            except FileExistsError:
                raise ValueError('Igor 仍有任务等待回执，避免重复运行；普通记录可继续') from None
            try:
                fields=['MM1',ready['session'],job_id,igor_path(manifest['pxp']),
                        ';'.join(r['file_name'] for r in manifest['records'])+';',
                        ';'.join(str(r['theta']) for r in manifest['records'])+';',
                        str(manifest['low']),str(manifest['high']),str(manifest['nx']),
                        str(manifest['ny']),str(manifest['hv'])]
                if any(any(c in s for c in '\r\n\0') for s in fields):
                    raise ValueError('Mapping 请求含不支持的换行或空字符')
                tmp=self.directory/(job_id+'.tmp')
                with tmp.open('w',encoding='utf-8',newline='') as f:
                    f.write('\r\n'.join(fields)+'\r\n')
                    f.flush()
                    os.fsync(f.fileno())
                tmp.replace(self.directory/'request.txt')
            except Exception:
                slot.unlink(missing_ok=True)
                raise
            return {'status':'awaiting_igor','message':'等待 Igor 处理回执；实验条件仍可继续记录。'}
