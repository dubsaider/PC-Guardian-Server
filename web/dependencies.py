"""
Зависимости для веб-слоя
Шаблоны и другие зависимости для веб-интерфейса
"""
from jinja2 import Environment, FileSystemLoader

# Настройка шаблонов
templates = Environment(loader=FileSystemLoader("templates"))


def get_templates() -> Environment:
    """Получить экземпляр шаблонов Jinja2"""
    return templates









