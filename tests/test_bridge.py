import datetime
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from app.igor_bridge import IgorBridge
from app.records import Store
from app.server import create_server


class BridgeTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'local'/'tests'
        root.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=root)
        self.dir=Path(self.tmp.name)
        self.bridge=IgorBridge(self.dir)
        self.manifest={'pxp':str(self.dir/'fixture.pxp'),'records':[
            {'file_name':'CUT_A','theta':0},{'file_name':'CUT_B','theta':-3}],
            'low':-.005,'high':.005,'nx':41,'ny':31,'hv':6.994}

    def tearDown(self):
        self.tmp.cleanup()

    def ready(self,age=0):
        clock=(datetime.datetime.now()-datetime.datetime(1904,1,1)).total_seconds()-age
        (self.dir/'ready.txt').write_text('MM1\n'+'a'*32+'\n'+str(clock)+'\n\n',encoding='utf-8')

    def receipt(self,job,status='memory_complete',complete=True):
        rows=['MM1',job,status,'root:MMResults:j'+job,'test only',
              '201','41','31','235126','20345','2.06e-12','END']
        (self.dir/(job+'.receipt.txt')).write_text('\n'.join(rows if complete else rows[:-1])+'\n',encoding='utf-8')

    def test_no_launch_without_live_attachment(self):
        with self.assertRaises(ValueError):
            self.bridge.submit(self.manifest,'0'*16)
        self.ready(age=30)
        with self.assertRaises(ValueError):
            self.bridge.submit(self.manifest,'0'*16)
        self.assertFalse((self.dir/'request.txt').exists())

    def test_persistent_slot_and_partial_receipt(self):
        self.ready()
        self.bridge.submit(self.manifest,'1'*16)
        fields=(self.dir/'request.txt').read_text(encoding='utf-8').splitlines()
        self.assertEqual(fields[4],'CUT_A;CUT_B;')
        self.assertNotIn('Execute',''.join(fields))
        restarted=IgorBridge(self.dir)
        self.receipt('1'*16,complete=False)
        with self.assertRaises(ValueError):
            restarted.submit(self.manifest,'2'*16)
        self.receipt('1'*16)
        self.assertEqual(self.bridge.receipt('1'*16)['shape'],[201,41,31])
        restarted.submit(self.manifest,'2'*16)
        self.assertEqual(json.loads((self.dir/'active.lock').read_text())['id'],'2'*16)

    def test_receipt_reconciles_after_server_restart_without_resending(self):
        store=Store(self.dir/'notebook.sqlite3')
        store.save_job({'id':'3'*16,'created':'2026-10-18T00:00:00+00:00',
                        'scan_id':'fixture','status':'awaiting_igor'})
        self.receipt('3'*16)
        server=create_server(0,store,Path('unused/Igor64.exe'),bridge=self.bridge)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/api/state',timeout=5) as response:
                job=json.load(response)['jobs'][0]
            self.assertEqual(job['status'],'memory_complete')
            self.assertEqual(Store(store.path).jobs()[0]['finite'],235126)
            self.assertFalse((self.dir/'request.txt').exists())
        finally:
            server.shutdown()
            server.server_close()

    def test_two_server_objects_cannot_publish_overlapping_jobs(self):
        self.ready()
        gate=threading.Barrier(2)
        outcomes=[]
        def submit(job):
            gate.wait()
            try:
                IgorBridge(self.dir).submit(self.manifest,job)
                outcomes.append(('submitted',job))
            except ValueError:
                outcomes.append(('rejected',job))
        threads=[threading.Thread(target=submit,args=(c*16,)) for c in ('4','5')]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=5)
        self.assertEqual(sorted(kind for kind,_ in outcomes),['rejected','submitted'])
        winner=next(job for kind,job in outcomes if kind=='submitted')
        self.assertEqual(json.loads((self.dir/'active.lock').read_text())['id'],winner)
        self.assertEqual((self.dir/'request.txt').read_text().splitlines()[2],winner)


if __name__=='__main__':
    unittest.main()
