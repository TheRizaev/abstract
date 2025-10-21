from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse


def admin_required(view_func):
    """
    Декоратор для проверки прав администратора
    Заменяет user_passes_test(is_admin) в существующих view
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Сохраняем URL для редиректа после входа
            login_url = reverse('admin_login')
            next_url = request.get_full_path()
            if next_url != '/superuser/':
                login_url += f'?next={next_url}'
            return redirect(login_url)
        
        if not request.user.is_staff:
            messages.error(request, 'У вас нет прав доступа к админ панели')
            return redirect('rental:preview')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def superuser_required(view_func):
    """
    Декоратор для функций, требующих права суперпользователя
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_url = reverse('admin_login')
            next_url = request.get_full_path()
            if next_url != '/superuser/':
                login_url += f'?next={next_url}'
            return redirect(login_url)
        
        if not request.user.is_superuser:
            messages.error(request, 'Эта функция доступна только суперпользователям')
            return redirect('admin_dashboard')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper
