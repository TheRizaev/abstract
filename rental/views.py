from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.template.loader import render_to_string
from .models import Product, Order, OrderItem, Tag
from .forms import OrderForm
import json
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO
import os
from .services import smart_search_service
from django.db.models import Q, Case, When, IntegerField, Value, F
from django.db.models.functions import Length
import re
import logging
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

logger = logging.getLogger(__name__)

def preview_page(request):
    return render(request, 'rental/preview.html')

def product_list(request):
    # Получаем параметры поиска и фильтрации
    search_query = request.GET.get('search', '').strip()
    tag_filter = request.GET.get('tag', '')
    page_number = request.GET.get('page', 1)
    
    # Сортировка тегов
    sort_preference = request.session.get('tag_sort_preference', 'order')
    
    if sort_preference == 'alphabetical':
        root_tags = Tag.objects.filter(parent=None).order_by('name')
    elif sort_preference == 'creation_date':
        root_tags = Tag.objects.filter(parent=None).order_by('id')
    else:  # order
        root_tags = Tag.objects.filter(parent=None).order_by('order', 'name')
    
    # Инициализация переменных
    selected_tag = None
    selected_tag_children = []
    products = Product.objects.all()
    search_type = 'all'
    
    # Обработка поиска - ВСЕГДА используем умный поиск
    if search_query:
        try:
            logger.info(f"Выполняется умный поиск для: '{search_query}'")
            smart_products = smart_search_service.smart_search(search_query)
            
            if smart_products:
                products = smart_products
                search_type = 'smart'
                logger.info(f"Умный поиск вернул {len(products)} товаров")
            else:
                products = []
                search_type = 'smart'
                logger.info("Умный поиск не нашел товаров")
                
        except Exception as e:
            logger.error(f"Ошибка умного поиска: {e}")
            expanded_query = smart_search_service.expand_search_query(search_query)
            products = Product.objects.filter(
                Q(name__icontains=search_query) | 
                Q(article__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(name__icontains=expanded_query) |
                Q(description__icontains=expanded_query)
            ).distinct().order_by('-created_at')  # ИЗМЕНЕНО: сортировка по дате
            search_type = 'fallback'
            messages.warning(request, 'Умный поиск временно недоступен, используется расширенный поиск.')
    
    # Обработка фильтрации по тегам
    if tag_filter:
        try:
            selected_tag = Tag.objects.get(id=tag_filter)
            descendant_tags = selected_tag.get_descendants()
            all_tags = [selected_tag] + descendant_tags
            
            if search_query:
                if isinstance(products, list):
                    filtered_products = []
                    for product in products:
                        if any(tag in product.tags.all() for tag in all_tags):
                            filtered_products.append(product)
                    products = filtered_products
                else:
                    products = products.filter(tags__in=all_tags).distinct()
            else:
                products = Product.objects.filter(tags__in=all_tags).distinct().order_by('-created_at')  # ИЗМЕНЕНО
            
            search_type = 'tag' if not search_query else f'{search_type}_tag'
            
            if sort_preference == 'alphabetical':
                selected_tag_children = selected_tag.get_children().order_by('name')
            elif sort_preference == 'creation_date':
                selected_tag_children = selected_tag.get_children().order_by('id')
            else:
                selected_tag_children = selected_tag.get_children().order_by('order', 'name')
        except Tag.DoesNotExist:
            pass
    
    # ИЗМЕНЕНО: Если нет поиска и фильтров, показываем последние добавленные
    if not search_query and not tag_filter:
        products = Product.objects.all().order_by('-created_at')  # По дате создания, новые сначала
        search_type = 'all'
    
    # НОВОЕ: Пагинация - 30 товаров на страницу
    paginator = Paginator(products, 30)
    
    try:
        products_page = paginator.page(page_number)
    except PageNotAnInteger:
        products_page = paginator.page(1)
    except EmptyPage:
        products_page = paginator.page(paginator.num_pages)
    
    # Подсчет результатов
    products_count = paginator.count
    
    context = {
        'products': products_page,  # ИЗМЕНЕНО: передаем объект страницы
        'root_tags': root_tags,
        'selected_tag': tag_filter,
        'selected_tag_obj': selected_tag,
        'selected_tag_children': selected_tag_children,
        'search_query': search_query,
        'search_type': search_type,
        'products_count': products_count,
        'paginator': paginator,  # НОВОЕ
        'page_obj': products_page,  # НОВОЕ
        'is_paginated': paginator.num_pages > 1,  # НОВОЕ
    }
    
    return render(request, 'rental/product_list.html', context)


def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'rental/product_detail.html', {'product': product})

def cart_view(request):
    cart = request.session.get('cart', {})
    cart_items = []
    total = 0
    
    for product_id, item_data in cart.items():
        try:
            product = Product.objects.get(id=product_id)
            
            # Поддержка разных форматов корзины
            if isinstance(item_data, int):
                # Старый формат - только количество
                quantity = item_data
                days = 1
            elif isinstance(item_data, dict):
                # Новый формат - словарь с quantity и days
                quantity = item_data.get('quantity', 1)
                days = item_data.get('days', 1)
            else:
                # Неизвестный формат, пропускаем
                continue
            
            # Рассчитываем стоимость (цена за день * количество * дни)
            item_total = product.daily_price * quantity * days
            
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'days': days,
                'total': item_total
            })
            
            total += item_total
            
        except Product.DoesNotExist:
            # Удаляем несуществующие товары из корзины
            pass
    
    # Очищаем корзину от несуществующих товаров
    valid_cart = {}
    for product_id, item_data in cart.items():
        try:
            Product.objects.get(id=product_id)
            valid_cart[product_id] = item_data
        except Product.DoesNotExist:
            pass
    
    if len(valid_cart) != len(cart):
        request.session['cart'] = valid_cart
        request.session.modified = True
    
    context = {
        'cart_items': cart_items,
        'total': total
    }
    return render(request, 'rental/cart.html', context)

def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        days = int(request.POST.get('days', 1))
        
        if quantity > product.available_quantity:
            messages.error(request, f'Недостаточно товара на складе. Доступно: {product.available_quantity}')
            return redirect(request.META.get('HTTP_REFERER', 'rental:product_detail'), product_id=product_id)
        
        cart = request.session.get('cart', {})
        
        # Получаем текущий элемент из корзины
        current_item = cart.get(str(product_id))
        
        # Проверяем формат данных в корзине
        if current_item is None:
            # Товара нет в корзине
            current_quantity = 0
        elif isinstance(current_item, int):
            # Старый формат - только количество
            current_quantity = current_item
        elif isinstance(current_item, dict):
            # Новый формат - словарь с quantity и days
            current_quantity = current_item.get('quantity', 0)
        else:
            # Неизвестный формат
            current_quantity = 0
        
        # Проверяем, не превышает ли общее количество доступное
        if current_quantity + quantity > product.available_quantity:
            messages.error(request, f'Недостаточно товара на складе. Доступно: {product.available_quantity}, уже в корзине: {current_quantity}')
            return redirect(request.META.get('HTTP_REFERER', 'rental:product_detail'), product_id=product_id)
        
        # Сохраняем в новом формате
        cart[str(product_id)] = {
            'quantity': current_quantity + quantity,
            'days': days
        }
        
        request.session['cart'] = cart
        request.session.modified = True
        
        messages.success(request, f'{product.name} добавлен в корзину на {days} дней')
        
        # Возвращаемся на предыдущую страницу
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        else:
            # Если нет referrer, возвращаемся на страницу товара
            return redirect('rental:product_detail', product_id=product_id)
    
    # Если не POST запрос, возвращаемся на страницу товара
    return redirect('rental:product_detail', product_id=product_id)

def remove_from_cart(request, product_id):
    cart = request.session.get('cart', {})
    
    if str(product_id) in cart:
        try:
            product = Product.objects.get(id=product_id)
            cart.pop(str(product_id), None)
            request.session['cart'] = cart
            request.session.modified = True
            messages.success(request, f'{product.name} удален из корзины')
        except Product.DoesNotExist:
            cart.pop(str(product_id), None)
            request.session['cart'] = cart
            request.session.modified = True
            messages.success(request, 'Товар удален из корзины')
    else:
        messages.error(request, 'Товар не найден в корзине')
    
    return redirect('rental:cart')

def cart_count_api(request):
    """API для получения количества товаров в корзине"""
    cart = request.session.get('cart', {})
    count = len(cart)
    return JsonResponse({'count': count})

def checkout(request):
    cart = request.session.get('cart', {})
    
    if not cart:
        messages.error(request, 'Корзина пуста')
        return redirect('rental:cart')
    
    if request.method == 'POST':
        # Передаем пользователя в форму для определения доступности поля deposit_amount
        form = OrderForm(request.POST, user=request.user)
        if form.is_valid():
            order = form.save(commit=False)
            
            # ИСПРАВЛЕНО: Правильный расчет общей суммы
            total = 0
            rental_days = (order.rental_end - order.rental_start).days + 1
            
            for product_id, item_data in cart.items():
                try:
                    product = Product.objects.get(id=product_id)
                    
                    if isinstance(item_data, int):
                        quantity = item_data
                        days = rental_days  # Используем дни из формы заказа
                    else:
                        quantity = item_data.get('quantity', 1)
                        # Игнорируем дни из корзины, используем дни из заказа
                        days = rental_days
                    
                    # Правильный расчет: цена за день * количество * дни аренды
                    item_total = product.daily_price * quantity * days
                    total += item_total
                except Product.DoesNotExist:
                    pass
            
            order.total_amount = total
            order.total_before_discount = total
            
            # Применяем скидку если есть
            discount_code = form.cleaned_data.get('discount_code')
            if discount_code and hasattr(form, 'discount_code_obj'):
                order.apply_discount(form.discount_code_obj)
            
            order.created_by_admin = request.user.is_staff if request.user.is_authenticated else False
            
            # Если заявка создается админом, автоматически подтверждаем
            if order.created_by_admin:
                order.status = 'confirmed'
            
            order.save()
            
            # Создаем позиции заявки
            for product_id, item_data in cart.items():
                try:
                    product = Product.objects.get(id=product_id)
                    
                    if isinstance(item_data, int):
                        quantity = item_data
                    else:
                        quantity = item_data.get('quantity', 1)
                    
                    # ИСПРАВЛЕНО: Цена указывается за единицу товара за весь период аренды из заказа
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price=product.daily_price * rental_days  # Цена за единицу за весь период
                    )
                    
                    # Если заявка подтверждена, списываем товар
                    if order.status == 'confirmed':
                        product.available_quantity -= quantity
                        product.save()
                        
                except Product.DoesNotExist:
                    pass
            
            # Очищаем корзину
            request.session['cart'] = {}
            
            messages.success(request, 'Заявка успешно создана!')
            return redirect('rental:order_success', order_id=order.id)
    else:
        # Передаем пользователя в форму и при GET запросе
        form = OrderForm(user=request.user)
    
    # ИСПРАВЛЕНО: Подготавливаем данные корзины для отображения с правильным расчетом
    cart_items = []
    total = 0
    
    # Получаем предварительные даты из GET параметров или используем значения по умолчанию
    rental_start = request.GET.get('rental_start')
    rental_end = request.GET.get('rental_end')
    
    if rental_start and rental_end:
        try:
            from datetime import datetime
            start_date = datetime.strptime(rental_start, '%Y-%m-%d').date()
            end_date = datetime.strptime(rental_end, '%Y-%m-%d').date()
            rental_days = (end_date - start_date).days + 1
        except:
            rental_days = 1
    else:
        rental_days = 1
    
    for product_id, item_data in cart.items():
        try:
            product = Product.objects.get(id=product_id)
            
            if isinstance(item_data, int):
                quantity = item_data
                # Используем rental_days вместо дней из корзины
                days = rental_days
            else:
                quantity = item_data.get('quantity', 1)
                # Используем rental_days вместо дней из корзины
                days = rental_days
            
            # Правильный расчет
            item_total = product.daily_price * quantity * days
            
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'days': days,
                'total': item_total
            })
            
            total += item_total
        except Product.DoesNotExist:
            pass
    
    context = {
        'form': form,
        'cart_items': cart_items,
        'total': total,
        'rental_days': rental_days
    }
    return render(request, 'rental/checkout.html', context)

def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    context = {'order': order}
    return render(request, 'rental/order_success.html', context)

def download_order_pdf(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    # Импорты для PDF
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase import pdfmetrics
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from django.conf import settings
    
    # Создаем PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, 
                           topMargin=2*cm, bottomMargin=2*cm)
    
    # Регистрируем шрифты из папки static/fonts/
    try:
        fonts_dir = os.path.join(settings.BASE_DIR, 'static', 'fonts')
        
        font_files = ['TT.ttf']
        bold_font_files = ['TTB.ttf']
        
        font_registered = False
        bold_font_registered = False
        
        for font_file in font_files:
            font_path = os.path.join(fonts_dir, font_file)
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('CustomFont', font_path))
                    font_registered = True
                    print(f"Зарегистрирован шрифт: {font_file}")
                    break
                except Exception as e:
                    print(f"Ошибка регистрации шрифта {font_file}: {e}")
                    continue
        
        for bold_font_file in bold_font_files:
            bold_font_path = os.path.join(fonts_dir, bold_font_file)
            if os.path.exists(bold_font_path):
                try:
                    pdfmetrics.registerFont(TTFont('CustomFont-Bold', bold_font_path))
                    bold_font_registered = True
                    print(f"Зарегистрирован жирный шрифт: {bold_font_file}")
                    break
                except Exception as e:
                    print(f"Ошибка регистрации жирного шрифта {bold_font_file}: {e}")
                    continue
        
        if font_registered:
            font_name = 'CustomFont'
        else:
            font_name = 'Times-Roman'
            print("Используется встроенный шрифт Times-Roman")
            
        if bold_font_registered:
            font_name_bold = 'CustomFont-Bold'
        else:
            font_name_bold = 'Times-Bold'
            print("Используется встроенный жирный шрифт Times-Bold")
            
    except Exception as e:
        print(f"Общая ошибка при работе со шрифтами: {e}")
        font_name = 'Times-Roman'
        font_name_bold = 'Times-Bold'
    
    # Стили с поддержкой кириллицы
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName=font_name_bold,
        fontSize=18,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2c3e50')
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontName=font_name_bold,
        fontSize=14,
        spaceAfter=12,
        textColor=colors.HexColor('#34495e')
    )
    
    # НОВЫЙ: Стиль для текста в ячейках таблицы с переносом
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=8,  # Уменьшенный размер
        leading=10,  # Межстрочный интервал
        wordWrap='CJK'  # Перенос слов
    )
    
    cell_style_bold = ParagraphStyle(
        'CellStyleBold',
        parent=styles['Normal'],
        fontName=font_name_bold,
        fontSize=8,
        leading=10,
        wordWrap='CJK'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10,
        spaceAfter=4
    )
    
    # Элементы документа
    story = []
    
    # Заголовок
    title_text = f"ЗАЯВКА НА АРЕНДУ ОБОРУДОВАНИЯ № {order.id}"
    story.append(Paragraph(title_text, title_style))
    story.append(Spacer(1, 15))
    
    # Информация о заявке
    story.append(Paragraph("ИНФОРМАЦИЯ О ЗАЯВКЕ", header_style))
    
    # ИЗМЕНЕНО: Используем Paragraph для всех ячеек
    info_data = [
        [Paragraph('Дата создания:', cell_style_bold), 
         Paragraph(order.created_at.strftime('%d.%m.%Y %H:%M'), cell_style)],
        [Paragraph('Период аренды:', cell_style_bold), 
         Paragraph(f"{order.rental_start.strftime('%d.%m.%Y')} - {order.rental_end.strftime('%d.%m.%Y')}", cell_style)],
        [Paragraph('Контактное лицо:', cell_style_bold), 
         Paragraph(order.contact_person, cell_style)],
        [Paragraph('Телефон:', cell_style_bold), 
         Paragraph(order.phone1, cell_style)],
        [Paragraph('Статус заявки:', cell_style_bold), 
         Paragraph(order.get_status_display(), cell_style)],
        [Paragraph('Статус оплаты:', cell_style_bold), 
         Paragraph(order.get_payment_status_display(), cell_style)],
    ]
    
    if order.phone2:
        info_data.insert(4, [Paragraph('Телефон 2:', cell_style_bold), 
                            Paragraph(order.phone2, cell_style)])
    
    if order.production_name:
        info_data.insert(3, [Paragraph('Продакшен:', cell_style_bold), 
                            Paragraph(order.production_name, cell_style)])
    
    if order.project_name:
        info_data.insert(4, [Paragraph('Проект:', cell_style_bold), 
                            Paragraph(order.project_name, cell_style)])
    
    if order.comment:
        # Обрабатываем многострочный комментарий
        comment_text = order.comment.replace('\n', '<br/>')
        info_data.insert(-2, [Paragraph('Комментарий:', cell_style_bold), 
                             Paragraph(comment_text, cell_style)])
    
    if order.created_by_admin:
        info_data.insert(-2, [Paragraph('Создана администратором:', cell_style_bold), 
                             Paragraph('Да', cell_style)])
    
    # Таблица с информацией
    info_table = Table(info_data, colWidths=[5*cm, 13*cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 20))
    
    # Товары
    story.append(Paragraph("ТОВАРЫ В ЗАЯВКЕ", header_style))
    
    # Заголовки таблицы товаров с Paragraph
    items_data = [[
        Paragraph('№', cell_style_bold),
        Paragraph('Наименование', cell_style_bold),
        Paragraph('Артикул', cell_style_bold),
        Paragraph('Штрих-код', cell_style_bold),
        Paragraph('Кол-во', cell_style_bold),
        Paragraph('Цена/период', cell_style_bold),
        Paragraph('Сумма', cell_style_bold),
        Paragraph('Место', cell_style_bold)
    ]]
    
    total_sum = 0
    for i, item in enumerate(order.items.all(), 1):
        item_total = item.price * item.quantity
        total_sum += item_total
        
        # Обрезаем длинные названия и используем Paragraph
        name = item.product.get_display_name()
        if len(name) > 25:
            name = name[:25] + '...'
        
        items_data.append([
            Paragraph(str(i), cell_style),
            Paragraph(name, cell_style),
            Paragraph(item.product.article, cell_style),
            Paragraph(getattr(item.product, 'barcode', '-'), cell_style),
            Paragraph(f"{item.quantity} шт.", cell_style),
            Paragraph(f"{item.price:.0f} сум", cell_style),
            Paragraph(f"{item_total:.0f} сум", cell_style),
            Paragraph(str(item.product.shelf), cell_style)
        ])
    
    # Добавляем итоговую строку
    items_data.append([
        Paragraph('', cell_style),
        Paragraph('', cell_style),
        Paragraph('', cell_style),
        Paragraph('', cell_style),
        Paragraph('', cell_style),
        Paragraph('ИТОГО:', cell_style_bold),
        Paragraph(f"{order.total_amount:.0f} сум", cell_style_bold),
        Paragraph('', cell_style)
    ])
    
    # Оптимизированные размеры колонок
    items_table = Table(items_data, colWidths=[0.7*cm, 3.5*cm, 2*cm, 2.2*cm, 1.3*cm, 2*cm, 2*cm, 1.5*cm])
    items_table.setStyle(TableStyle([
        # Заголовок
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), font_name_bold),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        
        # Содержимое
        ('FONTNAME', (0, 1), (-1, -2), font_name),
        ('ALIGN', (0, 1), (0, -2), 'CENTER'),  # Номера
        ('ALIGN', (2, 1), (-1, -2), 'CENTER'),  # Числа и коды
        ('ALIGN', (1, 1), (1, -2), 'LEFT'),    # Названия слева
        
        # Итоговая строка
        ('FONTNAME', (0, -1), (-1, -1), font_name_bold),
        ('FONTSIZE', (0, -1), (-1, -1), 9),
        ('ALIGN', (0, -1), (-1, -1), 'CENTER'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ecf0f1')),
        ('SPAN', (0, -1), (5, -1)),
        
        # Сетка
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Отступы
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    story.append(items_table)
    story.append(Spacer(1, 20))
    
    # Дополнительная информация
    story.append(Paragraph("ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ", header_style))
    
    rental_days = (order.rental_end - order.rental_start).days + 1
    
    additional_info = [
        [Paragraph('Количество дней аренды:', cell_style_bold), 
         Paragraph(f"{rental_days} дн.", cell_style)],
        [Paragraph('Средняя стоимость в день:', cell_style_bold), 
         Paragraph(f"{order.total_amount / rental_days:.0f} сум/день", cell_style)],
        [Paragraph('Общая сумма:', cell_style_bold), 
         Paragraph(f"{order.total_amount:.0f} сум", cell_style)],
    ]
    
    if order.deposit_amount > 0:
        additional_info.insert(2, [Paragraph('Сумма залога:', cell_style_bold), 
                                  Paragraph(f"{order.deposit_amount:.0f} сум", cell_style)])
    
    additional_table = Table(additional_info, colWidths=[6*cm, 8*cm])
    additional_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
    ]))
    
    story.append(additional_table)
    story.append(Spacer(1, 30))
    
    # Подпись
    footer_style = ParagraphStyle(
        'Footer', 
        parent=styles['Normal'], 
        fontSize=8,
        fontName=font_name,
        textColor=colors.grey, 
        alignment=TA_RIGHT
    )
    
    footer_text = f"Дата формирования документа: {(timezone.now() + timedelta(hours=5)).strftime('%d.%m.%Y %H:%M')}"
    story.append(Paragraph(footer_text, footer_style))
    
    # Генерируем PDF
    try:
        doc.build(story)
        print("PDF успешно создан")
    except Exception as e:
        print(f"Ошибка при создании PDF: {e}")
        # Создаем упрощенный PDF как fallback
        buffer.seek(0)
        buffer.truncate()
        
        from reportlab.pdfgen import canvas
        p = canvas.Canvas(buffer, pagesize=A4)
        
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, 800, f"ЗАЯВКА НА АРЕНДУ ОБОРУДОВАНИЯ № {order.id}")
        
        p.setFont("Helvetica", 10)
        y = 750
        p.drawString(50, y, f"Дата создания: {order.created_at.strftime('%d.%m.%Y %H:%M')}")
        y -= 20
        p.drawString(50, y, f"Контактное лицо: {order.contact_person}")
        y -= 20
        p.drawString(50, y, f"Телефон: {order.phone1}")
        y -= 20
        p.drawString(50, y, f"Период аренды: {order.rental_start.strftime('%d.%m.%Y')} - {order.rental_end.strftime('%d.%m.%Y')}")
        y -= 20
        p.drawString(50, y, f"Общая сумма: {order.total_amount} сум")
        
        y -= 40
        p.drawString(50, y, "ТОВАРЫ:")
        y -= 20
        
        for i, item in enumerate(order.items.all(), 1):
            if y < 50:
                p.showPage()
                y = 800
            p.drawString(70, y, f"{i}. {item.product.name} - {item.quantity} шт. - {item.get_total()} сум")
            y -= 15
        
        p.save()
    
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="order_{order.id}.pdf"'
    
    return response

def update_cart_quantity(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        new_quantity = int(request.POST.get('quantity', 1))
        
        cart = request.session.get('cart', {})
        
        if str(product_id) in cart:
            try:
                product = Product.objects.get(id=product_id)
                
                if new_quantity > product.available_quantity:
                    messages.error(request, f'Недостаточно товара на складе. Доступно: {product.available_quantity}')
                elif new_quantity <= 0:
                    # Удаляем товар из корзины
                    cart.pop(str(product_id), None)
                    messages.success(request, 'Товар удален из корзины')
                else:
                    # Обновляем количество
                    current_item = cart[str(product_id)]
                    
                    if isinstance(current_item, int):
                        # Старый формат - конвертируем в новый
                        cart[str(product_id)] = {
                            'quantity': new_quantity,
                            'days': 1
                        }
                    elif isinstance(current_item, dict):
                        # Новый формат - обновляем количество
                        cart[str(product_id)]['quantity'] = new_quantity
                    else:
                        # Неизвестный формат - создаем новый
                        cart[str(product_id)] = {
                            'quantity': new_quantity,
                            'days': 1
                        }
                    
                    messages.success(request, 'Количество обновлено')
                
                request.session['cart'] = cart
                request.session.modified = True
                
            except Product.DoesNotExist:
                messages.error(request, 'Товар не найден')
        else:
            messages.error(request, 'Товар не найден в корзине')
    
    return redirect('rental:cart')

def update_cart_days(request):
    product_id = request.GET.get('product_id')
    new_days = request.GET.get('days')
    
    if not product_id or not new_days:
        messages.error(request, 'Неверные параметры')
        return redirect('rental:cart')
    
    try:
        new_days = int(new_days)
        if new_days < 1 or new_days > 365:
            messages.error(request, 'Количество дней должно быть от 1 до 365')
            return redirect('rental:cart')
    except (ValueError, TypeError):
        messages.error(request, 'Неверное количество дней')
        return redirect('rental:cart')
    
    cart = request.session.get('cart', {})
    
    if str(product_id) in cart:
        try:
            product = Product.objects.get(id=product_id)
            
            # Обновляем количество дней
            current_item = cart[str(product_id)]
            
            if isinstance(current_item, int):
                # Старый формат - конвертируем в новый
                cart[str(product_id)] = {
                    'quantity': current_item,
                    'days': new_days
                }
            elif isinstance(current_item, dict):
                # Новый формат - обновляем дни
                cart[str(product_id)]['days'] = new_days
            else:
                # Неизвестный формат - создаем новый
                cart[str(product_id)] = {
                    'quantity': 1,
                    'days': new_days
                }
            
            request.session['cart'] = cart
            request.session.modified = True
            
            messages.success(request, f'Количество дней для "{product.name}" изменено на {new_days}')
            
        except Product.DoesNotExist:
            messages.error(request, 'Товар не найден')
    else:
        messages.error(request, 'Товар не найден в корзине')
    
    return redirect('rental:cart')

# API endpoint для переключения типа поиска
def toggle_search_type(request):
    """
    API endpoint для переключения между умным и обычным поиском
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            use_smart_search = data.get('use_smart_search', True)
            
            # Сохраняем предпочтение в сессии
            request.session['use_smart_search'] = use_smart_search
            
            return JsonResponse({
                'success': True,
                'use_smart_search': use_smart_search
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Метод не поддерживается'})


def smart_search_status(request):
    """
    API для проверки доступности ChatGPT API
    """
    try:
        # Проверяем, настроен ли API ключ
        from django.conf import settings
        api_key_configured = bool(getattr(settings, 'OPENAI_API_KEY', None))
        
        return JsonResponse({
            'available': api_key_configured and smart_search_service.api_available,
            'configured': api_key_configured
        })
    except Exception as e:
        return JsonResponse({
            'available': False,
            'configured': False,
            'error': str(e)
        })

def check_discount_code_api(request):
    """API для проверки скидочного кода"""
    from .models import DiscountCode
    
    code = request.GET.get('code', '').strip().upper()
    
    if not code:
        return JsonResponse({'valid': False, 'error': 'Код не указан'})
    
    try:
        discount_code = DiscountCode.objects.get(code=code, is_active=True)
        return JsonResponse({
            'valid': True,
            'code': discount_code.code,
            'discount_percent': float(discount_code.discount_percent)
        })
    except DiscountCode.DoesNotExist:
        return JsonResponse({'valid': False, 'error': 'Неверный код скидки или код неактивен'})