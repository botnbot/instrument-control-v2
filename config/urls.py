"""
URL configuration for config project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
import os

from core import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # --- Маршруты для бэкапа и синхронизации ---
    path('backup/', views.backup_view, name='backup_view'),
    path('backup/download/<str:filename>/', views.backup_download, name='backup_download'),
    path('backup/restore/', views.restore_view, name='restore_view'),
    path('sync-timecontrol/', views.sync_timecontrol_view, name='sync_timecontrol'),

    # --- Основные маршруты проекта ---
    path('', include('user.urls')),
    path('', include('core.urls')),

    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
]

if settings.DEBUG:
    # Раздача медиа-файлов
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Раздача статических файлов (CSS, JS, логотипы)
    if hasattr(settings, 'STATICFILES_DIRS') and settings.STATICFILES_DIRS:
        for static_dir in settings.STATICFILES_DIRS:
            urlpatterns += static(settings.STATIC_URL, document_root=static_dir)
    else:
        urlpatterns += static(settings.STATIC_URL, document_root=os.path.join(settings.BASE_DIR, 'static'))