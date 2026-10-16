from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import unicodedata
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from .db import Database, dumps, now, uid
from .domain import FIELDS, normalize_row, validate_mapping
from .parsers import parse_file
from .assistant_service import ExcelAssistantMixin
from .breakdown_service import BreakdownMixin, failed_breakdown
from .archive import isolated_breakdown
from .archive import ArchiveMixin, MAX_FILE, MAX_OWNER_BYTES, MAX_GLOBAL_BYTES, MAX_DOCUMENTS, safe_source_uri

MAX_UPLOAD=MAX_FILE
ACTIVE = ''' FROM observations o
 JOIN document_versions v ON v.id=o.version_id
 JOIN documents d ON d.id=v.document_id
 JOIN raw_assets a ON a.id=v.asset_id
 WHERE d.owner_id=? AND d.active_version_id=v.id AND v.active_mapping_rev=o.mapping_rev '''
SELECT_OBS = '''SELECT o.*,d.id AS document_id,d.filename,v.version_no,a.sha256,d.owner_id '''


def public_version(conn, version_id):
    item=conn.execute('''SELECT v.*,d.filename,d.active_version_id,d.owner_id,a.sha256,a.size_bytes
        FROM document_versions v JOIN documents d ON d.id=v.document_id
        JOIN raw_assets a ON a.id=v.asset_id WHERE v.id=?''',(version_id,)).fetchone()
    if not item: return None
    out=dict(item)
    out['is_demo']=out.pop('owner_id')=='demo'
    out['is_active']=out.pop('active_version_id')==version_id
    out.pop('asset_id',None)
    out['parsed_meta']=json.loads(out['parsed_meta']) if out['parsed_meta'] else None
    out['intake_meta']=json.loads(out['intake_meta'])
    out['is_external']=out['intake_meta'].get('intake_kind')=='external'
    job=conn.execute('SELECT id,status,kind,error FROM jobs WHERE version_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1',(version_id,)).fetchone()
    out['job']=dict(job) if job else None
    return out


class Service(BreakdownMixin, ExcelAssistantMixin, ArchiveMixin):
    def __init__(self, db: Database): self.db=db

    def can_read(self,conn,version_id,owner,allow_demo=True):
        row=conn.execute('''SELECT v.id,d.owner_id,d.id AS document_id,a.object_key,d.filename
            FROM document_versions v JOIN documents d ON d.id=v.document_id
            JOIN raw_assets a ON a.id=v.asset_id WHERE v.id=?''',(version_id,)).fetchone()
        if not row or (row['owner_id']!=owner and not (allow_demo and row['owner_id'] in ['demo','external'])):
            raise LookupError('Dokumen tidak ditemukan atau tidak dapat diakses.')
        return row

    def upload(self,owner,filename,data,metadata=None):
        filename=Path((filename or 'data.csv').replace('\\','/')).name
        filename=unicodedata.normalize('NFKC',filename)
        filename=re.sub(r'[\x00-\x1f\x7f]','',filename).strip()[:180]
        if Path(filename).suffix.lower() not in ['.csv','.xlsx']:
            raise ValueError('Mode pembelian hanya mendukung CSV/XLSX. Gunakan arsip umum untuk format lain.')
        if not data: raise ValueError('File kosong.')
        if len(data)>MAX_UPLOAD: raise ValueError(f'Maksimum ukuran file {MAX_UPLOAD/1024/1024:g} MB sesuai konfigurasi server.')
        metadata=metadata or {}
        if len(metadata.get('context',''))>2000: raise ValueError('Konteks maksimum 2.000 karakter.')
        if metadata.get('source_uri'): metadata['source_uri']=safe_source_uri(metadata['source_uri'])
        sha=hashlib.sha256(data).hexdigest()
        logical_key=filename.casefold()
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            kind_sql="v.intake_meta::jsonb->>'intake_kind'" if self.db.kind=='postgresql' else "json_extract(v.intake_meta,'$.intake_kind')"
            existing=conn.execute("SELECT v.id,v.document_id,a.object_key FROM raw_assets a JOIN document_versions v ON v.asset_id=a.id WHERE a.owner_id=? AND a.sha256=? AND "+kind_sql+" IS NULL LIMIT 1",(owner,sha)).fetchone()
            if existing:
                self.db.objects.put(existing['object_key'],data)
                acquisition_id=uid()
                conn.execute('INSERT INTO acquisitions VALUES(?,?,?,?,?,?)',(acquisition_id,owner,existing['id'],filename,now(),1))
                conn.execute('INSERT INTO acquisition_details VALUES(?,?)',(acquisition_id,dumps(metadata)))
                self.db.activity(conn,owner,'duplicate_detected','Unggahan identik dikenali; data tidak digandakan.',existing['document_id'])
                return {'version':public_version(conn,existing['id']),'duplicate':True}
            owner_bytes=conn.execute('SELECT COALESCE(SUM(size_bytes),0) FROM raw_assets WHERE owner_id=?',(owner,)).fetchone()[0]
            total_bytes=conn.execute('SELECT COALESCE(SUM(size_bytes),0) FROM raw_assets').fetchone()[0]
            asset=conn.execute('SELECT id FROM raw_assets WHERE owner_id=? AND sha256=?',(owner,sha)).fetchone()
            additional_bytes=0 if asset else len(data)
            if owner_bytes+additional_bytes>MAX_OWNER_BYTES or total_bytes+additional_bytes>MAX_GLOBAL_BYTES:
                raise ValueError('Kuota penyimpanan preview tercapai. Hapus arsip yang tidak diperlukan atau ekspor data sebelum melanjutkan.')
            doc=conn.execute('SELECT * FROM documents WHERE owner_id=? AND logical_key=?',(owner,logical_key)).fetchone()
            if not doc:
                count=conn.execute('SELECT COUNT(*) FROM documents WHERE owner_id=?',(owner,)).fetchone()[0]
                if count>=MAX_DOCUMENTS: raise ValueError('Batas dokumen tercapai; atur kapasitas server.')
                doc_id=uid()
                conn.execute('INSERT INTO documents(id,owner_id,filename,logical_key,created_at) VALUES(?,?,?,?,?)',(doc_id,owner,filename,logical_key,now()))
                version_no=1
            else:
                doc_id=doc['id']
                version_no=conn.execute('SELECT COALESCE(MAX(version_no),0)+1 FROM document_versions WHERE document_id=?',(doc_id,)).fetchone()[0]
            object_key=f'{owner}/{sha}'
            try:
                self.db.objects.put(object_key,data)
                asset_id=asset['id'] if asset else uid()
                if not asset:conn.execute('INSERT INTO raw_assets VALUES(?,?,?,?,?)',(asset_id,owner,sha,object_key,len(data)))
                version_id=uid()
                conn.execute('''INSERT INTO document_versions(id,document_id,asset_id,version_no,status,created_at)
                    VALUES(?,?,?,?,?,?)''',(version_id,doc_id,asset_id,version_no,'queued',now()))
                conn.execute('UPDATE document_versions SET intake_meta=? WHERE id=?',(dumps(metadata),version_id))
                conn.execute('UPDATE documents SET latest_version_id=? WHERE id=?',(version_id,doc_id))
                acquisition_id=uid()
                conn.execute('INSERT INTO acquisitions VALUES(?,?,?,?,?,?)',(acquisition_id,owner,version_id,filename,now(),0))
                conn.execute('INSERT INTO acquisition_details VALUES(?,?)',(acquisition_id,dumps(metadata)))
                conn.execute('INSERT INTO jobs(id,version_id,kind,status,created_at) VALUES(?,?,?,?,?)',(uid(),version_id,'parse','queued',now()))
                self.db.activity(conn,owner,'uploaded',f'Arsip asli diterima: {filename}',doc_id,{'version_no':version_no,'sha256':sha})
                return {'version':public_version(conn,version_id),'duplicate':False}
            except Exception:
                if not asset:self.db.objects.delete(object_key)
                raise

    def version(self,version_id,owner):
        with self.db.connect() as conn:
            self.can_read(conn,version_id,owner)
            return public_version(conn,version_id)

    def preview(self,version_id,owner,sheet=None,header_row=None,header_depth=1):
        return self.assistant_preview(version_id,owner,sheet,header_row,header_depth)

    def map_version(self,version_id,owner,config):
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self.can_read(conn,version_id,owner,False)
            v=public_version(conn,version_id)
            if not v['parsed_meta']: raise ValueError('Tunggu sampai pembacaan file selesai.')
            if v['status'] in ['queued','parsing','processing']: raise ValueError('Dokumen masih diproses. Tunggu pekerjaan sebelumnya selesai.')
            config,_=self.prepare_assistant_mapping(version_id,owner,config)
            if config.get('scope_confirmed') is not True:
                raise ValueError('Konfirmasi bahwa data berada dalam lingkup karet alam dan boleh diproses.')
            canonical=json.dumps(config,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
            hashed=hashlib.sha256(canonical.encode()).hexdigest()
            old=conn.execute('SELECT revision FROM mappings WHERE version_id=? AND config_hash=?',(version_id,hashed)).fetchone()
            if old:
                job=conn.execute('SELECT * FROM jobs WHERE version_id=? AND kind=? AND mapping_rev=?',(version_id,'normalize',old['revision'])).fetchone()
                if job and job['status']=='failed':
                    conn.execute('UPDATE jobs SET status=?,error=NULL,started_at=NULL,finished_at=NULL WHERE id=?',('queued',job['id']))
                    conn.execute('UPDATE document_versions SET status=?,error=NULL WHERE id=?',('processing',version_id))
                elif job and job['status']=='done' and (v['active_mapping_rev']!=old['revision'] or not v['is_active']):
                    # Explicit confirmation can reactivate archived results without duplicating them.
                    count=conn.execute('SELECT COUNT(*) FROM observations WHERE version_id=? AND mapping_rev=?',(version_id,old['revision'])).fetchone()[0]
                    issues=conn.execute('SELECT COUNT(*) FROM issues WHERE version_id=? AND mapping_rev=?',(version_id,old['revision'])).fetchone()[0]
                    conn.execute('UPDATE document_versions SET active_mapping_rev=?,valid_count=?,issue_count=?,status=?,error=NULL WHERE id=?',(old['revision'],count,issues,'ready_with_issues' if issues else 'ready',version_id))
                    conn.execute('UPDATE documents SET active_version_id=? WHERE id=?',(version_id,v['document_id']))
                    self.db.activity(conn,owner,'mapping_restored','Hasil pemetaan arsip diaktifkan kembali setelah konfirmasi.',v['document_id'],{'mapping_revision':old['revision']})
                return {'job_id':job['id'],'revision':old['revision'],'reused':True}
            rev=conn.execute('SELECT COALESCE(MAX(revision),0)+1 FROM mappings WHERE version_id=?',(version_id,)).fetchone()[0]
            conn.execute('INSERT INTO mappings VALUES(?,?,?,?,?)',(version_id,rev,canonical,hashed,now()))
            job_id=uid()
            conn.execute('INSERT INTO jobs(id,version_id,kind,mapping_rev,status,created_at) VALUES(?,?,?,?,?,?)',(job_id,version_id,'normalize',rev,'queued',now()))
            conn.execute('UPDATE document_versions SET status=?,error=NULL WHERE id=?',('processing',version_id))
            self.db.activity(conn,owner,'mapping_confirmed','Pemetaan kolom dikonfirmasi; validasi dijadwalkan.',v['document_id'],{'version_no':v['version_no'],'mapping_revision':rev,'sheet':config['sheet']})
            return {'job_id':job_id,'revision':rev,'reused':False}

    def process_next(self):
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row=conn.execute('SELECT * FROM jobs WHERE status=? ORDER BY created_at,rowid LIMIT 1',('queued',)).fetchone()
            if not row: return False
            job=dict(row)
            conn.execute('UPDATE jobs SET status=?,started_at=? WHERE id=?',('running',now(),job['id']))
            if job['kind']=='parse': conn.execute('UPDATE document_versions SET status=? WHERE id=?',('parsing',job['version_id']))
        try:
            if job['kind']=='parse': self._parse(job)
            elif job['kind']=='extract': self._extract(job)
            elif job['kind']=='breakdown': self._profile_intake(job)
            else: self._normalize(job)
        except Exception as exc:
            # Only a short actionable message is returned; no paths, tokens, or stack traces.
            error=str(exc)[:400] if isinstance(exc,ValueError) else 'Pemrosesan gagal. File dapat dicoba ulang setelah diperiksa.'
            with self.db.connect() as conn:
                conn.execute('UPDATE jobs SET status=?,error=?,finished_at=? WHERE id=?',('failed',error,now(),job['id']))
                if job['kind']!='breakdown':conn.execute('UPDATE document_versions SET status=?,error=? WHERE id=?',('failed',error,job['version_id']))
                d=conn.execute('SELECT d.id,d.owner_id FROM document_versions v JOIN documents d ON d.id=v.document_id WHERE v.id=?',(job['version_id'],)).fetchone()
                if d: self.db.activity(conn,d['owner_id'],'failed','Pembacaan atau validasi file gagal.',d['id'],{'reason':error})
        return True

    def _parse(self,job):
        with self.db.connect() as conn:
            item=conn.execute('''SELECT a.object_key,a.sha256,d.filename,d.owner_id,d.id AS document_id
                FROM document_versions v JOIN raw_assets a ON a.id=v.asset_id JOIN documents d ON d.id=v.document_id WHERE v.id=?''',(job['version_id'],)).fetchone()
            if not item: return
        path=self.db.object_path(item['object_key'],item['sha256'])
        meta,rows=parse_file(path,item['filename'])
        meta['breakdown']=isolated_breakdown(path,item['filename']) or failed_breakdown()
        with self.db.connect() as conn:
            conn.execute('DELETE FROM raw_rows WHERE version_id=?',(job['version_id'],))
            conn.executemany('INSERT INTO raw_rows VALUES(?,?,?,?,?)',[(job['version_id'],r['sheet'],r['row_no'],r['line_end'],dumps(r['cells'])) for r in rows])
            conn.execute('UPDATE document_versions SET status=?,parsed_meta=?,total_rows=?,error=NULL WHERE id=?',('awaiting_mapping',dumps(meta),len(rows),job['version_id']))
            conn.execute('UPDATE jobs SET status=?,finished_at=? WHERE id=?',('done',now(),job['id']))
            self.db.activity(conn,item['owner_id'],'parsed','Struktur file terbaca; menunggu pemetaan.',item['document_id'],{'rows':len(rows),'sheets':len(meta['sheets'])})

    def _normalize(self,job):
        with self.db.connect() as conn:
            mapping=conn.execute('SELECT config FROM mappings WHERE version_id=? AND revision=?',(job['version_id'],job['mapping_rev'])).fetchone()
            config=json.loads(mapping['config'])
            rows=conn.execute('SELECT * FROM raw_rows WHERE version_id=? AND sheet=? ORDER BY row_no',(job['version_id'],config['sheet'])).fetchall()
            item=conn.execute('SELECT d.id,d.owner_id,d.filename,a.object_key,a.sha256 FROM document_versions v JOIN documents d ON d.id=v.document_id JOIN raw_assets a ON a.id=v.asset_id WHERE v.id=?',(job['version_id'],)).fetchone()
        if config.get('header_row'):
            _, parsed_rows=parse_file(self.db.object_path(item['object_key'],item['sha256']),item['filename'],{config['sheet']:(config['header_row'],config.get('header_depth',1))})
            rows=[{**row,'cells':dumps(row['cells'])} for row in parsed_rows if row['sheet']==config['sheet']]
        valid=[]
        bad=[]
        for r in rows:
            cells=json.loads(r['cells'])
            normalized,errors=normalize_row(cells,config)
            record_id=uuid5(NAMESPACE_URL,f"rubber:{job['version_id']}:{job['mapping_rev']}:{config['sheet']}:{r['row_no']}").hex
            if errors:
                bad.append((record_id,job['version_id'],job['mapping_rev'],config['sheet'],r['row_no'],dumps(errors),r['cells']))
            else:
                n=normalized
                valid.append((record_id,job['version_id'],job['mapping_rev'],config['sheet'],r['row_no'],n['observed_date'],n['supplier'],n['supplier_identifier'],n['location'],n['material'],n['grade'],n['price'],n['currency'],n['unit'],n['weight_basis'],n['drc_percent'],n['quantity_kg'],n['price_kind'],n['price_per_kg'],n['dry_equivalent'],dumps(n['transform_notes']),r['cells']))
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('DELETE FROM observations WHERE version_id=? AND mapping_rev=?',(job['version_id'],job['mapping_rev']))
            conn.execute('DELETE FROM issues WHERE version_id=? AND mapping_rev=?',(job['version_id'],job['mapping_rev']))
            conn.executemany('INSERT INTO observations VALUES('+','.join('?' for _ in range(22))+')',valid)
            conn.executemany('INSERT INTO issues VALUES(?,?,?,?,?,?,?)',bad)
            status='ready_with_issues' if bad else 'ready'
            conn.execute('''UPDATE document_versions SET status=?,active_mapping_rev=?,valid_count=?,issue_count=?,error=NULL WHERE id=?''',(status,job['mapping_rev'],len(valid),len(bad),job['version_id']))
            conn.execute('UPDATE documents SET active_version_id=? WHERE id=?',(job['version_id'],item['id']))
            conn.execute('UPDATE jobs SET status=?,finished_at=? WHERE id=?',('done',now(),job['id']))
            self.db.activity(conn,item['owner_id'],'normalized',f'{len(valid)} observasi dipublikasikan, {len(bad)} baris ditahan untuk review.',item['id'],{'valid':len(valid),'issues':len(bad),'mapping_revision':job['mapping_rev']})

    def recover(self):
        with self.db.connect() as conn:
            conn.execute("UPDATE jobs SET status='queued',started_at=NULL WHERE status='running'")
        # Reconcile unreferenced raw files left by a crash between file and DB commit.
        with self.db.connect() as conn:
            known={r['object_key'] for r in conn.execute('SELECT object_key FROM raw_assets')}
        for path in self.db.raw.glob('*/*'):
            if path.is_file() and str(path.relative_to(self.db.raw)) not in known: path.unlink(missing_ok=True)

    def list_documents(self,owner,limit=100,offset=0):
        with self.db.connect() as conn:
            docs=conn.execute('SELECT * FROM documents WHERE owner_id=? ORDER BY created_at DESC,rowid DESC LIMIT ? OFFSET ?',(owner,limit,offset)).fetchall()
            result=[]
            for d in docs:
                latest=public_version(conn,d['latest_version_id'])
                versions=[public_version(conn,v['id']) for v in conn.execute('SELECT id FROM document_versions WHERE document_id=? ORDER BY version_no DESC LIMIT 20',(d['id'],))]
                result.append({'id':d['id'],'filename':d['filename'],'created_at':d['created_at'],'latest':latest,'versions':versions,'active_version_id':d['active_version_id'],'active_version':public_version(conn,d['active_version_id']) if d['active_version_id'] else None,'version_count':conn.execute('SELECT COUNT(*) FROM document_versions WHERE document_id=?',(d['id'],)).fetchone()[0],'is_demo':owner=='demo'})
            return result

    def document_versions(self,document_id,owner,limit=20,offset=0):
        with self.db.connect() as conn:
            doc=conn.execute('SELECT owner_id FROM documents WHERE id=?',(document_id,)).fetchone()
            if not doc or doc['owner_id'] not in (owner,'demo','external'): raise LookupError('Dokumen tidak dapat diakses.')
            count=conn.execute('SELECT COUNT(*) FROM document_versions WHERE document_id=?',(document_id,)).fetchone()[0]
            rows=conn.execute('SELECT id FROM document_versions WHERE document_id=? ORDER BY version_no DESC LIMIT ? OFFSET ?',(document_id,limit,offset)).fetchall()
            return {'items':[public_version(conn,r['id']) for r in rows],'total':count,'limit':limit,'offset':offset}

    def observations(self,owner,q='',limit=20,offset=0):
        where=ACTIVE
        args=[owner]
        if q:
            escaped=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
            where+=" AND (o.supplier LIKE ? ESCAPE '\\' OR o.material LIKE ? ESCAPE '\\' OR o.location LIKE ? ESCAPE '\\' OR o.grade LIKE ? ESCAPE '\\' OR d.filename LIKE ? ESCAPE '\\')"
            args += [f'%{escaped}%']*5
        with self.db.connect() as conn:
            total=conn.execute('SELECT COUNT(*)'+where,args).fetchone()[0]
            rows=conn.execute(SELECT_OBS+where+' ORDER BY o.observed_date DESC,o.row_no DESC LIMIT ? OFFSET ?',args+[limit,offset]).fetchall()
            items=[]
            for r in rows:
                item=dict(r)
                item['is_demo']=item.pop('owner_id')=='demo'
                item['transform_notes']=json.loads(item['transform_notes'])
                item.pop('raw_cells',None)
                items.append(item)
            return {'items':items,'total':total,'offset':offset,'limit':limit}

    def evidence(self,observation_id,owner):
        with self.db.connect() as conn:
            item=conn.execute('''SELECT o.*,d.id AS document_id,d.filename,d.owner_id,d.active_version_id,
                v.version_no,v.parsed_meta,v.active_mapping_rev,a.sha256,a.size_bytes
                FROM observations o JOIN document_versions v ON v.id=o.version_id
                JOIN documents d ON d.id=v.document_id JOIN raw_assets a ON a.id=v.asset_id WHERE o.id=?''',(observation_id,)).fetchone()
            if not item or item['owner_id'] not in [owner,'demo']: raise LookupError('Bukti tidak ditemukan atau tidak dapat diakses.')
            out=dict(item)
            meta=json.loads(out.pop('parsed_meta'))
            sheet=next(s for s in meta['sheets'] if s['name']==out['sheet'])
            saved=conn.execute('SELECT config FROM mappings WHERE version_id=? AND revision=?',(out['version_id'],out['mapping_rev'])).fetchone()
            mapped=json.loads(saved['config']) if saved else {}
            columns=mapped.get('column_snapshot') or sheet['columns']
            cells=json.loads(out.pop('raw_cells'))
            out['raw_values']=[{'label':c['label'],'value':cells.get(c['key'])} for c in columns]
            out['header_row']=mapped.get('header_row',sheet.get('header_row',1))
            out['header_depth']=mapped.get('header_depth',sheet.get('header_depth',1))
            out['is_demo']=out.pop('owner_id')=='demo'
            out['is_active']=out.pop('active_version_id')==out['version_id'] and out.pop('active_mapping_rev')==out['mapping_rev']
            out['transform_notes']=json.loads(out['transform_notes'])
            return out

    def issues(self,owner,limit=100):
        with self.db.connect() as conn:
            rows=conn.execute('''SELECT i.*,d.filename,v.version_no FROM issues i
                JOIN document_versions v ON v.id=i.version_id JOIN documents d ON d.id=v.document_id
                WHERE d.owner_id=? AND d.active_version_id=v.id AND v.active_mapping_rev=i.mapping_rev
                ORDER BY d.created_at DESC,i.row_no LIMIT ?''',(owner,limit)).fetchall()
            return [{**dict(r),'errors':json.loads(r['errors']),'raw_cells':json.loads(r['raw_cells']),'is_demo':owner=='demo'} for r in rows]

    def activity(self,owner):
        with self.db.connect() as conn:
            rows=conn.execute('SELECT * FROM activity WHERE owner_id=? ORDER BY created_at DESC,rowid DESC LIMIT 80',(owner,)).fetchall()
            return [{k:(json.loads(r[k]) if k=='details' else r[k]) for k in r.keys() if k!='owner_id'} for r in rows]

    def graph(self,owner):
        with self.db.connect() as conn:
            rows=conn.execute('''SELECT o.id,o.supplier,o.supplier_identifier,o.location,o.material,o.grade,
                o.version_id,d.id AS document_id,d.filename '''+ACTIVE+' ORDER BY o.observed_date DESC,o.row_no DESC',(owner,)).fetchall()
        nodes={}
        edges={}
        def nid(kind,key): return kind+'_'+hashlib.sha256(key.encode()).hexdigest()[:20]
        def node(id,label,kind,detail,evidence=None):
            if id not in nodes: nodes[id]={'id':id,'label':label,'type':kind,'detail':detail,'count':0,'evidence_ids':[]}
            if evidence:
                nodes[id]['count']+=1
                if len(nodes[id]['evidence_ids'])<8 and evidence not in nodes[id]['evidence_ids']: nodes[id]['evidence_ids'].append(evidence)
            return id
        def edge(source,target,kind,label,evidence=None):
            key=(source,target,kind)
            if key not in edges: edges[key]={'id':nid('edge','|'.join(key)),'source':source,'target':target,'kind':kind,'label':label,'count':0,'evidence_ids':[]}
            if evidence:
                edges[key]['count']+=1
                if len(edges[key]['evidence_ids'])<5 and evidence not in edges[key]['evidence_ids']: edges[key]['evidence_ids'].append(evidence)
        if rows: node('workspace','Karet alam','workspace','Lingkup workspace yang dinyatakan pengguna; bukan inferensi klasifikasi atau bukti asal-usul.')
        for r in rows:
            ev=r['id']
            doc=node(nid('document',r['document_id']),r['filename'],'document','Arsip sumber; setiap observasi menunjuk ke versi dan baris asli.',ev)
            material_label=r['material']+(f" · {r['grade']}" if r['grade'] else '')
            material=node(nid('material',material_label.casefold()),material_label,'material','Bentuk / grade seperti dilaporkan dalam sumber. Harga tetap dibedakan menurut basis, unit dan jenisnya.',ev)
            if r['supplier_identifier']:
                key='identifier:'+r['supplier_identifier']
                detail='Identitas berdasarkan ID internal yang dinyatakan sumber: '+r['supplier_identifier']+'. Belum diverifikasi terhadap registri eksternal.'
            else:
                key='document:'+r['document_id']+':'+r['supplier'].casefold()+':'+(r['location'] or '').casefold()
                detail='Identitas sementara dalam dokumen. Nama mirip di dokumen berbeda tidak otomatis digabungkan.'
            supplier=node(nid('organization',key),r['supplier'],'organization',detail,ev)
            edge(doc,'workspace','archived_in','Diarsipkan dalam workspace')
            edge(material,'workspace','workspace_scope','Termasuk lingkup yang dinyatakan')
            edge(doc,material,'records_price','Mencatat harga material',ev)
            edge(supplier,material,'reports_price','Harga dilaporkan untuk',ev)
            edge(supplier,doc,'appears_in','Tercantum dalam dokumen',ev)
            if r['location']:
                loc=node(nid('location',r['document_id']+':'+r['location'].casefold()),r['location'],'location','Lokasi teks yang dilaporkan pemasok; bukan hasil geocoding dan bukan bukti lokasi seluruh kebun asal.',ev)
                edge(supplier,loc,'reported_location','Lokasi pemasok yang dilaporkan',ev)
        all_nodes=list(nodes.values())
        total_nodes=len(all_nodes)
        total_edges=len(edges)
        ranking={'workspace':0,'material':1,'document':2,'organization':3,'location':4}
        selected=sorted(all_nodes,key=lambda n:(ranking[n['type']],-n['count'],n['label']))[:160]
        visible={n['id'] for n in selected}
        links=[e for e in edges.values() if e['source'] in visible and e['target'] in visible][:400]
        return {'nodes':selected,'edges':links,'total_nodes':total_nodes,'total_edges':total_edges,
                'entity_count':sum(n['type'] in ['organization','material','location'] for n in all_nodes),
                'truncated':total_nodes>len(selected) or total_edges>len(links),'is_demo':owner=='demo'}

    def stats(self,owner):
        with self.db.connect() as conn:
            rows=conn.execute('SELECT COUNT(*),MIN(o.observed_date),MAX(o.observed_date)'+ACTIVE,(owner,)).fetchone()
            docs=conn.execute('SELECT COUNT(*) FROM documents WHERE owner_id=?',(owner,)).fetchone()[0]
            issue_count=conn.execute('''SELECT COUNT(*) FROM issues i JOIN document_versions v ON v.id=i.version_id
                JOIN documents d ON d.id=v.document_id WHERE d.owner_id=? AND d.active_version_id=v.id AND v.active_mapping_rev=i.mapping_rev''',(owner,)).fetchone()[0]
            pending=conn.execute("SELECT COUNT(*) FROM jobs j JOIN document_versions v ON v.id=j.version_id JOIN documents d ON d.id=v.document_id WHERE d.owner_id=? AND j.status IN ('queued','running')",(owner,)).fetchone()[0]
        graph=self.graph(owner)
        return {'observations':rows[0],'first_date':rows[1],'last_date':rows[2],'documents':docs,'issues':issue_count,'entities':graph['entity_count'],'pending_jobs':pending,'external_sources_active':0,'is_demo':owner=='demo'}

    def delete_document(self,document_id,owner):
        paths=[]
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            doc=conn.execute('SELECT * FROM documents WHERE id=? AND owner_id=?',(document_id,owner)).fetchone()
            if not doc or owner in ['demo','external']: raise LookupError('Dokumen tidak ditemukan atau tidak dapat dihapus.')
            linked=conn.execute('SELECT 1 FROM source_fetches f JOIN document_versions v ON v.id=f.version_id WHERE v.document_id=? LIMIT 1',(document_id,)).fetchone()
            if linked: raise ValueError('Arsip ini dikelola kolektor. Hapus sumber privat beserta riwayatnya melalui halaman Sumber eksternal.')
            running=conn.execute("SELECT COUNT(*) FROM jobs j JOIN document_versions v ON v.id=j.version_id WHERE v.document_id=? AND j.status='running'",(document_id,)).fetchone()[0]
            if running: raise ValueError('Tunggu pekerjaan yang sedang berjalan sebelum menghapus dokumen.')
            assets=conn.execute('SELECT DISTINCT a.* FROM raw_assets a JOIN document_versions v ON v.asset_id=a.id WHERE v.document_id=?',(document_id,)).fetchall()
            conn.execute('UPDATE documents SET active_version_id=NULL,latest_version_id=NULL WHERE id=?',(document_id,))
            conn.execute('DELETE FROM activity WHERE document_id=?',(document_id,))
            conn.execute('DELETE FROM documents WHERE id=?',(document_id,))
            for asset in assets:
                if not conn.execute('SELECT 1 FROM document_versions WHERE asset_id=?',(asset['id'],)).fetchone():
                    conn.execute('DELETE FROM raw_assets WHERE id=?',(asset['id'],))
                    paths.append(asset['object_key'])
            self.db.activity(conn,owner,'document_deleted','Dokumen dan turunannya dihapus dari penyimpanan lokal.')
        for key in paths: self.db.objects.delete(key)

    def seed_demo(self):
        with self.db.connect() as conn:
            if conn.execute("SELECT 1 FROM documents WHERE owner_id='demo'").fetchone(): return
        output=io.StringIO()
        writer=csv.writer(output)
        writer.writerow(['tanggal','pemasok','id_pemasok','lokasi_pemasok','material','grade','harga','mata_uang','unit','basis_berat','kkk_persen','jenis_harga','kuantitas_kg'])
        suppliers=[('Koperasi Contoh Sejahtera','DEMO-001','Langkat'),('Unit Contoh Nusantara','DEMO-002','Deli Serdang'),('Pengolah Contoh Lestari','DEMO-003','Asahan'),('Koperasi Contoh Mandiri','DEMO-004','Labuhanbatu'),('Unit Contoh Hijau','DEMO-005','Simalungun'),('Pengolah Contoh Bersama','DEMO-006','Mandailing Natal')]
        materials=[('Bokar','', 'basah',60),('Lateks pekat','', 'produk',60),('Crumb rubber','SIR 20','produk',''),('Sheet','RSS 3','produk','')]
        for i in range(36):
            name,supplier_id,loc=suppliers[i%6]
            mat,grade,basis,drc=materials[i%4]
            writer.writerow([f'2026-10-{1+i%14:02d}',name,supplier_id,loc,mat,grade,14000+(i%4)*3100+(i//6)*125,'IDR','kg',basis,drc,'transaksi_internal',1000+i*20])
        writer.writerow(['2026-10-14','Pemasok Contoh Review','DEMO-007','Langkat','Bokar','',14000,'IDR','kg','basah',120,'dilaporkan',1000])
        writer.writerow(['2026-10-14','Pemasok Contoh Review','DEMO-007','Langkat','Bokar','','belum tersedia','IDR','kg','basah',60,'dilaporkan',1000])
        result=self.upload('demo','SIMULASI_pembelian_karet.csv',output.getvalue().encode())
        vid=result['version']['id']
        with self.db.connect() as conn:
            parse_job=dict(conn.execute("SELECT * FROM jobs WHERE version_id=? AND kind='parse'",(vid,)).fetchone())
        self._parse(parse_job)
        preview=self.preview(vid,'demo')
        # Internal seed only: the HTTP mutation endpoints never allow writes to demo.
        config={'sheet':preview['sheet'],'fields':preview['suggested_mapping'],'options':{'number_format':'id-ID','date_format':'iso','drc_scale':'percent','default_price_kind':'dilaporkan'},'scope_confirmed':True}
        with self.db.connect() as conn:
            configstr=json.dumps(config,sort_keys=True,ensure_ascii=False,separators=(',',':'))
            conn.execute('INSERT INTO mappings VALUES(?,?,?,?,?)',(vid,1,configstr,hashlib.sha256(configstr.encode()).hexdigest(),now()))
            seed_job_id=uid()
            conn.execute('INSERT INTO jobs(id,version_id,kind,mapping_rev,status,created_at) VALUES(?,?,?,?,?,?)',(seed_job_id,vid,'normalize',1,'queued',now()))
        self._normalize({'id':seed_job_id,'version_id':vid,'mapping_rev':1})
