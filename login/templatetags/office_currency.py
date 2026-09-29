"""Exact, Indian-grouped amount formatting for the Office ledger."""

from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


def _format_office_amount(value, *, symbol=True, plus=False):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal("0")
    if not amount.is_finite():
        amount = Decimal("0")

    negative = amount < 0
    whole, fraction = format(abs(amount), ".2f").split(".")
    if len(whole) > 3:
        tail = whole[-3:]
        head = whole[:-3]
        groups = []
        while head:
            groups.append(head[-2:])
            head = head[:-2]
        whole = ",".join(reversed(groups)) + "," + tail

    prefix = "−" if negative else ("+" if plus and amount > 0 else "")
    return f"{prefix}{'₹' if symbol else ''}{whole}.{fraction}"


@register.filter
def office_currency(value):
    return _format_office_amount(value)


@register.filter
def office_currency_plus(value):
    return _format_office_amount(value, plus=True)


@register.filter
def office_indian_number(value):
    return _format_office_amount(value, symbol=False)
