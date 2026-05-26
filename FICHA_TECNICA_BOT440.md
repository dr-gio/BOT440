# FICHA TÉCNICA — BOT440

**Documento de referencia.** Léelo antes de tocar el bot. Actualizado: 2026-05-26.

---

## 1. Ubicación

| Item | Valor |
|---|---|
| Repo local (Mac Dr. Gio) | `/Users/comandocentral440/BOT440` |
| Remote GitHub | `https://github.com/dr-gio/BOT440` |
| Branch productiva | `main` |
| Proyecto Vercel | `dr-gios-projects/bot-440` (project id `prj_YUkfTvPRgJpzvNiXzEou5sWPl771`) |
| URL producción | `https://bot-440.vercel.app` |
| Deploy | Auto en cada `git push origin main`. Vercel detecta, builda y publica en ~30 s. |
| Lenguaje | Python (runtime `@vercel/python`, configurado en `vercel.json`) |
| Framework | Sin framework — handlers nativos de Vercel Python. Cada archivo en `api/` exporta `handler`. |

### Estructura

```
BOT440/
├── api/                                  ← endpoints serverless (1 archivo = 1 endpoint)
│   ├── webhook.py                        → /webhook         (WhatsApp estética, brain.py)
│   ├── webhook-cx.py                     → /webhook-cx      (WhatsApp cirugía, brain_cx.py)
│   ├── webhook-ig.py                     → /webhook-ig      (Instagram estética)
│   ├── webhook-ig-simple.py              → /webhook-ig-simple
│   ├── webhook-ig-cx.py                  → /webhook-ig-cx   (Instagram @drgiovannifuentes)
│   ├── webhook-ig-cx-simple.py           → /webhook-ig-cx-simple
│   ├── test-ig-send.py                   → /test-ig-send    (diagnóstico)
│   └── test-ig-roles.py                  → /test-ig-roles   (diagnóstico)
├── core/
│   ├── brain.py                          ← Cerebro ESTÉTICA (clase Brain)
│   ├── brain_cx.py                       ← Cerebro CIRUGÍA  (clase BrainCX)
│   ├── whapi.py                          ← Cliente WhApi compartido (WhapiClient)
│   └── instagram.py                      ← Cliente Instagram Graph API
├── knowledge/
│   └── 440clinic.md                      ← Conocimiento de marca (referencial, no se inyecta)
├── vercel.json                           ← config Vercel (rutas + maxDuration)
├── requirements.txt                      ← deps Python
└── README.md / RULES.md
```

### Rutas en `vercel.json`

```json
{
  "/webhook"               → api/webhook.py
  "/webhook-ig"            → api/webhook-ig.py
  "/webhook-ig-simple"     → api/webhook-ig-simple.py
  "/webhook-cx"            → api/webhook-cx.py
  "/webhook-ig-cx"         → api/webhook-ig-cx.py
  "/webhook-ig-cx-simple"  → api/webhook-ig-cx-simple.py
  "/test-ig-send"          → api/test-ig-send.py
  "/test-ig-roles"         → api/test-ig-roles.py
}
```

---

## 2. Los bots

Dos cerebros independientes que comparten cliente WhApi y persistencia en Supabase.

| Cerebro | Archivo | Clase | Canales que atiende | Cuenta WhApi |
|---|---|---|---|---|
| Estética | `core/brain.py` | `Brain` | WhatsApp `440 Clinic by Dr. Gio` + Instagram `@440clinic` | `WHAPI_TOKEN` |
| Cirugía | `core/brain_cx.py` | `BrainCX` | WhatsApp `Dr Gio plastic surgery` + Instagram `@drgiovannifuentes` | `WHAPI_TOKEN_CX` (fallback a `WHAPI_TOKEN` si no está) |

### Modelo IA

- **Claude `claude-haiku-4-5-20251001`** (Anthropic API).
- Confirmado en ambos cerebros tras revert del 24-may (`ef3d31e`). Sonnet-4 estuvo probado un día y se revirtió.
- API key: env var `ANTHROPIC_API_KEY`.

### System prompts

| Cerebro | Variable / constante | Archivo | Tamaño aprox |
|---|---|---|---|
| Estética | `SYSTEM` (string global al inicio del archivo) | `core/brain.py` líneas ~20-1200 | ~1100 líneas de prompt |
| Cirugía | `CX_SYSTEM` (string global) | `core/brain_cx.py` líneas ~20-1170 | ~1150 líneas de prompt |

Ambos prompts incluyen reglas de marca, flujo de cierre, formato `<<<NOTIFY>>>...<<<END>>>`, datos obligatorios, y casos especiales (sin correo, sin nombre, etc.).

---

## 3. WhApi

Plataforma para WhatsApp Business. 2 canales, 2 tokens.

| Cuenta | Token (env var) | Nombre business | Número (`from`) | Webhook configurado |
|---|---|---|---|---|
| Estética | `WHAPI_TOKEN` | `440 Clinic By Dr Gio Medicina Estética y Bienestar` | (visible en `/settings` de WhApi) | `https://bot-440.vercel.app/webhook` |
| Cirugía | `WHAPI_TOKEN_CX` | `Dr Gio plastic surgery` | `573137917168` | `https://bot-440.vercel.app/webhook-cx` |

**Base API:** `https://gate.whapi.cloud` (env `WHAPI_URL`).

### Cómo verificar si un token está vivo (sin enviar mensaje)

```bash
TOK='<el token>'
curl -sS -H "Authorization: Bearer $TOK" https://gate.whapi.cloud/health
# Respuesta esperada: HTTP 200, JSON con "status":{"code":4,"text":"AUTH"} + datos del business
# Si devuelve 401/403 → token vencido o revocado, hay que regenerarlo en WhApi dashboard
```

```bash
# Settings — confirma el webhook URL configurado en el canal
curl -sS -H "Authorization: Bearer $TOK" https://gate.whapi.cloud/settings | python3 -m json.tool
# Buscar "webhooks":[{"url":"..."}]
```

### Cliente Python

`core/whapi.py` — clase `WhapiClient`. Métodos: `send_text(to, text)`, `send_image(to, url, caption)`. Loguea `[WHAPI INIT]`, `[WHAPI] POST ...`, `[WHAPI] OK sent=...`, `[WHAPI] HTTPError ...`.

---

## 4. Variables de entorno

Todas se configuran en **Vercel → bot-440 → Settings → Environment Variables**. Replica local en `.env.test` (no commiteado).

| Variable | Para qué | Quién la usa |
|---|---|---|
| `ANTHROPIC_API_KEY` | API key de Claude | brain.py + brain_cx.py |
| `WHAPI_TOKEN` | Token canal estética | brain.py, fallback de brain_cx |
| `WHAPI_TOKEN_CX` | Token canal cirugía | brain_cx.py |
| `WHAPI_URL` | Base de WhApi (default `https://gate.whapi.cloud`) | whapi.py |
| `SUPABASE_URL` | URL del proyecto Supabase (`https://snxidbyysfhzmgyqtsjg.supabase.co`) | Ambos cerebros (historial + leads) |
| `SUPABASE_ANON_KEY` | Anon key Supabase | Ambos cerebros |
| `SUPABASE_URL_CRM` | URL Supabase CRM (si separado) | `_upsert_lead_comercial` de brain.py |
| `SUPABASE_KEY_CRM` | Key Supabase CRM | `_upsert_lead_comercial` |
| `IG_PAGE_ACCESS_TOKEN` | Token Instagram `@440clinic` (estética) | instagram.py vía brain.py |
| `IG_ACCOUNT_ID` | Account ID Instagram estética | instagram.py |
| `IG_CX_PAGE_ACCESS_TOKEN` | Token Instagram `@drgiovannifuentes` (cirugía) | brain_cx.py |
| `IG_CX_ACCOUNT_ID` | Account ID Instagram cirugía | brain_cx.py |
| `IG_VERIFY_TOKEN` | Token de verificación webhooks Meta | webhook-ig*.py |
| `N8N_CHECK_SLOTS` | URL del webhook W21 (check slots estética) | brain.py |
| `N8N_CREATE_EVENT` | URL del webhook W22 (create event estética) | brain.py |
| `CHECK_SLOTS_CX_URL` (a.k.a. `N8N_CHECK_SLOTS_CX`) | URL W21-CX (check slots cirugía) | brain_cx.py |
| `CREATE_EVENT_CX_URL` (a.k.a. `N8N_CREATE_EVENT_CX`) | URL W22-CX (create event cirugía) | brain_cx.py |
| `ASESORA_1` | Teléfono Bibiana (con código país, sin `+`) | brain_cx.py rotación |
| `ASESORA_2` | Teléfono Sara | brain_cx.py rotación |
| `ASESORA_3` | Teléfono Lucero | brain_cx.py rotación |
| `DRA_SHARON` | Teléfono Dra. Sharon (notificación cirugía) | brain_cx.py |
| `ADMIN_CX` | Teléfono Central (cirugía) | brain_cx.py |
| `ADMIN_WHATSAPP` | Teléfono Central (uso general) | brain.py |
| `DRGIO_TEL` | Teléfono Dr. Gio (todos los avisos) | brain_cx.py (fallback `573181800131`) |
| `TELEGRAM_WEBHOOK_SECRET` | (si se conecta Telegram, no usado actualmente) | — |
| `ANTHROPIC_API_KEY` | Ya listado | — |
| (Otras `VERCEL_*`, `TURBO_*`, `NX_*`) | Inyectadas automáticamente por Vercel/Turbo | — |

**Mapa nombre → variable de asesoras** (`brain_cx.py` líneas 1180-1190):

```python
ASESORAS     = ['bibiana', 'sara', 'lucero']
ASESORA_ENV  = {'bibiana': 'ASESORA_1', 'sara': 'ASESORA_2', 'lucero': 'ASESORA_3'}
ASESORA_LABEL= {'bibiana': 'Bibiana',   'sara': 'Sara',      'lucero': 'Lucero'}
```

---

## 5. Avisos internos (NOTIFY al staff)

### Formato del bloque que emite Claude

```
<<<NOTIFY>>>
nombre: María
telefono: 573012345678
ciudad: Barranquilla
procedimiento: lipoescultura
score: CALIENTE
asesora: bibiana          (solo prediagnóstico)
fecha: Martes 2 Jun 4:30 PM (solo prediagnóstico)
tipo: prediagnostico virtual | valoracion | cita_estetica | ...
<<<END>>>
```

### Regex que lo captura

```python
re.search(r'<<<NOTIFY>>>(.*?)<<<END>>>', full_response, re.DOTALL)
```
Misma regex en `brain.py` línea 2279 y `brain_cx.py` línea 2955.

### Funciones de envío

| Cerebro | Función | Archivo / línea | Lógica |
|---|---|---|---|
| Estética | `_notify_admin` | `core/brain.py` línea 2398 | Envía a **4 fijos hardcodeados** (class attrs) |
| Cirugía | `_notify_lead` | `core/brain_cx.py` línea 2171 | Routing por score (URGENTE/CALIENTE/TIBIO/FRÍO) + asesora del turno |

### Destinatarios fijos (brain.py — estética)

Hardcodeados en `core/brain.py` líneas 2312-2315:

```python
SARA_TEL       = '573105762900'   # Sara (asesora estética)
DRA_SHARON_TEL = '573015135214'   # Dra. Sharon
CENTRAL_TEL    = '573181800130'   # Central 440
DR_GIO_TEL     = '573181800131'   # Dr. Gio
```

Sara siempre recibe (es la asesora única de estética actualmente).

### Destinatarios dinámicos (brain_cx.py — cirugía)

Por env vars (no hardcodeado):
- Asesora del turno (de `ASESORA_1/2/3` según rotación o slot elegido)
- `DRA_SHARON`
- `ADMIN_CX` (central)
- `DRGIO_TEL`

### Anti-duplicado (ventana 24h)

| Cerebro | Helper | Cómo funciona |
|---|---|---|
| Estética | `_already_notified` (brain.py línea 1523) | Query a `conversaciones_440` buscando `direccion=saliente AND mensaje ILIKE '%NOTIFY%' AND created_at >= now() - 24h` para el `sender_id` |
| Cirugía | `_already_notified_cx` (brain_cx.py línea 1266) | Misma lógica que arriba |

**Regla crítica:** el chequeo DEBE ejecutarse **antes** del `_save_message` que persiste `full_response` (porque `full_response` contiene el literal `<<<NOTIFY>>>` y la query lo detectaría como propio → self-block).

- brain.py ya lo hace correcto (líneas 2286 y 2376).
- brain_cx.py **lo hace correcto desde 2026-05-26 con el fix `aab2e9d`** (ver §8).

---

## 6. Base de datos

Proyecto Supabase: **`snxidbyysfhzmgyqtsjg`**  
URL: `https://snxidbyysfhzmgyqtsjg.supabase.co`

### Tablas usadas por el bot

| Tabla | Para qué |
|---|---|
| `conversaciones_440` | Historial completo de mensajes (entrante + saliente). Columnas: `id, contacto_telefono, contacto_nombre, canal, cuenta_receptora, mensaje, direccion (entrante/saliente), remitente (paciente/bot), leido, created_at`. Es la única fuente de verdad para historial conversacional. **OJO**: cuando se guarda saliente, `mensaje` contiene `full_response` con el bloque `<<<NOTIFY>>>` aún incluido (no strippeado). |
| `pacientes_440` | Pacientes recurrentes (memoria entre conversaciones). Se upsertea al primer turno. |
| `leads_comerciales` | CRM de leads (cirugía + estética). Columnas relevantes: `nombre, telefono, procedimiento_interes, asesora_asignada, categoria, prioridad, ciudad, etapa, bot_pausado, fecha_lead`. El bot respeta `bot_pausado=true` (pausa manual desde CRM). |
| `asesoras_cola` | Cola/registro de asesoras y su orden de rotación. |
| `asesoras_turno` | Estado actual del turno por canal (`cirugia`, `cirugia_valoracion`, `whatsapp`). Avanza con `_set_ultima_asesora`. |
| `telegram_conversations` / `telegram_logs` | Para el bot Telegram (no usado en producción todavía). |

### Asignación de leads — turno rotativo

Orden fijo: **bibiana → sara → lucero → bibiana …**

Lógica en `brain_cx.py`:
- `_next_asesora(canal)` lee de `asesoras_turno`, calcula la siguiente, devuelve `(slug, label, phone)`.
- `_set_ultima_asesora(slug, canal)` avanza el turno **solo después** de confirmar el agendamiento.
- Score **URGENTE** → todas las asesoras + Sharon + Central, **NO avanza** turno.
- Score **CALIENTE/TIBIO** → asesora en turno + Sharon + Central, **SÍ avanza**.
- Score **FRÍO** → solo Sharon + Central, **NO avanza**.
- **Prediagnóstico agendado** → asesora del slot + Sharon + Central + Dr. Gio, avanza turno.

### Canales del turno (brain_cx)

- `cirugia` → prediagnóstico
- `cirugia_valoracion` → valoración con Dr. Gio (presencial/virtual)

---

## 7. Guía rápida — "Si pasa X, revisa Y"

Comando base para todos los casos:
```bash
vercel logs https://bot-440.vercel.app --no-follow --limit 3000 --json | grep -i "PATRÓN"
```

### Caso A — "Los avisos al staff no llegan"

```bash
# 1. ¿Claude emite NOTIFY?
vercel logs https://bot-440.vercel.app --no-follow --limit 3000 --json | grep "NOTIFY fields"

# 2. ¿La dedup está bloqueando?
vercel logs https://bot-440.vercel.app --no-follow --limit 3000 --json | grep "NOTIFY duplicado"

# 3. ¿Llegó a _notify_lead?
vercel logs https://bot-440.vercel.app --no-follow --limit 3000 --json | grep "_notify_lead tipo"

# 4. ¿Se enviaron los WhApi?
vercel logs https://bot-440.vercel.app --no-follow --limit 3000 --json | grep "notify results="
# Esperado: {'asesora': True, 'sharon': True, 'central': True, 'drgio': True}
```

Si `NOTIFY fields` aparece pero `_notify_lead` no → bug tipo self-block (revisa orden de `_already_notified_cx` vs `_save_message`).  
Si `_notify_lead` aparece pero `notify results` muestra `False` → el WhApi falló o el env var del destinatario está vacío. Revisa env vars en Vercel.

### Caso B — "El bot no responde a clientes"

```bash
# ¿Llega el webhook?
vercel logs https://bot-440.vercel.app --no-follow --limit 3000 --json | grep "WEBHOOK-CX] POST recibido\|WEBHOOK] POST"

# ¿Claude respondió?
vercel logs https://bot-440.vercel.app --no-follow --limit 3000 --json | grep "Claude len="

# ¿WhApi mandó el mensaje?
vercel logs https://bot-440.vercel.app --no-follow --limit 3000 --json | grep "send_text OK\|❌ SEND ERROR"
```

Si no llega el webhook: revisa `https://gate.whapi.cloud/settings` con el token de la cuenta — el webhook URL debe apuntar a `https://bot-440.vercel.app/webhook` (o `/webhook-cx`).  
Si el token está caído (`/health` devuelve 401): regenerar en WhApi dashboard y actualizar env var en Vercel + redeploy (`vercel --prod` o trigger push).

### Caso C — "El lead no se asigna o se asigna 2x a la misma asesora"

```bash
vercel logs https://bot-440.vercel.app --no-follow --limit 3000 --json | grep "next_asesora\|turno avanzado\|PREDIAGNÓSTICO →"
```

Verifica también que `asesoras_turno` en Supabase tenga estado actualizado:
```sql
SELECT * FROM asesoras_turno WHERE canal IN ('cirugia', 'cirugia_valoracion');
```

### Caso D — "Quiero pausar el bot para un paciente específico"

```sql
UPDATE leads_comerciales SET bot_pausado = true WHERE telefono = '<sender>';
```
El bot lee `bot_pausado` al inicio de cada turno y se calla si está `true` (commit `3056207`).

### Caso E — "Quiero ver toda la conversación de un paciente"

```sql
SELECT created_at, direccion, remitente, LEFT(mensaje, 200) AS msg
FROM conversaciones_440
WHERE contacto_telefono = '<numero>'
ORDER BY created_at;
```

---

## 8. Historial de bugs

### 2026-05-26 — Self-dedup loop en avisos al staff

- **Síntoma:** desde el 25-may 06:15 ningún aviso al staff (Sara/Sharon/Central/Gio) llegaba. El bot seguía conversando con clientes normal.
- **Causa:** commit `795519f` (25-may 06:15) agregó `_already_notified_cx` para deduplicar NOTIFYs en `brain_cx.py`, pero lo posicionó **después** de `_save_message(full_response, 'saliente')`. Como `full_response` contenía el literal `<<<NOTIFY>>>...<<<END>>>`, la query `mensaje ILIKE '%NOTIFY%'` matcheaba el row recién insertado → True → skip → 0 envíos.
- **Evidencia:** Vercel logs 20 min: 60 `NOTIFY fields=` + 60 `NOTIFY duplicado` + 0 `_notify_lead`.
- **Fix:** commit `aab2e9d` — invertir el orden. Se evalúa `_already_notified_cx` **antes** del `_save_message`, se guarda en variable local `already_notified`, y el check posterior usa la variable. `brain.py` (estética) ya tenía el patrón correcto (líneas 2286 y 2376 con comentario explícito).
- **Verificación:** primer lead post-deploy (15:11 Bogotá, María, prediagnóstico CALIENTE con Bibiana) → `notify results={'asesora': True, 'sharon': True, 'central': True, 'drgio': True}`. ✅
- **TODO fase 2:** migrar dedup a `leads_comerciales.notificado_at` (opción C) para desacoplar la señal de la persistencia del mensaje.

### [futuros bugs — agregar aquí con fecha + síntoma + causa + commit del fix]

---

## Apéndice — Comandos útiles de Vercel CLI

```bash
# Login
vercel login

# Ver deploys recientes
vercel ls

# Ver logs en tiempo real
vercel logs https://bot-440.vercel.app

# Logs históricos (sin --follow)
vercel logs https://bot-440.vercel.app --no-follow --limit 3000 --json > /tmp/logs.json

# Forzar redeploy (sin cambios de código)
git commit --allow-empty -m "chore: redeploy" && git push origin main
```

## Apéndice — Convención de logging del bot

Todo log de Python usa `print(..., flush=True)` (importante: sin `flush=True` Vercel no captura).

Prefijos:
- `[WEBHOOK-CX]` / `[WEBHOOK]` — entrada del webhook
- `[CX]` — cerebro cirugía (brain_cx.py)
- `[BRAIN]` — cerebro estética (brain.py)
- `[WHAPI]` — cliente WhApi
- `[IG INIT]` / `[IG]` — cliente Instagram
- `[CX] ✅` / `[CX] ❌` — resultado de envío
