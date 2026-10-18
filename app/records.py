"""Notebook storage: normal records never depend on mapping readiness."""
import io
import json
import math
import sqlite3
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

# Original template headers remain separate from explicitly mapped Igor angles.
FIELDS = [
    ('file_name','File name','text'),('run_mode','Run Mode','text'),
    ('change','change','text'),('ep','Ep (eV)','number'),('slit','slit','text'),
    ('x','X','number'),('y','Y','number'),('z','Z','number'),
    ('polar','Polar (deg)','number'),('tilt','Tilt (deg)','number'),
    ('azimuth','Azimuth (deg)','number'),('directions','Directions','text'),
    ('hv','hv (eV)','number'),('polarization','polarization','text'),
    ('temperature','Temperature (K)','number'),('vacuum','vacuum','text'),
    ('energy_range','energy range','text'),('energy_center','energy center (eV)','number'),
    ('time','time','text'),('step_notes','STEP specific parameter / original notes','text'),
    ('counts','counts','number'),('other','other','text'),
    ('energy_step','Energy step (eV)','number'),('motor_step','Motor step (deg)','number'),
    ('frames','frames','number'),('repeats','repeats','number'),
    ('scan_id','Scan ID','text'),('processing','Processing type','text'),
    ('sequence','Acquisition sequence','number'),('theta','Igor theta (deg)','number'),
    ('phi','Igor phi (deg)','number'),('omega','Igor omega (deg)','number'),
    ('source_path','Source file path','text'),('angle_source','Angle source / convention','text'),
]
MODES = ['仅记录','单 CUT','机械 mapping','变温','其他']
SESSION_FIELDS = ['实验名称','样品','日期','实验装置','激光功率与形状','光斑大小',
                  '解理时间','解理温度与真空','液氦余量','位置单位','真空单位','备注']


def now():
    return datetime.now(timezone.utc).isoformat()


def normalize(record):
    clean = {}
    for key, label, kind in FIELDS:
        value = record.get(key)
        if value is None or value == '':
            clean[key] = None if kind == 'number' else ''
        elif kind == 'number':
            try:
                number = float(value)
            except (ValueError, TypeError):
                raise ValueError(label + ' 必须是数字') from None
            if not math.isfinite(number):
                raise ValueError(label + ' 必须是有限数值')
            clean[key] = number
        else:
            clean[key] = str(value).strip()
            if len(clean[key]) > 8000 or any(ord(c)<32 and c not in '\n\r\t' for c in clean[key]):
                raise ValueError(label + ' 包含不支持的字符或过长')
    if not clean['file_name']:
        raise ValueError('请填写文件名或记录名称；未采集的条件记录也可命名保存')
    clean['processing'] = clean['processing'] or '仅记录'
    return clean


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                    data TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, data TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def records(self):
        with self.connect() as db:
            return [dict(json.loads(data), id=rid, revision=rev, created=created, updated=updated)
                    for rid,rev,data,created,updated in db.execute('SELECT * FROM records ORDER BY created,id')]

    def save(self, record):
        data = normalize(record)
        rid = record.get('id') or uuid.uuid4().hex
        stamp = now()
        with self.connect() as db:
            if record.get('id'):
                cursor = db.execute('UPDATE records SET revision=revision+1,data=?,updated=? WHERE id=? AND revision=?',
                                    (json.dumps(data,ensure_ascii=False),stamp,rid,record.get('revision')))
                if cursor.rowcount != 1:
                    raise ValueError('记录已被其他窗口修改，请刷新后重新编辑')
            else:
                db.execute('INSERT INTO records VALUES(?,?,?,?,?)',
                           (rid,1,json.dumps(data,ensure_ascii=False),stamp,stamp))
        return rid

    def metadata(self):
        with self.connect() as db:
            row = db.execute("SELECT data FROM meta WHERE key='session'").fetchone()
        return json.loads(row[0]) if row else {}

    def save_metadata(self, data):
        clean = {key:str(data.get(key,'')).strip() for key in SESSION_FIELDS}
        if any(len(v)>8000 for v in clean.values()):
            raise ValueError('实验条件文本过长')
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO meta VALUES('session',?)",(json.dumps(clean,ensure_ascii=False),))

    def jobs(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT data FROM jobs ORDER BY rowid DESC')]

    def save_job(self, job):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?)',(job['id'],json.dumps(job,ensure_ascii=False)))


def column_name(number):
    name = ''
    while number:
        number, remainder = divmod(number-1,26)
        name = chr(65+remainder)+name
    return name


def export_xlsx(records, metadata):
    """Runtime export with stdlib OOXML; numbers are typed, text never becomes formulas.

    Does not open, edit, or rely on Excel. Empty values remain empty rather than zero.
    """
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    output = io.BytesIO()
    def xml(node):
        return tostring(node, encoding='utf-8',xml_declaration=True)
    def sheet(rows):
        root = Element('worksheet',xmlns=ns)
        views = SubElement(root,'sheetViews')
        view = SubElement(views,'sheetView',workbookViewId='0')
        SubElement(view,'pane',ySplit='1',topLeftCell='A2',activePane='bottomLeft',state='frozen')
        columns = SubElement(root,'cols')
        SubElement(columns,'col',min='1',max=str(len(rows[0])),width='20',customWidth='1')
        data = SubElement(root,'sheetData')
        for rindex,values in enumerate(rows,1):
            row = SubElement(data,'row',r=str(rindex))
            for cindex,value in enumerate(values,1):
                if value is None or value=='':
                    continue
                cell = SubElement(row,'c',r=column_name(cindex)+str(rindex),s='1' if rindex==1 else '0')
                if isinstance(value,(int,float)) and not isinstance(value,bool):
                    SubElement(cell,'v').text=str(value)
                else:
                    cell.set('t','inlineStr')
                    text=SubElement(SubElement(cell,'is'),'t')
                    text.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
                    text.text=str(value)
        if len(rows)>1:
            SubElement(root,'autoFilter',ref='A1:'+column_name(len(rows[0]))+str(len(rows)))
        return xml(root)
    keys = [key for key,_,_ in FIELDS]+['id','created','updated']
    tables = [
        [[label for _,label,_ in FIELDS]+['Record ID','Created UTC','Updated UTC']]+
        [[r.get(key) for key in keys] for r in records],
        [['实验条件','记录值']]+[[key,metadata.get(key,'')] for key in SESSION_FIELDS],
    ]
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>''')
        z.writestr('_rels/.rels','''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>''')
        z.writestr('xl/workbook.xml','''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="实验记录" sheetId="1" r:id="rId1"/><sheet name="实验条件" sheetId="2" r:id="rId2"/></sheets></workbook>''')
        z.writestr('xl/_rels/workbook.xml.rels','''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>''')
        z.writestr('xl/styles.xml','''<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Microsoft YaHei"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Microsoft YaHei"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF23374D"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>''')
        for i,rows in enumerate(tables,1):
            z.writestr(f'xl/worksheets/sheet{i}.xml',sheet(rows))
    return output.getvalue()
