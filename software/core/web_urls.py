from django.contrib.auth import views as auth_views
from django.urls import path

from . import views_web as v

urlpatterns = [
    path("", v.home, name="home"),
    path("login/", auth_views.LoginView.as_view(template_name="core/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", v.dashboard, name="dashboard"),
    path("dashboard/record/", v.doctor_record, name="doctor_record"),
    path("simulator/", v.simulator, name="simulator"),
]
