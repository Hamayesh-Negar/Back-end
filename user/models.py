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

    def get_conference_memberships(self):
        return self.conference_memberships.select_related('conference', 'role').all()

    def has_conference_permission(self, conference, permission_codename):
        try:
            membership = self.conference_memberships.get(
                conference=conference, status='active')
            return membership.has_permission(permission_codename)
        except:
            return False

    def get_conference_membership_status(self, conference):
        try:
            membership = self.conference_memberships.get(conference=conference)
            return membership.status, membership
        except:
            return None, None

    def check_conference_access(self, conference):
        status, membership = self.get_conference_membership_status(conference)

        if not membership:
            return False, "You are not a member of this conference."

        if status == 'suspended':
            return False, "Membership suspended."
        elif status == 'inactive':
            return False, "Membership inactive."

        return True, membership

    def get_conference_role(self, conference):
        try:
            membership = self.conference_memberships.get(
                conference=conference, status='active')
            return membership.role
        except:
            return None


class UserPreference(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='preference',
        help_text='User associated with this preference'
    )
    selected_conference = models.ForeignKey(
        'conference.Conference',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_preferences',
        help_text='User\'s currently selected conference'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Preference'
        verbose_name_plural = 'User Preferences'

    def __str__(self):
        return f"{self.user.username}'s preference"
