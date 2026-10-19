"""Behavioral tests for persistence, isolated jobs and spreadsheet interchange."""
import copy
import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from unittest.mock import patch

from app.records import FIELDS, Store, export_xlsx
from app.server import create_server, job_commands, scan_manifest


class NotebookTests(unittest.TestCase):
    def setUp(self):
        temp_root=Path(__file__).resolve().parents[1]/'local'/'tests'
        temp_root.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=temp_root)
        self.path=Path(self.tmp.name)
        self.store=Store(self.path/'notebook.sqlite3')

    def tearDown(self):
        self.tmp.cleanup()

    def group(self):
        pxp=self.path/'source.pxp'
        pxp.write_bytes(b'identity fixture; not scientific data')
        for i in range(2):
            self.store.save({'file_name':f'A2021111812000{i}','processing':'机械 mapping',
                             'scan_id':'scan1','sequence':i+1,'theta':-3*i,'hv':6.994,
                             'source_path':str(pxp),'angle_source':'fixture explicit table'})
        return self.store.records()

    def test_record_survives_restart_and_failed_mapping_readiness(self):
        self.store.save({'file_name':'普通记录','processing':'变温','theta':'','x':0,
                         'other':'尚未采集，仅记录条件'})
        with self.assertRaises(ValueError):
            scan_manifest(self.store.records(),'not-a-scan',{'low':-.005,'high':.005})
        reopened=Store(self.store.path).records()
        self.assertEqual(len(reopened),1)
        self.assertEqual(reopened[0]['x'],0)
        self.assertIsNone(reopened[0]['theta'])
        self.assertEqual(reopened[0]['other'],'尚未采集，仅记录条件')

    def test_conflicting_edit_cannot_silently_overwrite(self):
        self.store.save({'file_name':'record1'})
        original=self.store.records()[0]
        self.store.save(dict(original,other='first update'))
        with self.assertRaisesRegex(ValueError,'其他窗口'):
            self.store.save(dict(original,other='stale update'))
        self.assertEqual(self.store.records()[0]['other'],'first update')

    def test_fixed_hv_scan_identity_and_order_guards(self):
        records=self.group()
        config={'low':-.005,'high':.005}
        manifest=scan_manifest(records,'scan1',config)
        self.assertEqual([r['theta'] for r in manifest['records']],[0,-3])
        for key,value in [('hv',7),('sequence',1),('file_name','bad\";Abort'),('theta',None)]:
            changed=copy.deepcopy(records)
            changed[1][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                scan_manifest(changed,'scan1',config)
        self.assertEqual(len(self.store.records()),2)
        commands=job_commands(manifest,'abc123')
        self.assertIn('root:MMInput_abc123',commands['load'])
        self.assertNotIn('Save',json.dumps(commands))
        self.assertIn('6.994',commands['run'])
        self.assertNotIn('/O',commands['load'])
        for grid in (3.5,float('inf')):
            with self.assertRaises(ValueError):
                scan_manifest(records,'scan1',dict(config,nx=grid))

    def test_xlsx_all_fields_zero_blank_unicode_and_formula_text(self):
        record={'file_name':'=1+1','processing':'其他','x':0,'temperature':9.1,
                'other':'中文 & <备注>','theta':None}
        self.store.save(record)
        exported=export_xlsx(self.store.records(),{'实验装置':'laser ARPES'})
        ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        with zipfile.ZipFile(io.BytesIO(exported)) as z:
            root=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
            self.assertEqual(len(root.findall('.//m:row',ns)),2)
            self.assertFalse(root.findall('.//m:f',ns))
            self.assertEqual(root.find('.//m:c[@r="A2"]/m:is/m:t',ns).text,'=1+1')
            self.assertEqual(root.find('.//m:c[@r="F2"]/m:v',ns).text,'0.0')
            self.assertIn('中文 & <备注>',[t.text for t in root.findall('.//m:t',ns)])
            self.assertEqual(len(root.findall('.//m:row[@r="1"]/m:c',ns)),len(FIELDS)+3)
            self.assertIn('laser ARPES',z.read('xl/worksheets/sheet2.xml').decode())

    def test_http_recording_continues_after_bridge_failure(self):
        self.group()
        server=create_server(0,self.store,Path('missing/Igor64.exe'))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def request(path,data=None,token=None):
            req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data else None,
                    headers={'Content-Type':'application/json','X-Notebook-Token':token or ''})
            with urllib.request.urlopen(req,timeout=5) as response:
                return json.load(response)
        try:
            token=request('/api/state')['token']
            with self.assertRaises(urllib.error.HTTPError) as error:
                request('/api/record',{'file_name':'unauthorized'})
            self.assertEqual(error.exception.code,403)
            with patch('app.igor_bridge.IgorBridge.submit',side_effect=RuntimeError('Igor unavailable')):
                request('/api/run',{'scan_id':'scan1','low':-.005,'high':.005},token)
                # Join work by waiting for the persistent job state, bounded to 2s.
                import time
                deadline=time.monotonic()+2
                while self.store.jobs()[0]['status']=='queued' and time.monotonic()<deadline:
                    time.sleep(.02)
            self.assertEqual(self.store.jobs()[0]['status'],'failed')
            request('/api/record',{'file_name':'后续温度记录','processing':'变温','temperature':15},token)
            self.assertEqual(len(self.store.records()),3)
        finally:
            server.shutdown()
            server.server_close()


if __name__=='__main__':
    unittest.main()
