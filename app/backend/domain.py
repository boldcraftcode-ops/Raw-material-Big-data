from __future__ import annotations

import math
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

FIELDS = [
 {'key':'date','label':'Tanggal','required':True,'aliases':['tanggal','date','tanggal transaksi','tanggal pembelian']},
 {'key':'supplier','label':'Pemasok / organisasi','required':True,'aliases':['pemasok','supplier','nama pemasok','vendor']},
 {'key':'supplier_identifier','label':'ID pemasok internal','required':False,'aliases':['id pemasok','supplier id','kode pemasok']},
 {'key':'location','label':'Lokasi pemasok (dilaporkan)','required':False,'aliases':['lokasi pemasok','lokasi','wilayah','kabupaten']},
 {'key':'material','label':'Material / bentuk karet','required':True,'aliases':['material','bahan','produk','jenis karet']},
 {'key':'grade','label':'Grade / spesifikasi','required':False,'aliases':['grade','spesifikasi','mutu']},
 {'key':'price','label':'Harga','required':True,'aliases':['harga','price','harga satuan','harga beli']},
 {'key':'currency','label':'Mata uang','required':False,'aliases':['mata uang','currency','valuta']},
 {'key':'unit','label':'Unit harga','required':False,'aliases':['unit','unit harga','satuan','satuan harga']},
 {'key':'weight_basis','label':'Basis berat','required':False,'aliases':['basis berat','basis','weight basis']},
 {'key':'drc','label':'KKK / DRC','required':False,'aliases':['kkk persen','kkk','drc','drc percent']},
 {'key':'quantity','label':'Kuantitas (kg)','required':False,'aliases':['kuantitas kg','berat kg','quantity kg','volume kg']},
 {'key':'price_kind','label':'Jenis harga','required':False,'aliases':['jenis harga','price kind','tipe harga']},
]
KEYS = {f['key'] for f in FIELDS}
KINDS = {'dilaporkan','transaksi_internal','penawaran','benchmark'}


def clean(value) -> str:
    if value is None: return ''
    return re.sub(r'\s+', ' ', str(value)).strip()


def label_key(value) -> str:
    return re.sub(r'[^a-z0-9]', '', clean(value).lower())


def suggest_mapping(columns):
    found = {}
    used = set()
    for field in FIELDS:
        aliases = {label_key(x) for x in field['aliases']}
        for col in columns:
            if label_key(col['label']) in aliases and col['key'] not in used:
                found[field['key']] = col['key']
                used.add(col['key'])
                break
    return found


def number(value, locale='id-ID') -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError('Nilai angka kosong atau bukan angka.')
    if isinstance(value, (int, float, Decimal)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('Angka tidak terbatas tidak didukung.')
        result = Decimal(str(value))
    else:
        text = clean(value).replace('\u00a0', '')
        text = re.sub(r'^(Rp\.?|IDR|USD|US\$|\$)\s*', '', text, flags=re.I)
        text = text.replace(' ', '')
        if locale == 'id-ID':
            pattern = r'[+-]?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d+)?'
            if not re.fullmatch(pattern, text):
                raise ValueError('Format angka tidak sesuai Indonesia (contoh 15.000,50).')
            text = text.replace('.', '').replace(',', '.')
        elif locale == 'en-US':
            pattern = r'[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?'
            if not re.fullmatch(pattern, text):
                raise ValueError('Format angka tidak sesuai internasional (contoh 15,000.50).')
            text = text.replace(',', '')
        else:
            raise ValueError('Format angka tidak dikenal.')
        try: result = Decimal(text)
        except InvalidOperation: raise ValueError('Nilai tidak dapat dibaca sebagai angka.')
    if not result.is_finite() or abs(result) >= Decimal('1000000000000'):
        raise ValueError('Nilai angka di luar batas pilot.')
    return result


def decimal_text(value: Decimal | None):
    if value is None: return None
    return format(value.normalize(), 'f')


def observed_date(value, fmt='iso') -> str:
    if isinstance(value, datetime): return value.date().isoformat()
    if isinstance(value, date): return value.isoformat()
    text = clean(value)
    try:
        # ISO is unambiguous, including dates emitted from native Excel date cells.
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
            return date.fromisoformat(text).isoformat()
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}T.*', text):
            return datetime.fromisoformat(text.replace('Z','+00:00')).date().isoformat()
        if fmt == 'iso': raise ValueError()
        pattern = r'\d{1,2}[/\-]\d{1,2}[/\-]\d{4}'
        if not re.fullmatch(pattern, text): raise ValueError()
        form = '%d/%m/%Y' if fmt == 'dmy' else '%m/%d/%Y'
        return datetime.strptime(text.replace('-', '/'), form).date().isoformat()
    except (ValueError, TypeError):
        raise ValueError('Tanggal tidak sesuai format yang dipilih; tanggal ambigu tidak ditebak.')


def validate_mapping(config, columns):
    if not isinstance(config, dict): raise ValueError('Pemetaan harus berupa objek.')
    fields = config.get('fields', {})
    opts = config.get('options', {})
    if not isinstance(fields, dict) or not isinstance(opts, dict): raise ValueError('Struktur pemetaan tidak valid.')
    if set(fields) - KEYS: raise ValueError('Ada field pemetaan yang tidak dikenal.')
    allowed = {c['key'] for c in columns}
    selected = [v for v in fields.values() if v]
    if any(v not in allowed for v in selected): raise ValueError('Kolom pemetaan tidak ditemukan.')
    if len(selected) != len(set(selected)): raise ValueError('Satu kolom tidak boleh dipakai untuk dua field.')
    for field in FIELDS:
        if field['required'] and not fields.get(field['key']):
            raise ValueError(f"Kolom {field['label']} wajib dipetakan.")
    for field, opt in [('currency','default_currency'), ('unit','default_unit'), ('weight_basis','default_basis')]:
        if not fields.get(field) and not opts.get(opt):
            raise ValueError(f'Petakan {field} atau pilih nilai default secara eksplisit.')
    if opts.get('number_format', 'id-ID') not in ['id-ID','en-US']: raise ValueError('Format angka tidak valid.')
    if opts.get('date_format','iso') not in ['iso','dmy','mdy']: raise ValueError('Format tanggal tidak valid.')
    if opts.get('drc_scale','percent') not in ['percent','fraction']: raise ValueError('Skala KKK tidak valid.')
    if opts.get('default_currency') not in [None,'','IDR','USD']: raise ValueError('Mata uang default tidak didukung.')
    if opts.get('default_unit') not in [None,'','kg','t']: raise ValueError('Unit default tidak didukung.')
    if opts.get('default_basis') not in [None,'','basah','kering','produk']: raise ValueError('Basis default tidak didukung.')
    if opts.get('default_price_kind','dilaporkan') not in KINDS: raise ValueError('Jenis harga tidak didukung.')


def normalize_row(cells, config):
    fields, opts = config['fields'], config.get('options', {})
    errors, notes = [], []
    def val(key, default=None):
        col = fields.get(key)
        return cells.get(col) if col else default
    def parse(field, func, default=None, optional=False):
        raw = val(field, default)
        if optional and clean(raw) == '': return None
        try: return func(raw)
        except (ValueError, InvalidOperation, OverflowError) as exc:
            errors.append({'field':field,'message':str(exc) or 'Nilai tidak valid.'})
            return None
    def required_text(v):
        result=clean(v)
        if not result: raise ValueError('Nilai wajib tidak boleh kosong.')
        if len(result)>250: raise ValueError('Teks melebihi 250 karakter.')
        return result
    row = {}
    row['observed_date'] = parse('date', lambda v: observed_date(v,opts.get('date_format','iso')))
    row['supplier'] = parse('supplier',required_text)
    row['supplier_identifier'] = parse('supplier_identifier',required_text,optional=True)
    row['location'] = parse('location',required_text,optional=True)
    row['material'] = parse('material',required_text)
    row['grade'] = parse('grade',required_text,optional=True)
    locale=opts.get('number_format','id-ID')
    def positive(v):
        x=number(v,locale)
        if x<=0: raise ValueError('Nilai harus lebih besar dari nol.')
        return x
    price = parse('price',positive)
    def currency(v):
        x=clean(v).upper()
        if x not in ['IDR','USD']: raise ValueError('Mata uang harus IDR atau USD; tidak ditebak dari harga.')
        return x
    row['currency']=parse('currency',currency,opts.get('default_currency'))
    def unit(v):
        x=clean(v).lower()
        if x in ['kg','kilogram']: return 'kg'
        if x in ['t','ton','tonne','mt']: return 't'
        raise ValueError('Unit harga harus kg atau ton (t).')
    row['unit']=parse('unit',unit,opts.get('default_unit'))
    def basis(v):
        x=clean(v).lower()
        aliases={'basah':'basah','bahan basah':'basah','wet':'basah','kering':'kering','karet kering':'kering','dry':'kering','produk':'produk','product':'produk'}
        if x not in aliases: raise ValueError('Basis berat harus basah, kering, atau produk.')
        return aliases[x]
    row['weight_basis']=parse('weight_basis',basis,opts.get('default_basis'))
    def drc(v):
        raw = clean(v).removesuffix('%') if isinstance(v,str) else v
        x=number(raw,locale)
        if opts.get('drc_scale','percent')=='fraction':
            x *= 100
            notes.append('KKK fraksi dikonversi menjadi persen sesuai konfigurasi pengguna.')
        if not 0 < x <= 100: raise ValueError('KKK harus >0 dan ≤100 persen setelah konversi skala.')
        return x
    drc_value=parse('drc',drc,optional=True)
    quantity=parse('quantity',positive,optional=True)
    def kind(v):
        x=clean(v).lower().replace(' ','_')
        if x not in KINDS: raise ValueError('Jenis harga harus dilaporkan, transaksi_internal, penawaran, atau benchmark.')
        return x
    row['price_kind']=parse('price_kind',kind,opts.get('default_price_kind','dilaporkan'))
    row['price']=decimal_text(price)
    row['drc_percent']=decimal_text(drc_value)
    row['quantity_kg']=decimal_text(quantity)
    per_kg=None
    dry=None
    if price is not None and row['unit']:
        per_kg=price/1000 if row['unit']=='t' else price
        if row['unit']=='t': notes.append('Harga per ton dibagi 1.000 untuk basis per kg; nilai asli tetap dipertahankan.')
        if row['weight_basis']=='basah' and drc_value:
            dry=per_kg/(drc_value/100)
            notes.append('Ekuivalen karet kering = harga/kg basah ÷ (KKK/100). Tidak mencakup biaya proses dan tidak menyetarakan grade.')
        elif row['weight_basis']=='kering': dry=per_kg
    row['price_per_kg']=decimal_text(per_kg)
    row['dry_equivalent']=decimal_text(dry)
    row['transform_notes']=notes
    return row, errors
