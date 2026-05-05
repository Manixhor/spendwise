from django import template
from decimal import Decimal

register = template.Library()


@register.filter(name='indian_currency')
def indian_currency(value, show_plus=False):
    """
    Format number with Indian comma notation and rupee symbol.
    Example: 1234567.89 -> ₹12,34,567.89
    """
    try:
        # Convert to float
        num = float(value) if value else 0.0
        
        # Determine sign
        is_negative = num < 0
        abs_num = abs(num)
        
        # Format with 2 decimal places
        formatted = f"{abs_num:,.2f}"
        
        # Convert to Indian comma notation (lakhs and crores)
        parts = formatted.split('.')
        integer_part = parts[0].replace(',', '')
        decimal_part = parts[1] if len(parts) > 1 else '00'
        
        # Indian number system: last 3 digits, then groups of 2
        if len(integer_part) <= 3:
            result = integer_part
        else:
            last_three = integer_part[-3:]
            remaining = integer_part[:-3]
            
            # Add commas every 2 digits from right to left
            groups = []
            while remaining:
                groups.append(remaining[-2:])
                remaining = remaining[:-2]
            
            result = ','.join(reversed(groups)) + ',' + last_three
        
        # Add decimal part
        result = f"{result}.{decimal_part}"
        
        # Add sign
        if is_negative:
            result = f"-₹{result}"
        elif show_plus and num > 0:
            result = f"+₹{result}"
        else:
            result = f"₹{result}"
        
        return result
    except (ValueError, TypeError):
        return "₹0.00"


@register.filter(name='indian_number')
def indian_number(value):
    """
    Format number with Indian comma notation without rupee symbol.
    Example: 1234567.89 -> 12,34,567.89
    """
    try:
        num = float(value) if value else 0.0
        is_negative = num < 0
        abs_num = abs(num)
        
        formatted = f"{abs_num:,.2f}"
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
        
        result = f"{result}.{decimal_part}"
        
        if is_negative:
            result = f"-{result}"
        
        return result
    except (ValueError, TypeError):
        return "0.00"
