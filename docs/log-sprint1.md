# Log del Sprint 1

## Mar 03/11
- Hice: esqueleto FastAPI en `backend/app/` (`config.py`, `db.py`, `errores.py`, `auth.py`, `main.py`, `routers/`, `services/`). `/health` con `SELECT 1` (200 ok, 503 si la base no responde). Formato de error único `{"error", "detalle"}` para 4xx, validación y 500. Validación del JWT de Supabase (HS256, audiencia `authenticated`) en todo `/api/v1`; `/health`, `/docs` y los futuros `/webhooks/*` quedan públicos. Endpoint `GET /api/v1/yo` para probar el token. 14 tests (pytest) y ruff en verde. CI en `.github/workflows/ci.yml`. `backend/.env.example` con todas las variables. Se agregó `PyJWT` a `requirements.txt`.
- Sigue: desplegar en Railway o Render (root `backend/`, comando `uvicorn app.main:app --host 0.0.0.0 --port $PORT`) con las variables de entorno y abrir `/health` y `/docs` en la URL pública. Crear el tablero personal con las 8 historias. Pendiente del día 1: Alembic y la migración del esquema.
- Bloqueos: ninguno. Nota: el `.venv` local es Python 3.13; la CI usa 3.12 como dice el plan. Si el proyecto de Supabase usa claves de firma asimétricas (JWKS) en vez del JWT Secret legacy, hay que adaptar `app/auth.py`.

## Jue 05/11
- Hice: pendiente del día 1. Alembic inicializado en `backend/` (`alembic.ini`, `migrations/env.py` toma `DATABASE_URL` de `app.config`). Migración `0001_esquema_inicial` con el esquema de la sección 2: 4 enums, 8 tablas, índices, triggers de `actualizado_en` e historial de etapas, RLS con política para `authenticated` en las 8 tablas (y RLS en `alembic_version` para que no quede expuesta por la API de Supabase). Aplicada en Supabase y verificada: 8 tablas con RLS, subtotal generado, historial al cambiar de etapa, una sola lista activa, cliente sin identificador rechazado. Probado `downgrade base` + `upgrade head`. Conexión local por Session pooler (el host directo es solo IPv6).
- Sigue: abrir el PR del día 2 y este; desplegar en Railway/Render; arrancar HU-01 (día 3) y HU-05 (día 4), que vienen atrasados un día.
- Bloqueos: ninguno.
