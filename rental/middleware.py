from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages


class AdminAccessMiddleware:
    """
    Middleware для проверки доступа к админ панели через /superuser/
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Проверяем, если запрос идет к админ панели
        if request.path.startswith('/superuser/'):
            # Исключаем страницы, которые не требуют аутентификации
            public_admin_urls = [
                '/superuser/login/',
                '/superuser/logout/',
            ]
            
            # Если это публичная страница админки, пропускаем проверку
            if request.path in public_admin_urls:
                response = self.get_response(request)
                return response
            
            # Проверяем аутентификацию
            if not request.user.is_authenticated:
                # Сохраняем URL для редиректа после входа
                login_url = reverse('admin_login')
                if request.path != '/superuser/':
                    login_url += f'?next={request.path}'
                return redirect(login_url)
            
            # Проверяем права администратора
            if not request.user.is_staff:
                messages.error(request, 'У вас нет прав доступа к админ панели')
                return redirect('rental:preview')

        response = self.get_response(request)
        return response
