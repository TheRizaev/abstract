from django import forms
from django.core.validators import RegexValidator
from .models import Product, Storage, Shelf, Order

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'photo', 'quantity', 'daily_price', 'shelf', 'tags', 'barcode']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название товара'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 6, 
                'placeholder': 'Описание товара (поддерживается Markdown)',
                'style': 'text-transform: none;'  # Убираем любые CSS трансформации текста
            }),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control', 'id': 'photoInput'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'daily_price': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'shelf': forms.Select(attrs={'class': 'form-select'}),
            'tags': forms.CheckboxSelectMultiple(),
            'barcode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Оставьте пустым для автогенерации'})
        }
    
    def clean_description(self):
        """Очищаем описание, сохраняя исходный регистр"""
        description = self.cleaned_data.get('description')
        if description:
            return description.strip()
        return description

class StorageForm(forms.ModelForm):
    class Meta:
        model = Storage
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название стойки'})
        }

class ShelfForm(forms.ModelForm):
    class Meta:
        model = Shelf
        fields = ['storage', 'number']
        widgets = {
            'storage': forms.Select(attrs={'class': 'form-select'}),
            'number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Номер полки'})
        }

class OrderForm(forms.ModelForm):
    # Валидатор для телефонных номеров
    phone_validator = RegexValidator(
        regex=r'^\+998\s?\(\d{2}\)\s?\d{3}-\d{2}-\d{2}$',
        message="Введите номер в формате: +998 (99) 123-45-67"
    )
    
    discount_code = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите код скидки',
            'style': 'text-transform: uppercase;'
        }),
        label="Код скидки"
    )
    
    class Meta:
        model = Order
        fields = [
            'contact_person', 'phone1', 'phone2', 'production_name', 'project_name',
            'rental_start', 'rental_end', 'comment', 'deposit_amount', 'discount_code'
        ]
        widgets = {
            'contact_person': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ФИО контактного лица'
            }),
            'phone1': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+998 (99) 123-45-67'
            }),
            'phone2': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+998 (99) 123-45-67'
            }),
            'production_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название продакшн-компании'
            }),
            'project_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название проекта'
            }),
            'rental_start': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'rental_end': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Дополнительные комментарии'
            }),
            'deposit_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01',
                'placeholder': '0'
            })
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Поле залога доступно только для администраторов
        if not (user and user.is_staff):
            self.fields.pop('deposit_amount', None)
    
    def clean_phone1(self):
        phone = self.cleaned_data.get('phone1')
        if phone:
            # Удаляем все пробелы и символы для проверки
            digits_only = ''.join(filter(str.isdigit, phone))
            if not digits_only.startswith('998') or len(digits_only) != 12:
                raise forms.ValidationError("Номер должен начинаться с +998 и содержать 9 цифр после кода страны")
        return phone
    
    def clean_phone2(self):
        phone = self.cleaned_data.get('phone2')
        if phone:
            # Удаляем все пробелы и символы для проверки
            digits_only = ''.join(filter(str.isdigit, phone))
            if not digits_only.startswith('998') or len(digits_only) != 12:
                raise forms.ValidationError("Номер должен начинаться с +998 и содержать 9 цифр после кода страны")
        return phone
    
    def clean_discount_code(self):
        code = self.cleaned_data.get('discount_code')
        if code:
            code = code.upper().strip()
            try:
                from .models import DiscountCode
                discount_code = DiscountCode.objects.get(code=code, is_active=True)
                self.discount_code_obj = discount_code
                return code
            except DiscountCode.DoesNotExist:
                raise forms.ValidationError("Неверный код скидки или код неактивен")
        return code
    
    def clean(self):
        cleaned_data = super().clean()
        rental_start = cleaned_data.get('rental_start')
        rental_end = cleaned_data.get('rental_end')
        
        if rental_start and rental_end:
            if rental_end < rental_start:
                raise forms.ValidationError("Дата окончания не может быть раньше даты начала аренды")
        
        return cleaned_data