# accounts/templatetags/filters.py
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Ambil nilai dari dictionary dengan key yang berupa variabel"""
    if dictionary is None:
        return None
    return dictionary.get(key)