from decimal import Decimal
from typing import Dict, List

from login.models import Transaction
from .parsers import ParsedTransaction, parse_csv, parse_xlsx
from .dedupe import filter_new


CATEGORY_KEYWORDS = {
    'rent': ['rent'],
    'transport': ['cab', 'uber', 'ola', 'bus', 'train', 'metro', 'fuel', 'petrol', 'diesel'],
    'health': ['doctor', 'medicine', 'medical', 'hospital', 'pharmacy', 'clinic'],
    'groceries': ['grocery', 'groceries', 'vegetable', 'milk', 'supermarket', 'bigbasket', 'dmart'],
    'entertainment': ['movie', 'cinema', 'game', 'netflix', 'spotify', 'prime', 'hotstar', 'zee', 'bookmyshow'],
    'shopping': ['shopping', 'clothes', 'shoes', 'amazon', 'flipkart', 'myntra', 'ajio', 'meesho'],
    'food': ['food', 'lunch', 'dinner', 'breakfast', 'coffee', 'tea', 'snack', 'restaurant', 'swiggy', 'zomato', 'dominos', 'pizza'],
    'utilities': ['bill', 'electricity', 'wifi', 'internet', 'recharge', 'gas', 'water', 'postpaid', 'airtel', 'jio', 'vi'],
    'lend': ['lend', 'given', 'advance'],
}


def infer_category(title: str) -> str:
    v = (title or '').lower()
    for cat, words in CATEGORY_KEYWORDS.items():
        for w in words:
            if w in v:
                return cat
    return 'other'


def import_transactions(user, file_obj) -> Dict:
    content = file_obj.read()
    filename = (getattr(file_obj, 'name', '') or '').lower()
    parsed: List[ParsedTransaction] = []
    if filename.endswith('.csv'):
        parsed = parse_csv(content)
    elif filename.endswith(('.xlsx', '.xlsm')):
        parsed = parse_xlsx(content)
    else:
        # try to sniff
        try:
            if content.strip().startswith((b'<', b'{')):
                raise ValueError('unsupported file')
            parsed = parse_csv(content)
        except Exception:
            try:
                parsed = parse_xlsx(content)
            except Exception:
                raise ValueError('Unsupported file format. Upload CSV or XLSX.')
    if not parsed:
        raise ValueError('No valid transactions found in file')
    to_create = filter_new(user, parsed)
    created = []
    for p in to_create:
        created.append(
            Transaction(
                user=user,
                title=p.title,
                amount=p.amount,
                txn_type=p.txn_type,
                category=infer_category(p.title),
                date=p.date,
                note=p.note,
            )
        )
    Transaction.objects.bulk_create(created)
    return {'total': len(parsed), 'imported': len(created), 'skipped': len(parsed) - len(created)}
