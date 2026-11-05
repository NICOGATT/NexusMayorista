# Log del Sprint 1

## Mar 03/11
- Hice: esqueleto FastAPI en `backend/app/` (`config.py`, `db.py`, `errores.py`, `auth.py`, `main.py`, `routers/`, `services/`). `/health` con `SELECT 1` (200 ok, 503 si la base no responde). Formato de error único `{"error", "detalle"}` para 4xx, validación y 500. Validación del JWT de Supabase (HS256, audiencia `authenticated`) en todo `/api/v1`; `/health`, `/docs` y los futuros `/webhooks/*` quedan públicos. Endpoint `GET /api/v1/yo` para probar el token. 14 tests (pytest) y ruff en verde. CI en `.github/workflows/ci.yml`. `backend/.env.example` con todas las variables. Se agregó `PyJWT` a `requirements.txt`.
- Sigue: desplegar en Railway o Render (root `backend/`, comando `uvicorn app.main:app --host 0.0.0.0 --port $PORT`) con las variables de entorno y abrir `/health` y `/docs` en la URL pública. Crear el tablero personal con las 8 historias. Pendiente del día 1: Alembic y la migración del esquema.
- Bloqueos: ninguno. Nota: el `.venv` local es Python 3.13; la CI usa 3.12 como dice el plan. Si el proyecto de Supabase usa claves de firma asimétricas (JWKS) en vez del JWT Secret legacy, hay que adaptar `app/auth.py`.
