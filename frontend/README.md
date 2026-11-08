# Frontend — NexusMayorista

Next.js (App Router) + TypeScript + Tailwind. Usa Supabase Auth para el login y manda el JWT a la API FastAPI.

## Puesta en marcha

```bash
cp .env.example .env.local   # completar URL y anon key de Supabase, y la URL de la API
npm install
npm run dev                  # http://localhost:3000
```

En el backend, `CORS_ORIGENES` tiene que incluir la URL del frontend (por defecto `http://localhost:3000`).

## Pantallas

| Ruta | Qué hace |
| --- | --- |
| `/login` | Entrar con email y contraseña (usuario creado en Supabase Auth) |
| `/configuracion/reglas` | Preguntas a la fábrica: las respuestas cambian el cálculo de presupuestos |
| `/configuracion/reglas/ficha` | Ficha para que la fábrica confirme: imprimir o guardar PDF, o copiar para WhatsApp |

El tablero (HU-06) se suma el día 9.
