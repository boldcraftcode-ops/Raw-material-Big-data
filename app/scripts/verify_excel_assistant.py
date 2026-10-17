"""Optional browser smoke of the local Excel assistant; temporary private QA data is removed.
Requires Playwright/Chromium and an already-running app. No AI API or workspace token is exported.
"""
from __future__ import annotations
import argparse
import io
import json
import platform
from datetime import datetime,timezone
from pathlib import Path
from openpyxl import Workbook
from playwright.sync_api import sync_playwright,expect


def xlsx(rows):
    book=Workbook();book.active.title='Pembelian'
    for row in rows:book.active.append(row)
    out=io.BytesIO();book.save(out);return out.getvalue()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--output-dir',type=Path,default=Path('.cache/excel-qa'))
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'environment':'Chromium / '+platform.system(),'mode':'local_rules','external_ai_used':False,'checks':[],'page_errors':[],'cleanup':False}
    def passed(name):report['checks'].append(name);print('PASS:',name,flush=True)
    header=['Tgl Beli','Mitra Pasok','Material','Harga (Rp/kg)','Currency','Satuan Harga','Basis Berat']
    first=xlsx([['QA: laporan format berbeda'],['Contoh sintetis, bukan data perusahaan'],[],header,
                ['15/10/2026','Pemasok QA Satu','Bokar','15.000,50','IDR','kg','basah'],
                ['16/10/2026','Pemasok QA Dua','Bokar','16.000,50','IDR','kg','basah']])
    reordered=xlsx([[header[i] for i in (3,2,0,1,6,5,4)],['17.000,50','Bokar','17/10/2026','Pemasok QA Tiga','basah','kg','IDR']])
    two_level=xlsx([['Contoh dua header'],[],['Tanggal','Pemasok','Bahan','Harga',None,None,'Basis'],
                    [None,None,None,'Nilai','Mata Uang','Unit',None],['2026-10-15','Pemasok QA Empat','Bokar',14000,'IDR','kg','basah']])
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
        context=browser.new_context(viewport={'width':1440,'height':1050})
        page=context.new_page();page.set_default_timeout(12000)
        page.on('pageerror',lambda error:report['page_errors'].append(str(error)))
        headers={}
        def api(path,method='GET',body=None):
            response=context.request.fetch(args.base_url+path,method=method,headers=headers,data=body)
            assert response.ok,response.text()
            return response.json()
        def open_file(name,buffer):
            page.get_by_role('button',name='Tambah data',exact=True).click()
            page.get_by_role('button',name='Pemetaan pembelian',exact=True).click()
            page.locator('.consent-check input').first.check()
            page.locator('input[type=file]').set_input_files({'name':name,'mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','buffer':buffer})
            expect(page.get_by_role('region',name='Asisten Excel lokal')).to_be_visible()
        def approve():
            page.locator('.mapping-consent input').check()
            page.get_by_role('button',name='Validasi & publikasikan',exact=True).click()
            expect(page.get_by_role('button',name='Ingat pemetaan ini',exact=True)).to_be_visible()
        try:
            page.goto(args.base_url,wait_until='networkidle')
            headers={'X-Workspace-Token':page.evaluate("localStorage.getItem('rubber-workspace-token')")}
            open_file('QA_ASISTEN_pola_satu.xlsx',first)
            expect(page.get_by_label('Baris awal header',exact=True)).to_have_value('4')
            expect(page.get_by_label('Jumlah baris header',exact=True)).to_have_value('1')
            expect(page.get_by_label('Kolom Pemasok / organisasi',exact=True)).to_have_value('')
            expect(page.get_by_role('button',name='Periksa sampel',exact=True)).to_be_disabled()
            passed('Leading titles detected; unknown supplier header requires human mapping')
            page.get_by_label('Kolom Pemasok / organisasi',exact=True).select_option('c1')
            page.get_by_role('button',name='Periksa sampel',exact=True).click()
            expect(page.locator('.excel-check-result')).to_contain_text('2 perlu review')
            assert api('/api/stats?dataset=live')['observations']==0
            passed('Readonly sample check reports date errors without publishing')
            page.get_by_role('button',name='Gunakan saran format',exact=True).click()
            expect(page.locator('.excel-check-result')).to_have_count(0)
            page.get_by_role('button',name='Periksa sampel',exact=True).click()
            expect(page.locator('.excel-check-result')).to_contain_text('2 valid · 0 perlu review')
            expect(page.locator('.mapping-consent input')).not_to_be_checked()
            passed('Format hint fixes date parsing; edited rules clear old checks and consent')
            page.locator('.modal-scroll').evaluate('element=>element.scrollTop=0')
            page.screenshot(path=str(args.output_dir/'excel-assistant-desktop.png'),full_page=True)
            for width in (390,768,1440):
                page.set_viewport_size({'width':width,'height':1050})
                assert not page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
                box=page.locator('.upload-modal').bounding_box();assert box['x']>=0 and box['x']+box['width']<=width+1
                if width==390:
                    page.locator('.modal-scroll').evaluate('element=>element.scrollTop=0')
                    page.screenshot(path=str(args.output_dir/'excel-assistant-mobile.png'),full_page=True)
            passed('Assistant modal fits 390/768/1440px without page overflow')
            approve()
            assert api('/api/stats?dataset=live')['observations']==2
            passed('Explicit approval performs full validation and publishes correct rows')
            page.get_by_role('button',name='Ingat pemetaan ini',exact=True).click()
            expect(page.locator('.excel-remember')).to_contain_text('Pola pemetaan disimpan.')
            passed('Correction is remembered only through explicit approval button')
            page.get_by_role('button',name='Jelajahi data',exact=True).click()
            open_file('QA_ASISTEN_urutan_baru.xlsx',reordered)
            expect(page.get_by_label('Kolom Pemasok / organisasi',exact=True)).to_have_value('c3')
            expect(page.get_by_role('button',name='Gunakan aturan baca tersimpan',exact=True)).to_be_visible()
            date_selector=page.locator('.options-grid select').nth(1)
            expect(date_selector).to_have_value('iso')
            passed('Saved field mapping follows reordered headers; saved options are not applied silently')
            page.get_by_role('button',name='Gunakan aturan baca tersimpan',exact=True).click()
            expect(date_selector).to_have_value('dmy')
            page.get_by_role('button',name='Periksa sampel',exact=True).click()
            expect(page.locator('.excel-check-result')).to_contain_text('1 valid · 0 perlu review')
            passed('Approved reading rules can be reused explicitly and checked again')
            page.get_by_role('button',name='Lupakan pola',exact=True).click()
            expect(page.get_by_role('button',name='Gunakan aturan baca tersimpan',exact=True)).to_have_count(0)
            assert api('/api/stats?dataset=live')['observations']==2
            passed('Forgetting a pattern leaves existing observations untouched')
            approve()
            assert api('/api/stats?dataset=live')['observations']==3
            page.get_by_role('button',name='Jelajahi data',exact=True).click()
            open_file('QA_ASISTEN_header_bertingkat.xlsx',two_level)
            expect(page.get_by_label('Baris awal header',exact=True)).to_have_value('3')
            expect(page.get_by_label('Jumlah baris header',exact=True)).to_have_value('2')
            expect(page.get_by_label('Kolom Harga',exact=True)).to_have_value('c3')
            passed('Two-level headers are exposed with correct field mapping')
            page.get_by_role('button',name='Tutup unggah',exact=True).click()
            documents=api('/api/documents?dataset=live')
            original=next(item for item in documents if item['filename']=='QA_ASISTEN_pola_satu.xlsx')
            raw=context.request.get(args.base_url+'/api/versions/'+original['latest']['id']+'/raw',headers=headers)
            assert raw.body()==first
            obs=api('/api/observations?dataset=live')['items']
            evidence=api('/api/evidence/'+next(item['id'] for item in obs if item['filename']=='QA_ASISTEN_pola_satu.xlsx'))
            assert evidence['row_no'] in (5,6) and evidence['header_row']==4
            passed('Original XLSX bytes and physical evidence row pointers are preserved')
            assert not report['page_errors'],report['page_errors']
            passed('Zero JavaScript page errors')
            report['status']='passed'
        except Exception as error:
            report['status']='failed';report['failure']=str(error)
            page.screenshot(path=str(args.output_dir/'failure.png'),full_page=True)
            raise
        finally:
            if headers:
                documents=api('/api/documents?dataset=live')
                # Only this fresh, private browser workspace and this script's known prefix.
                for document in documents:
                    if document['filename'].startswith('QA_ASISTEN_'):api('/api/documents/'+document['id'],method='DELETE')
                assert not api('/api/documents?dataset=live')
                report['cleanup']=True
            report['passed_checks']=len(report['checks'])
            (args.output_dir/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            context.close();browser.close()
    print(json.dumps({'status':report['status'],'passed_checks':report['passed_checks'],'cleanup':report['cleanup']}))


if __name__=='__main__':main()
