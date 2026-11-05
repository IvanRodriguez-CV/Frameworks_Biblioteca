# API REST para sistema bibliotecario

API backend construida con **FastAPI**, SQLAlchemy y MySQL. No incluye sitio web. La documentación interactiva se genera automáticamente con OpenAPI/Swagger UI.

## Funciones

- Registro de lectores e inicio de sesión con JWT de acceso y renovación.
- Roles de administrador, bibliotecario y lector; solo un administrador puede asignar roles.
- CRUD de autores, categorías y libros; administración de ejemplares físicos.
- Préstamos, devoluciones, disponibilidad e historial.
- Validación de datos, paginación, búsquedas, claves foráneas protegidas y errores HTTP coherentes.

## Requisitos

- Python 3.10 o posterior.
- MySQL 8.0.11+ o MariaDB 10.5+ para despliegue. En desarrollo se puede usar SQLite.

## Desarrollo local

En Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

En Linux/macOS activa el entorno con `source .venv/bin/activate`. La API queda en `http://127.0.0.1:8000/`; Swagger UI está en `/api/docs`, ReDoc en `/api/redoc` y OpenAPI en `/api/openapi.json`. La ruta `/health` permite comprobar el servicio.

SQLite local se crea en `biblioteca.db`. Para un administrador inicial, en otra terminal ejecuta `python -m app.create_admin`; la contraseña se solicita de forma interactiva y no se guarda en argumentos de shell.

## Rutas principales

Las rutas de recursos mantienen el prefijo `/api`:

| Método | Ruta | Acceso |
|---|---|---|
| POST | `/api/auth/register/` | Público; siempre crea lector |
| POST | `/api/auth/token/` | Público; recibe JSON `username` y `password` |
| POST | `/api/auth/token/refresh/` | Público; rota y revoca el refresh anterior |
| GET | `/api/auth/me/` | Usuario autenticado |
| GET/POST | `/api/authors/`, `/api/categories/`, `/api/books/` | Lectura pública; escritura por personal |
| GET/POST/DELETE | `/api/copies/` | Lectura pública; cambios por personal |
| GET/POST | `/api/loans/` | Usuario autenticado; el lector solo crea préstamos propios |
| GET | `/api/loans/active/`, `/api/loans/history/` | Usuario autenticado |
| POST | `/api/loans/{id}/return/` | Propietario del préstamo o personal |
| CRUD | `/api/users/` | Personal; solo administrador asigna o cambia roles |

Swagger documenta los esquemas JSON, parámetros y respuestas. En **Authorize**, ingresa el access token; Swagger agrega el esquema Bearer.

## Reglas y permisos

- Un libro es una ficha bibliográfica; cada `BookCopy` representa un ejemplar físico.
- El préstamo reserva el ejemplar mediante una actualización condicional para evitar dos préstamos simultáneos de la misma copia.
- La devolución libera el ejemplar. Una segunda devolución responde `409`.
- El lector solo puede listar, consultar y devolver sus propios préstamos; el personal ve todos.
- El registro público siempre asigna `reader`; el rol suministrado no permite elevar privilegios.
- Los bibliotecarios pueden gestionar cuentas, pero no enviar el campo `role`; solo administradores pueden asignarlo.
- Contraseñas con hash Argon2; JWT firmados, de corta duración y verificados contra la cuenta actual.
- Eliminaciones que dejarían préstamos o relaciones huérfanas se rechazan.
- Errores habituales: `400` entrada inválida, `401` token ausente/inválido, `403` permiso insuficiente, `404` recurso inexistente y `409` conflicto.

## Despliegue en VPS Ubuntu

Usa una VPS para FastAPI y una base MySQL administrada o privada. No abras el puerto MySQL a toda Internet. La aplicación se ejecuta con Uvicorn y systemd detrás de Nginx; configura dominio y HTTPS antes de exponerla públicamente.

### Instalar

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential pkg-config nginx git
sudo useradd --system --create-home --home-dir /opt/biblioteca --shell /usr/sbin/nologin biblioteca
sudo -u biblioteca git clone https://github.com/IvanRodriguez-CV/Frameworks_Biblioteca.git /opt/biblioteca/app
sudo -u biblioteca python3 -m venv /opt/biblioteca/venv-fastapi
sudo -u biblioteca /opt/biblioteca/venv-fastapi/bin/pip install -r /opt/biblioteca/app/requirements.txt
sudo mkdir -p /etc/biblioteca
```

### Configurar entorno

Crea `/etc/biblioteca/biblioteca.env` con los datos propios del servidor:

```ini
DEBUG=0
SECRET_KEY=REEMPLAZAR_POR_UN_SECRETO_LARGO_ALEATORIO
DB_ENGINE=mysql
DB_NAME=biblioteca_fastapi
DB_USER=biblioteca_app
DB_PASSWORD=REEMPLAZAR_POR_LA_CLAVE_DE_LA_BASE
DB_HOST=servidor.mysql.database.azure.com
DB_PORT=3306
DB_SSL_CA=/ruta/al/certificado-ca.pem
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=1
```

Genera un secreto nuevo, no uses el ejemplo de desarrollo. `DB_SSL_CA` debe apuntar al certificado CA indicado por el proveedor; si el proveedor no lo requiere, deja la variable vacía. No guardes este archivo en Git:

```bash
sudo chown root:www-data /etc/biblioteca/biblioteca.env
sudo chmod 640 /etc/biblioteca/biblioteca.env
```

### Migrar y crear administrador

```bash
sudo systemd-run --wait --pipe --collect --property=User=biblioteca --property=WorkingDirectory=/opt/biblioteca/app --property=EnvironmentFile=/etc/biblioteca/biblioteca.env /opt/biblioteca/venv-fastapi/bin/alembic -c /opt/biblioteca/app/alembic.ini upgrade head
sudo systemd-run --wait --pty --collect --property=User=biblioteca --property=WorkingDirectory=/opt/biblioteca/app --property=EnvironmentFile=/etc/biblioteca/biblioteca.env /opt/biblioteca/venv-fastapi/bin/python -m app.create_admin
```

### Activar Uvicorn y Nginx

Personaliza `tu-dominio.example` en el archivo Nginx. Luego instala los archivos incluidos:

```bash
sudo cp /opt/biblioteca/app/deploy/biblioteca.service /etc/systemd/system/
sudo cp /opt/biblioteca/app/deploy/nginx-rate-limit.conf /etc/nginx/conf.d/biblioteca-rate-limit.conf
sudo cp /opt/biblioteca/app/deploy/nginx-biblioteca.conf /etc/nginx/sites-available/biblioteca
sudo ln -s /etc/nginx/sites-available/biblioteca /etc/nginx/sites-enabled/biblioteca
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now biblioteca
sudo systemctl restart nginx
```

Configura un certificado HTTPS para el dominio (por ejemplo, con Certbot). En el firewall permite SSH y HTTP/HTTPS; limita MySQL a la dirección privada de la VPS. No uses `DEBUG=1` en producción.

Comprobaciones y logs:

```bash
sudo systemctl status biblioteca nginx --no-pager
sudo journalctl -u biblioteca -n 100 --no-pager
curl -fsS http://127.0.0.1/health
```

## Actualizar una VPS que tenía la versión Django

Esta versión FastAPI crea un esquema de base de datos propio mediante Alembic. No ejecutes estas migraciones sobre la base Django ni elimines su entorno o sus datos: las tablas y el formato de contraseñas difieren. Para conservar datos anteriores se requiere exportar y transformar los registros por separado.

Si ya tenías la versión Django en la VPS:

1. Crea y verifica un respaldo de la base Django. Mantén esa base y el entorno virtual anterior mientras compruebas el nuevo servicio.
2. Descarga los cambios: `sudo -u biblioteca git -C /opt/biblioteca/app pull --ff-only origin main`.
3. Crea un entorno aislado `/opt/biblioteca/venv-fastapi` e instala allí los requisitos, sin reutilizar el entorno Django.
4. Crea una base MySQL nueva y vacía, por ejemplo `biblioteca_fastapi`, configura `/etc/biblioteca/biblioteca.env` con esas credenciales, aplica las migraciones Alembic y crea un administrador siguiendo las instrucciones anteriores.
5. Instala los archivos systemd y Nginx FastAPI de `deploy/`, ejecuta `sudo nginx -t`, recarga systemd y reinicia ambos servicios.
6. Comprueba `/health` y `/api/docs`. Conserva la instalación anterior hasta confirmar el funcionamiento.

La actualización del repositorio por sí sola no cambia la aplicación que está ejecutándose ni copia los datos Django a la base nueva.
