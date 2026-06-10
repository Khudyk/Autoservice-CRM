"""URL-маршрути для керування співробітниками та автентифікації.

Містить маршрути для CRUD-операцій зі співробітниками, а також
стандартні маршрути входу та виходу з системи (login/logout).
"""

from django.contrib.auth import views as auth_views
from django.urls import path

from accounts.views import (
    employee_create,
    employee_delete,
    employee_list,
    employee_update,
)

urlpatterns = [
    path('', employee_list, name='employee_list'),
    path('create/', employee_create, name='employee_create'),
    path('<int:pk>/edit/', employee_update, name='employee_update'),
    path('<int:pk>/delete/', employee_delete, name='employee_delete'),
    # Авторизація
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html',
        ),
        name='login',
    ),
    path(
        'logout/',
        auth_views.LogoutView.as_view(),
        name='logout',
    ),
]
