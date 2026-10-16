from datetime import datetime
from decimal import Decimal
import pytest
from backend.domain import number,observed_date,normalize_row,validate_mapping

@pytest.mark.parametrize('value,locale,want',[
 ('15.000,50','id-ID','15000.50'),('15000','id-ID','15000'),('Rp 15.000','id-ID','15000'),
 ('15,000.50','en-US','15000.50'),('2.35','en-US','2.35'),('2,35','id-ID','2.35'),
 (2.35,'id-ID','2.35'),(0,'id-ID','0'),('-15','id-ID','-15')])
def test_number(value,locale,want): assert number(value,locale)==Decimal(want)

@pytest.mark.parametrize('value,locale', [('2.35','id-ID'),('1,2,3','en-US'),('1.22.000','id-ID'),('nan','en-US'),(float('inf'),'id-ID'),(True,'id-ID'),('','id-ID')])
def test_invalid_number(value,locale):
 with pytest.raises(ValueError): number(value,locale)

@pytest.mark.parametrize('value,fmt,want', [('2026-10-15','iso','2026-10-15'),('15/10/2026','dmy','2026-10-15'),('10/15/2026','mdy','2026-10-15'),('2026-10-15T00:00:00','dmy','2026-10-15'),(datetime(2026,10,15),'iso','2026-10-15')])
def test_dates(value,fmt,want): assert observed_date(value,fmt)==want

def test_ambiguous_date_not_guessed():
 with pytest.raises(ValueError): observed_date('01/02/2026','iso')
 assert observed_date('01/02/2026','dmy')=='2026-02-01'
 assert observed_date('01/02/2026','mdy')=='2026-01-02'

@pytest.fixture
def config():
 return {'sheet':'CSV','fields':{k:k for k in ['date','supplier','material','price','currency','unit','weight_basis','drc']},'options':{'number_format':'id-ID','date_format':'iso','drc_scale':'percent'},'scope_confirmed':True}
@pytest.fixture
def cells():
 return {'date':'2026-10-15','supplier':'Koperasi Contoh','material':'Bokar','price':'15.000','currency':'IDR','unit':'kg','weight_basis':'basah','drc':'60'}

def test_dry_equivalent(config,cells):
 row,errors=normalize_row(cells,config)
 assert not errors
 assert row['price']=='15000'
 assert row['dry_equivalent']=='25000'
 assert row['weight_basis']=='basah'
 assert 'biaya proses' in row['transform_notes'][0]

def test_price_per_tonne(config,cells):
 cells.update(price='15.000.000',unit='t')
 row,errors=normalize_row(cells,config)
 assert not errors and row['price_per_kg']=='15000' and row['dry_equivalent']=='25000'

def test_drc_fraction_explicit(config,cells):
 config['options']['drc_scale']='fraction';cells['drc']='0,6'
 row,errors=normalize_row(cells,config)
 assert not errors and row['drc_percent']=='60'

@pytest.mark.parametrize('field,value', [('price','0'),('price','-1'),('currency',''),('weight_basis',''),('unit','sack'),('drc','120'),('date','2026-02-30')])
def test_invalid_rows_held(config,cells,field,value):
 cells[field]=value
 _,errors=normalize_row(cells,config)
 assert any(e['field']==field for e in errors)

def test_no_silent_drc_assumption(config,cells):
 cells['drc']=''
 row,errors=normalize_row(cells,config)
 assert not errors and row['dry_equivalent'] is None

def test_mapped_blank_not_replaced_by_default(config,cells):
 cells['currency']='';config['options']['default_currency']='IDR'
 _,errors=normalize_row(cells,config)
 assert any(e['field']=='currency' for e in errors)

def test_duplicate_column_mapping_rejected(config):
 config['fields']['supplier']='date'
 with pytest.raises(ValueError): validate_mapping(config,[{'key':k,'label':k} for k in config['fields']])
