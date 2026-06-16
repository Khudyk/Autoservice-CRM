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
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import path, include

from config import views

handler404 = views.page_not_found


def _test_404(request: HttpRequest) -> HttpResponse:
    return render(request, '404.html', {'exception': Exception('Тестова 404 — сторінку не знайдено')}, status=404)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('test-404/', _test_404, name='test_404'),
    path('companies/', include('company.urls')),
    path('employees/', include('accounts.urls')),
    path('vehicles/', include('vehicles.urls')),
    path('worktypes/', include('worktypes.urls')),
    path('suppliers/', include('suppliers.urls')),
    path('parts/', include('parts.urls')),
    path('purchases/', include('purchases.urls')),
    path('workorders/', include('workorders.urls')),
    path('clients/', include('clients.urls')),
    path('permissions/', include('permissions.urls')),
]
