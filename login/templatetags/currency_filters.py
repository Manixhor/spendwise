from django import template
from decimal import Decimal

register = template.Library()

CURRENCY_SYMBOLS = {
    'inr': '₹',
    'usd': '$',
}


def _format_with_symbol(value, symbol='₹', show_plus=False, use_indian_commas=True):
    """Core formatter: handles sign, decimals, and comma grouping."""
    try:
        num = float(value) if value else 0.0
        is_negative = num < 0
        abs_num = abs(num)
        formatted = f'{abs_num:,.2f}'
        parts = formatted.split('.')
        integer_part = parts[0].replace(',', '')
        decimal_part = parts[1] if len(parts) > 1 else '00'

        if use_indian_commas:
            # Indian number system: last 3 digits, then groups of 2
            if len(integer_part) <= 3:
                result = integer_part
            else:
                last_three = integer_part[-3:]
                remaining = integer_part[:-3]
                groups = []
                while remaining:
                    groups.append(remaining[-2:])
                    remaining = remaining[:-2]
                result = ','.join(reversed(groups)) + ',' + last_three
        else:
            # International commas: every 3 digits
            result = f'{int(integer_part):,}'

        result = f'{result}.{decimal_part}'

        if is_negative:
            return f'−{symbol}{result}'
        elif show_plus and num > 0:
            return f'+{symbol}{result}'
        else:
            return f'{symbol}{result}'
    except (ValueError, TypeError):
        return f'{symbol}0.00'


@register.filter(name='indian_currency')
def indian_currency(value, show_plus=False):
    """Format with Indian comma notation and rupee symbol (backward-compatible)."""
    return _format_with_symbol(value, symbol='₹', show_plus=show_plus, use_indian_commas=True)


@register.filter(name='currency')
def currency(value, currency_code='inr', show_plus=False):
    """
    Currency-aware formatting.
    Usage in templates: {{ value|currency:profile.currency }}
    Or with show_plus: {{ value|currency:"inr" }}
    """
    code = str(currency_code).strip().lower() if currency_code else 'inr'
    symbol = CURRENCY_SYMBOLS.get(code, '₹')
    use_indian = code == 'inr'
    return _format_with_symbol(value, symbol=symbol, show_plus=show_plus, use_indian_commas=use_indian)


@register.filter(name='indian_number')
def indian_number(value):
    """Format number with Indian comma notation without symbol."""
    try:
        num = float(value) if value else 0.0
        is_negative = num < 0
        abs_num = abs(num)
        formatted = f'{abs_num:,.2f}'
        parts = formatted.split('.')
        integer_part = parts[0].replace(',', '')
        decimal_part = parts[1] if len(parts) > 1 else '00'

        if len(integer_part) <= 3:
            result = integer_part
        else:
            last_three = integer_part[-3:]
            remaining = integer_part[:-3]
            groups = []
            while remaining:
                groups.append(remaining[-2:])
                remaining = remaining[:-2]
            result = ','.join(reversed(groups)) + ',' + last_three
        result = f'{result}.{decimal_part}'
        if is_negative:
            return f'-{result}'
        return result
    except (ValueError, TypeError):
        return '0.00'


@register.filter(name='currency_symbol')
def currency_symbol(currency_code):
    """Return the symbol for a currency code."""
    return CURRENCY_SYMBOLS.get(str(currency_code).strip().lower(), '₹')


@register.filter(name='currency_plus')
def currency_plus(value, currency_code='inr'):
    """Format with + prefix for positive values. Usage: {{ value|currency_plus:profile.currency }}"""
    code = str(currency_code).strip().lower() if currency_code else 'inr'
    symbol = CURRENCY_SYMBOLS.get(code, '₹')
    use_indian = code == 'inr'
    return _format_with_symbol(value, symbol=symbol, show_plus=True, use_indian_commas=use_indian)


@register.filter(name='currency_short')
def currency_short(value, currency_code='inr'):
    """Format with k/M suffix for large values. Usage: {{ value|currency_short:profile.currency }}"""
    code = str(currency_code).strip().lower() if currency_code else 'inr'
    symbol = CURRENCY_SYMBOLS.get(code, '₹')
    try:
        num = float(value) if value else 0.0
        if abs(num) >= 1_00_00_000:
            display = num / 1_00_00_000
            suffix = 'M'
        elif abs(num) >= 1000:
            display = num / 1000
            suffix = 'k'
        else:
            return f'{symbol}{int(round(num))}'
        digits = 1 if abs(display) < 10 and display % 1 else 0
        return f'{symbol}{display:.{digits}f}{suffix}'
    except (ValueError, TypeError):
        return f'{symbol}0'


@register.filter(name='usd_currency')
def usd_currency(value, show_plus=False):
    """Format with US comma notation and dollar symbol."""
    return _format_with_symbol(value, symbol='$', show_plus=show_plus, use_indian_commas=False)
