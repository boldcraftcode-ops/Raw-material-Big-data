"""Opt-in real-browser smoke. Creates/deletes its own anonymous QA data only.
Requires a running app, playwright package, Chromium and OS browser dependencies.
May create a real private BMKG subscription; never changes shared-source config.
Usage: python scripts/browser_smoke.py ; optional RUBBER_TEST_URL/RUBBER_QA_DIR.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import secrets
from playwright.sync_api import sync_playwright,expect

BASE=os.environ.get('RUBBER_TEST_URL','http://127.0.0.1:8000')
QA=Path(os.environ.get('RUBBER_QA_DIR',str(Path.home()/'.cache/rubber-v02-qa')));QA.mkdir(parents=True,exist_ok=True)
report={'checks':[],'page_errors':[],'viewport_overflow':{}}

def ok(text):report['checks'].append(text);print('PASS',text,flush=True)

def nav(page,name):
    toggle=page.get_by_role('button',name='Buka navigasi',exact=True)
    if toggle.is_visible():toggle.click()
    page.get_by_role('button',name=name,exact=True).click()

def api(page,path):
    return page.evaluate("""async path => {const r=await fetch(path,{headers:{'X-Workspace-Token':localStorage.getItem('rubber-workspace-token')}});if(!r.ok)throw Error('API '+r.status);return r.json()}""",path)

def upload(page,name,body,archive=True):
    page.locator('header').get_by_role('button',name='Tambah data',exact=True).click()
    dialog=page.get_by_role('dialog')
    if archive:
        dialog.get_by_role('button',name='Arsip semua format',exact=True).click()
        dialog.get_by_label('Kategori arsip').select_option('quality')
        dialog.get_by_label('Konteks arsip').fill('QA anonim untuk indeks karet alam; bukan informasi pemasok nyata.')
        dialog.get_by_label('URL sumber arsip').fill('https://example.org/qa-rubber-metadata-only')
    expect(dialog.get_by_role('button',name='Pilih file',exact=True)).to_be_disabled()
    dialog.get_by_role('checkbox').check()
    dialog.locator('input[type=file]').set_input_files({'name':name,'mimeType':'text/plain' if archive else 'text/csv','buffer':body})
    return dialog

def check_download(page,button,expected):
    with page.expect_download() as d:button.click()
    assert Path(d.value.path()).read_bytes()==expected

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
    page=context.new_page();page.set_default_timeout(15000)
    page.on('pageerror',lambda e:report['page_errors'].append(str(e)))
    urls=[];page.on('request',lambda r:urls.append(r.url))
    page.goto(BASE,wait_until='networkidle')
    # Private capability stays in excluded QA scratch, never in reports or release.
    context.storage_state(path=str(QA/'browser-context.json'))
    expect(page.get_by_role('heading',name='Semesta karet alam.',exact=True)).to_be_visible()
    expect(page.locator('.radar-table tbody tr')).to_have_count(6)
    assert not any(not url.startswith(BASE) for url in urls),urls
    ok('Default public galaxy loads with four-kind balanced overview; all startup resources local')
    page.locator('.graph-node').first.click()
    expect(page.locator('.entity-body .entity-type')).to_be_visible()
    page.get_by_role('button',name='Perbesar galaksi',exact=True).click()
    expect(page.locator('.galaxy-fullscreen')).to_be_visible();page.keyboard.press('Escape')
    expect(page.locator('.galaxy-fullscreen')).to_have_count(0)
    ok('Galaxy node selection and fullscreen/Escape')
    page.screenshot(path=str(QA/'galaxy-desktop.png'),full_page=True)
    nav(page,'Sumber eksternal');expect(page.locator('.collector-card')).to_have_count(4)
    page.screenshot(path=str(QA/'sources-desktop.png'),full_page=True)
    page.locator('.collector-card').first.get_by_role('button',name='Riwayat',exact=True).click()
    history=page.get_by_role('dialog',name='Riwayat koleksi')
    expect(history.locator('.source-receipt').first).to_be_visible()
    assert history.evaluate('(el)=>el.contains(document.activeElement)')
    page.keyboard.press('Shift+Tab');assert history.evaluate('(el)=>el.contains(document.activeElement)')
    page.keyboard.press('Escape');expect(history).to_have_count(0)
    ok('Real public acquisition ledger/raw manifests and drawer focus trap')
    nav(page,'Eksplorasi');page.get_by_label('Jenis record eksternal').select_option('market_price')
    expect(page.locator('.radar-table tbody tr')).to_have_count(15)
    page.get_by_role('button',name='Record berikutnya').click()
    expect(page.locator('.knowledge-panel .pagination')).to_contain_text('16–30')
    page.locator('.radar-table .evidence-link').first.click()
    external=page.get_by_role('dialog',name='Bukti record eksternal')
    expect(external.get_by_role('heading',name='Manifest arsip asli')).to_be_visible()
    assert re.fullmatch(r'[a-f0-9]{64}',external.locator('.hash-block').inner_text())
    page.keyboard.press('Escape');expect(external).to_have_count(0)
    ok('External kind filter, page 2, record-to-original evidence and Escape')
    page.get_by_role('button',name='Data saya',exact=True).click()
    expect(page.locator('.radar-table tbody tr')).to_have_count(0)
    suffix=secrets.token_hex(5);filename='qa-rubber-'+suffix+'.txt'
    marker='qaintakeuniktoken'+suffix;body=('Catatan karet alam '+marker+'\nKelembapan 71%.\n').encode()
    dialog=upload(page,filename,body)
    expect(dialog.get_by_role('heading',name='Raw diterima utuh.',exact=True)).to_be_visible(timeout=30000)
    dialog.get_by_role('button',name='Jelajahi data').click()
    nav(page,'Pusat data');expect(page.locator('.document-row')).to_have_count(1)
    hit=page.locator('.archive-hit').filter(has_text=filename)
    hit.get_by_role('button').click()
    raw=page.get_by_role('dialog',name='Bukti arsip raw')
    expect(raw.get_by_role('heading',name='Manifest arsip asli')).to_be_visible()
    expect(raw.locator('.archive-text-preview')).to_contain_text(marker)
    check_download(page,raw.get_by_role('button',name='Unduh byte raw asli'),body)
    page.keyboard.press('Escape')
    ok('All-format intake, natural-rubber consent, safe index and exact original-byte download')
    page.get_by_label('Cari seluruh arsip').fill(marker);page.get_by_label('Cari seluruh arsip').press('Enter')
    expect(page.locator('.archive-hit')).to_have_count(1)
    assert marker in page.locator('.archive-hit').inner_text()
    page.get_by_label('Cari seluruh arsip').fill('');nav(page,'Pusat data')
    dialog=upload(page,filename,body)
    expect(dialog.get_by_role('heading',name='Byte identik, penerimaan baru.',exact=True)).to_be_visible(timeout=30000)
    dialog.get_by_role('button',name='Jelajahi data').click()
    expect(page.locator('.document-row')).to_have_count(1)
    page.locator('.archive-hit').filter(has_text=filename).get_by_role('button').click()
    raw=page.get_by_role('dialog',name='Bukti arsip raw')
    expect(raw).to_contain_text('Akuisisi byte ini · 2');page.keyboard.press('Escape')
    body2=body+b'Revisi quality QA: 72%.\n';dialog=upload(page,filename,body2)
    expect(dialog.get_by_role('heading',name='Raw diterima utuh.',exact=True)).to_be_visible(timeout=30000)
    dialog.get_by_role('button',name='Jelajahi data').click()
    expect(page.locator('.document-row').filter(has_text=filename)).to_contain_text('2 versi')
    page.get_by_role('button',name='Riwayat '+filename,exact=True).click()
    history=page.get_by_role('dialog',name='Riwayat dokumen');expect(history.locator('.version-card')).to_have_count(2)
    check_download(page,history.get_by_role('button',name='Unduh asli v1',exact=True),body)
    page.keyboard.press('Escape')
    ok('Full-text search, duplicate receipt, version 2 and unchanged historical raw')
    purchase=('tanggal,pemasok,id_pemasok,lokasi_pemasok,material,grade,harga,mata_uang,unit,basis_berat,kkk_persen,jenis_harga,kuantitas_kg\n'
              '2026-10-15,Contoh QA,QA-001,Medan,Karet alam,RSS3,15000,IDR,kg,basah,60,transaksi_internal,1000\n'
              'not-a-date,Contoh QA,QA-001,Medan,Karet alam,RSS3,-1,IDR,kg,basah,60,transaksi_internal,1000\n').encode()
    purchase_name='qa-pembelian-'+suffix+'.csv';dialog=upload(page,purchase_name,purchase,archive=False)
    publish=dialog.get_by_role('button',name='Validasi & publikasikan')
    expect(publish).to_be_visible(timeout=30000);expect(publish).to_be_disabled()
    dialog.get_by_role('checkbox').check();expect(publish).to_be_enabled();publish.click()
    expect(dialog.get_by_role('heading',name='Dari file menjadi pengetahuan.',exact=True)).to_be_visible(timeout=30000)
    expect(dialog).to_contain_text('1Observasi aktif');expect(dialog).to_contain_text('1Perlu review')
    dialog.get_by_role('button',name='Jelajahi data').click();nav(page,'Eksplorasi')
    expect(page.locator('.observations-table:not(.radar-table) tbody tr')).to_have_count(1)
    page.locator('.evidence-button').first.click()
    evidence=page.get_by_role('dialog',name='Jejak bukti')
    expect(evidence).to_contain_text('Tervalidasi aturan, bukan audit kebenaran')
    check_download(page,evidence.get_by_role('button',name='Unduh file asli'),purchase)
    page.keyboard.press('Escape');nav(page,'Aktivitas & kualitas');expect(page.locator('.issue-card')).to_have_count(1)
    ok('Purchase CSV regression: explicit mapping gate, valid publication, invalid-row quarantine, raw evidence')
    nav(page,'Sumber eksternal');page.get_by_role('button',name='Tambah pantauan',exact=True).click()
    private='QA referensi cuaca '+suffix
    page.get_by_label('Nama pantauan',exact=True).fill(private)
    page.get_by_label('Konteks lokasi pantauan',exact=True).fill('QA lokasi referensi regional; bukan kebun atau pemasok terverifikasi.')
    page.get_by_role('button',name='Simpan pantauan',exact=True).click()
    card=page.locator('.collector-card').filter(has=page.get_by_role('heading',name=private,exact=True))
    expect(card).to_be_visible()
    expect(card.get_by_text('Berhasil',exact=True)).to_be_visible(timeout=90000)
    expect(card.get_by_role('button',name='Jeda '+private,exact=True)).to_be_enabled(timeout=15000)
    item=next(s for s in api(page,'/api/sources')['items'] if s['name']==private)
    assert item['latest_run'] and item['latest_run']['trigger_kind']=='scheduled' and item['record_count']>0
    report['private_bmkg_records']=item['record_count'];report['private_bmkg_trigger']=item['latest_run']['trigger_kind']
    card.get_by_role('button',name='Jeda '+private,exact=True).click();expect(card).to_contain_text('Dijeda')
    card.get_by_role('button',name='Ubah '+private,exact=True).click()
    page.get_by_label('Konteks lokasi pantauan',exact=True).fill('QA konteks direvisi; referensi regional, bukan kebun terverifikasi.')
    page.get_by_role('button',name='Simpan pantauan',exact=True).click()
    previous=item['latest_run']['id']
    card.get_by_role('button',name='Aktifkan '+private,exact=True).click()
    card.get_by_role('button',name='Riwayat',exact=True).click()
    history=page.get_by_role('dialog',name='Riwayat koleksi')
    expect(history.locator('.run-picker button')).to_have_count(2,timeout=90000)
    expect(history.locator('.run-picker button').first.get_by_text('Berhasil',exact=True)).to_be_visible(timeout=90000)
    updated=next(s for s in api(page,'/api/sources')['items'] if s['name']==private)
    assert updated['enabled'] and updated['latest_run']['id']!=previous and updated['latest_run']['trigger_kind']=='scheduled'
    page.keyboard.press('Escape')
    expect(card.get_by_role('button',name='Hapus sumber '+private,exact=True)).to_be_enabled(timeout=15000)
    page.once('dialog',lambda d:d.accept());card.get_by_role('button',name='Hapus sumber '+private,exact=True).click()
    expect(card).to_have_count(0)
    ok('REAL autonomous BMKG private source without manual run; pause/edit/resume/recollect/delete')
    # Only delete anonymous QA documents generated by this browser-owned token.
    nav(page,'Pusat data')
    for name in (filename,purchase_name):
        page.get_by_role('button',name='Hapus '+name,exact=True).click()
        modal=page.get_by_role('alertdialog',name='Hapus dokumen')
        modal.get_by_role('button',name='Hapus dokumen',exact=True).click()
        expect(page.locator('.document-row').filter(has_text=name)).to_have_count(0)
    assert api(page,'/api/documents?dataset=live')==[]
    assert api(page,'/api/knowledge?dataset=live')['total']==0
    ok('Private QA cleanup; no changes to other workspaces/public source configuration')
    page.get_by_role('button',name='Data eksternal',exact=True).click()
    for width in (390,768,1024,1440):
        page.set_viewport_size({'width':width,'height':1000});nav(page,'Galaksi pengetahuan')
        expect(page.get_by_role('heading',name='Semesta karet alam.',exact=True)).to_be_visible()
        overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
        report['viewport_overflow'][str(width)+'_galaxy']=overflow;assert not overflow
        nav(page,'Sumber eksternal');expect(page.locator('.collector-card')).to_have_count(4)
        overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
        report['viewport_overflow'][str(width)+'_sources']=overflow;assert not overflow
        if width==390:page.screenshot(path=str(QA/'sources-mobile.png'),full_page=True)
    ok('390/768/1024/1440px galaxy and sources: mobile navigation, no horizontal page overflow')
    assert not report['page_errors'],report['page_errors']
    page.set_viewport_size({'width':1440,'height':1000});nav(page,'Galaksi pengetahuan')
    page.screenshot(path=str(QA/'galaxy-desktop.png'),full_page=True)
    report['public_source_counts']={s['adapter']:s['record_count'] for s in api(page,'/api/sources')['items'] if s['is_public']}
    report['startup_requests_local_only']=True
    (QA/'browser-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    context.close();browser.close()
