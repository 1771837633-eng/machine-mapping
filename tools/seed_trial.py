"""Seed a separate notebook from the six source identities verified in Igor.

Does not invent missing experimental conditions or modify the normal notebook.
"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.records import Store

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--pxp',type=Path,required=True)
    p.add_argument('--db',type=Path,default=Path('local/trial-notebook.sqlite3'))
    a=p.parse_args()
    if not a.pxp.is_file():
        p.error('PXP missing')
    store=Store(a.db)
    if store.records():
        raise SystemExit('Trial notebook already contains records; no duplicate seed performed')
    store.save_metadata({'实验名称':'FeSe 20211118 · 已有处理后 CUT 内存试跑',
                         '样品':'FeSe（依据源文件名）','日期':'2021-11-18',
                         '备注':'六条身份、theta、hv 已与当前 Igor 隔离副本核对；其他未核验条件留空。'})
    names=['A20211118121854','A20211118123854','A20211118130449',
           'A20211118133047','A20211118135051','A20211118141230']
    for i,name in enumerate(names):
        store.save({'file_name':name,'processing':'机械 mapping','scan_id':'FeSe-20211118-MM01',
                    'sequence':i+1,'theta':-3*i,'phi':0,'hv':6.994,
                    'source_path':str(a.pxp.resolve()),
                    'angle_source':'原参数表 theta，已确认角度序列；当前副本核对一致',
                    'other':'试点使用 PXP 内已有处理后 CUT；本条其他条件未补填。'})
    print('Seeded six verified trial identities; missing conditions remain blank.')
