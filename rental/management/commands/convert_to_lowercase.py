from django.core.management.base import BaseCommand
from rental.models import Product, Tag, Order

class Command(BaseCommand):
    help = 'Конвертирует существующие данные в нижний регистр'

    def handle(self, *args, **options):
        # Конвертируем продукты
        products = Product.objects.all()
        for product in products:
            product.name = product.name.lower()
            product.article = product.article.upper()
            if product.description:
                product.description = product.description.lower()
            product.save()
        self.stdout.write(self.style.SUCCESS(f'Обновлено {products.count()} товаров'))
        
        # Конвертируем теги
        tags = Tag.objects.all()
        for tag in tags:
            tag.name = tag.name.lower()
            tag.save()
        self.stdout.write(self.style.SUCCESS(f'Обновлено {tags.count()} тегов'))
        
        # Конвертируем заказы
        orders = Order.objects.all()
        for order in orders:
            order.contact_person = ' '.join(word.capitalize() for word in order.contact_person.split())
            if order.comment:
                order.comment = order.comment.lower()
            order.save()
        self.stdout.write(self.style.SUCCESS(f'Обновлено {orders.count()} заказов'))