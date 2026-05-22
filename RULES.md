# REGLAS DEL ECOSISTEMA 440 CLINIC

Última actualización: 2026-05-22

---

## ARQUITECTURA DEL SISTEMA

### Proyectos y sus propósitos

| Proyecto    | URL                              | Repo / Branch                       | Propósito                          |
|-------------|----------------------------------|-------------------------------------|------------------------------------|
| BOT440      | bot-440.vercel.app               | `BOT440/main`                       | Bot WhatsApp / Instagram           |
| CORE440 CRM | core440-440clinic.vercel.app     | `SIC440-EMR/feature/core440`        | CRM comercial asesoras             |
| SIC440 EMR  | sic-440-emr.vercel.app           | `SIC440-EMR/main`                   | Historia clínica electrónica       |

### Supabase

- **Proyecto único**: `snxidbyysfhzmgyqtsjg` (historia-clinica).
- Los tres proyectos comparten la misma base de datos.

| Origen        | Tablas                                                                                                   |
|---------------|----------------------------------------------------------------------------------------------------------|
| BOT440        | `conversaciones_440`, `pacientes_440`, `agendamientos_440`, `asesoras_turno`                             |
| CRM           | `leads_comerciales`, `seguimientos_comerciales`, `presupuestos`, `prediagnosticos_comerciales`           |
| Clínicas EMR  | `historia_clinica`, `pacientes`, `encuentros`, `consentimientos`, `sesiones_spa`, `programacion_quirurgica`, etc. |

---

## REGLAS POR PROYECTO

### 🤖 BOT440 — REGLAS ABSOLUTAS

**Tests obligatorios antes de commitear:**

- Cambios de texto / formato / mensajes → `python3 tests/quick_check.py` (30 s).
- Cambios de lógica / flujo / state machine → `python3 tests/regression_bot.py` (8 min).
- Si algún test falla → **NO commitear**.

**Archivos críticos (no tocar sin tests):**

- `core/brain.py` — bot estética.
- `core/brain_cx.py` — bot cirugías.
- `api/webhook.py`.
- `api/webhook-cx.py`.

**Workflows n8n intocables:**

- W19 — Bot WhatsApp Cirugías legacy.
- W20 — Instagram Bot.
- W21 — Agendamiento estética.
- W21-CX — Check Slots cirugías.
- W22-CX — Create Event cirugías.

---

### 🖥️ CORE440 CRM — REGLAS

- **Branch**: siempre trabajar en `feature/core440`.
- **NUNCA** hacer merge a `main` sin autorización del Dr. Gio.
- TypeScript debe compilar sin errores antes de commitear (`npx tsc --noEmit -p .`).

**Roles en el CRM:**

- `asesora` ve **TODO** el CRM:
  - Leads, Pipeline, Conversaciones, Prediagnósticos, Presupuestos, Catálogo, Documentos.
  - **NO** ve: Marketing, Clínico, Financiero, Dashboard CEO, Reportes CEO, Agente IA.
- `admin` / Dr. Gio: ve todo el sistema.

**Pipeline:**

- 💆 **Estética** (`categoria='estetica'`):
  `lead → contactado → cita_agendada → asistio → venta_cerrada → fidelizado` (+ `perdido`).
- 🔬 **Cirugías** (`categoria='quirurgico'`):
  `lead → prediagnostico → consulta_agendada → pago_consulta → en_consulta → cotizacion_enviada → negociacion → vendido → servicio_programado → completado` (+ `perdido`).
- No se puede retroceder de etapa (excepto a `perdido`).

**Campo asesora (CRM y bot):**

- Usar `asesora_asignada` (text slug: `'sara'`, `'bibiana'`, `'lucero'`).
- **NO** usar `asesora_id` (legado SIC440 EMR Vite).
- Los dos campos coexisten en `leads_comerciales`; el CRM nuevo y el bot escriben siempre el slug.

---

### 🏥 SIC440 EMR — REGLAS ABSOLUTAS

- **Branch `main` = INTOCABLE** salvo cambios clínicos aprobados por Dr. Gio.
- **NUNCA** hacer merge de `feature/core440` → `main`.
- **Propósito**: SOLO clínico. **NADA** comercial en el EMR.

**Roles en SIC440:**

- `asesora` → redirige automáticamente a `core440-440clinic.vercel.app`. **NO** tiene acceso al EMR.
- `medico` → acceso clínico completo.
- `admin` → acceso total.
- `enfermeria` → solo clínico.
- `anestesiologo` → solo clínico (valoración preanestésica, registro anestésico).

**Rutas públicas — ABSOLUTAMENTE INTOCABLES** (las abre el paciente desde su correo):

- `/prediag/:token`
- `/presupuesto/:token`
- `/firma/:token` (alias `/firmar/:token`)
- `/formula/:token`
- `/laboratorio/:token`
- `/imagen/:token`

Estas rutas se resuelven **antes** del auth guard en `src/App.jsx`. Mover cualquiera detrás del guard = romper email a paciente.

**Tablas clínicas intocables desde CRM o bot:**

- `historia_clinica`
- `encuentros`
- `consentimientos`
- `firma_digital`
- `sesiones_spa`
- `programacion_quirurgica`

Ver también `src/REGLAS_CRITICAS.md` para reglas finas del EMR (consentimientos, n8n W6/W7/W8, PDF móvil, identidad visual, etc.).

---

### 🗄️ SUPABASE — REGLAS

- **NUNCA** borrar datos sin confirmación del Dr. Gio.
- **NUNCA** modificar tablas clínicas desde el CRM ni desde el bot.
- Cambios de schema (CREATE / ALTER / DROP) → reportar **SIEMPRE** antes de ejecutar.

**Separación sagrada:**

- Datos clínicos **NUNCA** en el CRM.
- Datos comerciales **NUNCA** en el EMR.
- El bot **NUNCA** toca tablas clínicas.

---

### 🔒 SEGURIDAD

- **NUNCA** mostrar en logs ni código:
  - `service_role` keys.
  - API keys, tokens (WhApi, Anthropic, etc.).
  - Contraseñas.
- Las variables sensibles van **SIEMPRE** en Vercel `--sensitive` o como envs encrypted.
- **NUNCA** commitear credenciales.

---

## FLUJO DE TRABAJO

1. **Reportar** qué archivo se va a cambiar antes de tocarlo.
2. Cambio **mínimo** necesario.
3. Correr **tests correspondientes** (bot: quick_check/regression; CRM: tsc).
4. **Reportar** resultado.
5. **Commitear** solo si todo pasa.

---

## CONEXIÓN CRM → EMR (pendiente / futuro)

Cuando un lead pasa a etapa `consulta_agendada` o `vendido` en el CRM → crear automáticamente el paciente en SIC440 EMR.

El EMR solo existe para pacientes **confirmados** que vienen a la clínica.

---

## PROYECTOS PROTEGIDOS — NO TOCAR SIN AUTORIZACIÓN

- ❌ `landing-belleza440`
- ❌ `dr-gio-content-hub`
- ❌ `suite-medica-440`
- ❌ `portal-440clinic`
- ❌ `agenda-pro-440`
- ❌ `sic-440-emr` (producción — branch `main`)
