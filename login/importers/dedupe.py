from decimal import Decimal
from typing import List

from login.models import Transaction


def _key_for_txn(t: Transaction) -> tuple:
    return (t.user_id, t.date, str(t.amount), t.txn_type, t.title[:60])


def filter_new(user, parsed_items) -> List:
    existing = set()
    for t in Transaction.objects.filter(user=user):
        existing.add(_key_for_txn(t))
    out = []
    for p in parsed_items:
        k = (user.id, p.date, f'{p.amount:.2f}', p.txn_type, p.title[:60])
        if k not in existing:
            out.append(p)
    return out
