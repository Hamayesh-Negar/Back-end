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
