import re
from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

T = TypeVar("T")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def clean_text(value: str, *, allow_blank: bool = True) -> str:
    value = value.strip()
    if not allow_blank and not value:
        raise ValueError("Este campo no puede estar vacío.")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in value):
        raise ValueError("El texto contiene caracteres no permitidos.")
    return value


def clean_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not EMAIL_PATTERN.fullmatch(value):
        raise ValueError("Ingresa un correo electrónico válido.")
    return value


class Page(BaseModel, Generic[T]):
    count: int
    next: str | None
    previous: str | None
    results: list[T]


class RegisterInput(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    email: str = Field(min_length=3, max_length=254)
    first_name: str = Field(default="", max_length=150)
    last_name: str = Field(default="", max_length=150)
    password: str = Field(min_length=10, max_length=128)
    role: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return clean_text(value, allow_blank=False)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, value: str) -> str:
        return clean_text(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return clean_email(value)


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=128)


class RefreshInput(BaseModel):
    refresh: str = Field(min_length=1)


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    email: str = Field(min_length=3, max_length=254)
    first_name: str = Field(default="", max_length=150)
    last_name: str = Field(default="", max_length=150)
    password: str = Field(min_length=10, max_length=128)
    role: str = Field(default="reader", pattern="^(admin|librarian|reader)$")
    is_active: bool = True

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return clean_text(value, allow_blank=False)

    @field_validator("email")
    @classmethod
    def validate_user_email(cls, value: str) -> str:
        return clean_email(value)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, value: str) -> str:
        return clean_text(value)


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=150)
    email: str | None = Field(default=None, min_length=3, max_length=254)
    first_name: str | None = Field(default=None, max_length=150)
    last_name: str | None = Field(default=None, max_length=150)
    password: str | None = Field(default=None, min_length=10, max_length=128)
    role: str | None = Field(default=None, pattern="^(admin|librarian|reader)$")
    is_active: bool | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        return clean_text(value, allow_blank=False) if value is not None else None

    @field_validator("email")
    @classmethod
    def validate_user_email(cls, value: str | None) -> str | None:
        return clean_email(value) if value is not None else None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, value: str | None) -> str | None:
        return clean_text(value) if value is not None else None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    role: str
    is_active: bool
    date_joined: datetime


class PublicUser(BaseModel):
    id: int
    username: str
    email: str
    role: str


class AuthorInput(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    biography: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return clean_text(value, allow_blank=False)

    @field_validator("biography")
    @classmethod
    def validate_biography(cls, value: str) -> str:
        return clean_text(value)


class AuthorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    biography: str
    created_at: datetime


class AuthorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    biography: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return clean_text(value, allow_blank=False) if value is not None else None

    @field_validator("biography")
    @classmethod
    def validate_biography(cls, value: str | None) -> str | None:
        return clean_text(value) if value is not None else None


class CategoryInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return clean_text(value, allow_blank=False)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return clean_text(value)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    created_at: datetime


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return clean_text(value, allow_blank=False) if value is not None else None

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return clean_text(value) if value is not None else None


class BookInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    isbn: str | None = Field(default=None, max_length=17)
    author: int = Field(gt=0)
    category: int = Field(gt=0)
    publication_year: int | None = Field(default=None, ge=1000, le=date.today().year + 1)
    description: str = ""
    initial_copies: int = Field(default=1, ge=1, le=100)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return clean_text(value, allow_blank=False)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return clean_text(value)

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, value: str | None) -> str | None:
        return validate_isbn_value(value)


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    isbn: str | None = Field(default=None, max_length=17)
    author: int | None = Field(default=None, gt=0)
    category: int | None = Field(default=None, gt=0)
    publication_year: int | None = Field(default=None, ge=1000, le=date.today().year + 1)
    description: str | None = None
    initial_copies: int | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        return clean_text(value, allow_blank=False) if value is not None else None

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, value: str | None) -> str | None:
        return validate_isbn_value(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        return clean_text(value) if value is not None else None

    @model_validator(mode="after")
    def reject_inventory_change(self):
        if self.initial_copies is not None:
            raise ValueError("No se puede cambiar el inventario inicial al actualizar un libro.")
        return self


def validate_isbn_value(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if value and not all(char.isdigit() or char in "-Xx" for char in value):
        raise ValueError("El ISBN solo puede contener dígitos, guiones y X.")
    if value and not 10 <= len(value) <= 17:
        raise ValueError("El ISBN debe tener entre 10 y 17 caracteres.")
    return value or None


class BookOut(BaseModel):
    id: int
    title: str
    isbn: str | None
    author: int
    category: int
    publication_year: int | None
    description: str
    copies_count: int
    available_copies: int
    created_at: datetime


class BookCopyCreate(BaseModel):
    book: int = Field(gt=0)


class BookCopyOut(BaseModel):
    id: int
    book: int
    book_title: str
    inventory_code: str
    status: str
    created_at: datetime


class LoanCreate(BaseModel):
    copy_id: int = Field(alias="copy", gt=0)
    due_date: date | None = None
    requested_user_id: int | None = Field(default=None, gt=0)


class LoanOut(BaseModel):
    id: int
    copy_id: int
    inventory_code: str
    book_title: str
    user_id: int
    username: str
    loan_date: datetime
    due_date: date
    returned_at: datetime | None
    status: str
