# BOT440

Bot conversacional de 440 Clinic by Dr. Giovanni Fuentes.

## Tests de regresión

### Regla obligatoria — antes de CUALQUIER commit a `main`

**PASO 1** — correr los tests:

```bash
python3 tests/regression_bot.py
```

**PASO 2** — interpretar el resultado:

- ✅ **Si todos pasan** → commitear y deployar.
- ❌ **Si algún test falla** → NO commitear, arreglar el problema y volver al PASO 1.

Esta regla aplica para cualquier cambio por pequeño que sea.

### Detalles

El script simula mensajes contra `/webhook` (estética) y `/webhook-cx`
(cirugías) en producción y verifica las respuestas del bot leyendo
`conversaciones_440` en Supabase.

Requiere las variables de entorno `SUPABASE_URL` y `SUPABASE_ANON_KEY`
(las mismas del bot).

El script sale con código 0 si todos los tests pasan, 1 si hay fallas.
