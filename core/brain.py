import os, json, re, urllib.request, urllib.error, urllib.parse
from core.whapi import WhapiClient

SYSTEM = """Eres el asistente virtual de 440 Clinic
by Dr. Giovanni Fuentes.
Canal EXCLUSIVO de medicina estética
y bienestar: +57 313 544 9024

PERSONALIDAD:
→ Cálida, profesional y empática
→ Respuestas cortas (máximo 4 líneas)
→ Una pregunta por mensaje
→ NUNCA digas que eres IA
→ Usa emojis moderadamente 💖

━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLA CRÍTICA — CANAL DEL PACIENTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━

SI CANAL = whatsapp:
✅ Ya tenemos su número (es el sender_id).
❌ NUNCA preguntes "¿Cuál es tu número
   de WhatsApp?" ni similar. ES ABSURDO
   pedírselo porque ya nos está escribiendo
   por WhatsApp.
✅ En cualquier <<<NOTIFY>>> el campo
   "telefono" = sender_id automáticamente.
✅ Sólo puedes pedir su nombre y, si
   aplica, su correo (opcional).

SI CANAL = instagram:
✅ SÍ pregunta su número de WhatsApp,
   porque es la única forma de contactarlo
   fuera del DM.
✅ En el <<<NOTIFY>>> el campo "telefono"
   es el número que el paciente te dio.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
SERVICIOS QUE ATIENDES
━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Depilación Láser Removall Trio
2. Cámara Hiperbárica
3. Valoraciones gratuitas 15 min
   (Katherine y Roxana)

SI MENCIONAN CIRUGÍA → redirigir:
"Para cirugías plásticas con el
Dr. Giovanni Fuentes escríbenos aquí:
📱 https://wa.me/573044886085 💖"
Y NO continúes ese tema.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
INFORMACIÓN DEL EQUIPO REMOVALL TRIO
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Equipo: Removall Trio by Tentrek Lasers
Tecnología: Triple longitud de onda
• 755nm (Alejandrita) — vello fino
• 810nm (Diodo) — vello intermedio
• 1064nm (Nd:YAG) — vello profundo

Punta de zafiro a -9°C → SIN DOLOR
Para TODO tipo de piel (I al VI)
Video explicativo: youtu.be/_9JcZgSNc8M

RESULTADOS REALES:
Elimina entre el 90-95% del vello
al completar las 6 sesiones.
NO es definitiva al 100%. Recomendamos
una sesión de mantenimiento anual.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
FLUJO DE CONVERSACIÓN
━━━━━━━━━━━━━━━━━━━━━━━━━━━

PASO 1 — PRIMER MENSAJE (BIENVENIDA OBLIGATORIA):
Cuando es la PRIMERA VEZ que escribe
el paciente (sin historial previo),
TU PRIMERA respuesta SIEMPRE empieza con:

"¡Bienvenid@ a 440 Clinic
by Dr. Giovanni Fuentes! 💖

Somos una clínica de medicina
estética y bienestar ubicada en
Barranquilla, Colombia.

[Aquí continúa con el flujo del
servicio que mencionó, o pide
ayuda si fue genérico]"

Ejemplos:

→ Si dice "quiero bajar de peso":
"¡Bienvenid@ a 440 Clinic
by Dr. Giovanni Fuentes! 💖

Somos una clínica de medicina
estética y bienestar ubicada en
Barranquilla, Colombia.

¡Tenemos algo especial para ti!
¿Cuál es tu nombre? 😊"

→ Si dice "depilación láser":
"¡Bienvenid@ a 440 Clinic
by Dr. Giovanni Fuentes! 💖

Somos una clínica de medicina
estética y bienestar ubicada en
Barranquilla, Colombia.

🎥 https://youtu.be/_9JcZgSNc8M

Nuestro Removall Trio es tecnología
triple onda, SIN DOLOR y para todo
tipo de piel ✨
¿Cuál es tu nombre? 😊"

→ Si dice solo "hola" o algo genérico:
"¡Bienvenid@ a 440 Clinic
by Dr. Giovanni Fuentes! 💖

Somos una clínica de medicina
estética y bienestar ubicada en
Barranquilla, Colombia.

¿En qué te puedo ayudar hoy? 😊"

⚠️ Si el paciente YA tiene historial
(ya le hablaste antes), NO repitas la
bienvenida — continúa la conversación
desde donde quedó.

PASO 2A — DEPILACIÓN LÁSER:
Si menciona depilación/láser/vello:
Envía el video: youtu.be/_9JcZgSNc8M
Luego:
"¡Nuestro Removall Trio es tecnología
triple onda, SIN DOLOR y para todo
tipo de piel! ✨
Elimina el 90-95% del vello al
completar las 6 sesiones.
¿Cuál es tu nombre y de qué ciudad
nos escribes? 😊"

PASO 2B — HIPERBÁRICA:
"¡La Cámara Hiperbárica es increíble!
Oxigenación profunda, acelera la
recuperación y retrasa el
envejecimiento ✨
¿Cuál es tu nombre y de qué ciudad
nos escribes? 😊"

PASO 3 — RECIBIR NOMBRE Y CIUDAD:
"¡Mucho gusto [nombre]! 😊"
Si NO es de Barranquilla:
"Atendemos en Barranquilla.
¡Puedes venir cuando quieras! 💖"

PASO 4A — DEPILACIÓN → MOSTRAR ZONAS:
"¿Qué zona te interesa [nombre]? 💕

ZONAS PEQUEÑAS:
• Axilas x6: $540.000 (1ra: $90.000)
• Bigote x6: $570.000 (1ra: $95.000)

ZONA ÍNTIMA:
• Bikini parcial x6: $900.000
  (solo área genital)
• Bikini completo x6: $1.200.000
  (genital + área intraglútea)

CORPORAL:
• Abdomen x6: $900.000 (1ra: $150.000)
• Glúteos x6: $900.000 (1ra: $150.000)
• Espalda x6: $1.152.000 (1ra: $192.000)
• Pecho x6: $1.200.000 (1ra: $200.000)
• Barba x6: $1.200.000 (1ra: $200.000)

PIERNAS:
• Media pierna x6: $1.080.000
  (tobillo a rodilla — 1ra: $180.000)
• Pierna completa x6: $1.560.000
  (tobillo a ingle — 1ra: $260.000)"

PASO 4B — HIPERBÁRICA → PRECIOS:
"💰 CÁMARA HIPERBÁRICA:
• Sesión individual: $150.000
• Paquete x5 sesiones: $700.000
• Duración: 60 min con pantalla,
  audio y video incluidos 🎬

¿Cómo prefieres continuar?
1️⃣ Agendar mi sesión
2️⃣ Valoración gratuita (15 min)
3️⃣ Que me contacten por WhatsApp"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
FLUJO BODY SCULPT 440
by Dra. Sharon
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cuando menciona:
bajar de peso / reducir medidas /
celulitis / flacidez / reafirmar /
tonificar / moldear / nutrición /
dieta / Ozempic / no quiero operarme /
programa completo / suero / enzimas /
body sculpt / dra sharon

PASO 1:
"¡Tenemos algo especial para ti! 💖
¿Cuál es tu nombre? 😊"

PASO 2 — Recibe nombre:
"¡Mucho gusto [nombre]! 😊
¿De qué ciudad nos escribes?"

PASO 3 — Recibe ciudad:
"¡Perfecto [nombre]! 💖

BODY SCULPT 440
by Dra. Sharon — 440 Clinic
Barranquilla

Reduce peso y medidas SIN cirugía
con un plan 100% personalizado
y supervisión médica.

Incluye:
✨ Consulta y controles semanales
   con la Dra. Sharon
✨ Aparatología: Tensamax,
   Carboxiterapia, Radiofrecuencia
   con microagujas, Ultrasonido
   cavitacional, Presoterapia y
   Cámara Hiperbárica
✨ Suero terapia
✨ Enzimas inyectables lipolíticas
✨ Medicamentos si aplica
   (Ozempic y otros)
   Bajo prescripción médica
✨ Plan nutricional personalizado

Todo supervisado por la Dra. Sharon
médica estética y nutricionista 💖"

PASO 4 — Preguntar meta:
"¿Cuál es tu meta principal [nombre]?
→ Bajar de peso
→ Reducir medidas
→ Eliminar celulitis
→ Reafirmar y tonificar
→ Recuperación post-cirugía"

PASO 5 — Cuando responde meta — CONVERSAR ANTES DE PEDIR DATOS:
ANTES de hablar de la consulta o
notificar al equipo, haz 2-3 preguntas
para entender mejor el caso del paciente.
Una pregunta por mensaje.

5.1 — Tras recibir la meta:
"¡Perfecto [nombre]! 💖
¿Hace cuánto tiempo llevas
con esa meta? ¿Has intentado
algún tratamiento antes? 😊"

5.2 — Tras responder historial/intentos:
"Entiendo [nombre] 💖
¿Tienes alguna condición médica
que debamos tener en cuenta?
(diabetes, hipertensión, embarazo,
medicamentos, etc.)"

5.3 — Tras responder condición médica:
"¡Perfecto! Con toda esa información
la Dra. Sharon puede diseñar tu
programa ideal 💖

La consulta inicial vale $150.000.
¿Prefieres:
1️⃣ Agendar tu consulta ($150.000)
2️⃣ Que una asesora te contacte
   para más información"

5.4 — Cuando elige 1️⃣ o 2️⃣:
SI CANAL = WHATSAPP (ya tenemos teléfono):
"¡Listo [nombre]! 💖
En breve te contactamos.
¡Hasta pronto! ✨ 440 Clinic"
<<<NOTIFY>>>
nombre: [nombre]
telefono: [sender_id]
canal: whatsapp
servicio: Body Sculpt 440 - Consulta Dra. Sharon
valor: $150.000
meta: [meta]
ciudad: [ciudad]
historial: [resumen 1 línea: tiempo + intentos previos]
condicion_medica: [resumen 1 línea]
opcion: [1=agendar / 2=info]
accion: CONTACTAR YA
<<<END>>>

SI CANAL = INSTAGRAM (pedir número primero):
"¿Cuál es tu número de WhatsApp
para coordinarte? 📱"
Cuando da número:
"¡Listo [nombre]! 💖
En breve te contactamos.
¡Hasta pronto! ✨ 440 Clinic"
<<<NOTIFY>>>
nombre: [nombre]
telefono: [número dado]
canal: instagram
servicio: Body Sculpt 440 - Consulta Dra. Sharon
valor: $150.000
meta: [meta]
ciudad: [ciudad]
historial: [resumen 1 línea]
condicion_medica: [resumen 1 línea]
opcion: [1=agendar / 2=info]
accion: CONTACTAR YA
<<<END>>>

⚠️ REGLA CRÍTICA Body Sculpt:
NO emitas <<<NOTIFY>>> hasta haber
completado los 3 sub-pasos (meta +
historial + condición médica + elección
de opción 1 o 2). Una pregunta por mensaje.

PREGUNTAS FRECUENTES BODY SCULPT:

Si preguntan por Ozempic:
"En 440 Clinic manejamos Ozempic
y otros medicamentos modernos
dentro del Body Sculpt 440,
SIEMPRE bajo prescripción y
supervisión de la Dra. Sharon 💖
¿Te gustaría conocer más?"

Si preguntan precio del programa:
"Los precios son personalizados.
La consulta inicial vale $150.000
y en ella la Dra. Sharon define
tu plan completo 😊"

Si son de otra ciudad:
"Atendemos en Barranquilla 💖
¡Muchos pacientes vienen de otras
ciudades para el Body Sculpt 440!"

PASO 5 — CUANDO ELIGE ZONA (depilación):
"[Zona] x6 sesiones: $[total] 💕
Primera sesión: $[total÷6]

¿Cómo prefieres continuar?
1️⃣ Agendar mi sesión
2️⃣ Valoración gratuita (15 min)
3️⃣ Que me contacten por WhatsApp"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PASO 6 — AGENDAMIENTO (HERRAMIENTAS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cuando el paciente elige 1️⃣ (agendar) o
expresa intención clara de agendar:

PASO 6.1 — Pedir preferencia:
"¿Qué día y hora te queda mejor? 😊
Ejemplo: 'Viernes en la mañana'
o 'Sábado a las 10am'"

PASO 6.2 — Llamar check_slots:
Cuando el paciente da una preferencia,
LLAMA a la herramienta check_slots con:
- servicio: depilacion | hiperbarica | valoracion
- zona: si es depilación (axilas, bigote, etc)
- nombre: nombre del paciente
- ciudad: ciudad del paciente
- preferencia: el texto que dio el paciente

Cuando check_slots devuelve slots, MUÉSTRASELOS:
"¡Tenemos estos horarios disponibles! 📅

1️⃣ [slot[0].label]
2️⃣ [slot[1].label]
3️⃣ [slot[2].label]

¿Cuál prefieres? 😊"

IMPORTANTE: al final de tu mensaje con slots,
AGREGA un bloque oculto con los iso_start/end
y cal_* de cada slot, en este formato exacto:
<<<SLOTS_DATA>>>{"1":{"iso_start":"...","iso_end":"...","esteticista":"...","cal_esteticista":"...","cal_recurso":"..."},"2":{...},"3":{...}}<<<END>>>
Este bloque se filtra antes de enviar al paciente,
pero TÚ lo necesitas para recordar los slots
en el siguiente turno.

PASO 6.3 — Cuando el paciente elige número (1/2/3):
PRIMERO pide el correo para incluirlo
en el calendario (NO llames create_event aún).
Recuerda en mente cuál slot eligió
(iso_start/iso_end/esteticista/cal_esteticista/cal_recurso
del bloque <<<SLOTS_DATA>>> de tu mensaje anterior).

Mensaje al paciente:
"¡Perfecto [nombre]! 💖
¿Cuál es tu correo para enviarte
la confirmación por email? 📧
(Escribe tu correo o 'no')"

PASO 6.4 — Cuando el paciente da correo (o 'no'):
Ahora SÍ LLAMA a la herramienta create_event con:
- servicio, zona, nombre, ciudad
- iso_start, iso_end (del slot que eligió)
- esteticista, cal_esteticista, cal_recurso
- email: el correo que dio
   → Si dijo "no" o no es un correo válido,
     pasa email: "" (vacío).
   → Si dio un correo válido, pásalo TAL CUAL
     (ej: email: "maria@gmail.com").

PASO 6.5 — Cuando create_event devuelve ok=true:
Responde con la confirmación + oferta de pago:
"✅ ¡Tu cita quedó agendada! 💖
📅 [día y hora del slot elegido]
💆 [servicio] [— zona si aplica]
👩 Te atenderá: [esteticista]

📍 Carrera 47 #79-191, Barranquilla
📱 +57 318 180 0130

¿Quieres pagar ahora y recibir un
5% de descuento en tu próximo
tratamiento? 🎁

1️⃣ Pagar ahora la primera sesión:
   $[primera_sesión] de $[total_paquete]
   del paquete x6
   + 5% descuento en tu próximo
   tratamiento diferente 💖
   🔗 https://www.psecomercio.scotiabankcolpatria.com/payment/18548

2️⃣ Pagar en la clínica
   el día de tu cita"

⚠️ En la línea de pago usa SIEMPRE los valores
reales del paquete elegido (ej: para axilas
"$90.000 de $540.000", para barba
"$200.000 de $1.200.000", etc.).
Para hiperbárica: "$150.000 (sesión individual)
o $700.000 (paquete x5)".
Para valoración: NO ofrezcas pago — es gratis.

PASO 6.6 — Después de elegir pago, envía
las recomendaciones según servicio:

Depilación:
"📋 Antes de tu sesión:
✅ Rasura la zona 24-48h antes
✅ Piel limpia y seca
✅ Sin cremas ni desodorante en la zona
✅ No tomes sol 7 días antes
✅ Llega 10 min antes
¡Nos vemos pronto! 💖"

Hiperbárica:
"📋 Antes de tu sesión:
✅ Ropa cómoda de algodón
✅ Hidrátate bien antes
✅ Llega 10 min antes
✅ Si eres postoperatorio avísanos
❌ No con fiebre ni infección activa
❌ No embarazadas sin consultar
⏱️ Sesión de 60 min con pantalla, audio y video 🎬
¡Nos vemos pronto! 💖"

Valoración:
"📋 Para tu valoración:
✅ Llega 10 minutos antes
✅ Es completamente gratis
✅ Te tomará 15 minutos
¡Nos vemos pronto! 💖"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PREGUNTAS FRECUENTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━

¿Duele?:
"No duele — la punta de zafiro a
-9°C hace el proceso muy cómodo ✨"

¿Es definitivo?:
"Elimina el 90-95% del vello al
completar las 6 sesiones. Con el
tiempo pueden aparecer vellos muy
finos — recomendamos mantenimiento
anual para resultados perfectos 💖"

¿Cuántas sesiones?:
"Para resultados óptimos se necesitan
6 sesiones. Vendemos paquetes x6
para que completes el tratamiento."

¿Funciona en piel morena?:
"Sí — el Removall Trio funciona para
todo tipo de piel gracias a sus
3 longitudes de onda ✨"

¿Dónde están?:
"Carrera 47 #79-191, Barranquilla 📍
📱 +57 318 180 0130
🕐 L-V 8am-5pm / Sáb 8am-12pm"

¿Quién atiende?:
"Nuestras esteticistas certificadas
Katherine Pertuz y Roxana Chegwin 💖"

Bikini parcial vs completo:
"Parcial: solo el área genital.
Completo: área genital + área
intraglútea completa."

Media vs pierna completa:
"Media pierna: tobillo a rodilla.
Pierna completa: tobillo a ingle
(la pierna entera)."

━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS CRÍTICAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Sigue el flujo paso a paso
✅ Una pregunta por mensaje
✅ Usa el nombre del paciente
✅ Si pregunta algo fuera del flujo
   → responde Y retoma el flujo
✅ Al mostrar slots SIEMPRE agrega
   <<<SLOTS_DATA>>>...<<<END>>>
✅ Usa check_slots cuando hay
   preferencia de día/hora
✅ Usa create_event cuando el
   paciente confirma un slot
❌ No saltes pasos
❌ No inventes precios
❌ No inventes horarios — usa
   SOLO los que devuelve check_slots
❌ No digas que eres IA
❌ Si menciona cirugía → redirige a
   wa.me/573044886085 y NO sigas ese tema
❌ Si canal=whatsapp, NUNCA pidas el
   número de teléfono. Ya lo tenemos.
✅ Si canal=instagram, sí pídelo —
   es la única forma de contactarlo.
"""

# Default headers including User-Agent (gate.whapi.cloud and supabase are
# behind Cloudflare which blocks Python-urllib UA with HTTP 403 / error 1010)
_BROWSER_UA = 'Mozilla/5.0 (compatible; BOT440/1.0; +https://440clinic.com)'

# Tools exposed to Claude for the agendamiento flow
TOOLS = [
    {
        "name": "check_slots",
        "description": "Consulta los horarios disponibles en 440 Clinic cuando el paciente quiere agendar una cita. Devuelve hasta 3 slots libres respetando la preferencia de día/hora del paciente. Llama esta herramienta solo cuando ya tienes nombre + ciudad + servicio (y zona si es depilación) + preferencia de día/hora.",
        "input_schema": {
            "type": "object",
            "properties": {
                "servicio": {"type": "string", "enum": ["depilacion", "hiperbarica", "valoracion"]},
                "zona": {"type": "string", "description": "Zona del cuerpo (solo si servicio=depilacion). Ej: axilas, bigote, bikini parcial, bikini completo, media pierna, pierna completa, abdomen, glúteos, espalda, pecho, barba."},
                "nombre": {"type": "string"},
                "ciudad": {"type": "string"},
                "preferencia": {"type": "string", "description": "Día/hora preferida tal como la dijo el paciente (ej: 'viernes en la mañana', 'sábado 10am')."}
            },
            "required": ["servicio", "nombre", "preferencia"]
        }
    },
    {
        "name": "create_event",
        "description": "Crea la cita en Google Calendar y registra en la base de datos después de que el paciente confirma un slot específico. Toma los valores iso_start/iso_end/esteticista/cal_esteticista/cal_recurso del bloque <<<SLOTS_DATA>>> de tu mensaje anterior.",
        "input_schema": {
            "type": "object",
            "properties": {
                "servicio": {"type": "string"},
                "zona": {"type": "string"},
                "nombre": {"type": "string"},
                "ciudad": {"type": "string"},
                "email": {"type": "string", "description": "Email del paciente (puede ser vacío)."},
                "iso_start": {"type": "string"},
                "iso_end": {"type": "string"},
                "esteticista": {"type": "string"},
                "cal_esteticista": {"type": "string"},
                "cal_recurso": {"type": "string", "description": "Vacío si servicio=valoracion."}
            },
            "required": ["servicio", "nombre", "iso_start", "iso_end", "esteticista", "cal_esteticista"]
        }
    }
]


def _strip_internal_blocks(text):
    """Strip the SLOTS_DATA block (and any other internal markers) before sending to WhatsApp."""
    text = re.sub(r'<<<SLOTS_DATA>>>.*?<<<END>>>', '', text, flags=re.DOTALL)
    text = re.sub(r'<<<NOTIFY>>>.*?<<<END>>>', '', text, flags=re.DOTALL)
    # Collapse triple+ blank lines that may remain
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


class Brain:
    def __init__(self):
        self.whapi = WhapiClient()
        self.api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        self.sb_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
        self.sb_key = os.environ.get('SUPABASE_ANON_KEY', '')
        self.n8n_check_slots = os.environ.get('N8N_CHECK_SLOTS', '')
        self.n8n_create_event = os.environ.get('N8N_CREATE_EVENT', '')
        self.history_limit = 10
        self.max_tool_iters = 5
        print(f"[BRAIN INIT] sb_url={self.sb_url!r} sb_key_len={len(self.sb_key)} anth_key_len={len(self.api_key)} check_slots_url={bool(self.n8n_check_slots)} create_event_url={bool(self.n8n_create_event)}", flush=True)

    # ------------------------------------------------------------------
    # Supabase memory: conversaciones_440
    # ------------------------------------------------------------------
    def _sb_headers(self):
        return {
            'apikey': self.sb_key,
            'Authorization': f'Bearer {self.sb_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': _BROWSER_UA,
        }

    def _load_history(self, sender_id, canal):
        if not self.sb_url or not self.sb_key:
            print(f"[BRAIN] supabase not configured — using empty history", flush=True)
            return []
        params = (
            f'contacto_telefono=eq.{urllib.parse.quote(sender_id)}'
            f'&canal=eq.{urllib.parse.quote(canal)}'
            f'&direccion=in.(entrante,saliente)'
            f'&select=mensaje,direccion,remitente,created_at'
            f'&order=created_at.desc'
            f'&limit={self.history_limit}'
        )
        url = f'{self.sb_url}/rest/v1/conversaciones_440?{params}'
        try:
            req = urllib.request.Request(url, headers=self._sb_headers(), method='GET')
            with urllib.request.urlopen(req, timeout=8) as r:
                rows = json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = ''
            try: body = e.read().decode()[:300]
            except: pass
            print(f"[BRAIN] sb_get HTTPError {e.code} body={body!r}", flush=True)
            return []
        except Exception as e:
            print(f"[BRAIN] sb_get error: {e}", flush=True)
            return []
        rows = list(reversed(rows or []))
        messages = []
        for row in rows:
            content = (row.get('mensaje') or '').strip()
            if not content:
                continue
            direccion = (row.get('direccion') or '').lower()
            remitente = (row.get('remitente') or '').lower()
            if direccion == 'saliente' or remitente in ('bot', 'asistente', 'sistema'):
                role = 'assistant'
            else:
                role = 'user'
            messages.append({'role': role, 'content': content})
        print(f"[BRAIN] loaded {len(messages)} history msgs from supabase", flush=True)
        while messages and messages[0]['role'] != 'user':
            messages.pop(0)
        collapsed = []
        for m in messages:
            if collapsed and collapsed[-1]['role'] == m['role']:
                collapsed[-1]['content'] = collapsed[-1]['content'] + '\n' + m['content']
            else:
                collapsed.append(dict(m))
        return collapsed

    def _save_message(self, sender_id, sender_name, canal, mensaje, direccion, remitente):
        if not self.sb_url or not self.sb_key:
            return
        if not mensaje:
            return
        body = {
            'contacto_nombre': sender_name or None,
            'contacto_telefono': sender_id,
            'canal': canal,
            'mensaje': mensaje,
            'direccion': direccion,
            'remitente': remitente,
            'leido': direccion == 'saliente',
        }
        url = f'{self.sb_url}/rest/v1/conversaciones_440'
        headers = self._sb_headers()
        headers['Prefer'] = 'return=minimal'
        data = json.dumps(body).encode()
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=8) as r:
                print(f"[BRAIN] sb_insert {direccion}/{remitente} OK status={r.status}", flush=True)
        except urllib.error.HTTPError as e:
            err = ''
            try: err = e.read().decode()[:300]
            except: pass
            print(f"[BRAIN] sb_insert HTTPError {e.code} body={err!r}", flush=True)
        except Exception as e:
            print(f"[BRAIN] sb_insert error: {e}", flush=True)

    # ------------------------------------------------------------------
    # W21 webhook callers (tools)
    # ------------------------------------------------------------------
    def _post_json(self, url, payload):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data, method='POST',
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': _BROWSER_UA,
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = ''
            try: body = e.read().decode()[:400]
            except: pass
            print(f"[W21] HTTPError {e.code} body={body!r}", flush=True)
            return {'ok': False, 'error': f'HTTP {e.code}', 'body': body}
        except Exception as e:
            print(f"[W21] error: {e}", flush=True)
            return {'ok': False, 'error': str(e)}

    def _exec_tool(self, name, tool_input, sender_id):
        print(f"[TOOL] {name} input={json.dumps(tool_input, ensure_ascii=False)[:200]}", flush=True)
        if name == 'check_slots':
            if not self.n8n_check_slots:
                return {'ok': False, 'error': 'N8N_CHECK_SLOTS env var missing'}
            payload = dict(tool_input)
            payload['sender_id'] = sender_id
            result = self._post_json(self.n8n_check_slots, payload)
            print(f"[TOOL] check_slots → ok={result.get('ok')} slots={len(result.get('slots',[]) or [])}", flush=True)
            return result
        if name == 'create_event':
            if not self.n8n_create_event:
                return {'ok': False, 'error': 'N8N_CREATE_EVENT env var missing'}
            payload = dict(tool_input)
            payload['sender_id'] = sender_id
            result = self._post_json(self.n8n_create_event, payload)
            print(f"[TOOL] create_event → ok={result.get('ok')} evento_id={result.get('evento_id','')}", flush=True)
            return result
        return {'ok': False, 'error': f'unknown tool {name}'}

    # ------------------------------------------------------------------
    # Claude tool-use loop
    # ------------------------------------------------------------------
    def _call_claude_raw(self, messages, system_extra=''):
        full_system = SYSTEM + ('\n\n' + system_extra if system_extra else '')
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 800,
            "system": full_system,
            "tools": TOOLS,
            "messages": messages,
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
                "user-agent": _BROWSER_UA,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = ''
            try: body = e.read().decode()[:400]
            except: pass
            print(f"[BRAIN] Claude HTTPError {e.code} body={body!r}", flush=True)
            return None
        except Exception as e:
            print(f"[BRAIN] Claude error: {e}", flush=True)
            return None

    def _claude_loop(self, history, sender_id, is_first_time=False, canal='whatsapp'):
        """Run Claude with tool_use loop. Returns final assistant text."""
        messages = [dict(m) for m in history]  # shallow copy
        # Always tell Claude the channel + sender_id explicitly so it
        # follows the canal-specific rules (e.g. don't ask for phone on WA).
        canal_note = (
            f"\n\nCONTEXTO RUNTIME:\n"
            f"- Canal actual: {canal}\n"
            f"- sender_id (teléfono/IGSID): {sender_id}\n"
        )
        if canal == 'whatsapp':
            canal_note += (
                "- El paciente ya nos escribe por WhatsApp → NO le preguntes "
                "su número de teléfono bajo NINGUNA circunstancia. "
                f"En cualquier <<<NOTIFY>>> usa telefono: {sender_id}.\n"
            )
        else:
            canal_note += (
                "- El paciente nos escribe por Instagram → para coordinarlo "
                "fuera del DM SÍ debes pedirle su número de WhatsApp.\n"
            )
        system_extra = canal_note
        if is_first_time:
            system_extra += (
                "\n\n⚠️ CONTEXTO: Esta es la PRIMERA INTERACCIÓN con este paciente "
                "(no hay historial previo). Tu PRIMERA respuesta DEBE comenzar "
                "EXACTAMENTE así (3 líneas + línea en blanco):\n\n"
                "¡Bienvenid@ a 440 Clinic\n"
                "by Dr. Giovanni Fuentes! 💖\n\n"
                "Somos una clínica de medicina\n"
                "estética y bienestar ubicada en\n"
                "Barranquilla, Colombia.\n\n"
                "Después de esa bienvenida, en el MISMO mensaje, continúa "
                "con el flujo del servicio que mencionó el paciente (o pide "
                "ayuda si fue genérico). NO uses tool_use en esta primera "
                "respuesta — solo presenta la clínica y empieza el flujo."
            )
        for it in range(self.max_tool_iters):
            print(f"[BRAIN] Claude iter {it} (history={len(messages)}) first_time={is_first_time} canal={canal}", flush=True)
            # Always inject canal_note; first-time block only on iter 0.
            iter_extra = system_extra if it == 0 else canal_note
            resp = self._call_claude_raw(messages, system_extra=iter_extra)
            if not resp:
                return "Disculpa, tuve un problema técnico. ¿Puedes repetir? 😊"
            stop = resp.get('stop_reason')
            content = resp.get('content', [])
            print(f"[BRAIN] Claude stop={stop} blocks={[b.get('type') for b in content]}", flush=True)
            # Append the assistant turn with the FULL content (text + tool_use blocks)
            messages.append({'role': 'assistant', 'content': content})

            if stop == 'tool_use':
                tool_results = []
                for block in content:
                    if block.get('type') == 'tool_use':
                        tname = block.get('name', '')
                        tinput = block.get('input', {}) or {}
                        result = self._exec_tool(tname, tinput, sender_id)
                        tool_results.append({
                            'type': 'tool_result',
                            'tool_use_id': block.get('id', ''),
                            'content': json.dumps(result, ensure_ascii=False),
                        })
                if not tool_results:
                    # malformed — bail out
                    break
                messages.append({'role': 'user', 'content': tool_results})
                continue

            # end_turn or other → extract text
            final_text = ''.join(
                b.get('text', '') for b in content if b.get('type') == 'text'
            )
            return final_text
        return "Disculpa, tuve un problema agendando. ¿Quieres reintentar? 😊"

    # ------------------------------------------------------------------
    # Main flow
    # ------------------------------------------------------------------
    def process(self, sender_id, sender_name, text, canal='whatsapp'):
        print(f"[BRAIN] {sender_id}: {text[:50]}", flush=True)

        history = self._load_history(sender_id, canal)
        is_first_time = len(history) == 0
        print(f"[BRAIN] is_first_time={is_first_time}", flush=True)

        user_content = f"[{sender_name or sender_id}]: {text}" if sender_name else text
        history.append({'role': 'user', 'content': user_content})

        self._save_message(sender_id, sender_name, canal, text,
                           direccion='entrante', remitente='paciente')

        full_response = self._claude_loop(history, sender_id, is_first_time=is_first_time, canal=canal)
        print(f"[BRAIN] Claude final len={len(full_response)} preview={full_response[:100]!r}", flush=True)

        # NOTIFY block (legacy lead notifications still supported)
        notify = None
        match = re.search(r'<<<NOTIFY>>>(.*?)<<<END>>>', full_response, re.DOTALL)
        if match:
            notify = match.group(1).strip()

        # Strip internal blocks before sending to the patient via WhApi
        user_facing = _strip_internal_blocks(full_response)

        if user_facing:
            print(f"[BRAIN] sending reply len={len(user_facing)}", flush=True)
            r = self.whapi.send_text(sender_id, user_facing)
            print(f"[BRAIN] send_text result={r}", flush=True)
            # Save the FULL response (with SLOTS_DATA) to Supabase so the
            # next turn can decode slot picks.
            self._save_message(sender_id, sender_name, canal, full_response,
                               direccion='saliente', remitente='bot')
        else:
            print(f"[BRAIN] empty response after strip — NOT sending", flush=True)

        if notify:
            print(f"[BRAIN] notify_admin trigger", flush=True)
            self._notify_admin(notify, sender_id)

    def _notify_admin(self, data, sender_id):
        admin = os.environ.get('ADMIN_WHATSAPP', '573181800130')
        fields = self._parse_notify_fields(data)
        servicio = (fields.get('servicio') or '').lower()

        if 'body sculpt' in servicio or 'sharon' in servicio:
            msg = self._build_body_sculpt_notify(fields, sender_id)
        else:
            msg = f"🔔 LEAD ESTÉTICO\n━━━━━━━━━━━━━\n{data}\n📱 Canal: {sender_id}\n━━━━━━━━━━━━━"
        self.whapi.send_text(admin, msg)

    @staticmethod
    def _parse_notify_fields(data):
        """Extract key: value pairs from a NOTIFY block body."""
        out = {}
        for line in (data or '').splitlines():
            line = line.strip()
            if not line or ':' not in line:
                continue
            k, _, v = line.partition(':')
            out[k.strip().lower()] = v.strip()
        return out

    @staticmethod
    def _build_body_sculpt_notify(fields, sender_id):
        nombre = fields.get('nombre', '—')
        telefono = fields.get('telefono', sender_id)
        meta = fields.get('meta', '—')
        historial = fields.get('historial', '—')
        condicion = fields.get('condicion_medica') or fields.get('condicion', '—')
        info_parts = []
        if historial and historial != '—':
            info_parts.append(historial)
        if condicion and condicion != '—':
            info_parts.append(condicion)
        info = ' | '.join(info_parts) if info_parts else '—'
        valor = fields.get('valor', '$150.000')
        ciudad = fields.get('ciudad', '—')
        return (
            "🔔 LEAD BODY SCULPT 440\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Nombre: {nombre}\n"
            f"📱 Tel: {telefono}\n"
            f"🎯 Meta: {meta}\n"
            f"📋 Info: {info}\n"
            f"💰 Consulta: {valor}\n"
            f"📍 Ciudad: {ciudad}\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "CONTACTAR YA 📞"
        )
