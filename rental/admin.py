from django.contrib import admin
from .models import Storage, Shelf, Tag, Product, Order, OrderItem, DiscountCode

@admin.register(Storage)
class StorageAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']

@admin.register(Shelf)
class ShelfAdmin(admin.ModelAdmin):
    list_display = ['storage', 'number']
    list_filter = ['storage']
    search_fields = ['storage__name', 'number']

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent']
    list_filter = ['parent']
    search_fields = ['name']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'article', 'quantity', 'available_quantity', 'daily_price', 'shelf', 'created_at']
    list_filter = ['shelf__storage', 'tags', 'created_at']
    search_fields = ['name', 'article', 'description']
    filter_horizontal = ['tags']
    readonly_fields = ['created_at']

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'price']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'contact_person', 'phone1', 'status', 'payment_status', 'total_amount', 'created_at']
    list_filter = ['status', 'payment_status', 'created_by_admin', 'created_at']
    search_fields = ['contact_person', 'phone1', 'phone2']
    readonly_fields = ['created_at', 'total_amount']
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('Контактная информация', {
            'fields': ('contact_person', 'phone1', 'phone2')
        }),
        ('Период аренды', {
            'fields': ('rental_start', 'rental_end')
        }),
        ('Статусы', {
            'fields': ('status', 'payment_status')
        }),
        ('Дополнительная информация', {
            'fields': ('comment', 'total_amount', 'created_by_admin', 'created_at')
        }),
    )

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'price']
    list_filter = ['order__status', 'product']
    search_fields = ['order__contact_person', 'product__name']


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_percent', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['code']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('code', 'discount_percent')
        }),
        ('Настройки', {
            'fields': ('is_active',)
        }),
        ('Служебная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )