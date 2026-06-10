"""URL-маршрути для керування компаніями.

Надає маршрути для перегляду списку, створення та редагування компаній.
"""

from django.urls import path

from company.views import company_list, company_create, company_update

urlpatterns = [
    path("", company_list, name="company_list"),
    path("create/", company_create, name="company_create"),
    path("<int:pk>/edit/", company_update, name="company_update"),
]
