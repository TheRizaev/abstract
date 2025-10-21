from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def mul(value, arg):
    """Умножает значение на аргумент"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def subtract(value, arg):
    """Вычитает аргумент из значения"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def range_filter(value):
    """Создает range для цикла в шаблоне"""
    try:
        return range(int(value))
    except (ValueError, TypeError):
        return range(0)

@register.filter
def get_item(dictionary, key):
    """Получает элемент из словаря по ключу"""
    return dictionary.get(key)

@register.filter
def div(value, arg):
    """Делит значение на аргумент"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def sub(value, arg):
    """Вычитает аргумент из значения (псевдоним для subtract)"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def add(value, arg):
    """Добавляет аргумент к значению"""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return 0
    
@register.filter
def format_price(value):
    if value is None:
        return "0"
    
    try:
        # Преобразуем в число
        if isinstance(value, str):
            value = float(value)
        elif isinstance(value, Decimal):
            value = float(value)
        
        # Округляем до целого числа
        value = int(round(value))
        
        # Форматируем с пробелами как разделителями тысяч
        return f"{value:,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(value)