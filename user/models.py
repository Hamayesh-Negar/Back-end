from django.contrib.auth.base_user import BaseUserManager, AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models


class CustomUserManager(BaseUserManager):
    def create_user(self, email, phone, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        if not phone:
            raise ValueError('The Phone field must be set')

        email = self.normalize_email(email)
        user = self.model(email=email, phone=phone, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', User.UserType.SUPER_USER)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email=email, phone=phone, password=password, **extra_fields)

    def create_hamayesh_manager(self, email, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('user_type', User.UserType.HAMAYESH_MANAGER)
        return self.create_user(email=email, phone=phone, password=password, **extra_fields)

    def create_hamayesh_yar(self, email, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('user_type', User.UserType.HAMAYESH_YAR)
        return self.create_user(email=email, phone=phone, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class UserType(models.TextChoices):
        SUPER_USER = 'SU', 'SUPER_USER'
        HAMAYESH_MANAGER = 'HM', 'HAMAYESH_MANAGER'
        HAMAYESH_YAR = 'HY', 'HAMAYESH_YAR'

    email = models.EmailField(unique=True, help_text='Email')
    phone = models.CharField(
        max_length=20,
        unique=True,
        default='+000000000000',
        help_text='Phone number, format: +980123456789',
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Mobile number must be entered in the format: '+980123456789'. Up to 15 digits allowed."
            )
        ])
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    user_type = models.CharField(max_length=2, choices=UserType.choices, default=UserType.HAMAYESH_YAR)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['phone']
    objects = CustomUserManager()

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_hamayesh_manager(self):
        return self.user_type == User.UserType.HAMAYESH_MANAGER

    @property
    def is_hamayesh_yar(self):
        return self.user_type == User.UserType.HAMAYESH_YAR
