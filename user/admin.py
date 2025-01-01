from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'phone', 'full_name', 'user_type_badge', 'is_active', 'is_staff')
    list_filter = ('is_active', 'is_staff', 'user_type', 'date_joined')
    search_fields = ('email', 'phone', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    filter_horizontal = ('groups', 'user_permissions',)
    readonly_fields = ('date_joined',)

    fieldsets = (
        (None, {'fields': ('email', 'phone', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name')}),
        (_('Permissions'), {
            'fields': ('user_type', 'is_active', 'is_staff', 'is_superuser',
                       'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'phone', 'password1', 'password2', 'user_type'),
        }),
    )

    def full_name(self, obj):
        return obj.get_full_name()

    full_name.short_description = _('Full Name')

    def user_type_badge(self, obj):
        colors = {
            User.UserType.SUPER_USER: 'red',
            User.UserType.HAMAYESH_MANAGER: 'green',
            User.UserType.HAMAYESH_YAR: 'blue'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px;">{}</span>',
            colors[obj.user_type],
            obj.get_user_type_display()
        )

    user_type_badge.short_description = _('User Type')

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        is_superuser = request.user.is_superuser

        if not is_superuser:
            form.base_fields['user_type'].disabled = True
            form.base_fields['is_superuser'].disabled = True
            form.base_fields['is_staff'].disabled = True
            form.base_fields['user_permissions'].disabled = True
            form.base_fields['groups'].disabled = True

        return form

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(user_type__in=[User.UserType.HAMAYESH_MANAGER, User.UserType.HAMAYESH_YAR])
        return qs

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
