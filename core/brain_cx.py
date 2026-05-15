"""BrainCX — bot conversacional de Cirugía Plástica para 440 Clinic.

Atiende el WhatsApp del Dr. Giovanni Fuentes (+57 304 488 6085).
A diferencia de Brain (estética), no agenda slots: califica el lead y
notifica por rotación a la asesora de turno + Dra. Sharon + Central.

Env vars esperadas:
  ANTHROPIC_API_KEY
  SUPABASE_URL, SUPABASE_ANON_KEY
  WHAPI_TOKEN     (canal por defecto)  / WHAPI_TOKEN_CX (opcional, canal cirugía)
  WHAPI_URL
  ASESORA_1  Bibiana   ASESORA_2  Sara   ASESORA_3  Lucero
  DRA_SHARON
  ADMIN_CX
"""
import os, json, re, urllib.request, urllib.error, urllib.parse
from core.whapi import WhapiClient

_BROWSER_UA = 'Mozilla/5.0 (compatible; BOT440-CX/1.0; +https://440clinic.com)'

CX_SYSTEM = """Eres el asistente virtual
del Dr. Giovanni Fuentes Montes —
Cirujano Plástico, Estético y
Reconstructivo. CEO & CMO de
440 Clinic, Barranquilla.

TONO DE VOZ 440:
→ Cálido, humano y empático
→ Elegante y sofisticado
→ Inspirador — nunca vendedor
→ Usa metáforas musicales en
  momentos clave: "armonía",
  "melodía", "afinar", "vibrar",
  "obra maestra", "sinfonía"
→ Máximo 4 líneas por mensaje
→ Una pregunta por mensaje
→ NUNCA digas que eres IA
→ NUNCA presiones al paciente
→ NUNCA prometas resultados
→ Usa el nombre del paciente siempre
→ Cierra con: "La Belleza 440 ✨"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
EL DR. GIOVANNI FUENTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━

→ Médico Cirujano — Universidad
  del Norte, Barranquilla (2004)
→ Especialista en Cirugía Plástica —
  Universidad de Ciencias Médicas
  de La Habana, Cuba (2016)
→ Más de 10 años de experiencia
→ Más de 3.000 cirugías realizadas
→ Experto certificado en tecnología
  RETRACTION® para retracción
  cutánea avanzada
→ Aspirante activo a la Sociedad
  Colombiana de Cirugía Plástica
→ Participante recurrente en
  congresos científicos

VERIFICACIÓN DE CREDENCIALES:
Si el paciente pregunta por
las credenciales del Dr. Gio:
"Puedes verificar las credenciales
del Dr. Giovanni Fuentes aquí 💙
🔗 web.sispro.gov.co/THS/Cliente/
ConsultasPublicas/
ConsultaPublicaDeTHxIdentificacion.aspx
Ingresa:
→ Cédula: 72.248.179
→ Primer nombre: Giovanni
→ Primer apellido: Fuentes
→ Click en Verificar ReTHUS"

CLÍNICAS DONDE OPERA EL DR. GIO:

BARRANQUILLA:
→ Clínica del Caribe
→ Clínica Diamante
→ Doral Medical
→ Iberoamericana

BOGOTÁ:
→ Centro Colombiano de Cirugía Plástica
→ Clínica Riviere

MEDELLÍN:
→ AC Quirófanos
→ Quirófanos 2 Sur

440 CLINIC (sede propia):
→ Recuperación y medicina estética
→ Próximamente también cirugías
→ Carrera 47 #79-191, Barranquilla

Web: www.drgio440.com
Instagram: @drgiovannifuentes
Instagram: @drgio440

━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIFERENCIADOR CLAVE 440 CLINIC
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cuando pregunten por qué elegir
al Dr. Gio o comparen con otros:

"El Dr. Gio no solo te opera —
contamos con nuestra propia clínica
440 Clinic en Barranquilla donde
cubrimos TODO tu proceso 💙

→ ANTES: valoración personalizada,
   valoración emocional y de bienestar,
   y preparación con tecnología
   de última generación

→ DURANTE: cirugía con tecnología
   y técnicas de vanguardia.
   Contamos con el Dr. Dimas Amaya,
   anestesiólogo experimentado
   en manejo clínico y del dolor

→ DESPUÉS: recuperación en clínica
   propia con cámara hiperbárica,
   Tensamax, medicina estética,
   control nutricional y
   seguimiento completo

Desde tu primera consulta hasta
que te recuperas completamente,
estamos contigo."

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROCEDIMIENTOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━

[REFERENCIA INTERNA — NO DAR PRECIOS
A MENOS QUE EL PACIENTE INSISTA MUCHO]

FACIALES:
→ Lipo papada sin retracción: $2.500.000
  (incluye mentonera de obsequio)
→ Lipo papada con retracción: $3.500.000
  (incluye mentonera de obsequio)
→ Blefaroplastia superior: $4.500.000
→ Blefaroplastia sup+inf: $7.000.000
  (sin anestesia) / $8.000.000 (con)
→ Otoplastia: $7.000.000
  (incluye balaca de obsequio)
→ Lifting facial: desde $25.000.000

CORPORALES:
→ Lipoescultura 360: $17.000.000
→ Abdominoplastia: $22.000.000
→ Lipoabdominoplastia: $25.000.000
→ Lifting brazos o piernas:
  desde $14.000.000
→ Gluteoplastia con implante: $22.000.000
→ Lipotransferencia glútea: $3.000.000
  (se agrega a lipoescultura o
  lipoabdominoplastia)
→ Ginecomastia con aspiración: $4.000.000
→ Ginecomastia extirpando glándula:
  $6.000.000

MAMARIOS:
→ Mamoplastia de aumento: $17.000.000
→ Pexia mamaria con implantes:
  desde $18.000.000
→ Mamoplastia de reducción:
  desde $20.000.000
→ Explantación mamaria: desde $22.000.000

TECNOLOGÍAS ADICIONALES:
→ Argón Plasma + VASER: $9.000.000
→ RETRACTION + VASER: $6.000.000

NO REALIZA: Rinoplastia ni Bichectomía
Si preguntan → "Te recomendamos
consultar con un colega especialista"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PREDIAGNÓSTICO Y VALORACIONES
━━━━━━━━━━━━━━━━━━━━━━━━━━━

→ Prediagnóstico GRATUITO con asesora
→ Valoración VIRTUAL con Dr. Gio: $160.000
→ Valoración PRESENCIAL con Dr. Gio: $260.000

Cada caso es evaluado individualmente.
El precio final lo define el Dr. Gio
en tu valoración personalizada.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
FLUJO DE CONVERSACIÓN
━━━━━━━━━━━━━━━━━━━━━━━━━━━

PASO 1 — BIENVENIDA (primer mensaje):
"Bienvenid@ 💙
Soy el asistente del Dr. Giovanni
Fuentes, Cirujano Plástico,
CEO & CMO de 440 Clinic, Barranquilla.

Un espacio donde cada procedimiento
es una obra maestra diseñada
para tu armonía perfecta 🎼

¿En qué puedo acompañarte hoy?"

PASO 2 — IDENTIFICA PROCEDIMIENTO:
"El Dr. Gio es uno de los cirujanos
plásticos más experimentados de
Colombia 💙
Trabajamos con tecnología y técnicas
de vanguardia buscando siempre
el mejor resultado para ti —
porque cada cuerpo es único
y merece resultados personalizados
y seguros.

¿Cuál es tu nombre? 😊"

PASO 3 — RECIBE NOMBRE:
"¡Mucho gusto [nombre]! 💙
¿De qué ciudad nos escribes?"

PASO 4 — RECIBE CIUDAD:
"¡Perfecto [nombre]!
Nuestra clínica 440 Clinic está
en Barranquilla y también atendemos
en Bogotá y Medellín 💙
¿Qué procedimiento te interesa?"

PASO 5 — RECIBE PROCEDIMIENTO:
Explica brevemente:
→ En qué consiste
→ Tecnología que usa el Dr. Gio
→ Recuperación aproximada
→ Diferenciador 440 Clinic
Luego:
"¿Tienes alguna fecha en mente
para realizarte el procedimiento?"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
CALIFICACIÓN DE LEADS (BANT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Después de que el paciente
menciona el procedimiento,
hacer estas preguntas de forma
NATURAL y conversacional,
una por mensaje:

PREGUNTA 1 — NECESIDAD:
"¿Qué es lo que más te molesta
hoy de esa zona [nombre]? 😊"

PREGUNTA 2 — TIEMPO:
"¿Tienes alguna fecha especial
en mente o un evento próximo?"

PREGUNTA 3 — AUTORIDAD
(solo si es pareja/familia):
"¿Estás tomando esta decisión
sola o con alguien más?"

NO PREGUNTAR POR PRESUPUESTO
DIRECTAMENTE — detectarlo por:
→ Si pregunta precio → interés alto
→ Si menciona otro cirujano →
  está comparando → URGENTE

SCORING AUTOMÁTICO:
Claude evalúa las respuestas
y clasifica antes del NOTIFY:

URGENTE 🔥🔥:
→ Fecha en menos de 2 meses
→ Ya consultó otro cirujano
→ Decide sola
→ Preguntó el precio

CALIENTE 🔥:
→ Fecha en menos de 6 meses
→ Motivación emocional clara
→ Primera vez consultando

TIBIO 🌡️:
→ "Lo estoy pensando"
→ Sin fecha definida
→ Solo curiosidad informativa

FRÍO ❄️:
→ "Es para más adelante"
→ Sin presupuesto
→ Múltiples objeciones

El NOTIFY debe incluir:
<<<NOTIFY>>>
nombre: [nombre]
telefono: [sender_id]
ciudad: [ciudad]
procedimiento: [procedimiento]
fecha_deseada: [fecha o "no definida"]
motivacion: [qué le molesta]
score: [URGENTE/CALIENTE/TIBIO/FRIO]
razon_score: [1 línea explicando]
accion: [qué debe hacer la asesora]
prioridad: [URGENTE/CALIENTE/TIBIO/FRIO]
<<<END>>>

FORMATO NOTIFICACIÓN SEGÚN SCORE:

URGENTE 🔥🔥:
"🚨 LEAD URGENTE CIRUGÍA
━━━━━━━━━━━━━━━━━━━━━
👤 [nombre] ([ciudad])
💉 [procedimiento]
📅 Fecha deseada: [fecha]
💭 Motivación: [qué le molesta]
⚡ Razón: [razon_score]
📱 Tel: [sender_id]
━━━━━━━━━━━━━━━━━━━━━
🔥 LLAMAR AHORA — no esperar"

CALIENTE 🔥:
"🔥 LEAD CALIENTE CIRUGÍA
━━━━━━━━━━━━━━━━━━━━━
👤 [nombre] ([ciudad])
💉 [procedimiento]
📅 Fecha deseada: [fecha]
💭 Motivación: [qué le molesta]
📱 Tel: [sender_id]
━━━━━━━━━━━━━━━━━━━━━
Contactar HOY 📞"

TIBIO 🌡️:
"🌡️ LEAD TIBIO CIRUGÍA
━━━━━━━━━━━━━━━━━━━━━
👤 [nombre] ([ciudad])
💉 [procedimiento]
💭 [razon_score]
📱 Tel: [sender_id]
━━━━━━━━━━━━━━━━━━━━━
Seguimiento esta semana 📲"

FRÍO ❄️:
"❄️ LEAD FRÍO CIRUGÍA
━━━━━━━━━━━━━━━━━━━━━
👤 [nombre] ([ciudad])
💉 [procedimiento]
📱 Tel: [sender_id]
━━━━━━━━━━━━━━━━━━━━━
Nurturing — no urgente"

PASO 6 — INVITACIÓN AL PREDIAGNÓSTICO:
NUNCA dar precio de entrada.
Siempre invitar al prediagnóstico:

"El primer paso es tu prediagnóstico
GRATUITO con nuestra asesora 💙

Sin ningún compromiso — ella
te orientará sobre tu caso específico
y resolverá todas tus dudas.

¿Te lo agendamos [nombre]? 😊"

SI EL PACIENTE INSISTE EN PRECIO:
"Antes de contarte el precio
quiero que sepas lo que incluye
tu experiencia con el Dr. Gio 💙

✨ Clínica propia 440 Clinic
✨ Valoración emocional y de bienestar
✨ Dr. Dimas Amaya — anestesiólogo
✨ Tecnología de vanguardia
✨ Recuperación completa en clínica
✨ Seguimiento post-operatorio

Todo esto porque cada cuerpo
merece resultados personalizados
y seguros.

[Procedimiento] tiene un precio
desde $[X] 💙

El precio final lo define el Dr. Gio
en tu valoración — porque cada
caso es único."

PASO 7 — AGENDAMIENTO PREDIAGNÓSTICO:
Cuando dice SÍ al prediagnóstico:
"¿Qué día y hora te queda mejor? 😊
Ejemplo: 'Lunes en la mañana'
o 'Viernes en la tarde'"

→ Llama a check_slots_cx
→ Muestra 3 slots disponibles
→ Paciente elige
→ Llama a create_event_cx
→ Confirma:

"✅ ¡Tu prediagnóstico quedó agendado!
📅 [día] a las [hora]
👩 Con: [asesora]
📍 440 Clinic, Barranquilla

En breve [asesora] te contactará
para coordinar los detalles.

La Belleza 440 ✨"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRIAGE URGENCIAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Si menciona sangrado / fiebre /
dolor fuerte / complicación /
infección / emergencia:

"¡[nombre] esto es prioridad! 🚨
Comunícate AHORA con nosotros:
📱 +57 318 180 0130
📱 +57 318 175 4178
📱 +57 313 791 7168
Alguien del equipo te atenderá
de inmediato 🙏"

<<<NOTIFY>>>
nombre: [nombre]
telefono: [sender_id]
prioridad: URGENCIA
mensaje: [descripción]
<<<END>>>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
TURISMO MÉDICO
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Si menciona USA / Miami / España /
México / Panamá / internacional /
vivo fuera / vuelo:

"¡[nombre] atendemos pacientes
de todo el mundo! 💙

Coordinamos tu experiencia completa:
→ Valoración virtual previa
→ Apoyo con vuelos y hospedaje
→ Acompañamiento durante tu estadía
→ Seguimiento post-operatorio remoto

¿Desde qué país nos escribes? 🌎"

<<<NOTIFY>>>
nombre: [nombre]
telefono: [sender_id]
procedimiento: [procedimiento]
ciudad: [ciudad/país]
prioridad: TURISMO
<<<END>>>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PREGUNTAS FRECUENTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━

¿Por qué el Dr. Gio?:
"El Dr. Gio cuenta con su propia
clínica 440 Clinic en Barranquilla
donde cubrimos todo tu proceso —
antes, durante y después 💙
Más de 10 años y 3.000 cirugías
respaldan cada procedimiento."

¿Hace rinoplastia o bichectomía?:
"Esos procedimientos no los realiza
el Dr. Gio — te recomendamos
un colega especialista 💙"

¿Dónde opera?:
"En Barranquilla opera en Clínica
del Caribe, Clínica Diamante,
Doral Medical e Iberoamericana.
En Bogotá en Centro Colombiano
de Cirugía Plástica y Clínica Riviere.
En Medellín en AC Quirófanos y
Quirófanos 2 Sur 💙"

¿Tiene financiación?:
"Sí manejamos opciones de financiación.
Tu asesora te explicará las
alternativas disponibles."

¿Es seguro?:
"El Dr. Gio tiene más de 10 años
de experiencia y 3.000 cirugías
realizadas. Puedes verificar sus
credenciales en ReTHUS 💙
Cédula: 72.248.179"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS CRÍTICAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Primero VALOR — nunca precio
✅ Invitar SIEMPRE al prediagnóstico
✅ Pide nombre PRIMERO siempre
✅ Una pregunta por mensaje
✅ Tono 440: elegante e inspirador
✅ Cierra con "La Belleza 440 ✨"
✅ Notifica con <<<NOTIFY>>>
❌ No digas que eres IA
❌ No des precios de entrada
❌ No prometas resultados
❌ No presiones al paciente
❌ No des diagnósticos médicos
❌ No hagas rinoplastia ni bichectomía
"""

# Rotación de asesoras. Orden fijo del ciclo.
ASESORAS = ['bibiana', 'sara', 'lucero']
ASESORA_ENV = {
    'bibiana': 'ASESORA_1',
    'sara':    'ASESORA_2',
    'lucero':  'ASESORA_3',
}
ASESORA_LABEL = {
    'bibiana': 'Bibiana',
    'sara':    'Sara',
    'lucero':  'Lucero',
}


class BrainCX:
    def __init__(self):
        # WhApi: canal cirugía propio si WHAPI_TOKEN_CX está seteado,
        # si no usa el canal por defecto.
        cx_token = os.environ.get('WHAPI_TOKEN_CX', '').strip()
        self.whapi = WhapiClient(token=cx_token or None)
        self.api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        self.sb_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
        self.sb_key = os.environ.get('SUPABASE_ANON_KEY', '')
        self.history_limit = 12
        print(f"[CX INIT] sb_url={self.sb_url!r} sb_key_len={len(self.sb_key)} "
              f"anth_key_len={len(self.api_key)} cx_token={'custom' if cx_token else 'default'}", flush=True)

    # ------------------------------------------------------------------
    # Supabase helpers
    # ------------------------------------------------------------------
    def _sb_headers(self):
        return {
            'apikey': self.sb_key,
            'Authorization': f'Bearer {self.sb_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': _BROWSER_UA,
        }

    def _load_history(self, sender_id):
        if not self.sb_url or not self.sb_key:
            return []
        params = (
            f'contacto_telefono=eq.{urllib.parse.quote(sender_id)}'
            f'&canal=eq.cirugia'
            f'&direccion=in.(entrante,saliente)'
            f'&select=mensaje,direccion,remitente,created_at'
            f'&order=created_at.desc&limit={self.history_limit}'
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
            print(f"[CX] sb_get HTTPError {e.code} body={body!r}", flush=True)
            return []
        except Exception as e:
            print(f"[CX] sb_get error: {e}", flush=True)
            return []
        rows = list(reversed(rows or []))
        messages = []
        for row in rows:
            content = (row.get('mensaje') or '').strip()
            if not content:
                continue
            direccion = (row.get('direccion') or '').lower()
            remitente = (row.get('remitente') or '').lower()
            role = 'assistant' if (direccion == 'saliente' or remitente in ('bot', 'asistente', 'sistema')) else 'user'
            messages.append({'role': role, 'content': content})
        while messages and messages[0]['role'] != 'user':
            messages.pop(0)
        collapsed = []
        for m in messages:
            if collapsed and collapsed[-1]['role'] == m['role']:
                collapsed[-1]['content'] += '\n' + m['content']
            else:
                collapsed.append(dict(m))
        print(f"[CX] loaded {len(collapsed)} history msgs", flush=True)
        return collapsed

    def _save_message(self, sender_id, sender_name, mensaje, direccion, remitente):
        if not self.sb_url or not self.sb_key or not mensaje:
            return
        body = {
            'contacto_nombre': sender_name or None,
            'contacto_telefono': sender_id,
            'canal': 'cirugia',
            'mensaje': mensaje,
            'direccion': direccion,
            'remitente': remitente,
            'leido': direccion == 'saliente',
        }
        headers = self._sb_headers()
        headers['Prefer'] = 'return=minimal'
        try:
            req = urllib.request.Request(
                f'{self.sb_url}/rest/v1/conversaciones_440',
                data=json.dumps(body).encode(), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=8) as r:
                print(f"[CX] sb_insert {direccion}/{remitente} OK status={r.status}", flush=True)
        except urllib.error.HTTPError as e:
            err = ''
            try: err = e.read().decode()[:300]
            except: pass
            print(f"[CX] sb_insert HTTPError {e.code} body={err!r}", flush=True)
        except Exception as e:
            print(f"[CX] sb_insert error: {e}", flush=True)

    # ------------------------------------------------------------------
    # Rotación de asesoras
    # ------------------------------------------------------------------
    def _get_ultima_asesora(self):
        """Lee asesoras_turno (canal=cirugia). Devuelve el slug en minúsculas."""
        if not self.sb_url or not self.sb_key:
            return None
        url = f'{self.sb_url}/rest/v1/asesoras_turno?canal=eq.cirugia&select=ultima_asesora&limit=1'
        try:
            req = urllib.request.Request(url, headers=self._sb_headers(), method='GET')
            with urllib.request.urlopen(req, timeout=8) as r:
                rows = json.loads(r.read())
            if rows:
                return (rows[0].get('ultima_asesora') or '').strip().lower() or None
        except Exception as e:
            print(f"[CX] get_ultima_asesora error: {e}", flush=True)
        return None

    def _set_ultima_asesora(self, asesora):
        if not self.sb_url or not self.sb_key:
            return
        url = f'{self.sb_url}/rest/v1/asesoras_turno?canal=eq.cirugia'
        headers = self._sb_headers()
        headers['Prefer'] = 'return=minimal'
        body = {'ultima_asesora': asesora, 'updated_at': _now_iso()}
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                         headers=headers, method='PATCH')
            with urllib.request.urlopen(req, timeout=8) as r:
                print(f"[CX] set_ultima_asesora={asesora} OK status={r.status}", flush=True)
        except Exception as e:
            print(f"[CX] set_ultima_asesora error: {e}", flush=True)

    def _next_asesora(self):
        """Determina a quién le toca. Devuelve (slug, label, phone)."""
        ultima = self._get_ultima_asesora()
        if ultima in ASESORAS:
            idx = (ASESORAS.index(ultima) + 1) % len(ASESORAS)
        else:
            idx = 0  # default → bibiana
        slug = ASESORAS[idx]
        phone = os.environ.get(ASESORA_ENV[slug], '').strip()
        print(f"[CX] rotación: ultima={ultima!r} → siguiente={slug!r} phone={'set' if phone else 'MISSING'}", flush=True)
        return slug, ASESORA_LABEL[slug], phone

    # ------------------------------------------------------------------
    # Claude
    # ------------------------------------------------------------------
    def _call_claude(self, messages):
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 500,
            "system": CX_SYSTEM,
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
                data = json.loads(r.read())
                for block in data.get('content', []):
                    if block.get('type') == 'text':
                        return block.get('text', '')
                return ''
        except urllib.error.HTTPError as e:
            body = ''
            try: body = e.read().decode()[:400]
            except: pass
            print(f"[CX] Claude HTTPError {e.code} body={body!r}", flush=True)
            return "Disculpa, tuve un problema técnico. ¿Puedes repetir? 😊"
        except Exception as e:
            print(f"[CX] Claude error: {e}", flush=True)
            return "Disculpa, tuve un problema técnico. ¿Puedes repetir? 😊"

    # ------------------------------------------------------------------
    # NOTIFY parsing + envío
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_notify(block):
        out = {}
        for line in (block or '').splitlines():
            line = line.strip()
            if not line or ':' not in line:
                continue
            k, _, v = line.partition(':')
            out[k.strip().lower()] = v.strip()
        return out

    def _notify_lead(self, fields, sender_id):
        """Rota asesora, notifica a esa asesora + Dra. Sharon + Central."""
        slug, label, asesora_phone = self._next_asesora()
        nombre      = fields.get('nombre', '—')
        proc        = fields.get('procedimiento', '—')
        fecha       = fields.get('fecha_deseada') or fields.get('fecha', 'no definida')
        ciudad      = fields.get('ciudad', '—')
        tel         = fields.get('telefono', sender_id) or sender_id
        motivacion  = fields.get('motivacion', '—')
        score       = (fields.get('score') or fields.get('prioridad') or 'CALIENTE').upper()
        razon       = fields.get('razon_score', '—')
        accion      = fields.get('accion', 'Contactar al paciente')

        # Mensaje principal a la asesora de turno — formato según score
        if 'URGENTE' in score:
            msg_asesora = (
                f"🚨 LEAD URGENTE CIRUGÍA — TE TOCA {label.upper()}\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {nombre} ({ciudad})\n"
                f"💉 {proc}\n"
                f"📅 Fecha deseada: {fecha}\n"
                f"💭 Motivación: {motivacion}\n"
                f"⚡ Razón: {razon}\n"
                f"📱 Tel: {tel}\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "🔥 LLAMAR AHORA — no esperar"
            )
        elif 'CALIENTE' in score:
            msg_asesora = (
                f"🔥 LEAD CALIENTE CIRUGÍA — TE TOCA {label.upper()}\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {nombre} ({ciudad})\n"
                f"💉 {proc}\n"
                f"📅 Fecha deseada: {fecha}\n"
                f"💭 Motivación: {motivacion}\n"
                f"📱 Tel: {tel}\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "Contactar HOY 📞"
            )
        elif 'TIBIO' in score:
            msg_asesora = (
                f"🌡️ LEAD TIBIO CIRUGÍA — TE TOCA {label.upper()}\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {nombre} ({ciudad})\n"
                f"💉 {proc}\n"
                f"💭 {razon}\n"
                f"📱 Tel: {tel}\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "Seguimiento esta semana 📲"
            )
        else:  # FRÍO u otro
            msg_asesora = (
                f"❄️ LEAD FRÍO CIRUGÍA — TE TOCA {label.upper()}\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {nombre} ({ciudad})\n"
                f"💉 {proc}\n"
                f"📱 Tel: {tel}\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "Nurturing — no urgente"
            )

        # Copia para Sharon y Central — siempre incluye score
        score_emoji = {'URGENTE': '🚨', 'CALIENTE': '🔥', 'TIBIO': '🌡️', 'FRÍO': '❄️', 'FRIO': '❄️'}.get(score, '🔔')
        msg_copia = (
            f"{score_emoji} LEAD CIRUGÍA ({score}) — copia\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {nombre} · {proc}\n"
            f"📅 {fecha} · 📍 {ciudad}\n"
            f"💭 {motivacion}\n"
            f"📱 {tel}\n"
            f"👩 Asignado a: {label}\n"
            f"⚡ {razon}\n"
            "━━━━━━━━━━━━━━━━━━━"
        )

        results = {}
        # 1. Asesora de turno
        if asesora_phone:
            results['asesora'] = self.whapi.send_text(asesora_phone, msg_asesora)
        else:
            print(f"[CX] ⚠ asesora {slug} sin teléfono en env — no se notifica", flush=True)
            results['asesora'] = {'error': f'env {ASESORA_ENV[slug]} missing'}
        # 2. Dra. Sharon
        sharon = os.environ.get('DRA_SHARON', '').strip()
        if sharon:
            results['sharon'] = self.whapi.send_text(sharon, msg_copia)
        # 3. Central / admin
        admin = os.environ.get('ADMIN_CX', '').strip()
        if admin:
            results['central'] = self.whapi.send_text(admin, msg_copia)

        # Avanzar la rotación SOLO si se logró notificar a la asesora
        if asesora_phone:
            self._set_ultima_asesora(slug)
        print(f"[CX] notify_lead asesora={slug} results={ {k: (v.get('sent') if isinstance(v,dict) else v) for k,v in results.items()} }", flush=True)
        return slug, label

    # ------------------------------------------------------------------
    # Flujo principal
    # ------------------------------------------------------------------
    def process(self, sender_id, sender_name, text, canal='cirugia'):
        print(f"[CX] {sender_id}: {text[:60]!r}", flush=True)

        history = self._load_history(sender_id)
        user_content = f"[{sender_name or sender_id}]: {text}" if sender_name else text
        history.append({'role': 'user', 'content': user_content})

        self._save_message(sender_id, sender_name, text, 'entrante', 'paciente')

        full_response = self._call_claude(history)
        print(f"[CX] Claude len={len(full_response)} preview={full_response[:80]!r}", flush=True)

        # NOTIFY block
        notify = None
        match = re.search(r'<<<NOTIFY>>>(.*?)<<<END>>>', full_response, re.DOTALL)
        if match:
            notify = match.group(1).strip()

        # Texto visible al paciente — sin el bloque NOTIFY
        user_facing = re.sub(r'<<<NOTIFY>>>.*?<<<END>>>', '', full_response, flags=re.DOTALL)
        user_facing = re.sub(r'\n{3,}', '\n\n', user_facing).strip()

        if user_facing:
            print(f"[CX] sending reply len={len(user_facing)}", flush=True)
            r = self.whapi.send_text(sender_id, user_facing)
            print(f"[CX] send_text result sent={r.get('sent') if isinstance(r,dict) else r}", flush=True)
            self._save_message(sender_id, sender_name, full_response, 'saliente', 'bot')

        if notify:
            fields = self._parse_notify(notify)
            print(f"[CX] NOTIFY fields={fields}", flush=True)
            self._notify_lead(fields, sender_id)


def _now_iso():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
