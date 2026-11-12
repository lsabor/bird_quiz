from django import template

register = template.Library()


@register.filter
def pct(value) -> str:
    """0.374 -> '37%', 0.012 -> '1.2%'."""
    try:
        v = float(value) * 100
    except (TypeError, ValueError):
        return ""
    return f"{v:.0f}%" if v >= 10 else f"{v:.1f}%"
