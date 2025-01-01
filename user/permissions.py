from rest_framework import permissions
from rest_framework.permissions import BasePermission


class IsHamayeshManager(BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (request.user.is_authenticated and request.user.is_hamayesh_manager) or request.user.is_superuser


class IsHamayeshYar(BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (request.user.is_authenticated and request.user.is_hamayesh_yar) or request.user.is_superuser


class IsSuperuser(BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_superuser


class CanEditBasicFields(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        if request.method in ['PUT', 'PATCH']:
            allowed_fields = {'name', 'description'}
            request_data = set(request.data.keys())
            return not (request_data - allowed_fields)

        return False


class CanEditAllFields(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return True
