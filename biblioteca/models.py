import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models
from django.db.models import Q
from django.utils import timezone


def generate_inventory_code():
    return f"CP-{uuid.uuid4().hex[:16].upper()}"


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrador"
        LIBRARIAN = "librarian", "Bibliotecario"
        READER = "reader", "Usuario"

    role = models.CharField(max_length=12, choices=Role.choices, default=Role.READER)
    objects = UserManager()

    @property
    def can_manage_library(self):
        return self.is_authenticated and (
            self.is_superuser or self.role in {self.Role.ADMIN, self.Role.LIBRARIAN}
        )


class Author(models.Model):
    name = models.CharField(max_length=150, unique=True)
    biography = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=200)
    isbn = models.CharField(max_length=17, unique=True, null=True, blank=True)
    author = models.ForeignKey(Author, on_delete=models.PROTECT, related_name="books")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="books")
    publication_year = models.PositiveSmallIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(publication_year__isnull=True) | Q(publication_year__gte=1000),
                name="book_publication_year_min_1000",
            ),
        ]

    def __str__(self):
        return self.title


class BookCopy(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Disponible"
        LOANED = "loaned", "Prestado"
        MAINTENANCE = "maintenance", "Mantenimiento"

    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="copies")
    inventory_code = models.CharField(max_length=20, unique=True, default=generate_inventory_code)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.AVAILABLE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["inventory_code"]

    def __str__(self):
        return f"{self.inventory_code} - {self.book.title}"


class Loan(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Activo"
        RETURNED = "returned", "Devuelto"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="loans")
    copy = models.ForeignKey(BookCopy, on_delete=models.PROTECT, related_name="loans")
    loan_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateField()
    returned_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ["-loan_date", "-id"]
        indexes = [
            models.Index(fields=["user", "status"], name="loan_user_status_idx"),
            models.Index(fields=["status", "due_date"], name="loan_status_due_idx"),
        ]

    def __str__(self):
        return f"{self.copy.inventory_code} - {self.user.username} ({self.status})"
