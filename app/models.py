import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index
from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_inventory_code() -> str:
    return f"CP-{uuid.uuid4().hex[:16].upper()}"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(150), default="")
    last_name: Mapped[str] = mapped_column(String(150), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(12), default="reader", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    date_joined: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    loans: Mapped[list["Loan"]] = relationship(back_populates="user")

    @property
    def can_manage_library(self) -> bool:
        return self.role in {"admin", "librarian"}


class Author(Base):
    __tablename__ = "authors"
    __table_args__ = (UniqueConstraint("name", name="uq_authors_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    biography: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    books: Mapped[list["Book"]] = relationship(back_populates="author")


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", name="uq_categories_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    books: Mapped[list["Book"]] = relationship(back_populates="category")


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint(
            "publication_year IS NULL OR publication_year >= 1000",
            name="ck_books_publication_year_min",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    isbn: Mapped[str | None] = mapped_column(String(17), unique=True, nullable=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id", ondelete="RESTRICT"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    author: Mapped[Author] = relationship(back_populates="books")
    category: Mapped[Category] = relationship(back_populates="books")
    copies: Mapped[list["BookCopy"]] = relationship(back_populates="book")


class BookCopy(Base):
    __tablename__ = "book_copies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="RESTRICT"), index=True)
    inventory_code: Mapped[str] = mapped_column(
        String(20), unique=True, default=generate_inventory_code
    )
    status: Mapped[str] = mapped_column(String(12), default="available", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    book: Mapped[Book] = relationship(back_populates="copies")
    loans: Mapped[list["Loan"]] = relationship(back_populates="copy")


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = (
        Index("ix_loans_user_status", "user_id", "status"),
        Index("ix_loans_status_due_date", "status", "due_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    copy_id: Mapped[int] = mapped_column(ForeignKey("book_copies.id", ondelete="RESTRICT"), index=True)
    loan_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    due_date: Mapped[date] = mapped_column(Date)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="active", index=True)

    user: Mapped[User] = relationship(back_populates="loans")
    copy: Mapped[BookCopy] = relationship(back_populates="loans")


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
