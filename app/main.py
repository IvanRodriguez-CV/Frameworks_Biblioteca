from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.auth import router as auth_router
from app.database import engine
from app.routes import router as api_router

app = FastAPI(
    title="API del Sistema Bibliotecario",
    description=(
        "API REST para gestionar usuarios, autores, categorías, libros, ejemplares y préstamos. "
        "Autenticación JWT y permisos por roles. Todos los mensajes y descripciones se presentan en español."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [
        {
            "campo": ".".join(str(part) for part in error["loc"][1:]),
            "mensaje": error["msg"],
        }
        for error in exc.errors()
    ]
    return JSONResponse(status_code=400, content={"detail": errors})


@app.get("/health", tags=["Sistema"], summary="Comprobar estado")
def health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(api_router)
