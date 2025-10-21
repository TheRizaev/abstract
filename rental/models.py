from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import random
import string
import markdown
from django.core.validators import MaxValueValidator, MinValueValidator

class Storage(models.Model):
    name = models.CharField(max_length=10, verbose_name='Название стойки')
    
    def save(self, *args, **kwargs):
        self.name = self.name.strip().upper()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Стойка'
        verbose_name_plural = 'Стойки'

class Shelf(models.Model):
    storage = models.ForeignKey(Storage, on_delete=models.CASCADE, verbose_name='Стойка')
    number = models.CharField(max_length=10, verbose_name='Номер полки')
    
    def save(self, *args, **kwargs):
        self.number = self.number.strip()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.storage.name}{self.number}"
    
    class Meta:
        verbose_name = 'Полка'
        verbose_name_plural = 'Полки'

class Tag(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название тега')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, verbose_name='Родительский тег')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок сортировки')
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.get_display_name()} → {self.get_display_name()}"
        return self.get_display_name()
    
    def save(self, *args, **kwargs):
        self.name = self.name.strip().lower()
        super().save(*args, **kwargs)

    def get_display_name(self):
        return self.name.capitalize()

    def get_full_path(self):
        path = []
        current = self
        while current:
            path.insert(0, current.get_display_name())
            current = current.parent
        return ' → '.join(path)
    
    def get_level(self):
        """Возвращает уровень вложенности тега"""
        level = 0
        current = self.parent
        while current:
            level += 1
            current = current.parent
        return level
    
    def get_children(self):
        """Возвращает прямых потомков"""
        return Tag.objects.filter(parent=self).order_by('order', 'name')
    
    def get_descendants(self):
        """Возвращает всех потомков (включая потомков потомков)"""
        descendants = []
        for child in self.get_children():
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants
    
    def get_ancestors(self):
        """Возвращает всех предков"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors
    
    def is_ancestor_of(self, tag):
        """Проверяет, является ли текущий тег предком другого тега"""
        return self in tag.get_ancestors()
    
    def is_descendant_of(self, tag):
        """Проверяет, является ли текущий тег потомком другого тега"""
        return tag in self.get_ancestors()
    
    def get_root(self):
        """Возвращает корневой тег"""
        current = self
        while current.parent:
            current = current.parent
        return current
    
    def is_leaf(self):
        """Проверяет, является ли тег листом (нет потомков)"""
        return not self.get_children().exists()
    
    class Meta:
        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'
        ordering = ['order', 'name']

class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название')
    photo = models.ImageField(upload_to='products/', verbose_name='Фото')
    article = models.CharField(max_length=50, unique=True, verbose_name='Артикул', blank=True)
    barcode = models.CharField(max_length=13, unique=True, verbose_name='Штрих-код', blank=True)
    description = models.TextField(blank=True, verbose_name='Описание')
    quantity = models.IntegerField(default=0, verbose_name='Количество')
    available_quantity = models.IntegerField(default=0, verbose_name='Доступное количество')
    tags = models.ManyToManyField(Tag, blank=True, verbose_name='Теги')
    daily_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена за день')
    shelf = models.ForeignKey(Shelf, on_delete=models.CASCADE, verbose_name='Место хранения')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def generate_ean13_barcode(self):
        """Генерирует уникальный 13-значный EAN-13 штрих-код"""
        while True:
            prefix = "200"
            main_code = ''.join([str(random.randint(0, 9)) for _ in range(9)])
            code_without_check = prefix + main_code
            
            odd_sum = sum(int(code_without_check[i]) for i in range(0, 12, 2))
            even_sum = sum(int(code_without_check[i]) for i in range(1, 12, 2))
            total = odd_sum + (even_sum * 3)
            check_digit = (10 - (total % 10)) % 10
            
            barcode = code_without_check + str(check_digit)
            
            if not Product.objects.filter(barcode=barcode).exists():
                return barcode
    
    def save(self, *args, **kwargs):
        self.name = self.name.strip().lower()
        
        # Если штрих-код не указан, генерируем его
        if not self.barcode:
            self.barcode = self.generate_ean13_barcode()
        
        if not self.pk:  # Если это новый товар (еще не сохранен в БД)
            self.available_quantity = self.quantity

        # Артикул всегда равен штрих-коду
        self.article = self.barcode
        
        if self.description:
            self.description = self.description.strip()
            
        super().save(*args, **kwargs)

    def get_display_name(self):
        """Возвращает название с заглавной буквы"""
        return self.name.capitalize()
    
    def get_display_description(self):
        """Возвращает описание с заглавной буквы"""
        if self.description:
            return self.description
        return ''
    
    def get_description_html(self):
        """Возвращает описание, конвертированное из Markdown в HTML"""
        if self.description:
            description_text = self.get_display_description()
            return markdown.markdown(description_text, extensions=['nl2br'])
        return ''
    
    def get_availability_status(self):
        """Возвращает статус доступности товара с правильной логикой"""
        if self.available_quantity <= 0:
            return 'out'  # Нет в наличии (красный)
        
        # Логика для желтого статуса: только если общее количество >= 50 И доступно < 10
        if self.quantity >= 50 and self.available_quantity < 10:
            return 'low'  # Мало (желтый)
        
        # Во всех остальных случаях - зеленый
        return 'available'  # В наличии (зеленый)
    
    def __str__(self):
        return self.get_display_name()
    
    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'

ORDER_STATUS_CHOICES = [
    ('pending', 'Ожидает подтверждения'),
    ('confirmed', 'Подтверждена'),
    ('completed', 'Завершена'),
    ('rejected', 'Отклонена'),
]

PAYMENT_STATUS_CHOICES = [
    ('unpaid', 'Не оплачена'),
    ('paid', 'Оплачена'),
]

class Order(models.Model):
    contact_person = models.CharField(max_length=200, verbose_name="Контактное лицо")
    phone1 = models.CharField(max_length=20, verbose_name="Основной телефон")
    phone2 = models.CharField(max_length=20, blank=True, verbose_name="Дополнительный телефон")
    production_name = models.CharField(max_length=200, blank=True, verbose_name="Название продакшена")
    project_name = models.CharField(max_length=200, blank=True, verbose_name="Название проекта")
    rental_start = models.DateField(verbose_name="Дата начала аренды")
    rental_end = models.DateField(verbose_name="Дата окончания аренды")
    comment = models.TextField(blank=True, verbose_name="Комментарий")
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending', verbose_name="Статус")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid', verbose_name="Статус оплаты")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Общая сумма")
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Сумма залога")
    
    # Новые поля для скидки
    discount_code = models.CharField(max_length=50, blank=True, null=True, verbose_name="Код скидки")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Процент скидки")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Сумма скидки")
    total_before_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Сумма до скидки")
    
    created_by_admin = models.BooleanField(default=False, verbose_name="Создана администратором")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Заявка"
        verbose_name_plural = "Заявки"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Заявка #{self.id} - {self.contact_person}"
    
    def get_status_display(self):
        return dict(ORDER_STATUS_CHOICES)[self.status]
    
    def get_payment_status_display(self):
        return dict(PAYMENT_STATUS_CHOICES)[self.payment_status]
    
    def get_display_comment(self):
        """Возвращает отформатированный комментарий для отображения"""
        if self.comment:
            # Заменяем переносы строк на <br> для HTML отображения
            return self.comment.replace('\n', '<br>')
        return ""
    
    def get_rental_days(self):
        """Возвращает количество дней аренды"""
        if self.rental_start and self.rental_end:
            return (self.rental_end - self.rental_start).days + 1
        return 0
    
    def get_daily_average(self):
        """Возвращает среднюю стоимость за день"""
        days = self.get_rental_days()
        if days > 0:
            return self.total_amount / days
        return 0
    
    def get_final_total(self):
        """Возвращает финальную сумму с учетом скидки"""
        if self.discount_amount > 0:
            return max(0, self.total_amount - self.discount_amount)
        return self.total_amount

    def apply_discount(self, discount_code_obj):
        """Применяет скидку к заказу"""
        self.discount_code = discount_code_obj.code
        self.discount_percent = discount_code_obj.discount_percent
        self.total_before_discount = self.total_amount
        self.discount_amount = (self.total_amount * self.discount_percent) / 100
        self.total_amount = self.get_final_total()

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name='Заявка')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name='Товар')
    quantity = models.IntegerField(verbose_name='Количество')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
    
    def get_total(self):
        """Возвращает общую стоимость позиции"""
        return self.price * self.quantity
    
    class Meta:
        verbose_name = 'Позиция заявки'
        verbose_name_plural = 'Позиции заявки'

class DiscountCode(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Код скидки")
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, validators=[
        MinValueValidator(0), MaxValueValidator(100)
    ], verbose_name="Процент скидки")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Скидочный код"
        verbose_name_plural = "Скидочные коды"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} ({self.discount_percent}%)"
    
    def save(self, *args, **kwargs):
        # Приводим код к верхнему регистру
        self.code = self.code.upper()
        super().save(*args, **kwargs)