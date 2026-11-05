from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, render
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import decorators, filters, mixins, permissions, response, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import CreateAPIView
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from biblioteca.models import Author, Book, BookCopy, Category, Loan, User
from biblioteca.permissions import IsLibraryManager, ReadOnlyOrLibraryManager
from biblioteca.serializers import (
    AuthorSerializer,
    BookCopySerializer,
    BookSerializer,
    CategorySerializer,
    LoanSerializer,
    RegistrationSerializer,
    UserSerializer,
)
from biblioteca.services import Conflict, return_loan


def library_home(request):
    search = request.GET.get("q", "").strip()[:100]
    books = Book.objects.select_related("author", "category").annotate(
        available_copies_count=Count(
            "copies",
            filter=Q(copies__status=BookCopy.Status.AVAILABLE),
            distinct=True,
        )
    ).order_by("title", "id").prefetch_related(
        Prefetch(
            "copies",
            queryset=BookCopy.objects.filter(status=BookCopy.Status.AVAILABLE).only(
                "id", "book_id", "inventory_code"
            ),
            to_attr="available_inventory",
        )
    )
    if search:
        books = books.filter(
            Q(title__icontains=search)
            | Q(author__name__icontains=search)
            | Q(category__name__icontains=search)
            | Q(isbn__icontains=search)
        )

    page = Paginator(books, 12).get_page(request.GET.get("page"))
    return render(
        request,
        "biblioteca/home.html",
        {
            "page": page,
            "search": search,
        },
    )


class LoginThrottle(AnonRateThrottle):
    scope = "login"


class RegisterThrottle(AnonRateThrottle):
    scope = "register"


def document_crud(
    tag,
    resource,
    *,
    singular=None,
    public_read=False,
    searchable=False,
    sortable=False,
    description_overrides=None,
    actions=None,
):
    singular = singular or resource
    summaries = {
        "list": f"Listar {resource}",
        "retrieve": f"Consultar {singular}",
        "create": f"Registrar {singular}",
        "update": f"Reemplazar {singular}",
        "partial_update": f"Actualizar {singular}",
        "destroy": f"Eliminar {singular}",
    }
    descriptions = {
        "list": f"Devuelve la lista de {resource}.",
        "retrieve": f"Devuelve los datos del registro de {singular}.",
        "create": "Crea un registro. Requiere personal autorizado.",
        "update": "Reemplaza los datos del registro. Requiere personal autorizado.",
        "partial_update": "Actualiza parcialmente el registro. Requiere personal autorizado.",
        "destroy": "Elimina el registro si no tiene datos relacionados. Requiere personal autorizado.",
    }
    descriptions.update(description_overrides or {})
    schemas = {}
    for action in actions or summaries:
        options = {
            "tags": [tag],
            "summary": summaries[action],
            "description": descriptions[action],
        }
        if action == "list":
            parameters = [
                OpenApiParameter(
                    "page",
                    int,
                    OpenApiParameter.QUERY,
                    description="Número de página del resultado; cada página contiene hasta 20 registros.",
                )
            ]
            if searchable:
                parameters.append(
                    OpenApiParameter(
                        "search",
                        str,
                        OpenApiParameter.QUERY,
                        description="Texto que se buscará en los campos indicados para este recurso.",
                    )
                )
            if sortable:
                parameters.append(
                    OpenApiParameter(
                        "ordering",
                        str,
                        OpenApiParameter.QUERY,
                        description="Campo por el que se ordenan los resultados; antepón - para orden descendente.",
                    )
                )
            options["parameters"] = parameters
        if public_read and action in {"list", "retrieve"}:
            options["auth"] = []
        schemas[action] = extend_schema(**options)
    return extend_schema_view(**schemas)


@extend_schema_view(
    post=extend_schema(
        tags=["Autenticación"],
        summary="Iniciar sesión",
        description="Valida usuario y contraseña y devuelve los tokens de acceso y renovación.",
    )
)
class LibraryTokenObtainPairView(TokenObtainPairView):
    throttle_classes = (LoginThrottle,)


@extend_schema_view(
    post=extend_schema(
        tags=["Autenticación"],
        summary="Renovar sesión",
        description="Recibe el token de renovación y devuelve tokens vigentes.",
    )
)
class LibraryTokenRefreshView(TokenRefreshView):
    pass


@extend_schema(
    tags=["Autenticación"],
    summary="Consultar mi cuenta",
    description="Devuelve el identificador, nombre de usuario y rol de la cuenta autenticada.",
    responses={
        200: {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "description": "Identificador de la cuenta."},
                "username": {"type": "string", "description": "Nombre usado para iniciar sesión."},
                "role": {
                    "type": "string",
                    "enum": ["reader", "librarian", "admin"],
                    "description": "Rol asignado a la cuenta.",
                },
            },
        }
    },
)
class CurrentUserView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        return response.Response(
            {
                "id": request.user.pk,
                "username": request.user.username,
                "role": request.user.role,
            }
        )


@extend_schema_view(
    post=extend_schema(
        tags=["Autenticación"],
        summary="Registrar lector",
        description=(
            "Crea una cuenta lectora. El registro público no permite asignar roles de "
            "bibliotecario ni administrador."
        ),
    )
)
class RegisterView(CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (RegisterThrottle,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return response.Response(
            {
                "id": user.pk,
                "username": user.username,
                "email": user.email,
                "role": user.role,
            },
            status=status.HTTP_201_CREATED,
        )


@document_crud(
    "Usuarios",
    "usuarios",
    singular="usuario",
    description_overrides={
        "create": "Crea una cuenta. Requiere autenticación y rol de administrador o bibliotecario."
    },
)
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated, IsLibraryManager)
    http_method_names = ("get", "post", "put", "patch", "delete", "head", "options")

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise Conflict("No puedes eliminar tu propia cuenta mientras estás autenticado.")
        if instance.loans.exists():
            raise Conflict("No se puede eliminar un usuario que tiene préstamos registrados.")
        try:
            instance.delete()
        except ProtectedError as exc:
            raise Conflict("No se puede eliminar una cuenta que tiene registros relacionados.") from exc


class ProtectedDeleteMixin:
    def perform_destroy(self, instance):
        if instance._meta.related_objects:
            related_managers = [
                getattr(instance, relation.get_accessor_name())
                for relation in instance._meta.related_objects
                if relation.on_delete.__name__ == "PROTECT"
            ]
            if any(manager.exists() for manager in related_managers):
                raise Conflict("No se puede eliminar el recurso porque tiene datos relacionados.")
        try:
            instance.delete()
        except ProtectedError as exc:
            raise Conflict("No se puede eliminar el recurso porque tiene datos relacionados.") from exc


@document_crud(
    "Autores", "autores", singular="autor", public_read=True, searchable=True, sortable=True
)
class AuthorViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = (ReadOnlyOrLibraryManager,)
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("name",)
    ordering_fields = ("name", "created_at")
    ordering = ("name",)


@document_crud(
    "Categorías", "categorías", singular="categoría", public_read=True, searchable=True, sortable=True
)
class CategoryViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = (ReadOnlyOrLibraryManager,)
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("name",)
    ordering_fields = ("name", "created_at")
    ordering = ("name",)


@document_crud(
    "Libros",
    "libros",
    singular="libro",
    public_read=True,
    searchable=True,
    sortable=True,
    description_overrides={
        "create": (
            "Registra un libro y crea al menos un ejemplar disponible. El personal puede indicar "
            "initial_copies para crear entre 1 y 100 ejemplares."
        )
    },
)
class BookViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = Book.objects.select_related("author", "category").annotate(
        copies_count=Count("copies", distinct=True)
    )
    serializer_class = BookSerializer
    permission_classes = (ReadOnlyOrLibraryManager,)
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ("title", "isbn", "author__name", "category__name")
    ordering_fields = ("title", "publication_year", "created_at")
    ordering = ("title", "id")


@document_crud(
    "Ejemplares",
    "ejemplares",
    singular="ejemplar",
    public_read=True,
    searchable=True,
    actions=("list", "retrieve", "create", "destroy"),
)
class BookCopyViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = BookCopy.objects.select_related("book").all()
    serializer_class = BookCopySerializer
    permission_classes = (ReadOnlyOrLibraryManager,)
    filter_backends = (filters.SearchFilter,)
    search_fields = ("inventory_code", "book__title")
    http_method_names = ("get", "post", "delete", "head", "options")


@document_crud(
    "Préstamos",
    "préstamos",
    singular="préstamo",
    actions=("list", "retrieve", "create"),
    description_overrides={
        "list": "Devuelve el historial visible para la cuenta autenticada.",
        "retrieve": "Devuelve los datos del préstamo si pertenece a la cuenta o es visible para el personal.",
        "create": (
            "Crea un préstamo de un ejemplar disponible. Los lectores solo pueden solicitarlo para sí mismos; "
            "el personal autorizado puede indicar requested_user_id."
        ),
    },
)
class LoanViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Loan.objects.none()
    serializer_class = LoanSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        queryset = Loan.objects.select_related("user", "copy", "copy__book").all()
        if not self.request.user.can_manage_library:
            queryset = queryset.filter(user=self.request.user)
        return queryset

    def perform_destroy(self, instance):
        raise PermissionDenied("Los préstamos no se eliminan; registra su devolución.")

    @extend_schema(
        tags=["Préstamos"],
        summary="Listar préstamos activos",
        description="Devuelve los préstamos vigentes visibles para la cuenta autenticada.",
        parameters=[
            OpenApiParameter(
                "page",
                int,
                OpenApiParameter.QUERY,
                description="Número de página del resultado; cada página contiene hasta 20 préstamos.",
            )
        ],
    )
    @decorators.action(detail=False, methods=("get",))
    def active(self, request):
        loans = self.filter_queryset(self.get_queryset().filter(status=Loan.Status.ACTIVE))
        page = self.paginate_queryset(loans)
        serializer = self.get_serializer(page if page is not None else loans, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return response.Response(serializer.data)

    @extend_schema(
        tags=["Préstamos"],
        summary="Consultar historial de préstamos",
        description="Devuelve los préstamos devueltos visibles para la cuenta autenticada.",
        parameters=[
            OpenApiParameter(
                "page",
                int,
                OpenApiParameter.QUERY,
                description="Número de página del resultado; cada página contiene hasta 20 préstamos.",
            )
        ],
    )
    @decorators.action(detail=False, methods=("get",))
    def history(self, request):
        loans = self.filter_queryset(self.get_queryset().filter(status=Loan.Status.RETURNED))
        page = self.paginate_queryset(loans)
        serializer = self.get_serializer(page if page is not None else loans, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return response.Response(serializer.data)

    @extend_schema(
        tags=["Préstamos"],
        summary="Registrar devolución",
        description="Registra la devolución de un préstamo propio o visible para el personal autorizado.",
    )
    @decorators.action(detail=True, methods=("post",), url_path="return")
    def return_book(self, request, pk=None):
        loan = get_object_or_404(self.get_queryset(), pk=pk)
        if not request.user.can_manage_library and loan.user_id != request.user.pk:
            raise PermissionDenied("No tienes permiso para devolver este préstamo.")
        returned_loan = return_loan(loan_id=loan.pk)
        return response.Response(self.get_serializer(returned_loan).data)
