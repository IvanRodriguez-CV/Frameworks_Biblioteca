from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from biblioteca.models import Author, Book, BookCopy, Category, Loan, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (("Biblioteca", {"fields": ("role",)}),)
    list_display = ("username", "email", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "created_at")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("name", "created_at")


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    search_fields = ("title", "isbn", "author__name")
    list_display = ("title", "author", "category", "isbn")
    list_filter = ("category",)


@admin.register(BookCopy)
class BookCopyAdmin(admin.ModelAdmin):
    search_fields = ("inventory_code", "book__title")
    list_display = ("inventory_code", "book", "status")
    list_filter = ("status",)


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    search_fields = ("user__username", "copy__inventory_code", "copy__book__title")
    list_display = ("user", "copy", "loan_date", "due_date", "returned_at", "status")
    list_filter = ("status",)
    readonly_fields = ("loan_date", "returned_at")
