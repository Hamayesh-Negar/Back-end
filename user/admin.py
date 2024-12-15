from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from .models import User


class UserResource(resources.ModelResource):
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'phone',
                  'user_type', 'is_active', 'date_joined')
        export_order = fields


@admin.register(User)
class CustomUserAdmin(UserAdmin, ImportExportModelAdmin):
    resource_class = UserResource

    list_display = (
        'email',
        'get_full_name',
        'phone',
        'get_user_type_badge',
        'get_status_badge',
        'date_joined'
    )
    list_filter = (
        'user_type',
        'is_active',
        'is_staff',
        'date_joined'
    )
    search_fields = (
        'email',
        'first_name',
        'last_name',
        'phone'
    )
    ordering = ('email',)

    fieldsets = (
        (None, {
            'fields': ('email', 'password')
        }),
        ('Personal info', {
            'fields': (
                ('first_name', 'last_name'),
                'phone',
            )
        }),
        ('Permissions', {
            'fields': (
                'user_type',
                ('is_active', 'is_staff', 'is_superuser'),
                'groups',
                'user_permissions',
            ),
            'classes': ('collapse',)
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'phone',
                'password1',
                'password2',
                'user_type',
                'is_active',
                'is_staff',
            ),
        }),
    )

    readonly_fields = ('date_joined', 'last_login')
    filter_horizontal = ('groups', 'user_permissions',)

    def get_full_name(self, obj):
        return obj.get_full_name()

    get_full_name.short_description = 'Full Name'

    def get_user_type_badge(self, obj):
        colors = {
            'SU': 'danger',  # Super User
            'HM': 'success',  # Hamayesh Manager
            'HY': 'info'  # Hamayesh Yar
        }
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            colors.get(obj.user_type, 'secondary'),
            obj.get_user_type_display()
        )

    get_user_type_badge.short_description = 'Role'

    def get_status_badge(self, obj):
        if not obj.is_active:
            return format_html(
                '<span class="badge badge-danger">Inactive</span>'
            )
        if obj.is_superuser:
            return format_html(
                '<span class="badge badge-danger">Superuser</span>'
            )
        if obj.is_staff:
            return format_html(
                '<span class="badge badge-success">Staff</span>'
            )
        return format_html(
            '<span class="badge badge-info">Active</span>'
        )

    get_status_badge.short_description = 'Status'

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        is_superuser = request.user.is_superuser

        if not is_superuser:
            if 'user_type' in form.base_fields:
                form.base_fields['user_type'].disabled = True
            if 'is_superuser' in form.base_fields:
                form.base_fields['is_superuser'].disabled = True
            if 'user_permissions' in form.base_fields:
                form.base_fields['user_permissions'].disabled = True
            if 'groups' in form.base_fields:
                form.base_fields['groups'].disabled = True

        return form

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        # Hamayesh Managers can only see Hamayesh Yars they created
        if request.user.is_hamayesh_manager:
            return qs.filter(
                user_type=User.UserType.HAMAYESH_YAR,
                registered_by=request.user
            )

        return qs.none()

    def has_change_permission(self, request, obj=None):
        if not obj:
            return True
        # Allow superusers to edit anyone
        if request.user.is_superuser:
            return True
        # Allow Hamayesh Managers to edit their Hamayesh Yars
        if request.user.is_hamayesh_manager and obj.user_type == User.UserType.HAMAYESH_YAR:
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        if not obj:
            return True
        # Only superusers can delete users
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new user
            if not request.user.is_superuser:
                # Hamayesh Managers can only create Hamayesh Yars
                obj.user_type = User.UserType.HAMAYESH_YAR
            obj.registered_by = request.user
        super().save_model(request, obj, form, change)

    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
        js = ('js/custom_admin.js',)