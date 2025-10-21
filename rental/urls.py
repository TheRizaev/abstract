from django.urls import path
from . import views

app_name = 'rental'

urlpatterns = [
    path('', views.preview_page, name='preview'),
    path('catalog/', views.product_list, name='product_list'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('cart/', views.cart_view, name='cart'),
    path('cart-count/', views.cart_count_api, name='cart_count_api'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('update-cart-quantity/', views.update_cart_quantity, name='update_cart_quantity'),
    path('update-cart-days/', views.update_cart_days, name='update_cart_days'),
    path('remove-from-cart/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('order-success/<int:order_id>/', views.order_success, name='order_success'),
    path('download-order/<int:order_id>/', views.download_order_pdf, name='download_order_pdf'),
    
    path('api/smart-search-status/', views.smart_search_status, name='smart_search_status'),
    path('api/check-discount-code/', views.check_discount_code_api, name='check_discount_code_api'),
]