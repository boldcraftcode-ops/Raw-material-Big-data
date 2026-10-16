from pathlib import Path
from html import escape
from markdown_it import MarkdownIt
from bs4 import BeautifulSoup
import math
import random
import re

ROOT = Path(__file__).resolve().parent


def svg_text(x, y, text, size=19, color='#223344', weight=400, anchor='start'):
    return f'<text x="{x}" y="{y}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{escape(text)}</text>'


def architecture_svg():
    p = ['''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 552" role="img" aria-labelledby="arch-title arch-desc">
<title id="arch-title">Arsitektur Rubber Intelligence Platform</title>
<desc id="arch-desc">Alur dari sumber, katalog dan penerimaan, arsip mentah, pekerjaan durabel, worker, data ternormalisasi, API, menuju pencarian dan galaksi. Hak akses, audit, serta observabilitas melintasi seluruh komponen.</desc>
<defs>
<marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="none" stroke="#77889b" stroke-width="1.5"/></marker>
</defs>
<rect x="0" y="0" width="1200" height="552" rx="22" fill="#f4f7fb"/>
''']
    p += [svg_text(28, 32, 'DATA FLOW / MVP', 13, '#63758c', 700)]
    cards = [
        (28, 64, '01', 'Sumber', ['Unggah file internal', 'API / feed disetujui'], '#64748b', '#ffffff'),
        (322, 64, '02', 'Katalog + intake', ['Izin · jadwal · kuota', 'Pemeriksaan keamanan'], '#64748b', '#ffffff'),
        (616, 64, '03', 'Raw / bronze', ['Object storage privat', 'Byte asli · hash · versi'], '#b77920', '#fff9ed'),
        (910, 64, '04', 'Job durabel', ['PostgreSQL + outbox', 'Queue + checkpoint'], '#5269c8', '#f2f4ff'),
        (910, 294, '05', 'Worker asinkron', ['Parse · normalisasi', 'Validasi · ekstraksi'], '#5269c8', '#f2f4ff'),
        (616, 294, '06', 'Normalized / silver', ['PostgreSQL + bukti', 'Klaim · entitas · waktu'], '#168e91', '#ecfaf8'),
        (322, 294, '07', 'Serving / gold', ['Graph · indeks · aturan', 'API + hak akses'], '#795fc3', '#f6f1ff'),
        (28, 294, '08', 'Pengalaman', ['Cari · galaksi · timeline', 'Review · watchlist · alert'], '#168e91', '#ecfaf8'),
    ]
    for x, y, number, title, lines, accent, fill in cards:
        p.append(f'<rect x="{x}" y="{y}" width="262" height="148" rx="14" fill="{fill}" stroke="#dce4ed"/>')
        p.append(f'<rect x="{x}" y="{y+19}" width="4" height="34" rx="2" fill="{accent}"/>')
        p += [svg_text(x+20, y+28, number, 13, accent, 700), svg_text(x+20, y+58, title, 21, '#1b2d43', 700)]
        for i, line in enumerate(lines):
            p.append(svg_text(x+20, y+94+i*26, line, 17, '#53667d'))
    paths = [
        'M294 138 H312', 'M588 138 H606', 'M882 138 H900',
        'M1041 219 V280', 'M904 368 H888', 'M610 368 H594', 'M316 368 H300'
    ]
    for d in paths:
        p.append(f'<path d="{d}" fill="none" stroke="#77889b" stroke-width="2" marker-end="url(#arr)"/>')
    p.append(svg_text(600, 257, 'Perubahan membentuk versi baru; data meragukan masuk review.', 17, '#63758c', 400, 'middle'))
    p.append('<rect x="28" y="476" width="1144" height="48" rx="10" fill="#e5ecf4"/>')
    p.append(svg_text(600, 506, 'LINTAS LAPISAN   /   RBAC · audit · retensi · observabilitas · pemulihan', 18, '#3e5671', 600, 'middle'))
    p.append('</svg>')
    return ''.join(p)


def galaxy_svg(hero=False):
    rng = random.Random(741 if not hero else 119)
    if hero:
        w, h, cx, cy = 680, 430, 335, 215
        clusters = [
            (154, 104, 'Pasokan', '#62e6c5'), (508, 94, 'Harga', '#ae9bff'),
            (548, 290, 'Cuaca', '#f5c578'), (165, 329, 'Bukti', '#7dbbff'),
            (345, 45, 'Regulasi', '#f6a9c0'), (355, 371, 'Logistik', '#80d9f2')
        ]
    else:
        w, h, cx, cy = 1200, 550, 598, 268
        clusters = [
            (248, 155, 'PASOKAN', '#62e6c5'), (931, 153, 'HARGA & PASAR', '#ae9bff'),
            (950, 407, 'CUACA', '#f5c578'), (239, 405, 'DOKUMEN & BUKTI', '#7dbbff'),
            (603, 74, 'REGULASI', '#f6a9c0'), (606, 466, 'LOGISTIK', '#80d9f2')
        ]
    ident = 'hero' if hero else 'galaxy'
    p = [f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-labelledby="{ident}-title {ident}-desc">
<title id="{ident}-title">Galaksi informasi karet alam, ilustrasi skematis</title>
<desc id="{ident}-desc">Enam gugus topik terhubung dengan konsep karet alam. Ini ilustrasi desain, bukan visualisasi data nyata.</desc>
<defs>
<radialGradient id="{ident}-nebula"><stop offset="0" stop-color="#454080" stop-opacity=".38"/><stop offset=".6" stop-color="#1c3760" stop-opacity=".16"/><stop offset="1" stop-color="#101c30" stop-opacity="0"/></radialGradient>
<radialGradient id="{ident}-core"><stop stop-color="#4fe6bc" stop-opacity=".25"/><stop offset="1" stop-color="#4fe6bc" stop-opacity="0"/></radialGradient>
</defs>
''']
    if not hero:
        p.append(f'<rect width="{w}" height="{h}" rx="20" fill="#101b2e"/>')
    p.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{w*.49}" ry="{h*.46}" fill="url(#{ident}-nebula)" transform="rotate(-16 {cx} {cy})"/>')
    for i in range(110 if hero else 190):
        x, y = rng.randint(18, w-18), rng.randint(16, h-16)
        rad = rng.choice([.7, .8, 1.0, 1.2, 1.5])
        p.append(f'<circle cx="{x}" cy="{y}" r="{rad}" fill="#c2d4ee" opacity="{rng.uniform(.12,.56):.2f}"/>')
    for ratio in [.65, 1, 1.35]:
        rx, ry = w*.29*ratio, h*.26*ratio
        p.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx:.1f}" ry="{ry:.1f}" fill="none" stroke="#53698a" stroke-opacity=".2" stroke-dasharray="3 8" transform="rotate(-14 {cx} {cy})"/>')
    for idx, (x, y, label, color) in enumerate(clusters):
        mx, my = (cx+x)/2, (cy+y)/2
        offset = 45 if idx%2 else -45
        p.append(f'<path d="M{cx} {cy} Q{mx+offset} {my-offset} {x} {y}" fill="none" stroke="{color}" stroke-width="1.4" stroke-opacity=".35"/>')
        for j in range(5 if hero else 7):
            ang = j*math.tau/(5 if hero else 7)+.3*idx
            radius = rng.randint(28, 49) if hero else rng.randint(39, 73)
            nx, ny = x+math.cos(ang)*radius, y+math.sin(ang)*radius*.55
            p.append(f'<path d="M{x} {y} L{nx:.1f} {ny:.1f}" stroke="{color}" stroke-opacity=".27"/>')
            p.append(f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="{rng.choice([2.5,3,4])}" fill="{color}" opacity=".8"/>')
        p.append(f'<circle cx="{x}" cy="{y}" r="18" fill="{color}" opacity=".09"/>')
        p.append(f'<circle cx="{x}" cy="{y}" r="6" fill="{color}"/>')
        # Labels use a small dark backplate for legibility over links.
        label_size = 14 if hero else 16
        by = y - (24 if hero else 30)
        bw = len(label)*label_size*.62+18
        p.append(f'<rect x="{x-bw/2:.1f}" y="{by-label_size:.1f}" width="{bw:.1f}" height="{label_size+8}" rx="5" fill="#111e32" fill-opacity=".84"/>')
        p.append(svg_text(x, by+1, label, label_size, color, 600, 'middle'))
    p.append(f'<circle cx="{cx}" cy="{cy}" r="90" fill="url(#{ident}-core)"/>')
    core_r = 48 if hero else 63
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{core_r}" fill="#142d3d" stroke="#74e7c7" stroke-opacity=".7"/>')
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{core_r+9}" fill="none" stroke="#7ee8ce" stroke-opacity=".13"/>')
    p.append(svg_text(cx, cy-2, 'KARET', 17 if hero else 21, '#d8fff1', 700, 'middle'))
    p.append(svg_text(cx, cy+19, 'ALAM', 17 if hero else 21, '#d8fff1', 700, 'middle'))
    if not hero:
        p.append(svg_text(24, 30, 'KNOWLEDGE GALAXY / KONSEP ANTARMUKA', 13, '#8ea6c7', 600))
        p.append(svg_text(w-24, h-22, 'SKEMATIS · BUKAN DATA NYATA', 12, '#8ea6c7', 600, 'end'))
    p.append('</svg>')
    return ''.join(p)


text = (ROOT / 'blueprint.md').read_text()
md = MarkdownIt('commonmark', {'html': True, 'typographer': True}).enable('table')
rendered = md.render(text)
rendered = rendered.replace('<!-- ARCHITECTURE_DIAGRAM -->', '<figure class="diagram architecture"><div class="diagram-scroll">'+architecture_svg()+'</div><figcaption>Arsitektur MVP: satu fondasi data, pemrosesan asinkron, dan antarmuka yang dapat ditelusuri. Komponen belum diimplementasikan.</figcaption></figure>')
rendered = rendered.replace('<!-- GALAXY_DIAGRAM -->', '<figure class="diagram galaxy"><div class="diagram-scroll">'+galaxy_svg()+'</div><figcaption>Galaksi adalah proyeksi pengetahuan. Garis harus memiliki makna dan bukti; kedekatan visual bukan sebab-akibat.</figcaption></figure>')
soup = BeautifulSoup(rendered, 'html.parser')
for h in list(soup.find_all(['h1', 'h2']))[:2]:
    if h.get_text().startswith(('Rubber Intelligence Platform', 'Blueprint teknis')):
        h.decompose()
for a in soup.find_all('a', href=True):
    if a['href'].startswith('https://'):
        a['target'] = '_blank'
        a['rel'] = 'noopener noreferrer'
        if a.get_text().strip().isdigit():
            a['class'] = 'citation'
            a.string = '[' + a.get_text().strip() + ']'
for table in list(soup.find_all('table')):
    wrapper = soup.new_tag('div', attrs={'class':'table-wrap', 'tabindex':'0', 'role':'region', 'aria-label':'Tabel rincian teknis; dapat digeser horizontal'})
    table.wrap(wrapper)

article = soup.new_tag('div', attrs={'class':'article'})
intro = soup.new_tag('div', attrs={'class':'intro', 'id':'ringkasan'})
article.append(intro)
current = intro
nav = [('<span>00</span> Ringkasan', 'ringkasan')]
for node in list(soup.contents):
    if getattr(node, 'name', None) == 'h2':
        title = node.get_text()
        match = re.match(r'(\d{2}) · (.*)', title)
        if match:
            n, title_body = match.groups()
            sid = 's' + n
            node.clear()
            num = soup.new_tag('span', attrs={'class':'section-no'})
            num.string = n
            node.append(num)
            node.append(title_body)
            nav.append((f'<span>{n}</span> '+escape(title_body), sid))
        else:
            sid = 'referensi'
            nav.append(('<span>R</span> Referensi', sid))
        current = soup.new_tag('section', attrs={'class':'doc-section', 'id':sid})
        article.append(current)
        current.append(node.extract())
    else:
        current.append(node.extract())

nav_html = ''.join(f'<a href="#{sid}">{label}</a>' for label, sid in nav)
css = r'''
:root {--ink:#182b42;--muted:#5a6d82;--line:#dfe6ed;--teal:#0c7f70;--bg:#f6f8fb;--paper:#fff;--dark:#101c30;--accent:#73e4c3;}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:30px}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;font-size:16px;line-height:1.75;-webkit-font-smoothing:antialiased}a{color:#116f91;text-underline-offset:3px}a:focus-visible{outline:3px solid #f1bd59;outline-offset:4px}::selection{background:#b7f1dd;color:#122940}.topbar{background:var(--dark);color:#c1cde1;border-bottom:1px solid #ffffff14}.topbar-inner{max-width:1450px;margin:auto;padding:17px 48px;display:flex;align-items:center;justify-content:space-between;gap:20px;font-size:11px;font-weight:650;letter-spacing:1.6px}.brand{display:flex;align-items:center;gap:12px}.brand svg{width:25px;height:25px}.status{display:flex;align-items:center;gap:8px;color:#a8bbd4;letter-spacing:.7px}.status i{height:6px;width:6px;border-radius:50%;background:#f6c777;display:inline-block}.hero{background:var(--dark);color:#fff;overflow:hidden;position:relative}.hero-inner{max-width:1450px;padding:62px 48px 44px;margin:auto;position:relative;display:grid;grid-template-columns:1fr 1.04fr;gap:24px;align-items:center}.eyebrow{font-size:11px;font-weight:650;letter-spacing:2.1px;color:var(--accent);margin-bottom:23px}.hero h1{font-size:clamp(39px,4.2vw,61px);line-height:1.07;letter-spacing:-2.3px;font-weight:650;margin:0 0 24px;max-width:650px}.hero h1 em{font-style:normal;color:#b0b7ef}.hero .subtitle{max-width:510px;font-size:17px;line-height:1.75;color:#b8c8df;margin:0 0 29px}.pills{display:flex;flex-wrap:wrap;gap:8px}.pill{border:1px solid #52617a8c;border-radius:30px;color:#d2deef;padding:5px 11px;font-size:11px;letter-spacing:.2px}.hero-art svg{width:100%;height:auto;display:block}.hero-foot{max-width:1354px;margin:auto;display:flex;justify-content:space-between;align-items:center;gap:16px;color:#9dafc9;padding:20px 0 25px;border-top:1px solid #ffffff1c;font-size:11px;letter-spacing:.6px}.hero-foot strong{color:#d7e1f0;font-weight:550}.decision-band{background:#eaf4f1;border-bottom:1px solid #dce9e3}.decision-inner{max-width:1354px;margin:auto;display:grid;grid-template-columns:repeat(3,1fr);padding:23px 0;gap:32px}.decision{border-left:2px solid #1d9682;padding-left:16px}.decision b{display:block;font-size:14px;color:#174d45;font-weight:650}.decision span{display:block;color:#5f766f;font-size:12px;margin-top:3px}.report-shell{max-width:1450px;margin:0 auto;padding:48px;display:grid;grid-template-columns:238px minmax(0,1fr);gap:50px;align-items:start}.sidebar{position:sticky;top:28px;max-height:calc(100vh - 56px);overflow-y:auto;padding-right:10px;scrollbar-width:thin}.sidebar-title{font-size:10px;font-weight:750;letter-spacing:2px;color:#7b8da1;padding:0 0 13px 11px}.sidebar a{display:flex;gap:9px;text-decoration:none;font-size:12px;line-height:1.45;color:#5e728a;padding:8px 10px;border-radius:7px;border:1px solid transparent;margin-bottom:2px}.sidebar a span{font-family:ui-monospace,monospace;font-size:10px;color:#98a8b8;flex:0 0 20px;padding-top:1px}.sidebar a:hover{background:#e7efed;color:#0d7164;border-color:#d9e7e1}.sidebar-note{font-size:11px;color:#8090a3;margin:22px 11px 0;line-height:1.75;border-top:1px solid #dfe6ed;padding-top:16px}.article{min-width:0;background:var(--paper);padding:38px 42px;border:1px solid #e2e8ee;border-radius:14px;box-shadow:0 8px 28px #20355004}.intro{padding-bottom:9px}.intro>p:first-child{font-size:12px;line-height:1.85;color:#6f8092}.intro>p:nth-child(2){font-size:12px;color:#6f8092}.article p{margin:0 0 18px}.article strong{font-weight:650;color:#213c52}.article blockquote{margin:25px 0;padding:19px 23px;background:#eef7f4;border-left:3px solid #1a9b80;border-radius:0 9px 9px 0;color:#375e56;font-size:15px}.article blockquote p:last-child{margin-bottom:0}.doc-section{border-top:1px solid var(--line);margin-top:36px;padding-top:35px;scroll-margin-top:24px}.doc-section h2{font-size:25px;line-height:1.3;letter-spacing:-.65px;font-weight:650;margin:0 0 24px;color:#152c42;display:flex;align-items:baseline;gap:14px}.section-no{font-size:13px;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-weight:500;color:#0b8b76;letter-spacing:0;min-width:25px}.article h3{font-size:17px;font-weight:650;letter-spacing:-.25px;line-height:1.45;color:#25465b;margin:27px 0 12px}.article ol,.article ul{padding-left:23px;margin:0 0 22px}.article li{padding-left:3px;margin:7px 0}.article li::marker{color:#52877e}.article code{font-family:ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace;font-size:.82em;line-height:1.55;background:#eef2f6;color:#38546b;padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}.article pre{border:1px solid #dce5ee;border-radius:9px;padding:20px;overflow:auto;background:#f5f8fb;font-size:13px;line-height:1.7;margin:20px 0 25px}.article pre code{font-size:12px;background:none;padding:0;border-radius:0;white-space:pre;overflow-wrap:normal;color:#344f67}.table-wrap{overflow-x:auto;margin:19px 0 24px;border:1px solid #dfe7ef;border-radius:9px;scrollbar-width:thin}.table-wrap:focus-visible{outline:3px solid #72bdb0;outline-offset:3px}.article table{border-collapse:collapse;width:100%;min-width:540px;font-size:13px;line-height:1.65}.article th{padding:13px 15px;background:#eef3f7;color:#3a526a;text-align:left;font-weight:650;border-bottom:1px solid #dce5ec;vertical-align:top}.article th:first-child{width:25%}.article td{padding:13px 15px;vertical-align:top;border-bottom:1px solid #e6ecf1;overflow-wrap:anywhere;color:#4d6277}.article tr:last-child td{border-bottom:0}.article tbody tr:nth-child(even) td{background:#fafbfd}.article td code{font-size:11px}.article .citation{font-size:10px;white-space:nowrap;vertical-align:super;text-decoration:none;color:#138d78;margin-left:2px;font-weight:700}.article .citation:hover{text-decoration:underline}.diagram{margin:24px 0;border:1px solid #e2e8ef;border-radius:12px;overflow:hidden;background:#f4f7fb}.diagram-scroll{overflow-x:auto;scrollbar-width:thin}.diagram svg{display:block;width:100%;height:auto;min-width:680px}.diagram figcaption{font-size:11px;line-height:1.65;color:#697d91;padding:12px 16px;background:#f8fafc;border-top:1px solid #e2e8ef}.galaxy{background:#101b2e}.galaxy figcaption{background:#17263c;color:#a8bbd3;border-color:#2e4058}.architecture+pre{display:none}.article hr{border:0;border-top:1px solid var(--line);margin:27px 0}.footer{background:#eaf0f4;border-top:1px solid #dce4ec;color:#718499;font-size:11px}.footer>div{max-width:1450px;margin:auto;padding:23px 48px;display:flex;justify-content:space-between;gap:20px}.back-top{display:inline-block;margin-top:18px;color:#18816d;text-decoration:none;font-size:11px}.mobile-contents{display:none}.end-note{font-size:12px;color:#61758a;margin-top:28px;line-height:1.8}
@media(min-width:1450px){.hero-foot,.decision-inner{margin-left:auto;margin-right:auto}}
@media(max-width:1449px){.hero-foot,.decision-inner{margin-left:48px;margin-right:48px}}
@media(max-width:1170px){.report-shell{grid-template-columns:205px minmax(0,1fr);gap:25px;padding:34px 30px}.article{padding:30px}.sidebar a{font-size:11px}.hero-inner{padding:46px 32px 30px;grid-template-columns:1fr .95fr}.hero h1{font-size:44px}.hero-foot,.decision-inner{margin-left:32px;margin-right:32px}.topbar-inner{padding-left:32px;padding-right:32px}}
@media(max-width:950px){.sidebar{display:none}.report-shell{display:block;max-width:900px;padding:25px 22px}.article{padding:30px}.hero-inner{grid-template-columns:1fr .8fr;gap:0}.hero h1{font-size:39px;letter-spacing:-1.6px}.hero .subtitle{font-size:15px}.hero-art{margin-right:-70px}.hero-foot{font-size:10px}.decision-inner{gap:16px}.decision b{font-size:12px}.decision span{font-size:11px}.mobile-contents{display:block;margin:0 0 20px;padding:13px 18px;background:white;border:1px solid #e2e8ee;border-radius:9px;font-size:12px;color:#425e72}.mobile-contents summary{cursor:pointer;color:#0f7c6b;font-weight:650}.mobile-contents nav{display:grid;grid-template-columns:1fr 1fr;gap:5px 15px;margin-top:16px}.mobile-contents a{text-decoration:none;font-size:11px;color:#5c7388}.mobile-contents span{font-family:monospace;color:#93a4b6;margin-right:7px}}
@media(max-width:640px){body{font-size:14px;line-height:1.8}.topbar-inner{padding:14px 20px;font-size:9px;letter-spacing:1px}.status{font-size:9px;letter-spacing:.1px}.brand{gap:8px}.brand svg{width:21px;height:21px}.hero-inner{display:block;padding:34px 22px 12px}.eyebrow{font-size:9px;margin-bottom:18px}.hero h1{font-size:39px;max-width:420px;letter-spacing:-1.8px;margin-bottom:18px}.hero .subtitle{font-size:14px;max-width:430px;margin-bottom:21px}.pill{font-size:10px;padding:3px 9px}.hero-art{margin:5px -22px -5px}.hero-art svg{max-height:245px}.hero-foot{margin:0 22px;padding:16px 0;display:block;line-height:1.9;font-size:10px}.hero-foot>span{display:block}.decision-inner{margin:0 22px;padding:19px 0;grid-template-columns:1fr;gap:13px}.decision{padding-left:12px}.decision b{font-size:12px}.decision span{display:inline;font-size:11px}.report-shell{padding:18px 12px}.article{padding:25px 18px;border-radius:10px}.doc-section{margin-top:27px;padding-top:28px}.doc-section h2{font-size:21px;gap:10px;letter-spacing:-.4px}.section-no{font-size:11px;min-width:21px}.article h3{font-size:16px}.article blockquote{padding:15px 16px;font-size:13px}.article pre{margin-left:-4px;margin-right:-4px;padding:14px;font-size:11px}.article pre code{font-size:10px}.article table{font-size:12px;min-width:580px}.article th,.article td{padding:11px 13px}.intro>p:first-child,.intro>p:nth-child(2){font-size:11px}.footer>div{padding:20px 22px;display:block;line-height:1.9}.footer span{display:block}.diagram svg{min-width:720px}.diagram figcaption{font-size:10px}.mobile-contents nav{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
@media print{@page{size:A4;margin:17mm 15mm}body{background:white;font-size:10px;line-height:1.55;color:#172b40}.topbar{background:white;color:#263d53;border-color:#dce5ec}.topbar-inner{padding:5px 0;font-size:8px}.topbar .status{color:#7e6b40}.brand svg{display:none}.hero{background:#101c30!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}.hero-inner{padding:24px;grid-template-columns:1.1fr .9fr}.hero h1{font-size:32px}.hero .subtitle{font-size:11px}.hero .eyebrow{font-size:8px;margin-bottom:15px}.hero-foot{margin:0 24px;padding:12px 0;font-size:8px}.pill{font-size:8px}.decision-inner{margin:0;padding:15px 0;gap:15px}.decision b{font-size:10px}.decision span{font-size:8px}.decision-band{background:white}.sidebar,.mobile-contents,.back-top{display:none}.report-shell{display:block;padding:0;max-width:none}.article{border:0;box-shadow:none;border-radius:0;padding:15px 0}.doc-section{margin-top:20px;padding-top:20px}.doc-section h2{font-size:18px;break-after:avoid;page-break-after:avoid;margin-bottom:14px}.article h3{font-size:12px;break-after:avoid;page-break-after:avoid;margin-top:18px}.article p{margin-bottom:11px;orphans:3;widows:3}.article li{margin:4px 0}.article table{min-width:0;font-size:9px;line-height:1.5}.article th,.article td{padding:7px 8px}.table-wrap{overflow:visible;border:1px solid #dfe7ef}.article tr{break-inside:avoid;page-break-inside:avoid}thead{display:table-header-group}.article td code{font-size:8px}.article code{font-size:9px}.article pre{white-space:pre-wrap;font-size:9px;break-inside:avoid}.article pre code{font-size:8px;white-space:pre-wrap;overflow-wrap:anywhere}.article blockquote{font-size:10px;padding:12px 15px;break-inside:avoid}.diagram{break-inside:avoid;-webkit-print-color-adjust:exact;print-color-adjust:exact}.diagram-scroll{overflow:visible}.diagram svg{min-width:0}.diagram figcaption{font-size:8px}.footer>div{padding:12px 0;font-size:8px}.footer{background:white}.intro>p:first-child,.intro>p:nth-child(2){font-size:9px}.article .citation{font-size:8px}a{color:inherit}}
'''
logo = '<svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><ellipse cx="16" cy="16" rx="14" ry="7" stroke="#73e4c3" transform="rotate(-32 16 16)"/><circle cx="16" cy="16" r="4" fill="#73e4c3"/><circle cx="27" cy="8" r="2" fill="#b3a6ff"/></svg>'
html = f'''<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Blueprint teknis Rubber Intelligence Platform: arsitektur, sumber data, model pengetahuan, galaksi, keamanan dan roadmap untuk karet alam.">
<title>Rubber Intelligence Platform — Blueprint v1.0</title>
<style>{css}</style>
</head>
<body id="atas">
<header class="topbar"><div class="topbar-inner"><div class="brand">{logo}<span>RUBBER / INTELLIGENCE</span></div><div class="status"><i></i>Dokumen desain · bukan data live</div></div></header>
<div class="hero">
<div class="hero-inner">
<div class="hero-copy"><div class="eyebrow">TECHNICAL BLUEPRINT / 001</div>
<h1>Rubber<br><em>Intelligence</em> Platform.</h1>
<p class="subtitle">Memori industri karet alam—dari data mentah menuju hubungan, kejadian, dan bukti yang dapat ditelusuri.</p>
<div class="pills"><span class="pill">Karet alam</span><span class="pill">Provenance-first</span><span class="pill">Galaxy interface</span></div>
</div>
<div class="hero-art">{galaxy_svg(hero=True)}</div>
</div>
<div class="hero-foot"><span><strong>v1.0</strong> &nbsp;/&nbsp; 15 Oktober 2026 &nbsp;/&nbsp; Rancangan dari nol</span><span>ARSIPKAN &nbsp;·&nbsp; VALIDASI &nbsp;·&nbsp; HUBUNGKAN &nbsp;·&nbsp; TELUSURI</span></div>
</div>
<div class="decision-band"><div class="decision-inner">
<div class="decision"><b>Memori sebelum intelligence</b><span>Data asli, versi, waktu, dan bukti.</span></div>
<div class="decision"><b>Otomatis, tetap terkendali</b><span>Sumber disetujui; cakupan terlihat.</span></div>
<div class="decision"><b>Galaksi yang dapat dijelaskan</b><span>Setiap garis memiliki makna.</span></div>
</div></div>
<div class="report-shell">
<aside class="sidebar" aria-label="Daftar isi"><div class="sidebar-title">DALAM BLUEPRINT INI</div><nav>{nav_html}</nav><div class="sidebar-note">Nama produk adalah nama kerja. Belum ada kolektor aktif atau data perusahaan terhubung.<br><a class="back-top" href="#atas">↑ Kembali ke awal</a></div></aside>
<main><details class="mobile-contents"><summary>Daftar isi · 16 bagian + referensi</summary><nav>{nav_html}</nav></details>{str(article)}
<p class="end-note">Dokumen ini mandiri: seluruh diagram dan gaya tertanam, tanpa library, font, atau gambar eksternal. Tautan referensi memerlukan koneksi bila dibuka. Versi sumber yang dapat diedit tersedia sebagai <strong>blueprint.md</strong>.</p>
</main></div>
<footer class="footer"><div><span>RUBBER INTELLIGENCE PLATFORM / BLUEPRINT v1.0</span><span>15 Oktober 2026 · Rancangan teknis, belum implementasi</span></div></footer>
</body></html>'''
(ROOT / 'blueprint.html').write_text(html, encoding='utf-8')
print(f'Written: {ROOT / "blueprint.html"} ({len(html):,} chars)')
print(f'Markdown: {len(text.split()):,} words; sections: {len(nav)-2}')
