from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsLibraryManager(BasePermission):
    message = "Se requiere el rol de administrador o bibliotecario."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.can_manage_library
        )


class ReadOnlyOrLibraryManager(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.can_manage_library
        )
