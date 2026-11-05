from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import RevokedToken, User
from app.schemas import LoginInput, PublicUser, RefreshInput, RegisterInput
from app.security import (
    DUMMY_PASSWORD_HASH,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post(
    "/register/",
    response_model=PublicUser,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar lector",
    description="Crea una cuenta lectora. El rol siempre se asigna como reader.",
)
def register(payload: RegisterInput, db: Session = Depends(get_db)):
    if payload.role is not None and payload.role != "reader":
        raise HTTPException(status_code=400, detail="El registro público solo permite crear lectores.")
    if db.scalar(select(User.id).where(User.username == payload.username)):
        raise HTTPException(status_code=400, detail="El nombre de usuario ya está registrado.")
    if db.scalar(select(User.id).where(User.email == payload.email)):
        raise HTTPException(status_code=400, detail="El correo electrónico ya está registrado.")
    user = User(
        username=payload.username,
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        password_hash=hash_password(payload.password),
        role="reader",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre de usuario o correo electrónico ya está registrado.",
        ) from None
    db.refresh(user)
    return user


@router.post(
    "/token/",
    summary="Iniciar sesión",
    description="Valida usuario y contraseña y devuelve tokens JWT de acceso y renovación.",
)
def login(payload: LoginInput, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    stored_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    valid_password = verify_password(payload.password, stored_hash)
    if user is None or not user.is_active or not valid_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access, refresh, _ = create_token_pair(user.id)
    return {"access": access, "refresh": refresh, "token_type": "bearer"}


@router.post(
    "/token/refresh/",
    summary="Renovar sesión",
    description="Rota el token de renovación y revoca el token anterior.",
)
def refresh_token(payload: RefreshInput, db: Session = Depends(get_db)):
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="El token de renovación es inválido, expiró o ya fue utilizado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token_data = decode_token(payload.refresh)
        if token_data.get("type") != "refresh":
            raise unauthorized
        user_id = int(token_data["sub"])
        token_id = str(token_data["jti"])
        expires_at = datetime.fromtimestamp(token_data["exp"], tz=timezone.utc)
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise unauthorized from None
    if db.scalar(select(RevokedToken.id).where(RevokedToken.token_id == token_id)):
        raise unauthorized
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    db.add(RevokedToken(token_id=token_id, expires_at=expires_at))
    access, refresh, _ = create_token_pair(user.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise unauthorized from None
    return {"access": access, "refresh": refresh, "token_type": "bearer"}


@router.get(
    "/me/",
    summary="Consultar mi cuenta",
    description="Devuelve los datos básicos de la cuenta autenticada.",
)
def current_user(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "role": user.role}
