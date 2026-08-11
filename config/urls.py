"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as django_serve
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView
from login.admin_views import admin_broadcast, admin_dashboard

urlpatterns = [
    path(
        'sw.js',
        never_cache(TemplateView.as_view(
            template_name='sw.js',
            content_type='application/javascript',
        )),
        name='service_worker',
    ),
    path('admin/analytics/', admin_dashboard, name='admin_dashboard'),
    path('admin/broadcast/', admin_broadcast, name='admin_broadcast'),
    path('admin/', admin.site.urls),
    path('', include('login.urls')),
]

# Serve media in production too (Django's static() helper is a no-op when DEBUG=False).
# For larger deployments, replace this with an external object store (S3/Cloudinary) via
# DEFAULT_FILE_STORAGE — but for a small Render app this keeps uploaded avatars working.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        path(
            "media/<path:path>",
            never_cache(django_serve),
            {"document_root": settings.MEDIA_ROOT},
            name="media_serve",
        ),
    ]
