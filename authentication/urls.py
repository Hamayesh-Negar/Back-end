from django.urls import path

from .views import (
    LogoutView, RegisterView, LoginView, VerifyTokenView, CheckUsernameView,
    ForgetPasswordView, ResetPasswordView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('verify/', VerifyTokenView.as_view(), name='verify-token'),
    path('check-username/', CheckUsernameView.as_view(), name='check-username'),
    path('forget-password/', ForgetPasswordView.as_view(), name='forget-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
]
