from django.db import migrations, models
import random

def generate_barcode(existing_barcodes):
    """Генерирует уникальный 13-значный EAN-13 штрих-код"""
    while True:
        # Префикс для внутреннего использования (200-299)
        prefix = "200"
        # Генерируем 9 случайных цифр
        main_code = ''.join([str(random.randint(0, 9)) for _ in range(9)])
        # Собираем 12 цифр
        code_without_check = prefix + main_code
        
        # Вычисляем контрольную цифру для EAN-13
        odd_sum = sum(int(code_without_check[i]) for i in range(0, 12, 2))
        even_sum = sum(int(code_without_check[i]) for i in range(1, 12, 2))
        total = odd_sum + (even_sum * 3)
        check_digit = (10 - (total % 10)) % 10
        
        barcode = code_without_check + str(check_digit)
        
        # Проверяем уникальность
        if barcode not in existing_barcodes:
            existing_barcodes.add(barcode)
            return barcode

def populate_barcodes(apps, schema_editor):
    Product = apps.get_model('rental', 'Product')
    existing_barcodes = set()
    
    # Собираем существующие штрих-коды (если есть)
    for product in Product.objects.exclude(barcode='').exclude(barcode__isnull=True):
        existing_barcodes.add(product.barcode)
    
    # Генерируем штрих-коды для товаров без них
    for product in Product.objects.filter(barcode=''):
        product.barcode = generate_barcode(existing_barcodes)
        product.save()

def reverse_populate_barcodes(apps, schema_editor):
    # При откате миграции ничего не делаем
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('rental', '0004_alter_product_article'),
    ]

    operations = [
        # Сначала добавляем поле без уникальности
        migrations.AddField(
            model_name='product',
            name='barcode',
            field=models.CharField(blank=True, default='', max_length=13, verbose_name='Штрих-код'),
        ),
        # Заполняем штрих-коды
        migrations.RunPython(populate_barcodes, reverse_populate_barcodes),
        # Затем делаем поле уникальным
        migrations.AlterField(
            model_name='product',
            name='barcode',
            field=models.CharField(blank=True, max_length=13, unique=True, verbose_name='Штрих-код'),
        ),
    ]