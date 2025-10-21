from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
from django.http import Http404


@never_cache
@csrf_protect
def admin_login_view(request):
    """
    Кастомная страница входа для администраторов
    """
    # Если пользователь уже аутентифицирован и является администратором
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin_dashboard')
        else:
            # Если пользователь не администратор, показываем ошибку
            messages.error(request, 'У вас нет прав доступа к админ панели')
            return redirect('rental:preview')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            user = authenticate(username=username, password=password)
            
            if user is not None:
                # Проверяем, что пользователь является администратором
                if user.is_staff:
                    login(request, user)
                    messages.success(request, f'Добро пожаловать, {user.get_full_name() or user.username}!')
                    
                    # Перенаправляем на админ дашборд или на next URL
                    next_url = request.GET.get('next')
                    if next_url and next_url.startswith('/superuser/'):
                        return redirect(next_url)
                    else:
                        return redirect('admin_dashboard')
                else:
                    # Пользователь существует, но не администратор
                    messages.error(request, 'У вас нет прав доступа к админ панели')
            else:
                messages.error(request, 'Неверное имя пользователя или пароль')
        else:
            # Форма невалидна
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = AuthenticationForm()
    
    context = {
        'form': form,
        'title': 'Вход в админ панель'
    }
    
    return render(request, 'rental/admin/login.html', context)


def admin_logout_view(request):
    """
    Выход из админ панели с редиректом на главную страницу
    """
    from django.contrib.auth import logout
    
    logout(request)
    messages.success(request, 'Вы успешно вышли из системы')
    return redirect('rental:preview')