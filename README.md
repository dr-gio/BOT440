# BOT440

Bot conversacional de 440 Clinic by Dr. Giovanni Fuentes.

## TESTING — REGLAS OBLIGATORIAS

### ⚡ Quick Check (30 segundos)

```bash
python3 tests/quick_check.py
```

Usar cuando cambias:
- Texto o mensajes al paciente
- Precios o nombres de servicios
- Emojis o formato visual
- `knowledge/440clinic.md`

### 🔬 Regression Completa (8 minutos)

```bash
python3 tests/regression_bot.py
```

Usar cuando cambias:
- Lógica o flujo del bot
- `brain.py` o `brain_cx.py`
- Webhooks Python
- Workflows n8n (W21/W22)
- Cualquier cambio de comportamiento

### REGLA SIMPLE

- ¿Cambié solo texto/palabras? → **Quick check (30 seg)**
- ¿Cambié lógica/código/flujo? → **Regression completa (8 min)**
- ¿No estoy seguro? → **Regression completa (8 min)**

### Detalles

`quick_check.py` verifica que todos los endpoints respondan (GET y POST)
sin tocar Supabase ni el modelo. Diseñado para detectar quiebres tras
deploys de texto/copys.

`regression_bot.py` simula conversaciones completas contra `/webhook` y
`/webhook-cx` en producción y verifica las respuestas del bot leyendo
`conversaciones_440` en Supabase. Requiere `SUPABASE_URL` y
`SUPABASE_ANON_KEY` en el entorno.

Ambos salen con código 0 si todos los tests pasan, 1 si hay fallas.
