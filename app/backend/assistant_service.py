"""Owner-scoped spreadsheet advice and explicitly approved mapping memory."""
from __future__ import annotations
import json
from .db import dumps, now, uid
from .domain import label_key, normalize_row, validate_mapping
from .excel_assistant import sample_advice, template_signature
from .parsers import parse_file

OPTION_KEYS={'number_format','date_format','drc_scale','default_currency','default_unit','default_basis','default_price_kind'}


class ExcelAssistantMixin:
    def assistant_preview(self, version_id, owner, sheet=None, header_row=None, header_depth=1, row_limit=8):
        version=self.version(version_id,owner)
        meta=version['parsed_meta'] or {}
        sheets=meta.get('sheets',[])
        if not sheets:
            return {'version':version,'sheets':[],'columns':[],'rows':[],'mapping':None,'warnings':meta.get('warnings',[])}
        selected=next((item for item in sheets if item['name']==sheet),None) if sheet else max(sheets,key=lambda item:(item.get('header_score',0),bool(item['row_count'])))
        if not selected: raise ValueError('Lembar tidak ditemukan.')
        with self.db.connect() as conn:
            previous=conn.execute('SELECT config FROM mappings WHERE version_id=? ORDER BY revision DESC LIMIT 1',(version_id,)).fetchone()
            config=json.loads(previous['config']) if previous else None
            if config and config['sheet']!=selected['name']: config=None
            if header_row is None and config and config.get('header_row'):
                header_row=config['header_row'];header_depth=config.get('header_depth',1)
            if header_row is not None:
                access=self.can_read(conn,version_id,owner)
                asset=conn.execute('SELECT a.sha256 FROM raw_assets a JOIN document_versions v ON v.asset_id=a.id WHERE v.id=?',(version_id,)).fetchone()
                source=self.db.object_path(access['object_key'],asset['sha256'])
            else:
                stored=conn.execute('SELECT row_no,line_end,cells FROM raw_rows WHERE version_id=? AND sheet=? ORDER BY row_no LIMIT 50',(version_id,selected['name'])).fetchall()
                samples=[{'row_no':item['row_no'],'line_end':item['line_end'],'cells':json.loads(item['cells'])} for item in stored]
        warnings=meta.get('warnings',[])
        if header_row is not None:
            fresh, rows=parse_file(source,version['filename'],{selected['name']:(header_row,header_depth)})
            selected=next(item for item in fresh['sheets'] if item['name']==selected['name'])
            samples=[{key:row[key] for key in ('row_no','line_end','cells')} for row in rows if row['sheet']==selected['name']][:50]
            warnings=fresh['warnings']
            if config and (config.get('header_row',1)!=header_row or config.get('header_depth',1)!=header_depth): config=None
        advice=sample_advice(selected['columns'],samples)
        advice.update({'header_row':selected.get('header_row',1),'header_depth':selected.get('header_depth',1),
                       'header_candidates':selected.get('header_candidates',[]),'recalled_profile':None})
        signature=template_signature(selected['columns'])
        if signature and owner not in ('demo','external'):
            with self.db.connect() as conn:
                profile=conn.execute('SELECT id,field_labels,options,updated_at FROM excel_templates WHERE owner_id=? AND signature=?',(owner,signature)).fetchone()
            if profile:
                keys={label_key(column['label']):column['key'] for column in selected['columns']}
                fields={field:keys[label] for field,label in json.loads(profile['field_labels']).items() if label in keys}
                advice['recalled_profile']={'id':profile['id'],'fields':fields,'options':json.loads(profile['options']),'updated_at':profile['updated_at']}
        if config:
            config={key:value for key,value in config.items() if key!='column_snapshot'}
        return {'version':version,'sheets':sheets,'sheet':selected['name'],'columns':selected['columns'],
                'row_count':selected['row_count'],'rows':samples[:row_limit],
                'suggested_mapping':advice['suggested_mapping'],'mapping':config,'warnings':warnings,'assistant':advice}

    def prepare_assistant_mapping(self,version_id,owner,config,row_limit=8):
        config={key:value for key,value in config.items() if value is not None and key!='column_snapshot'}
        header=config.get('header_row')
        if header is not None and (isinstance(header,bool) or not isinstance(header,int) or not 1<=header<=50): raise ValueError('Baris header harus 1–50.')
        if config.get('header_depth',1) not in (1,2): raise ValueError('Gunakan satu atau dua baris header.')
        preview=self.assistant_preview(version_id,owner,config.get('sheet'),header,config.get('header_depth',1),row_limit=row_limit)
        if not preview.get('assistant'): raise ValueError('Struktur tabel belum tersedia untuk pemetaan.')
        if not preview['row_count']: raise ValueError('Lembar yang dipilih tidak memiliki baris data.')
        validate_mapping(config,preview['columns'])
        config.update({'header_row':preview['assistant']['header_row'],'header_depth':preview['assistant']['header_depth'],
                       'column_snapshot':preview['columns']})
        return config,preview

    def check_assistant_mapping(self,version_id,owner,config):
        config,preview=self.prepare_assistant_mapping(version_id,owner,config,row_limit=50)
        failures=[];valid=0
        for row in preview['rows']:
            _, errors=normalize_row(row['cells'],config)
            if errors: failures.append({'row_no':row['row_no'],'line_end':row['line_end'],'errors':errors})
            else: valid+=1
        return {'mode':'local_rules','external_ai_used':False,'sampled_rows':len(preview['rows']),
                'total_rows':preview['row_count'],'valid_rows':valid,'invalid_rows':len(failures),
                'issues':failures[:12],'full_validation':False,'published':False,
                'note':'Pemeriksaan sampel saja; tidak menerbitkan atau mengubah data. Semua baris tetap divalidasi setelah konfirmasi.'}

    def remember_excel_template(self,version_id,owner,revision):
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self.can_read(conn,version_id,owner,False)
            version=conn.execute('SELECT status,active_mapping_rev,valid_count FROM document_versions WHERE id=?',(version_id,)).fetchone()
            if version['status'] not in ('ready','ready_with_issues') or version['active_mapping_rev']!=revision or version['valid_count']<1:
                raise ValueError('Pola hanya dapat diingat setelah pemetaan terkonfirmasi selesai dan memiliki baris valid.')
            item=conn.execute('SELECT config FROM mappings WHERE version_id=? AND revision=?',(version_id,revision)).fetchone()
            config=json.loads(item['config'])
            if config.get('scope_confirmed') is not True: raise ValueError('Pemetaan belum disetujui.')
            columns=config.get('column_snapshot')
            if not columns:
                meta=json.loads(conn.execute('SELECT parsed_meta FROM document_versions WHERE id=?',(version_id,)).fetchone()['parsed_meta'])
                columns=next(sheet['columns'] for sheet in meta['sheets'] if sheet['name']==config['sheet'])
            signature=template_signature(columns)
            if not signature or any(len(column['label'])>160 for column in columns):
                raise ValueError('Header kosong/duplikat/terlalu panjang: pola tidak disimpan untuk menghindari pencocokan keliru.')
            by_key={column['key']:label_key(column['label']) for column in columns}
            labels={field:by_key[key] for field,key in config['fields'].items() if key}
            options={key:value for key,value in config.get('options',{}).items() if key in OPTION_KEYS and isinstance(value,str) and len(value)<=50}
            old=conn.execute('SELECT id FROM excel_templates WHERE owner_id=? AND signature=?',(owner,signature)).fetchone()
            if old:
                template_id=old['id']
                conn.execute('UPDATE excel_templates SET field_labels=?,options=?,source_version_id=?,source_revision=?,updated_at=? WHERE id=?',
                             (dumps(labels),dumps(options),version_id,revision,now(),template_id))
            else:
                if conn.execute('SELECT COUNT(*) FROM excel_templates WHERE owner_id=?',(owner,)).fetchone()[0]>=50:
                    raise ValueError('Batas 50 pola/workspace tercapai. Lupakan pola lama terlebih dahulu.')
                template_id=uid()
                conn.execute('INSERT INTO excel_templates VALUES(?,?,?,?,?,?,?,?,?)',
                             (template_id,owner,signature,dumps(labels),dumps(options),version_id,revision,now(),now()))
            self.db.activity(conn,owner,'excel_pattern_approved','Pola header/pemetaan diingat setelah persetujuan; tidak melatih model AI.',details={'template_id':template_id,'field_count':len(labels)})
            return {'id':template_id,'field_count':len(labels),'mode':'local_rules','external_ai_used':False}

    def forget_excel_template(self,template_id,owner):
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            item=conn.execute('SELECT id FROM excel_templates WHERE id=? AND owner_id=?',(template_id,owner)).fetchone()
            if not item or owner in ('demo','external'): raise LookupError('Pola tidak ditemukan atau tidak dapat diakses.')
            conn.execute('DELETE FROM excel_templates WHERE id=? AND owner_id=?',(template_id,owner))
            self.db.activity(conn,owner,'excel_pattern_forgotten','Pola pemetaan dilupakan; arsip dan observasi tidak diubah.')
        return {'deleted':True}
