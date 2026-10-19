"""Local-only notebook. Run: python -m app.server --port 8766.

No third-party Python packages. The Igor bridge dispatches memory-only trials;
it does not claim a successful launch is successful scientific processing.
"""
import argparse
import json
import math
import secrets
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from app.records import FIELDS, MODES, SESSION_FIELDS, Store, export_xlsx, now
from app.igor_bridge import IgorBridge

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = r'D:\Applications\Igor Pro 9.0.5.1\Igor Pro 9 Folder\IgorBinaries_x64\Igor64.exe'


def quote_igor(text):
    text = str(text)
    if any(c in text for c in '\r\n\0'):
        raise ValueError('Igor 参数不支持换行或空字符')
    return '"'+text.replace('\\','\\\\').replace('"','\\"')+'"'


def scan_manifest(records, scan_id, config):
    import re
    group = [r for r in records if r['scan_id']==scan_id and r['processing']=='机械 mapping']
    if not scan_id or len(group)<2:
        raise ValueError('此扫描组至少需要两条机械 mapping 记录；普通记录不受影响')
    for r in group:
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,30}',r['file_name']):
            raise ValueError('试点文件名须填写 Igor 原始 Wave 名，例如 A20211118121854')
        if r['theta'] is None or r['sequence'] is None or r['sequence']<1 or r['sequence']%1:
            raise ValueError('每条 mapping 记录需要实际 theta 和正整数采集顺序')
        if not r['angle_source']:
            raise ValueError('请记录角度来源及约定，避免把 Polar/Tilt 默认映射到 theta')
    if len({r['file_name'] for r in group})!=len(group) or len({r['sequence'] for r in group})!=len(group):
        raise ValueError('扫描组有重复的 CUT 或采集顺序')
    if len({r['theta'] for r in group})!=len(group):
        raise ValueError('此试点不支持重复 theta，重复采集需先明确合并方式')
    if len({r['hv'] for r in group})!=1 or group[0]['hv'] is None or group[0]['hv']<=0:
        raise ValueError('固定光子能量 mapping 需要本组一致的正 hv')
    if len({r['source_path'] for r in group})!=1:
        raise ValueError('当前试点要求 CUT 来自同一 PXP，原始文件批量加载尚待接入')
    pxp=Path(group[0]['source_path'])
    if pxp.suffix.lower()!='.pxp' or not pxp.is_file():
        raise ValueError('请选择包含这些 CUT 的本地 PXP 文件')
    for key in ('temperature','polarization'):
        if len({r[key] for r in group})!=1:
            raise ValueError('扫描组的温度或偏振不同，请先确认分组')
    if any(r.get('phi') not in (None,0) or r.get('omega') is not None for r in group):
        raise ValueError('当前试点只接受 phi=0 或留空，omega 留空；马达映射尚未定标')
    try:
        low,high=float(config['low']),float(config['high'])
        gx,gy=float(config.get('nx',121)),float(config.get('ny',81))
        nx,ny=int(gx),int(gy)
    except (KeyError,ValueError,TypeError,OverflowError):
        raise ValueError('积分窗口和网格参数无效') from None
    if not math.isfinite(low+high) or low>=high or gx!=nx or gy!=ny or not (3<=nx<=301 and 3<=ny<=301):
        raise ValueError('需要有限且递增的积分窗口，网格范围 3–301')
    group.sort(key=lambda r:r['sequence'])
    return {'records':group,'pxp':str(pxp.resolve()),'low':low,'high':high,'nx':nx,'ny':ny,
            'scope':'existing processed CUTs; zero-bias legacy EK geometry; memory only',
            'hv':group[0]['hv']}


def job_commands(manifest, job_id):
    # Data are loaded into a unique job subtree, including on repeated runs.
    base='root:MMInput_'+job_id+':'
    target='root:MMResults:j'+job_id
    path=str(Path(manifest['pxp'])).replace('\\','/').replace('/',':')
    # Drive separator already exists; convert D::folder to Igor D:folder.
    path=path.replace('::',':')
    cuts=';'.join(r['file_name'] for r in manifest['records'])+';'
    angles=';'.join(str(r['theta']) for r in manifest['records'])+';'
    load='NewDataFolder/S '+base[:-1]+'; LoadData/R '+quote_igor(path)+'; SetDataFolder root:'
    # Check hv against recorded value before calculation; no silent substitution.
    run=f'MMMapping#MM_Run({quote_igor(base)},{quote_igor(target)},{quote_igor(cuts)},{quote_igor(angles)},{manifest["low"]:.12g},{manifest["high"]:.12g},{manifest["nx"]},{manifest["ny"]},{manifest["hv"]:.12g})'
    module=str(ROOT/'igor'/'MMMomentum.ipf').replace('\\',':').replace('/',':').replace('::',':')
    setup='OpenProc/V=0 '+quote_igor(module)+'; Execute/P "COMPILEPROCEDURES "'
    return {'setup':setup,'load':load,'run':run,'result_folder':target}


def create_server(port, store, exe, bridge=None):
    token=secrets.token_urlsafe(24)
    bridge=bridge or IgorBridge()

    def reconcile_jobs():
        jobs=store.jobs()
        for job in jobs:
            if job['status'] in ('queued','awaiting_igor','waiting_unverified'):
                receipt=bridge.receipt(job['id'])
                if receipt:
                    job.update(receipt,completed=now())
                    store.save_job(job)
                elif job['status']!='queued':
                    # Missing response is uncertainty, never successful completion.
                    import datetime
                    age=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(job['created'])).total_seconds()
                    if age>180 and job['status']!='waiting_unverified':
                        job.update(status='waiting_unverified',message='尚未收到回执；任务仍被占用，请检查 Igor，勿重复提交。')
                        store.save_job(job)
        return jobs

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def reply(self,body,status=200,mime='application/json; charset=utf-8',headers=None):
            if not isinstance(body,bytes):
                body=json.dumps(body,ensure_ascii=False,allow_nan=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'")
            for k,v in (headers or {}).items():
                self.send_header(k,v)
            self.end_headers()
            self.wfile.write(body)

        def allowed_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}

        def do_GET(self):
            if not self.allowed_host():
                return self.reply({'error':'Local access only'},403)
            path=urlsplit(self.path).path
            if path=='/api/state':
                return self.reply({'records':store.records(),'session':store.metadata(),'jobs':reconcile_jobs(),
                                   'fields':FIELDS,'modes':MODES,'session_fields':SESSION_FIELDS,'token':token,
                                   'igor_executable':str(exe),'igor_bridge':bridge.state(),'trial_only':True})
            if path=='/api/export.xlsx':
                return self.reply(export_xlsx(store.records(),store.metadata()),mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                  headers={'Content-Disposition':'attachment; filename="experimental-record.xlsx"'})
            files={'/':'index.html','/app.js':'app.js'}
            if path in files:
                return self.reply((ROOT/'app'/'static'/files[path]).read_bytes(),mime='text/html; charset=utf-8' if path=='/' else 'text/javascript; charset=utf-8')
            return self.reply({'error':'Not found'},404)

        def do_POST(self):
            try:
                length=int(self.headers.get('Content-Length','0'))
            except ValueError:
                return self.reply({'error':'请求大小无效'},400)
            if not 0<length<=200000:
                return self.reply({'error':'请求大小无效'},400)
            payload=self.rfile.read(length)
            if not self.allowed_host() or self.headers.get('X-Notebook-Token')!=token:
                return self.reply({'error':'请从本机面板提交'},403)
            origin=self.headers.get('Origin')
            if origin and origin not in {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}:
                return self.reply({'error':'Invalid origin'},403)
            try:
                data=json.loads(payload)
                path=urlsplit(self.path).path
                if path=='/api/record':
                    return self.reply({'id':store.save(data)})
                if path=='/api/session':
                    store.save_metadata(data)
                    return self.reply({'saved':True})
                if path=='/api/run':
                    manifest=scan_manifest(store.records(),data.get('scan_id',''),data)
                    job_id=uuid.uuid4().hex[:16]
                    job={'id':job_id,'created':now(),'scan_id':data['scan_id'],
                         'status':'queued','manifest':manifest}
                    job['commands']=job_commands(manifest,job_id)
                    store.save_job(job)
                    try:
                        job.update(bridge.submit(manifest,job_id))
                    except Exception as error:
                        job.update(status='failed',error=str(error))
                    store.save_job(job)
                    return self.reply({'job_id':job_id})
                return self.reply({'error':'Not found'},404)
            except (ValueError,TypeError,json.JSONDecodeError) as error:
                return self.reply({'error':str(error)},400)
            except Exception:
                return self.reply({'error':'操作未完成，请检查本地文件权限；已保存的记录仍保留'},500)
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--db',type=Path,default=ROOT/'local'/'notebook.sqlite3')
    parser.add_argument('--igor',type=Path,default=Path(DEFAULT_EXE))
    parser.add_argument('--bridge-dir',type=Path,default=ROOT/'local'/'igor-bridge',
                        help='Use a separate project-local directory for each processing computer')
    args=parser.parse_args()
    server=create_server(args.port,Store(args.db),args.igor,bridge=IgorBridge(args.bridge_dir))
    print(f'Notebook: http://127.0.0.1:{server.server_port}',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
