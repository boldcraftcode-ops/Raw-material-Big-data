"""Bounded, deterministic spreadsheet assistance. No model, training or external I/O."""
from __future__ import annotations

import hashlib
import json
import re
from .domain import FIELDS, label_key

HEADER_SCAN = 50
EXTRA = {
    'date': ['tgl', 'tgl beli', 'tgl pembelian', 'tgl transaksi', 'tanggal beli', 'transaction date', 'purchase date'],
    'supplier': ['nama supplier', 'nama vendor', 'supplier name', 'penjual'],
    'supplier_identifier': ['kode supplier', 'vendor id', 'supplier code'],
    'material': ['nama bahan', 'nama material', 'bentuk karet', 'rubber material'],
    'price': ['harga rp kg', 'harga idr kg', 'harga usd kg', 'harga per kg', 'harga per ton', 'unit price'],
    'currency': ['kode mata uang', 'ccy'],
    'unit': ['price unit'],
    'quantity': ['berat bersih kg', 'net weight kg', 'qty kg', 'jumlah kg'],
    'drc': ['kkk %', 'drc %'],
}
ALIASES = {field['key']: {label_key(value) for value in field['aliases'] + EXTRA.get(field['key'], [])} for field in FIELDS}
REQUIRED = {field['key'] for field in FIELDS if field['required']}


def column_advice(columns):
    candidates = {field['key']: [] for field in FIELDS}
    for column in columns:
        parts = [part.strip() for part in column['label'].split(' / ')]
        # A meaningful leaf wins over a merged group label; never fuzzy-match values.
        levels = [parts[-1], column['label']] + list(reversed(parts[:-1]))
        for value in levels:
            hits = [key for key, aliases in ALIASES.items() if label_key(value) in aliases]
            if hits:
                if len(hits) == 1:
                    candidates[hits[0]].append({'column': column['key'], 'label': column['label'], 'reason': f'Header cocok dengan alias terdaftar: {value}.'})
                break
    suggestions, reasons, conflicts = {}, [], []
    for field in FIELDS:
        matches = candidates[field['key']]
        if len(matches) == 1:
            suggestions[field['key']] = matches[0]['column']
            reasons.append({'field': field['key'], **matches[0]})
        elif len(matches) > 1:
            conflicts.append({'field': field['key'], 'columns': [item['column'] for item in matches], 'message': f"Lebih dari satu kolom cocok dengan {field['label']}; pilih sendiri."})
    return {'suggested_mapping': suggestions, 'reasons': reasons, 'conflicts': conflicts,
            'missing_required': sorted(REQUIRED - suggestions.keys())}


def _data_like(value):
    if value is None or isinstance(value, bool): return False
    if isinstance(value, (int, float)): return True
    text = str(value).strip()
    return bool(re.match(r'^\d{4}-\d{2}-\d{2}', text) or re.fullmatch(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{4}', text) or re.fullmatch(r'[+-]?[\d.,]+%?', text))


def header_columns(first, second=None):
    width = max(len(first), len(second or []))
    first = list(first) + [None] * (width-len(first))
    second = list(second) + [None] * (width-len(second)) if second is not None else None
    columns, parent = [], ''
    for i, value in enumerate(first):
        top = '' if value is None else str(value).strip()
        if second is None:
            label = top
        else:
            if top: parent = top
            leaf = '' if second[i] is None else str(second[i]).strip()
            label = ' / '.join(dict.fromkeys(item for item in [parent, leaf] if item))
        columns.append({'key': f'c{i}', 'label': label or f'Kolom {i+1}', 'source_blank': not bool(label)})
    return columns


def choose_header(records, override=None):
    """records contain original row_no, line_end and serialised cells, including blanks."""
    choices = []
    for i, record in enumerate(records):
        if record['row_no'] > HEADER_SCAN: break
        values = record['values']
        if not any(value is not None and str(value).strip() for value in values): continue
        for depth in (1, 2):
            second = records[i+1]['values'] if depth == 2 and i+1 < len(records) else None
            if depth == 2:
                if second is None or not any(value is not None and str(value).strip() for value in second): continue
                if any(_data_like(value) for value in second): continue
            columns = header_columns(values, second)
            advice = column_advice(columns)
            mapped = advice['suggested_mapping']
            score = 8*len(REQUIRED & mapped.keys()) + 2*len(mapped) - 3*len(advice['conflicts'])
            score += .05*sum(bool(str(value or '').strip()) for value in values) - .4*(depth-1)
            score -= 6*sum(_data_like(value) for value in values)
            choices.append({'header_row': record['row_no'], 'header_depth': depth,
                            'header_end_row': records[i+depth-1]['line_end'], 'index': i,
                            'columns': columns, 'score': round(score, 3), **advice})
    if not choices: raise ValueError('Header kolom tidak ditemukan dalam 50 baris pertama; raw tetap tersimpan.')
    choices.sort(key=lambda item: (-item['score'], item['header_row'], item['header_depth']))
    chosen = choices[0]
    if override:
        row, depth = override
        chosen = next((item for item in choices if item['header_row'] == row and item['header_depth'] == depth), None)
        if not chosen: raise ValueError('Baris header tidak valid. Pilih 1–50 dan satu atau dua baris header teks; jangan gunakan baris transaksi sebagai header.')
    return chosen, [{'header_row': item['header_row'], 'header_depth': item['header_depth'], 'matched_fields': len(item['suggested_mapping'])} for item in choices[:4]]


def sample_advice(columns, rows):
    advice = column_advice(columns)
    notes, hints = [], {}
    date_key = advice['suggested_mapping'].get('date')
    dates = [str(row['cells'].get(date_key) or '').strip() for row in rows] if date_key else []
    dmy = mdy = ambiguous = False
    for text in dates:
        match = re.fullmatch(r'(\d{1,2})[/\-](\d{1,2})[/\-]\d{4}', text)
        if match:
            a, b = map(int, match.groups())
            dmy |= a > 12 and 1 <= b <= 12
            mdy |= b > 12 and 1 <= a <= 12
            ambiguous |= 1 <= a <= 12 and 1 <= b <= 12
    if dmy and not mdy: hints['date_format'] = 'dmy'
    if mdy and not dmy: hints['date_format'] = 'mdy'
    if (ambiguous and not (dmy or mdy)) or (dmy and mdy): notes.append('Tanggal teks ambigu/campuran; pilih format tanggal secara eksplisit, bukan menebak hari/bulan.')
    id_numbers = en_numbers = False
    for field in ('price', 'quantity', 'drc'):
        key = advice['suggested_mapping'].get(field)
        for row in rows:
            value = row['cells'].get(key) if key else None
            if not isinstance(value, str): continue
            text = value.strip()
            id_numbers |= bool(re.search(r'\d\.\d{3},\d|\d,\d{1,2}$', text))
            en_numbers |= bool(re.search(r'\d,\d{3}\.\d|\d\.\d{1,2}$', text))
    if id_numbers and not en_numbers: hints['number_format'] = 'id-ID'
    if en_numbers and not id_numbers: hints['number_format'] = 'en-US'
    if id_numbers and en_numbers: notes.append('Ada indikasi format angka campuran. Satu aturan mungkin tidak cukup; periksa sumber dan hasil validasi.')
    if advice['suggested_mapping'].get('drc'): notes.append('Skala KKK tidak ditebak dari besar angka. Pastikan persen atau fraksi.')
    if advice['conflicts']: notes.extend(item['message'] for item in advice['conflicts'])
    if advice['missing_required']: notes.append('Belum semua field wajib pembelian dikenali; jangan memaksakan laporan stok/mutu menjadi transaksi pembelian.')
    notes.append('Saran berasal dari alias header dan sampel terbatas; bukan pemahaman AI, bukti isi, atau validasi seluruh file.')
    return {**advice, 'mode': 'local_rules', 'external_ai_used': False,
            'classification': 'purchase_candidate' if len(REQUIRED & advice['suggested_mapping'].keys()) >= 3 else 'other_or_uncertain',
            'sampled_rows': len(rows), 'option_hints': hints, 'notes': notes, 'requires_confirmation': True}


def template_signature(columns):
    labels = [label_key(column['label']) for column in columns]
    if not labels or any(column.get('source_blank') for column in columns) or len(labels) != len(set(labels)):
        return None
    return hashlib.sha256(json.dumps(sorted(labels), separators=(',', ':')).encode()).hexdigest()
