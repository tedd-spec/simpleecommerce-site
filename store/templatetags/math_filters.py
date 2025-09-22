from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """Multiply two values"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def add(value, arg):
    """Add two values"""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def sub(value, arg):
    """Subtract two values"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def div(value, arg):
    """Divide two values"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return ''

@register.filter
def round_filter(value, arg=2):
    """Round a value to specified decimal places"""
    try:
        return round(float(value), int(arg))
    except (ValueError, TypeError):
        return value

@register.filter
def format_currency(value):
    """Format value as currency"""
    try:
        return f"${float(value):,.2f}"
    except (ValueError, TypeError):
        return f"${value}"