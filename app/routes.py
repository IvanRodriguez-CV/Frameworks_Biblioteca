from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import PAGE_SIZE
from app.database import get_db
from app.dependencies import get_current_user, require_staff
from app.models import Author, Book, BookCopy, Category, Loan, User
from app.schemas import (
    AuthorInput,
    AuthorOut,
    AuthorUpdate,
    BookCopyCreate,
    BookCopyOut,
    BookInput,
    BookOut,
    BookUpdate,
    CategoryInput,
    CategoryOut,
    CategoryUpdate,
    LoanCreate,
    LoanOut,
    Page,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.security import hash_password

router = APIRouter()
authors_router = APIRouter(prefix="/api/authors", tags=["Autores"])
categories_router = APIRouter(prefix="/api/categories", tags=["Categorías"])
books_router = APIRouter(prefix="/api/books", tags=["Libros"])
copies_router = APIRouter(prefix="/api/copies", tags=["Ejemplares"])
users_router = APIRouter(prefix="/api/users", tags=["Usuarios"])
loans_router = APIRouter(prefix="/api/loans", tags=["Préstamos"])


def paginated(
    request: Request, db: Session, statement, page: int
) -> dict[str, Any]:
    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    count = db.scalar(count_statement) or 0
    results = db.scalars(
        statement.limit(PAGE_SIZE).offset((page - 1) * PAGE_SIZE)
    ).all()
    next_url = (
        str(request.url.include_query_params(page=page + 1))
        if page * PAGE_SIZE < count
        else None
    )
    previous_url = (
        str(request.url.include_query_params(page=page - 1)) if page > 1 else None
    )
    return {
        "count": count,
        "next": next_url,
        "previous": previous_url,
        "results": results,
    }


def commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="La operación entra en conflicto con datos existentes o relacionados.",
        ) from None


def require_item(model, item_id: int, db: Session, label: str):
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"No se encontró {label}.")
    return item


def author_order(ordering: str | None):
    allowed = {"name": Author.name, "created_at": Author.created_at}
    field = (ordering or "name").lstrip("-")
    if field not in allowed:
        raise HTTPException(status_code=400, detail="Campo de ordenamiento no permitido.")
    column = allowed[field]
    return column.desc() if ordering and ordering.startswith("-") else column.asc()


def category_order(ordering: str | None):
    allowed = {"name": Category.name, "created_at": Category.created_at}
    field = (ordering or "name").lstrip("-")
    if field not in allowed:
        raise HTTPException(status_code=400, detail="Campo de ordenamiento no permitido.")
    column = allowed[field]
    return column.desc() if ordering and ordering.startswith("-") else column.asc()


def book_order(ordering: str | None):
    allowed = {
        "title": Book.title,
        "publication_year": Book.publication_year,
        "created_at": Book.created_at,
    }
    field = (ordering or "title").lstrip("-")
    if field not in allowed:
        raise HTTPException(status_code=400, detail="Campo de ordenamiento no permitido.")
    column = allowed[field]
    return (column.desc() if ordering and ordering.startswith("-") else column.asc(), Book.id.asc())


def author_matches(query: str):
    pattern = f"%{query}%"
    return Author.name.ilike(pattern)


def category_matches(query: str):
    pattern = f"%{query}%"
    return Category.name.ilike(pattern)


def book_output(book: Book, db: Session) -> dict[str, Any]:
    copies_count = db.scalar(
        select(func.count(BookCopy.id)).where(BookCopy.book_id == book.id)
    ) or 0
    available_copies = db.scalar(
        select(func.count(BookCopy.id)).where(
            BookCopy.book_id == book.id,
            BookCopy.status == "available",
        )
    ) or 0
    return {
        "id": book.id,
        "title": book.title,
        "isbn": book.isbn,
        "author": book.author_id,
        "category": book.category_id,
        "publication_year": book.publication_year,
        "description": book.description,
        "copies_count": copies_count,
        "available_copies": available_copies,
        "created_at": book.created_at,
    }


def copy_output(copy: BookCopy) -> dict[str, Any]:
    return {
        "id": copy.id,
        "book": copy.book_id,
        "book_title": copy.book.title,
        "inventory_code": copy.inventory_code,
        "status": copy.status,
        "created_at": copy.created_at,
    }


def loan_output(loan: Loan) -> dict[str, Any]:
    return {
        "id": loan.id,
        "copy_id": loan.copy_id,
        "inventory_code": loan.copy.inventory_code,
        "book_title": loan.copy.book.title,
        "user_id": loan.user_id,
        "username": loan.user.username,
        "loan_date": loan.loan_date,
        "due_date": loan.due_date,
        "returned_at": loan.returned_at,
        "status": loan.status,
    }


@authors_router.get("/", response_model=Page[AuthorOut], summary="Listar autores")
def list_authors(
    request: Request,
    page: int = Query(1, ge=1),
    search: str | None = Query(None, max_length=100),
    ordering: str | None = None,
    db: Session = Depends(get_db),
):
    statement = select(Author)
    if search:
        statement = statement.where(author_matches(search))
    return paginated(request, db, statement.order_by(author_order(ordering)), page)


@authors_router.get("/{item_id}/", response_model=AuthorOut, summary="Consultar autor")
def get_author(item_id: int, db: Session = Depends(get_db)):
    return require_item(Author, item_id, db, "el autor solicitado")


@authors_router.post("/", response_model=AuthorOut, status_code=201, summary="Registrar autor")
def create_author(
    payload: AuthorInput,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    author = Author(name=payload.name, biography=payload.biography)
    db.add(author)
    commit_or_conflict(db)
    db.refresh(author)
    return author


@authors_router.put("/{item_id}/", response_model=AuthorOut, summary="Reemplazar autor")
@authors_router.patch("/{item_id}/", response_model=AuthorOut, summary="Actualizar autor")
def update_author(
    item_id: int,
    payload: AuthorUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    author = require_item(Author, item_id, db, "el autor solicitado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(author, field, value.strip())
    commit_or_conflict(db)
    db.refresh(author)
    return author


@authors_router.delete("/{item_id}/", status_code=204, summary="Eliminar autor")
def delete_author(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    author = require_item(Author, item_id, db, "el autor solicitado")
    if db.scalar(select(Book.id).where(Book.author_id == item_id).limit(1)):
        raise HTTPException(status_code=409, detail="No se puede eliminar un autor asociado a libros.")
    db.delete(author)
    commit_or_conflict(db)
    return Response(status_code=204)


@categories_router.get("/", response_model=Page[CategoryOut], summary="Listar categorías")
def list_categories(
    request: Request,
    page: int = Query(1, ge=1),
    search: str | None = Query(None, max_length=100),
    ordering: str | None = None,
    db: Session = Depends(get_db),
):
    statement = select(Category)
    if search:
        statement = statement.where(category_matches(search))
    return paginated(request, db, statement.order_by(category_order(ordering)), page)


@categories_router.get("/{item_id}/", response_model=CategoryOut, summary="Consultar categoría")
def get_category(item_id: int, db: Session = Depends(get_db)):
    return require_item(Category, item_id, db, "la categoría solicitada")


@categories_router.post("/", response_model=CategoryOut, status_code=201, summary="Registrar categoría")
def create_category(
    payload: CategoryInput,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    category = Category(name=payload.name, description=payload.description)
    db.add(category)
    commit_or_conflict(db)
    db.refresh(category)
    return category


@categories_router.put("/{item_id}/", response_model=CategoryOut, summary="Reemplazar categoría")
@categories_router.patch("/{item_id}/", response_model=CategoryOut, summary="Actualizar categoría")
def update_category(
    item_id: int,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    category = require_item(Category, item_id, db, "la categoría solicitada")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(category, field, value.strip())
    commit_or_conflict(db)
    db.refresh(category)
    return category


@categories_router.delete("/{item_id}/", status_code=204, summary="Eliminar categoría")
def delete_category(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    category = require_item(Category, item_id, db, "la categoría solicitada")
    if db.scalar(select(Book.id).where(Book.category_id == item_id).limit(1)):
        raise HTTPException(status_code=409, detail="No se puede eliminar una categoría asociada a libros.")
    db.delete(category)
    commit_or_conflict(db)
    return Response(status_code=204)


@books_router.get("/", response_model=Page[BookOut], summary="Listar libros")
def list_books(
    request: Request,
    page: int = Query(1, ge=1),
    search: str | None = Query(None, max_length=100),
    ordering: str | None = None,
    db: Session = Depends(get_db),
):
    statement = select(Book)
    if search:
        pattern = f"%{search}%"
        statement = (
            statement.join(Author, Book.author_id == Author.id)
            .join(Category, Book.category_id == Category.id)
            .where(
                or_(
                    Book.title.ilike(pattern),
                    Book.isbn.ilike(pattern),
                    Author.name.ilike(pattern),
                    Category.name.ilike(pattern),
                )
            )
        )
    data = paginated(request, db, statement.order_by(*book_order(ordering)), page)
    data["results"] = [book_output(book, db) for book in data["results"]]
    return data


@books_router.get("/{item_id}/", response_model=BookOut, summary="Consultar libro")
def get_book(item_id: int, db: Session = Depends(get_db)):
    return book_output(require_item(Book, item_id, db, "el libro solicitado"), db)


@books_router.post("/", response_model=BookOut, status_code=201, summary="Registrar libro")
def create_book(
    payload: BookInput,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    require_item(Author, payload.author, db, "el autor solicitado")
    require_item(Category, payload.category, db, "la categoría solicitada")
    book = Book(
        title=payload.title,
        isbn=payload.isbn,
        author_id=payload.author,
        category_id=payload.category,
        publication_year=payload.publication_year,
        description=payload.description,
    )
    db.add(book)
    db.flush()
    db.add_all(
        [BookCopy(book_id=book.id, status="available") for _ in range(payload.initial_copies)]
    )
    commit_or_conflict(db)
    db.refresh(book)
    return book_output(book, db)


@books_router.put("/{item_id}/", response_model=BookOut, summary="Reemplazar libro")
@books_router.patch("/{item_id}/", response_model=BookOut, summary="Actualizar libro")
def update_book(
    item_id: int,
    payload: BookUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    book = require_item(Book, item_id, db, "el libro solicitado")
    values = payload.model_dump(exclude_unset=True, exclude={"initial_copies"})
    for field in ("author", "category"):
        if field in values and values[field] is not None:
            require_item(Author if field == "author" else Category, values[field], db, f"el {field} solicitado")
            values[f"{field}_id"] = values.pop(field)
    for field, value in values.items():
        if value is not None:
            setattr(book, field, value.strip() if isinstance(value, str) else value)
    commit_or_conflict(db)
    db.refresh(book)
    return book_output(book, db)


@books_router.delete("/{item_id}/", status_code=204, summary="Eliminar libro")
def delete_book(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    book = require_item(Book, item_id, db, "el libro solicitado")
    if db.scalar(select(BookCopy.id).where(BookCopy.book_id == item_id).limit(1)):
        raise HTTPException(status_code=409, detail="No se puede eliminar un libro con ejemplares asociados.")
    db.delete(book)
    commit_or_conflict(db)
    return Response(status_code=204)


@copies_router.get("/", response_model=Page[BookCopyOut], summary="Listar ejemplares")
def list_copies(
    request: Request,
    page: int = Query(1, ge=1),
    search: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
):
    statement = select(BookCopy).options(joinedload(BookCopy.book))
    if search:
        pattern = f"%{search}%"
        statement = statement.join(Book, BookCopy.book_id == Book.id).where(
            or_(BookCopy.inventory_code.ilike(pattern), Book.title.ilike(pattern))
        )
    data = paginated(request, db, statement.order_by(BookCopy.inventory_code), page)
    data["results"] = [copy_output(copy) for copy in data["results"]]
    return data


@copies_router.get("/{item_id}/", response_model=BookCopyOut, summary="Consultar ejemplar")
def get_copy(item_id: int, db: Session = Depends(get_db)):
    copy = db.scalar(
        select(BookCopy).options(joinedload(BookCopy.book)).where(BookCopy.id == item_id)
    )
    if copy is None:
        raise HTTPException(status_code=404, detail="No se encontró el ejemplar solicitado.")
    return copy_output(copy)


@copies_router.post("/", response_model=BookCopyOut, status_code=201, summary="Registrar ejemplar")
def create_copy(
    payload: BookCopyCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    book = require_item(Book, payload.book, db, "el libro solicitado")
    copy = BookCopy(book_id=book.id, status="available")
    db.add(copy)
    commit_or_conflict(db)
    db.refresh(copy)
    copy.book = book
    return copy_output(copy)


@copies_router.delete("/{item_id}/", status_code=204, summary="Eliminar ejemplar")
def delete_copy(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    copy = require_item(BookCopy, item_id, db, "el ejemplar solicitado")
    if db.scalar(select(Loan.id).where(Loan.copy_id == item_id).limit(1)):
        raise HTTPException(status_code=409, detail="No se puede eliminar un ejemplar con préstamos registrados.")
    db.delete(copy)
    commit_or_conflict(db)
    return Response(status_code=204)


@users_router.get("/", response_model=Page[UserOut], summary="Listar usuarios")
def list_users(
    request: Request,
    page: int = Query(1, ge=1),
    search: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    statement = select(User)
    if search:
        pattern = f"%{search}%"
        statement = statement.where(
            or_(User.username.ilike(pattern), User.email.ilike(pattern))
        )
    return paginated(request, db, statement.order_by(User.id), page)


@users_router.get("/{item_id}/", response_model=UserOut, summary="Consultar usuario")
def get_user(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
):
    return require_item(User, item_id, db, "el usuario solicitado")


@users_router.post("/", response_model=UserOut, status_code=201, summary="Registrar usuario")
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_staff),
):
    if current.role != "admin" and "role" in payload.model_fields_set:
        raise HTTPException(status_code=400, detail="Solo un administrador puede asignar roles.")
    if db.scalar(select(User.id).where(User.username == payload.username)):
        raise HTTPException(status_code=400, detail="El nombre de usuario ya está registrado.")
    if db.scalar(select(User.id).where(User.email == payload.email.lower())):
        raise HTTPException(status_code=400, detail="El correo electrónico ya está registrado.")
    user = User(
        username=payload.username.strip(),
        email=payload.email.strip().lower(),
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role if current.role == "admin" else "reader",
        is_active=payload.is_active,
    )
    db.add(user)
    commit_or_conflict(db)
    db.refresh(user)
    return user


@users_router.put("/{item_id}/", response_model=UserOut, summary="Reemplazar usuario")
@users_router.patch("/{item_id}/", response_model=UserOut, summary="Actualizar usuario")
def update_user(
    item_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_staff),
):
    if "role" in payload.model_fields_set and current.role != "admin":
        raise HTTPException(status_code=400, detail="Solo un administrador puede asignar o cambiar roles.")
    user = require_item(User, item_id, db, "el usuario solicitado")
    values = payload.model_dump(exclude_unset=True)
    if "password" in values and values["password"]:
        values["password_hash"] = hash_password(values.pop("password"))
    if "email" in values and values["email"] is not None:
        values["email"] = values["email"].strip().lower()
    for field, value in values.items():
        if value is not None:
            setattr(user, field, value.strip() if isinstance(value, str) and field != "password_hash" else value)
    commit_or_conflict(db)
    db.refresh(user)
    return user


@users_router.delete("/{item_id}/", status_code=204, summary="Eliminar usuario")
def delete_user(
    item_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_staff),
):
    user = require_item(User, item_id, db, "el usuario solicitado")
    if user.id == current.id:
        raise HTTPException(status_code=409, detail="No puedes eliminar tu propia cuenta activa.")
    if db.scalar(select(Loan.id).where(Loan.user_id == item_id).limit(1)):
        raise HTTPException(status_code=409, detail="No se puede eliminar un usuario con préstamos registrados.")
    db.delete(user)
    commit_or_conflict(db)
    return Response(status_code=204)


def visible_loans_statement(user: User):
    statement = (
        select(Loan)
        .options(joinedload(Loan.user), joinedload(Loan.copy).joinedload(BookCopy.book))
    )
    if not user.can_manage_library:
        statement = statement.where(Loan.user_id == user.id)
    return statement


def list_loans(
    request: Request,
    db: Session,
    user: User,
    page: int,
    loan_status: str | None = None,
):
    statement = visible_loans_statement(user)
    if loan_status:
        statement = statement.where(Loan.status == loan_status)
    data = paginated(request, db, statement.order_by(Loan.loan_date.desc(), Loan.id.desc()), page)
    data["results"] = [loan_output(loan) for loan in data["results"]]
    return data


@loans_router.get("/", response_model=Page[LoanOut], summary="Listar historial de préstamos")
def get_loans(
    request: Request,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return list_loans(request, db, user, page)


@loans_router.get("/active/", response_model=Page[LoanOut], summary="Listar préstamos activos")
def get_active_loans(
    request: Request,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return list_loans(request, db, user, page, "active")


@loans_router.get("/history/", response_model=Page[LoanOut], summary="Consultar historial devuelto")
def get_loan_history(
    request: Request,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return list_loans(request, db, user, page, "returned")


@loans_router.get("/{item_id}/", response_model=LoanOut, summary="Consultar préstamo")
def get_loan(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    statement = visible_loans_statement(user).where(Loan.id == item_id)
    loan = db.scalar(statement)
    if loan is None:
        raise HTTPException(status_code=404, detail="No se encontró el préstamo solicitado.")
    return loan_output(loan)


@loans_router.post("/", response_model=LoanOut, status_code=201, summary="Registrar préstamo")
def create_loan(
    payload: LoanCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    user_id = current.id
    if payload.requested_user_id is not None:
        if not current.can_manage_library:
            raise HTTPException(status_code=400, detail="Solo el personal puede crear préstamos para otra persona.")
        requested = db.get(User, payload.requested_user_id)
        if requested is None or not requested.is_active:
            raise HTTPException(status_code=400, detail="El usuario solicitado no existe o está inactivo.")
        user_id = requested.id

    due_date = payload.due_date or (date.today() + timedelta(days=14))
    if due_date < date.today():
        raise HTTPException(status_code=400, detail="La fecha de devolución no puede estar en el pasado.")
    copy = db.get(BookCopy, payload.copy_id)
    if copy is None:
        raise HTTPException(status_code=400, detail="El ejemplar solicitado no existe.")
    changed = db.execute(
        update(BookCopy)
        .where(BookCopy.id == payload.copy_id, BookCopy.status == "available")
        .values(status="loaned")
    ).rowcount
    if changed != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="El ejemplar no está disponible para préstamo.")
    loan = Loan(user_id=user_id, copy_id=copy.id, due_date=due_date, status="active")
    db.add(loan)
    db.commit()
    loan = db.scalar(
        select(Loan)
        .options(joinedload(Loan.user), joinedload(Loan.copy).joinedload(BookCopy.book))
        .where(Loan.id == loan.id)
    )
    return loan_output(loan)


@loans_router.post("/{item_id}/return/", response_model=LoanOut, summary="Registrar devolución")
def return_loan(
    item_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    loan = db.scalar(
        visible_loans_statement(current).where(Loan.id == item_id)
    )
    if loan is None:
        raise HTTPException(status_code=404, detail="No se encontró el préstamo solicitado.")
    returned_at = datetime.now(timezone.utc)
    changed = db.execute(
        update(Loan)
        .where(Loan.id == item_id, Loan.status == "active")
        .values(status="returned", returned_at=returned_at)
    ).rowcount
    if changed != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="El préstamo ya fue devuelto.")
    db.execute(
        update(BookCopy)
        .where(BookCopy.id == loan.copy_id)
        .values(status="available")
    )
    db.commit()
    loan = db.scalar(
        select(Loan)
        .options(joinedload(Loan.user), joinedload(Loan.copy).joinedload(BookCopy.book))
        .where(Loan.id == item_id)
    )
    return loan_output(loan)


router.include_router(authors_router)
router.include_router(categories_router)
router.include_router(books_router)
router.include_router(copies_router)
router.include_router(users_router)
router.include_router(loans_router)
