from django.urls import path
from . import admin_views
from . import admin_auth_views

urlpatterns = [
    path('login/', admin_auth_views.admin_login_view, name='admin_login'),
    path('logout/', admin_auth_views.admin_logout_view, name='admin_logout'),

    path('', admin_views.admin_dashboard, name='admin_dashboard'),
    path('orders/', admin_views.admin_orders, name='admin_orders'),
    path('orders/<int:order_id>/', admin_views.admin_order_detail, name='admin_order_detail'),
    path('orders/<int:order_id>/edit/', admin_views.edit_order, name='edit_order'),
    path('orders/<int:order_id>/update-status/', admin_views.update_order_status, name='update_order_status'),
    
    # Управление стойками и полками
    path('storage/', admin_views.storage_management, name='storage_management'),
    path('storage/add/', admin_views.add_storage, name='add_storage'),
    path('storage/<int:storage_id>/edit/', admin_views.edit_storage, name='edit_storage'),
    path('storage/<int:storage_id>/delete/', admin_views.delete_storage, name='delete_storage'),
    path('shelf/<int:shelf_id>/edit/', admin_views.edit_shelf, name='edit_shelf'),
    path('shelf/<int:shelf_id>/delete/', admin_views.delete_shelf, name='delete_shelf'),
    
    # Управление товарами
    path('products/', admin_views.product_management, name='product_management'),
    path('products/add/', admin_views.add_product, name='add_product'),
    path('products/<int:product_id>/edit/', admin_views.edit_product, name='edit_product'),
    path('products/<int:product_id>/delete/', admin_views.delete_product, name='delete_product'),
    path('inventory/', admin_views.inventory_view, name='inventory_view'),
    
    # Создание заявок
    path('create-order/', admin_views.admin_create_order, name='admin_create_order'),
    
    # Управление тегами
    path('tags/', admin_views.tag_management, name='tag_management'),
    path('api/tags/children/', admin_views.get_tag_children, name='get_tag_children'),
    path('api/tags/structure/', admin_views.tag_structure_api, name='tag_structure_api'),
    
    # НОВОЕ: API для автозаполнения названий товаров
    path('api/product-name-autocomplete/', admin_views.product_name_autocomplete, name='product_name_autocomplete'),

    # Штрих-коды
    path('barcode-scanner/', admin_views.barcode_scanner, name='barcode_scanner'),
    path('api/barcode/add-to-cart/', admin_views.barcode_add_to_cart, name='barcode_add_to_cart'),
    path('api/barcode/remove-from-cart/', admin_views.barcode_remove_from_cart, name='barcode_remove_from_cart'),
    path('api/barcode/clear-cart/', admin_views.barcode_clear_cart, name='barcode_clear_cart'),
    path('api/barcode/get-cart/', admin_views.barcode_get_cart, name='barcode_get_cart'),
    path('api/barcode/lookup/', admin_views.barcode_lookup, name='barcode_lookup'),
    path('barcode/generate/<int:product_id>/', admin_views.generate_barcode_image, name='generate_barcode_image'),
    path('barcode/download/<int:product_id>/', admin_views.download_barcode, name='download_barcode'),
    path('barcodes/print/', admin_views.print_all_barcodes, name='print_all_barcodes'),

    path('discount-codes/', admin_views.discount_codes_management, name='discount_codes_management'),
    path('api/check-discount-code/', admin_views.check_discount_code_api, name='check_discount_code_api'),
]