from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.errores import ErrorAPI, registrar_manejadores


def _app_de_prueba() -> FastAPI:
    app = FastAPI()
    registrar_manejadores(app)

    class Entrada(BaseModel):
        cantidad: int

    @app.post("/validar")
    def validar(entrada: Entrada) -> dict[str, int]:
        return {"cantidad": entrada.cantidad}

    @app.get("/negocio")
    def negocio() -> None:
        raise ErrorAPI(409, "sin_lista_activa", "No hay una lista de precios activa.")

    @app.get("/explota")
    def explota() -> None:
        raise RuntimeError("detalle interno que no debe salir")

    return app


cliente = TestClient(_app_de_prueba(), raise_server_exceptions=False)


def test_ruta_inexistente_usa_formato_unico() -> None:
    respuesta = cliente.get("/no-existe")

    assert respuesta.status_code == 404
    assert respuesta.json() == {"error": "no_encontrado", "detalle": "Not Found"}


def test_error_de_validacion_lista_los_campos() -> None:
    respuesta = cliente.post("/validar", json={"cantidad": "muchas"})

    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["error"] == "validacion"
    assert cuerpo["detalle"][0]["campo"] == "body.cantidad"


def test_error_de_negocio() -> None:
    respuesta = cliente.get("/negocio")

    assert respuesta.status_code == 409
    assert respuesta.json() == {
        "error": "sin_lista_activa",
        "detalle": "No hay una lista de precios activa.",
    }


def test_error_inesperado_no_filtra_detalles() -> None:
    respuesta = cliente.get("/explota")

    assert respuesta.status_code == 500
    assert respuesta.json() == {"error": "error_interno", "detalle": "Ocurrió un error inesperado."}
