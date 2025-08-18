from django.contrib.auth.base_user import BaseUserManager, AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models


class CustomUserManager(BaseUserManager):

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        user = self.model(username=username, password=password, **extra_fields)
        user.set_password(password)
        user.save()
        return user


class User(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(
        max_length=150, unique=True, help_text='Username')
    email = models.EmailField(blank=True, null=True, help_text='Email')
    phone = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text='Phone number, format: +989XXXXXXXXX',
        validators=[
            RegexValidator(
                regex=r'^(\+\d{1,2})9(\d{9})$',
                message="Mobile number must be entered in the format: '+989XXXXXXXXX'."
            )
        ])
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []
    objects = CustomUserManager()

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_hamayesh_yar(self):
        return self.user_type == User.UserType.HAMAYESH_YAR
