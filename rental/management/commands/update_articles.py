from django.core.management.base import BaseCommand
from rental.models import Product
import random

class Command(BaseCommand):
    help = 'Обновляет артикулы товаров, генерирует автоматические артикулы'

    def handle(self, *args, **options):
        def generate_unique_article():
            """Генерирует уникальный 8-значный артикул"""
            while True:
                # Генерируем 8-значный номер
                article = ''.join([str(random.randint(0, 9)) for _ in range(8)])
                
                # Проверяем, что такой артикул не существует
                if not Product.objects.filter(article=article).exists():
                    return article

        # Обновляем товары с пустыми артикулами
        products_updated = 0
        for product in Product.objects.filter(article=''):
            product.article = generate_unique_article()
            product.save()
            products_updated += 1
            self.stdout.write(f'Обновлен артикул для товара: {product.name} -> {product.article}')

        self.stdout.write(
            self.style.SUCCESS(f'Успешно обновлено {products_updated} товаров')
        )