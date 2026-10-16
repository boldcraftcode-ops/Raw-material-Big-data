"""Owner-scoped, version-bound classification reviews; no downstream publication."""
from __future__ import annotations
import hashlib
import json
from fastapi import HTTPException
from .db import dumps, now, uid
from .intake_breakdown import VERSION, CATEGORIES, ROLES
from .archive import isolated_breakdown

DATATYPES={'empty','boolean','date','number','invalid_number','date_text_iso','date_text_ambiguous',
           'period_text','percent_text','money_text','code_text','number_text','text','excel_error','mixed'}


def profile_hash(report):
    return hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def failed_breakdown():
    from .intake_breakdown import build_breakdown
    report=build_breakdown(b'','')
    report.update(status='failed',notes=['Batas proses tercapai atau breakdown aman gagal. Raw tetap tersimpan; klasifikasi tidak ditebak.'])
    return report


class BreakdownMixin:
    def breakdown(self, version_id, owner):
        with self.db.connect() as conn:
            access=self.can_read(conn,version_id,owner)
            version=conn.execute('SELECT parsed_meta FROM document_versions WHERE id=?',(version_id,)).fetchone()
            meta=json.loads(version['parsed_meta'] or '{}')
            report=meta.get('breakdown'); digest=profile_hash(report) if report else None
            review=conn.execute('SELECT * FROM intake_classification_reviews WHERE version_id=? ORDER BY revision DESC LIMIT 1',(version_id,)).fetchone()
            result_review=None
            if review:
                result_review={'revision':review['revision'],'profile_hash':review['profile_hash'],
                               'tables':json.loads(review['decision'])['tables'],'created_at':review['created_at'],
                               'stale':review['profile_hash']!=digest}
            job=conn.execute("SELECT status,error FROM jobs WHERE version_id=? AND kind IN ('extract','parse','breakdown') ORDER BY created_at DESC,rowid DESC LIMIT 1",(version_id,)).fetchone()
            return {'available':bool(report),'profile':report,'profile_hash':digest,'review':result_review,
                    'can_edit':access['owner_id']==owner and owner not in ('demo','external'),
                    'pending':bool(job and job['status'] in ('queued','running')),'job':dict(job) if job else None,
                    'categories':CATEGORIES,'roles':sorted(ROLES),'datatypes':sorted(DATATYPES),
                    'published':False}

    def request_breakdown(self,version_id,owner):
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self.can_read(conn,version_id,owner,False)
            version=conn.execute('SELECT parsed_meta FROM document_versions WHERE id=?',(version_id,)).fetchone()
            report=json.loads(version['parsed_meta'] or '{}').get('breakdown')
            if report and report.get('schema_version')==VERSION and report.get('status')!='failed':
                return {'reused':True,'queued':False}
            # Fresh intake already includes profiling. Do not race its extraction/parse.
            pending=conn.execute("SELECT id FROM jobs WHERE version_id=? AND kind IN ('extract','parse','breakdown') AND status IN ('queued','running')",(version_id,)).fetchone()
            if pending:return {'reused':True,'queued':True}
            job=conn.execute("SELECT id FROM jobs WHERE version_id=? AND kind='breakdown'",(version_id,)).fetchone()
            if job:conn.execute("UPDATE jobs SET status='queued',error=NULL,started_at=NULL,finished_at=NULL WHERE id=?",(job['id'],))
            else:conn.execute('INSERT INTO jobs(id,version_id,kind,status,created_at) VALUES(?,?,?,?,?)',(uid(),version_id,'breakdown','queued',now()))
            return {'reused':False,'queued':True}

    def _profile_intake(self,job):
        with self.db.connect() as conn:
            row=conn.execute('SELECT a.object_key,a.sha256,d.filename FROM document_versions v JOIN documents d ON d.id=v.document_id JOIN raw_assets a ON a.id=v.asset_id WHERE v.id=?',(job['version_id'],)).fetchone()
            if not row:return
        report=isolated_breakdown(self.db.object_path(row['object_key'],row['sha256']),row['filename']) or failed_breakdown()
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row=conn.execute('SELECT parsed_meta FROM document_versions WHERE id=?',(job['version_id'],)).fetchone()
            if not row:return
            meta=json.loads(row['parsed_meta'] or '{}');meta['breakdown']=report
            conn.execute('UPDATE document_versions SET parsed_meta=? WHERE id=?',(dumps(meta),job['version_id']))
            conn.execute("UPDATE jobs SET status='done',finished_at=? WHERE id=?",(now(),job['id']))

    def review_breakdown(self,version_id,owner,config):
        if config.get('confirmed') is not True:raise ValueError('Konfirmasi review metadata sebelum menyimpan.')
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            access=self.can_read(conn,version_id,owner,False)
            row=conn.execute('SELECT parsed_meta FROM document_versions WHERE id=?',(version_id,)).fetchone()
            report=json.loads(row['parsed_meta'] or '{}').get('breakdown')
            if not report or report.get('status') not in ('ready','partial'):raise ValueError('Belum ada breakdown yang dapat ditinjau.')
            digest=profile_hash(report)
            if config.get('profile_hash')!=digest:raise HTTPException(409,'Breakdown berubah. Muat ulang lalu tinjau hasil terbaru.')
            tables={table['id']:table for sheet in report['sheets'] for table in sheet['tables']}
            corrections=config.get('tables',[])
            if not corrections or len(corrections)>20:raise ValueError('Review membutuhkan 1–20 tabel terdeteksi.')
            if len({item['table_id'] for item in corrections})!=len(corrections):raise ValueError('ID tabel review berulang.')
            previous=conn.execute('SELECT * FROM intake_classification_reviews WHERE version_id=? ORDER BY revision DESC LIMIT 1',(version_id,)).fetchone()
            merged={item['table_id']:item for item in json.loads(previous['decision'])['tables']} if previous and previous['profile_hash']==digest else {}
            for item in corrections:
                table=tables.get(item['table_id'])
                if not table:raise ValueError('Tabel review tidak ditemukan pada versi ini.')
                if item['category'] not in CATEGORIES:raise ValueError('Kategori bisnis tidak dikenal.')
                columns=item.get('columns',[])
                expected={column['id'] for column in table['columns']}
                if len(columns)!=len(expected) or {column['column_id'] for column in columns}!=expected:raise ValueError('Tinjau seluruh kolom tabel; ID kolom harus sama dengan breakdown.')
                if any(column['role'] not in ROLES or column['datatype'] not in DATATYPES for column in columns):raise ValueError('Peran atau tipe data tidak dikenal.')
                merged[item['table_id']]={'table_id':item['table_id'],'category':item['category'],
                                         'columns':sorted(columns,key=lambda column:column['column_id'])}
            decision={'tables':sorted(merged.values(),key=lambda item:item['table_id'])}
            canonical=dumps(decision)
            if previous and previous['profile_hash']==digest and previous['decision']==canonical:
                return {'revision':previous['revision'],'reused':True,'published':False,'raw_changed':False}
            revision=previous['revision']+1 if previous else 1
            if revision>200:raise ValueError('Batas 200 revisi review per versi file tercapai; hubungi pengelola penyimpanan.')
            conn.execute('INSERT INTO intake_classification_reviews VALUES(?,?,?,?,?)',(version_id,revision,digest,canonical,now()))
            self.db.activity(conn,owner,'intake_classification_reviewed','Review klasifikasi intake disimpan; raw dan observasi tidak berubah.',access['document_id'],{'version_id':version_id,'review_revision':revision,'tables_reviewed':len(decision['tables'])})
            return {'revision':revision,'reused':False,'published':False,'raw_changed':False}
