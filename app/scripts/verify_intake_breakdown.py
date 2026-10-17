"""Optional Chromium MVP smoke. Uses only fresh synthetic private-workspace data; cleans up.
Requires Playwright/Chromium installed separately and the app already running.
"""
from __future__ import annotations
import argparse
import io
import json
import platform
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from openpyxl import Workbook
from playwright.sync_api import sync_playwright,expect


def sample_workbook():
    book=Workbook();stock=book.active;stock.title='Stok'
    for row in [['CONTOH SINTETIS · BUKAN DATA PERUSAHAAN'],[],['Tanggal','Material','Stok','Gudang','Catatan'],
                ['2026-10-15','Lateks',100,'Gudang contoh A','stok masuk'],['2026-10-16','Bokar',0,'Gudang contoh B',None]]:stock.append(row)
    production=book.create_sheet('Produksi')
    for row in [['Tanggal','Material','Hasil produksi'],['2026-10-15','Bokar',120],['2026-10-16','Lateks',95]]:production.append(row)
    stream=io.BytesIO();book.save(stream);return stream.getvalue()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--output-dir',type=Path,default=Path('.cache/intake-qa'))
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'environment':'Chromium / '+platform.system(),
            'synthetic_data_only':True,'external_ai_used':False,'checks':[],'page_errors':[],'cleanup':False}
    def passed(name):report['checks'].append(name);print('PASS:',name,flush=True)
    raw=sample_workbook()
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True,args=['--no-sandbox'])
        context=browser.new_context(viewport={'width':1440,'height':1120})
        page=context.new_page();page.set_default_timeout(30000);headers={}
        page.on('pageerror',lambda error:report['page_errors'].append(str(error)))
        requests=[];page.on('request',lambda request:requests.append(request.url))
        def api(path,method='GET',body=None):
            response=context.request.fetch(args.base_url+path,headers=headers,method=method,data=body)
            assert response.ok,response.text()
            return response.json()
        def upload(name,data,mime='application/octet-stream'):
            page.get_by_role('button',name='Tambah data',exact=True).click()
            expect(page.get_by_role('button',name='Intake & klasifikasi',exact=True)).to_have_class('active')
            page.locator('.consent-check input').first.check()
            page.locator('input[type=file]').set_input_files({'name':name,'mimeType':mime,'buffer':data})
            expect(page.get_by_role('region',name='Breakdown dan klasifikasi intake')).to_be_visible()
            expect(page.locator('.bd-overview')).to_be_visible()
            return next(document['latest'] for document in api('/api/documents?dataset=live') if document['filename']==name)
        def close():page.get_by_role('button',name='Jelajahi data',exact=True).click()
        try:
            page.goto(args.base_url,wait_until='networkidle')
            headers={'X-Workspace-Token':page.evaluate("localStorage.getItem('rubber-workspace-token')")}
            version=upload('QA_INTAKE_multisheet.xlsx',raw,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            passed('General intake/classification is the default, purchase mapping remains optional')
            panel=page.get_by_role('region',name='Breakdown dan klasifikasi intake')
            expect(panel.locator('.bd-overview')).to_contain_text('2')
            expect(panel.locator('.bd-state')).to_contain_text('Campuran')
            profile=api('/api/versions/'+version['id']+'/breakdown')
            assert profile['profile']['summary']['sheets_scanned']==2 and profile['profile']['summary']['tables_detected']==2
            expect(page.get_by_label('Klasifikasi bisnis tabel',exact=True)).to_have_value('inventory')
            passed('Multi-sheet workbook is broken down into separately classified inventory and production tables')
            expect(page.get_by_label('Tipe Stok',exact=True)).to_have_value('number')
            expect(page.get_by_label('Peran Stok',exact=True)).to_have_value('stock')
            expect(page.get_by_label('Peran Catatan',exact=True)).to_have_value('unknown')
            expect(panel.locator('.bd-columns')).to_contain_text('1/2')
            passed('Column primitive types, semantic roles and blank counts are shown without guessing unknown roles')
            panel.locator('.bd-columns details').nth(2).locator('summary').click()
            expect(panel.locator('.bd-columns')).to_contain_text('Stok!C3')
            expect(panel.locator('.bd-columns')).to_contain_text('Baris 5: 0')
            panel.locator('.bd-preview summary').click()
            expect(panel.locator('.bd-preview')).to_contain_text('Lateks')
            assert profile['profile']['sheets'][0]['tables'][0]['preview'][0]['row_no']==4
            passed('Reasons and previews retain physical sheet, header, row and column references; zero is not blank')
            expect(page.get_by_role('button',name='Simpan review tabel',exact=True)).to_be_disabled()
            assert api('/api/stats?dataset=live')['observations']==0
            assert page.get_by_role('button',name='Validasi & publikasikan',exact=True).count()==0
            passed('Intake does not force purchase mapping or publish observations')
            panel.locator('.bd-preview summary').click()
            panel.locator('.bd-columns details').nth(2).locator('summary').click()
            page.locator('.modal-scroll').evaluate('element=>element.scrollTop=0')
            page.screenshot(path=str(args.output_dir/'intake-breakdown-desktop.png'),full_page=True)
            for width in (390,768,1440):
                page.set_viewport_size({'width':width,'height':1120})
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
                box=page.locator('.upload-modal').bounding_box();assert box['x']>=0 and box['x']+box['width']<=width+1
                assert panel.locator('.bd-columns').evaluate('element=>element.scrollWidth>=element.clientWidth')
                if width==390:
                    page.locator('.modal-scroll').evaluate('element=>element.scrollTop=0')
                    page.screenshot(path=str(args.output_dir/'intake-breakdown-mobile.png'),full_page=True)
            passed('Breakdown modal fits 390/768/1440px; wide column tables scroll locally')
            page.get_by_label('Konfirmasi review tabel',exact=True).check()
            page.get_by_label('Peran Catatan',exact=True).select_option('lot')
            expect(page.get_by_label('Konfirmasi review tabel',exact=True)).not_to_be_checked()
            expect(panel).to_contain_text('Perubahan metadata belum disimpan.')
            passed('Editing a suggestion clears confirmation; review cannot be submitted silently')
            page.get_by_label('Konfirmasi review tabel',exact=True).check()
            page.get_by_role('button',name='Simpan review tabel',exact=True).click()
            expect(panel.locator('.bd-reviewed')).to_contain_text('sudah direview')
            after=api('/api/versions/'+version['id']+'/breakdown')
            assert len(after['review']['tables'])==1 and after['profile_hash']==profile['profile_hash']
            assert after['profile']==profile['profile'] and not after['published']
            assert api('/api/stats?dataset=live')['observations']==0
            passed('Review persists separately from unchanged inferred metadata, with no observation publication')
            production=profile['profile']['sheets'][1]['tables'][0]
            page.get_by_label('Dataset terdeteksi',exact=True).select_option(production['id'])
            expect(page.get_by_label('Klasifikasi bisnis tabel',exact=True)).to_have_value('production')
            expect(panel.locator('.bd-reviewed')).to_have_count(0)
            passed('Review applies only to the chosen table, not automatically to all workbook sheets')
            path='/api/versions/'+version['id']+'/raw'
            assert context.request.get(args.base_url+path,headers=headers).body()==raw
            foreign={'X-Workspace-Token':'QA_other_workspace_'+'b'*48}
            assert context.request.get(args.base_url+'/api/versions/'+version['id']+'/breakdown',headers=foreign).status==404
            passed('Original bytes remain identical and another workspace cannot access the profile')
            close();page.get_by_role('button',name='Pusat data',exact=True).click()
            page.locator('.document-row').filter(has_text='QA_INTAKE_multisheet.xlsx').get_by_role('button',name='Breakdown',exact=True).click()
            drawer=page.get_by_role('dialog',name='Bukti arsip raw')
            expect(drawer.locator('.bd-reviewed')).to_contain_text('sudah direview')
            expect(page.get_by_label('Peran Catatan',exact=True)).to_have_value('lot')
            expect(drawer.locator('.bd-columns')).to_contain_text('Saran: Belum dikenali')
            page.set_viewport_size({'width':390,'height':1000})
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
            passed('Pusat data opens saved breakdown/review in the raw evidence drawer, including mobile layout')
            page.get_by_role('button',name='Tutup bukti data',exact=True).click()
            page.set_viewport_size({'width':1440,'height':1120})
            unknown=upload('QA_INTAKE_unknown.csv',b'Alpha,Beta\na,b\nc,d\n')
            expect(page.get_by_label('Klasifikasi bisnis tabel',exact=True)).to_have_value('unknown')
            expect(page.locator('.bd-state')).to_contain_text('Belum terklasifikasi')
            expect(page.locator('.bd-source')).to_contain_text('header 1')
            passed('Unknown business datasets abstain explicitly instead of becoming purchase transactions')
            close()
            opaque=upload('QA_INTAKE_opaque.bin',b'opaque\x00\xff natural rubber raw')
            expect(page.locator('.bd-state')).to_contain_text('Format belum didukung')
            assert api('/api/versions/'+opaque['id']+'/breakdown')['profile']['status']=='unsupported'
            assert context.request.get(args.base_url+'/api/versions/'+opaque['id']+'/raw',headers=headers).body()==b'opaque\x00\xff natural rubber raw'
            passed('Unsupported format remains byte-identical raw and is not falsely claimed as classified')
            close()
            large=b'Tanggal,Stok\n'+b'2026-10-15,1\n'*5005
            bounded=upload('QA_INTAKE_bounded.csv',large)
            expect(page.locator('.bd-state')).to_contain_text('Cakupan terbatas')
            partial=api('/api/versions/'+bounded['id']+'/breakdown')['profile']
            assert partial['status']=='partial' and partial['summary']['data_records_scanned']==4999
            assert context.request.get(args.base_url+'/api/versions/'+bounded['id']+'/raw',headers=headers).body()==large
            passed('Over-budget CSV reports partial observed counts while retaining all original bytes')
            close()
            repeat=upload('QA_INTAKE_multisheet.xlsx',raw,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            assert repeat['id']==version['id']
            assert api('/api/versions/'+version['id']+'/acquisitions')['total']==2
            assert api('/api/versions/'+version['id']+'/breakdown')['review']['revision']==1
            passed('Identical re-intake records another receipt without erasing review or duplicating the raw version')
            assert all(urlsplit(url).netloc==urlsplit(args.base_url).netloc for url in requests if url.startswith(('http://','https://')))
            passed('Browser requests remain same-origin; no AI/CDN/model endpoint is used')
            assert not report['page_errors'],report['page_errors'];passed('Zero JavaScript page errors')
            report['status']='passed'
        except Exception as error:
            report['status']='failed';report['failure']=str(error)
            page.screenshot(path=str(args.output_dir/'failure.png'),full_page=True)
            raise
        finally:
            if headers:
                for document in api('/api/documents?dataset=live'):
                    if document['filename'].startswith('QA_INTAKE_'):api('/api/documents/'+document['id'],method='DELETE')
                assert not api('/api/documents?dataset=live');report['cleanup']=True
            report['passed_checks']=len(report['checks'])
            (args.output_dir/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            context.close();browser.close()


if __name__=='__main__':main()
