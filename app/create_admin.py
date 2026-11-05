from getpass import getpass

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.security import hash_password


def main() -> None:
    username = input("Nombre del administrador: ").strip()
    email = input("Correo electrónico: ").strip().lower()
    password = getpass("Contraseña (mínimo 10 caracteres): ")
    if len(password) < 10:
        raise SystemExit("La contraseña debe tener al menos 10 caracteres.")
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.username == username)):
            raise SystemExit("Ese nombre de usuario ya existe.")
        if db.scalar(select(User.id).where(User.email == email)):
            raise SystemExit("Ese correo electrónico ya está registrado.")
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
    print("Cuenta administradora creada.")


if __name__ == "__main__":
    main()
