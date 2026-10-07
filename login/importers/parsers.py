import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable, List, Optional, Tuple


@dataclass
class ParsedTransaction:
    date: datetime.date
    amount: Decimal  # positive magnitude; polarity is txn_type
    txn_type: str  # 'expense' or 'income'
    title: str
    category: str = 'other'
    note: str = ''


def _normalize(s: str) -> str:
    if s is None:
        return ''
    return str(s).strip().replace('\ufeff', '')


def _parse_date(s: str):
    s = _normalize(s)
    if not s:
        raise ValueError('empty date')
    formats = ['%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y', '%d-%b-%Y', '%d-%b-%y', '%b %d, %Y', '%d %b %Y', '%Y/%m/%d']
    for f in formats:
        try:
            return datetime.strptime(s.replace('\xa0', ' '), f).date()
        except Exception:
            continue
    # try ISO
    try:
        return datetime.fromisoformat(s.split(' ')[0]).date()
    except Exception:
        pass
    raise ValueError(f'unparsable date: {s}')


def _clean_amount(s: str) -> Decimal:
    s = _normalize(s).replace(',', '').replace('₹', '').replace('$', '')
    s = re.sub(r'\s+', '', s)
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    if s in ('', '-'):
        raise ValueError('empty amount')
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ValueError(f'unparsable amount: {s}')
    if not d.is_finite() or d == 0:
        raise ValueError(f'zero/invalid amount: {s}')
    return d


def _infer_polarity(amt: Decimal, debit_cols: Iterable[str] | None = None, credit_cols: Iterable[str] | None = None) -> Tuple[str, Decimal]:
    # If explicit debit/credit columns exist, prefer them
    if debit_cols:
        pass
    if amt < 0:
        return 'expense', -amt
    return 'expense', amt  # default to expense unless explicitly credit


def parse_csv(file_content: bytes | str) -> List[ParsedTransaction]:
    if isinstance(file_content, bytes):
        text = file_content.decode('utf-8-sig', errors='replace')
    else:
        text = file_content
    # Try to sniff delimiter
    sample = text[:4096]
    delimiter = ','
    if ';' in sample and sample.count(';') > sample.count(','):
        delimiter = ';'
    elif '\t' in sample and sample.count('\t') > sample.count(','):
        delimiter = '\t'
    f = io.StringIO(text)
    reader = csv.DictReader(f, delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError('CSV has no header row')
    header_map = {normalize_header(h): h for h in reader.fieldnames if h}
    # common column names
    date_keys = ['date', 'txn_date', 'transaction_date', 'entry_date', 'value_date', 'posting_date']
    amt_keys = ['amount', 'amt', 'transaction_amount', 'debit', 'credit', 'withdrawal', 'deposit', 'dr', 'cr']
    desc_keys = ['description', 'narration', 'details', 'particulars', 'transaction_details', 'remarks', 'merchant', 'payee']

    def get(*cands):
        for c in cands:
            if c in header_map:
                return row.get(header_map[c], '')
        return ''

    results = []
    for row in reader:
        try:
            date = _parse_date(get(*date_keys))
        except Exception:
            continue  # skip unparseable rows
        # try amount first; else debit/credit
        amt_raw = get(*amt_keys)
        if amt_raw:
            amt = _clean_amount(amt_raw)
            txn_type = 'expense'
            if amt < 0:
                txn_type, amt_mag = 'expense', -amt
            else:
                # many banks show positive for debits; but we can't know. default expense unless column name says credit
                txn_type, amt_mag = 'expense', amt
            # if came from credit/deposit column explicitly
            for k in ['credit', 'deposit', 'cr']:
                if k in header_map and row.get(header_map[k], '').strip():
                    try:
                        cr = _clean_amount(row.get(header_map[k], ''))
                        if cr > 0:
                            txn_type, amt_mag = 'income', cr
                            break
                    except Exception:
                        pass
            for k in ['debit', 'withdrawal', 'dr']:
                if k in header_map and row.get(header_map[k], '').strip():
                    try:
                        db = _clean_amount(row.get(header_map[k], ''))
                        if db > 0:
                            txn_type, amt_mag = 'expense', db
                            break
                    except Exception:
                        pass
        else:
            continue
        title = _normalize(get(*desc_keys)) or 'Imported transaction'
        if len(title) > 120:
            title = title[:117] + '...'
        results.append(ParsedTransaction(date=date, amount=amt_mag, txn_type=txn_type, title=title))
    return results


def normalize_header(h):
    h = _normalize(h).lower()
    h = re.sub(r'[^a-z0-9_]', '_', h)
    h = re.sub(r'_+', '_', h).strip('_')
    return h


def parse_xlsx(file_content: bytes) -> List[ParsedTransaction]:
    try:
        import openpyxl
    except ImportError:
        raise ValueError('openpyxl not available')
    bio = io.BytesIO(file_content)
    wb = openpyxl.load_workbook(bio, data_only=True, read_only=True)
    ws = wb.active
    rows = list(ws.rows)
    if not rows:
        raise ValueError('empty workbook')
    # header row
    header = [_normalize(c.value) for c in rows[0]]
    header_n = [normalize_header(h) for h in header]
    idx = {k: i for i, k in enumerate(header_n) if k}
    date_idx = None
    for k in ['date', 'txn_date', 'transaction_date', 'posting_date', 'value_date', 'entry_date']:
        if k in idx:
            date_idx = idx[k]; break
    desc_idx = None
    for k in ['description', 'narration', 'particulars', 'details', 'merchant', 'remarks', 'payee']:
        if k in idx:
            desc_idx = idx[k]; break
    amt_idx = None
    for k in ['amount', 'amt', 'transaction_amount']:
        if k in idx:
            amt_idx = idx[k]; break
    db_idx = idx.get('debit') or idx.get('dr') or idx.get('withdrawal')
    cr_idx = idx.get('credit') or idx.get('cr') or idx.get('deposit')
    if date_idx is None or (amt_idx is None and db_idx is None and cr_idx is None):
        raise ValueError('cannot detect required columns')
    results = []
    for r in rows[1:]:
        try:
            dv = r[date_idx].value
            if dv is None:
                continue
            if hasattr(dv, 'date'):
                d = dv.date()
            else:
                d = _parse_date(str(dv))
        except Exception:
            continue
        txn_type = 'expense'; amt_mag = Decimal('0')
        got = False
        if cr_idx is not None and r[cr_idx].value not in (None, ''):
            try:
                cr = _clean_amount(str(r[cr_idx].value))
                if cr > 0:
                    txn_type, amt_mag, got = 'income', cr, True
            except Exception:
                pass
        if not got and db_idx is not None and r[db_idx].value not in (None, ''):
            try:
                db = _clean_amount(str(r[db_idx].value))
                if db > 0:
                    txn_type, amt_mag, got = 'expense', db, True
            except Exception:
                pass
        if not got and amt_idx is not None and r[amt_idx].value not in (None, ''):
            try:
                amt = _clean_amount(str(r[amt_idx].value))
                txn_type, amt_mag = ('expense', -amt) if amt < 0 else ('expense', amt)
                got = True
            except Exception:
                pass
        if not got or amt_mag <= 0:
            continue
        title = ''
        if desc_idx is not None and r[desc_idx].value not in (None, ''):
            title = _normalize(str(r[desc_idx].value))
        if not title:
            title = 'Imported transaction'
        if len(title) > 120:
            title = title[:117] + '...'
        results.append(ParsedTransaction(date=d, amount=amt_mag, txn_type=txn_type, title=title))
    return results
