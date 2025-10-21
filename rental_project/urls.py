from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from rental.admin_auth_views import admin_login_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('superuser/login/', admin_login_view, name='admin_login'),  # Отдельный роут для входа
    path('superuser/', include('rental.admin_urls')),
    path('admin/logout/', auth_views.LogoutView.as_view(next_page='/'), name='admin_logout'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('', include('rental.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)