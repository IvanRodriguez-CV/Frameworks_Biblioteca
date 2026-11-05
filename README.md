# Sistema Bibliotecario

API REST y sitio web para administrar usuarios, catálogo, ejemplares y préstamos, desarrollado con Django REST Framework.

## Funciones

- Registro de lectores y autenticación JWT con expiración y renovación.
- Roles de administrador, bibliotecario y lector.
- Catálogo de autores, categorías y libros; cada libro cuenta con ejemplares físicos.
- Préstamos, devoluciones, disponibilidad e historial.
- Documentación interactiva en `/api/docs/` y esquema OpenAPI en `/api/schema/`.
- Interfaz web en `/`.

Los lectores pueden consultar el catálogo y gestionar sus propios préstamos. Bibliotecarios y administradores administran el catálogo y las cuentas. Solo un administrador puede asignar o cambiar roles. El registro público siempre crea lectores.

## Requisitos

- Python 3.10 o posterior.
- MySQL compatible con Django 5.2 (MySQL 8.0.11+ o MariaDB 10.5+).
- Para desarrollo local también puede usarse SQLite.

## Desarrollo local

Desde la carpeta del proyecto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

La aplicación queda en `http://127.0.0.1:8000/` y Swagger UI en `http://127.0.0.1:8000/api/docs/`. Para SQLite, deja `DB_ENGINE=sqlite` en `.env`. No copies una base SQLite local al servidor VPS.

## Despliegue en VPS Ubuntu

La aplicación de producción debe ejecutarse con Gunicorn detrás de Nginx y HTTPS; no uses `runserver` en una VPS pública.

### 1. Preparar sistema y aplicación

Instala Python, Nginx y los paquetes necesarios para compilar `mysqlclient`:

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential pkg-config default-libmysqlclient-dev nginx
sudo useradd --system --create-home --home-dir /opt/biblioteca --shell /usr/sbin/nologin biblioteca
```

Clona el repositorio en `/opt/biblioteca/app`, instala dependencias y prepara la carpeta de configuración:

```bash
sudo -u biblioteca git clone https://github.com/IvanRodriguez-CV/Frameworks_Biblioteca.git /opt/biblioteca/app
sudo -u biblioteca python3 -m venv /opt/biblioteca/app/.venv
sudo -u biblioteca /opt/biblioteca/app/.venv/bin/pip install -r /opt/biblioteca/app/requirements.txt
sudo mkdir -p /etc/biblioteca
```

### 2. Configurar secretos y base de datos

Crea una base MySQL vacía (por ejemplo, Azure Database for MySQL Flexible Server), un usuario exclusivo para la aplicación y una conexión TLS limitada a la VPS. No abras MySQL a toda Internet.

Crea `/etc/biblioteca/biblioteca.env` fuera del repositorio con valores propios del servidor:

```ini
DEBUG=0
SECRET_KEY=reemplazar-por-un-secreto-aleatorio-largo
ALLOWED_HOSTS=tu-dominio.example
DB_ENGINE=mysql
DB_NAME=biblioteca_api
DB_USER=biblioteca_app
DB_PASSWORD=reemplazar-por-la-clave-de-la-base
DB_HOST=tu-servidor.mysql.database.azure.com
DB_PORT=3306
DB_SSL_CA=/etc/ssl/certs/ca-certificates.crt
```

Genera un `SECRET_KEY` nuevo y no reutilices las claves de ejemplo. Ajusta la ruta CA a la indicada por tu proveedor y limita permisos del archivo:

```bash
sudo chown root:www-data /etc/biblioteca/biblioteca.env
sudo chmod 640 /etc/biblioteca/biblioteca.env
```

### 3. Inicializar y activar el servicio

Revisa y personaliza los archivos de `/opt/biblioteca/app/deploy/` para tu dominio. Instala la unidad systemd y la configuración de Nginx:

```bash
sudo cp /opt/biblioteca/app/deploy/biblioteca.service /etc/systemd/system/
sudo cp /opt/biblioteca/app/deploy/nginx-biblioteca.conf /etc/nginx/sites-available/biblioteca
sudo ln -s /etc/nginx/sites-available/biblioteca /etc/nginx/sites-enabled/biblioteca
```

Antes de activar Nginx, reemplaza `tu-dominio.example` en su configuración. Después:

```bash
sudo -u biblioteca /opt/biblioteca/app/.venv/bin/python /opt/biblioteca/app/manage.py migrate
sudo -u biblioteca /opt/biblioteca/app/.venv/bin/python /opt/biblioteca/app/manage.py createsuperuser
sudo -u biblioteca /opt/biblioteca/app/.venv/bin/python /opt/biblioteca/app/manage.py collectstatic --noinput
sudo -u biblioteca /opt/biblioteca/app/.venv/bin/python /opt/biblioteca/app/manage.py check --deploy
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now biblioteca
sudo systemctl restart nginx
```

Configura un certificado HTTPS (por ejemplo, con Certbot) antes de usar el sistema públicamente. Abre únicamente SSH y HTTP/HTTPS en el firewall; la base de datos debe aceptar conexiones solo desde la VPS.

Para revisar el servicio:

```bash
sudo systemctl status biblioteca
sudo journalctl -u biblioteca -n 100 --no-pager
```

## Endpoints principales

| Método | Ruta | Acceso |
|---|---|---|
| POST | `/api/auth/register/` | Público; crea lectores |
| POST | `/api/auth/token/` | Público; entrega JWT |
| POST | `/api/auth/token/refresh/` | Público; renueva JWT |
| GET | `/api/auth/me/` | Usuario autenticado |
| GET/POST | `/api/authors/`, `/api/categories/`, `/api/books/` | Lectura pública; escritura por personal |
| GET/POST | `/api/copies/` | Lectura pública; administración por personal |
| GET/POST | `/api/loans/` | Usuario autenticado |
| GET | `/api/loans/active/`, `/api/loans/history/` | Usuario autenticado |
| POST | `/api/loans/{id}/return/` | Propietario del préstamo o personal |
| GET/POST/PATCH/DELETE | `/api/users/` | Administrador o bibliotecario; cambios de rol solo administrador |

Swagger documenta los demás métodos, parámetros y cuerpos de cada operación.

## Reglas principales

- El lector solo puede pedir ejemplares disponibles para sí mismo.
- Una reserva condicional del ejemplar evita préstamos simultáneos del mismo ejemplar.
- Al devolver se libera el ejemplar; un segundo intento se rechaza.
- Los préstamos se conservan como historial.
- La eliminación de libros o usuarios con relaciones protegidas se rechaza.
- Entradas inválidas responden `400`; autenticación faltante o inválida `401`; falta de permisos `403`; conflictos de disponibilidad o integridad `409`.

## Demostración manual

La rúbrica solicita demostrar los flujos funcionales, no conservar una suite de pruebas automatizadas:

1. Registra un lector, inicia sesión y muestra los tokens. Comprueba también un login inválido.
2. Sin token, consulta préstamos activos y confirma `401`; como lector, intenta escribir en catálogo y confirma `403`.
3. Como personal, crea autor, categoría y libro con ejemplar disponible.
4. Como lector, solicita el ejemplar y confirma que ya no está disponible.
5. Intenta pedirlo otra vez y confirma `409`; devuelve el préstamo y comprueba que vuelve a estar disponible.
6. Intenta cambiar un rol como bibliotecario (rechazado) y muestra que solo un administrador puede asignar roles.
