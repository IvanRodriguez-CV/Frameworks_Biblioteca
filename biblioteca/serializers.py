import re
from datetime import date

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from biblioteca.models import Author, Book, BookCopy, Category, Loan, User
from biblioteca.services import create_loan


CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def validate_text(value):
    if CONTROL_CHARACTERS.search(value):
        raise serializers.ValidationError("El texto contiene caracteres de control no permitidos.")
    return value.strip()


def password_validation_user(serializer):
    instance = serializer.instance
    fields = ("username", "email", "first_name", "last_name")
    values = {field: getattr(instance, field, "") for field in fields}
    for field in fields:
        supplied = serializer.initial_data.get(field)
        if isinstance(supplied, str):
            values[field] = supplied
    return User(**values)


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        label="Contraseña",
        help_text="Contraseña de la nueva cuenta; debe cumplir las reglas de seguridad.",
        write_only=True,
        trim_whitespace=False,
    )

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "password", "role")
        read_only_fields = ("id", "role")
        extra_kwargs = {
            "username": {
                "max_length": 150,
                "help_text": "Nombre único para iniciar sesión.",
            },
            "email": {"required": True, "help_text": "Correo electrónico de la persona."},
            "first_name": {"required": False, "help_text": "Nombre de la persona."},
            "last_name": {"required": False, "help_text": "Apellido de la persona."},
            "role": {"help_text": "Rol asignado por el sistema; no se puede elegir en el registro público."},
        }

    def validate_username(self, value):
        return validate_text(value)

    def validate_email(self, value):
        return value.strip().lower()

    def validate_password(self, value):
        validate_password(value, user=password_validation_user(self))
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        label="Contraseña",
        help_text="Contraseña nueva; déjala fuera si no deseas cambiarla.",
        write_only=True,
        required=False,
        trim_whitespace=False,
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "date_joined",
            "password",
        )
        read_only_fields = ("id", "date_joined")
        extra_kwargs = {
            "username": {"help_text": "Nombre utilizado para iniciar sesión."},
            "email": {"required": True, "help_text": "Correo electrónico de la persona."},
            "first_name": {"help_text": "Nombre de la persona."},
            "last_name": {"help_text": "Apellido de la persona."},
            "role": {"help_text": "Rol: reader (lector), librarian (bibliotecario) o admin (administrador)."},
            "is_active": {"help_text": "Indica si la cuenta puede iniciar sesión."},
            "date_joined": {"help_text": "Fecha de creación de la cuenta."},
        }

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        can_assign_roles = user and user.is_authenticated and (
            user.is_superuser or user.role == User.Role.ADMIN
        )
        if "role" in self.initial_data and not can_assign_roles:
            raise serializers.ValidationError(
                {"role": "Solo un administrador puede asignar o cambiar roles."}
            )
        return attrs

    def validate_password(self, value):
        validate_password(value, user=password_validation_user(self))
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ("id", "name", "biography", "created_at")
        read_only_fields = ("id", "created_at")
        extra_kwargs = {
            "name": {"help_text": "Nombre completo del autor."},
            "biography": {"help_text": "Biografía del autor."},
            "created_at": {"help_text": "Fecha de creación del registro."},
        }

    def validate_name(self, value):
        return validate_text(value)

    def validate_biography(self, value):
        return validate_text(value)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "description", "created_at")
        read_only_fields = ("id", "created_at")
        extra_kwargs = {
            "name": {"help_text": "Nombre único de la categoría."},
            "description": {"help_text": "Descripción de la categoría."},
            "created_at": {"help_text": "Fecha de creación del registro."},
        }

    def validate_name(self, value):
        return validate_text(value)

    def validate_description(self, value):
        return validate_text(value)


class BookSerializer(serializers.ModelSerializer):
    initial_copies = serializers.IntegerField(
        label="Ejemplares iniciales",
        help_text="Cantidad de copias disponibles a crear con el libro (de 1 a 100).",
        write_only=True,
        required=False,
        min_value=1,
        max_value=100,
    )
    copies_count = serializers.SerializerMethodField()
    available_copies = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = (
            "id",
            "title",
            "isbn",
            "author",
            "category",
            "publication_year",
            "description",
            "initial_copies",
            "copies_count",
            "available_copies",
            "created_at",
        )
        read_only_fields = ("id", "created_at")
        extra_kwargs = {
            "title": {"help_text": "Título del libro."},
            "isbn": {"allow_null": True, "required": False, "help_text": "ISBN único; admite dígitos, guiones y X."},
            "author": {"help_text": "Identificador del autor registrado."},
            "category": {"help_text": "Identificador de la categoría registrada."},
            "publication_year": {"help_text": "Año de publicación; debe ser 1000 o posterior."},
            "description": {"help_text": "Descripción del libro."},
            "copies_count": {"help_text": "Cantidad total de ejemplares."},
            "available_copies": {"help_text": "Cantidad de ejemplares disponibles para préstamo."},
            "created_at": {"help_text": "Fecha de creación del registro."},
        }

    def get_copies_count(self, obj: Book) -> int:
        if hasattr(obj, "copies_count"):
            return obj.copies_count
        return obj.copies.count()

    def get_available_copies(self, obj: Book) -> int:
        return obj.copies.filter(status=BookCopy.Status.AVAILABLE).count()

    def validate_title(self, value):
        return validate_text(value)

    def validate_isbn(self, value):
        value = value.strip()
        if value and not re.fullmatch(r"[0-9Xx-]{10,17}", value):
            raise serializers.ValidationError("El ISBN solo puede contener dígitos, guiones y X.")
        return value or None

    def validate_description(self, value):
        return validate_text(value)

    def validate_publication_year(self, value):
        if value is not None and value < 1000:
            raise serializers.ValidationError("El año de publicación debe ser igual o posterior a 1000.")
        if value is not None and value > date.today().year + 1:
            raise serializers.ValidationError("El año de publicación no puede ser futuro.")
        return value

    def validate(self, attrs):
        if self.instance and "initial_copies" in attrs:
            raise serializers.ValidationError(
                {"initial_copies": "No se puede cambiar el inventario inicial al actualizar un libro."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        copies_count = validated_data.pop("initial_copies", 1)
        book = super().create(validated_data)
        BookCopy.objects.bulk_create([BookCopy(book=book) for _ in range(copies_count)])
        return book


class BookCopySerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(
        label="Título del libro",
        help_text="Título del libro al que pertenece este ejemplar.",
        source="book.title",
        read_only=True,
    )

    class Meta:
        model = BookCopy
        fields = ("id", "book", "book_title", "inventory_code", "status", "created_at")
        read_only_fields = ("id", "inventory_code", "status", "created_at")
        extra_kwargs = {
            "book": {"help_text": "Identificador del libro al que pertenece el ejemplar."},
            "inventory_code": {"help_text": "Código único generado para el inventario."},
            "status": {
                "help_text": "Estado: available (disponible), loaned (prestado) o maintenance (mantenimiento)."
            },
            "created_at": {"help_text": "Fecha de registro del ejemplar."},
        }


class LoanSerializer(serializers.ModelSerializer):
    copy = serializers.PrimaryKeyRelatedField(
        label="Ejemplar",
        help_text="Identificador del ejemplar disponible que se desea pedir.",
        queryset=BookCopy.objects.select_related("book").all(),
        write_only=True,
    )
    copy_id = serializers.IntegerField(
        label="Identificador del ejemplar", help_text="Identificador del ejemplar prestado.",
        source="copy.id", read_only=True,
    )
    inventory_code = serializers.CharField(
        label="Código de inventario", help_text="Código único del ejemplar prestado.",
        source="copy.inventory_code", read_only=True,
    )
    book_title = serializers.CharField(
        label="Título del libro", help_text="Título del libro prestado.",
        source="copy.book.title", read_only=True,
    )
    user_id = serializers.IntegerField(
        label="Identificador del usuario", help_text="Identificador de quien tiene el préstamo.",
        source="user.id", read_only=True,
    )
    username = serializers.CharField(
        label="Usuario", help_text="Nombre de usuario de quien tiene el préstamo.",
        source="user.username", read_only=True,
    )
    requested_user_id = serializers.PrimaryKeyRelatedField(
        label="Usuario para el préstamo",
        help_text="Identificador de la persona; solo el personal puede pedir prestado para otra cuenta.",
        source="user",
        queryset=User.objects.filter(is_active=True),
        write_only=True,
        required=False,
    )
    due_date = serializers.DateField(
        label="Fecha límite de devolución",
        help_text="Fecha límite en formato AAAA-MM-DD; por defecto, 14 días desde el préstamo.",
        required=False,
    )

    class Meta:
        model = Loan
        fields = (
            "id",
            "copy",
            "copy_id",
            "inventory_code",
            "book_title",
            "user_id",
            "username",
            "requested_user_id",
            "loan_date",
            "due_date",
            "returned_at",
            "status",
        )
        read_only_fields = ("id", "loan_date", "returned_at", "status")
        extra_kwargs = {
            "loan_date": {"help_text": "Fecha y hora en que se registró el préstamo."},
            "returned_at": {"help_text": "Fecha y hora de devolución; nula si el préstamo sigue activo."},
            "status": {"help_text": "Estado: active (activo) o returned (devuelto)."},
        }

    def validate_due_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("La fecha de devolución no puede estar en el pasado.")
        return value

    def validate(self, attrs):
        request = self.context["request"]
        if not request.user.can_manage_library and "user" in attrs:
            raise serializers.ValidationError(
                {"requested_user_id": "Solo el personal puede crear préstamos para otra persona."}
            )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        requested_user = validated_data.pop("user", request.user)
        if not request.user.can_manage_library:
            requested_user = request.user
        loan = create_loan(
            user=requested_user,
            copy_id=validated_data["copy"].pk,
            due_date=validated_data.get("due_date"),
        )
        return loan
