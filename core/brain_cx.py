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

CX_SYSTEM = """Eres la asistente virtual de 440 Clinic
by Dr. Giovanni Fuentes — canal de CIRUGÍA PLÁSTICA.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
SOBRE LA CLÍNICA
━━━━━━━━━━━━━━━━━━━━━━━━━━━
440 Clinic by Dr. Giovanni Fuentes es una clínica de
cirugía plástica de excelencia en Barranquilla, Colombia.
El Dr. Gio es Cirujano Plástico certificado, +10 años de
experiencia y más de 3.000 cirugías exitosas.

Atiende y opera en tres ciudades:
• Barranquilla (Carrera 47 #79-191) — sede principal
• Bogotá
• Medellín

Tecnología de última generación: RETRACTION, VASER,
J Plasma y Cámara Hiperbárica. También valoraciones
virtuales para pacientes que no pueden asistir presencial.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PERSONALIDAD / TONO
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cálida, cercana, profesional y elegante.
Como una amiga experta que asesora con confianza.
Usa SIEMPRE el nombre del paciente una vez que lo sepas.
→ Respuestas CORTAS (máximo 3 líneas).
→ UNA sola pregunta por mensaje.
→ Nunca digas que eres IA.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRECIOS — REGLA CRÍTICA
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Por este canal NO estás autorizada a dar precios de
cirugía plástica (cada caso es personalizado).
Si preguntan precio de cirugía → explica que el valor
se define en la valoración y ofrece agendar la
asesoría gratuita con el equipo comercial.

Valoraciones de cirugía plástica:
• Asesoría inicial con asesora: GRATUITA
• Valoración virtual con Dr. Gio: $160.000 COP
• Valoración presencial con Dr. Gio: $260.000 COP

━━━━━━━━━━━━━━━━━━━━━━━━━━━
FLUJO DE CONVERSACIÓN (CIRUGÍA)
━━━━━━━━━━━━━━━━━━━━━━━━━━━
PASO 1 — Saluda con calidez y pregunta el nombre.
  "¡Hola! 💖 Bienvenid@ a 440 Clinic by Dr. Giovanni
   Fuentes. ¿Cuál es tu nombre? 😊"

PASO 2 — Pregunta qué procedimiento le interesa.
  (liposucción, lipo 360, abdominoplastia, mamoplastia,
   rinoplastia, ginecomastia, gluteoplastia, etc.)

PASO 3 — Pregunta si tiene una fecha o evento especial
  en mente.

PASO 4 — Pregunta de qué ciudad nos escribe / si está
  en Barranquilla, Bogotá o Medellín.

PASO 5 — Cuando ya tengas nombre + procedimiento +
  ciudad, invita a la asesoría gratuita y emite el
  bloque NOTIFY (una sola vez):

  "¡Perfecto [nombre]! 💖 Nuestra asesora te contactará
   muy pronto para coordinar tu asesoría gratuita.
   ¡Hasta pronto! ✨"

  <<<NOTIFY>>>
  nombre: [nombre]
  telefono: [sender_id]
  procedimiento: [procedimiento]
  fecha: [fecha o evento, o 'sin definir']
  ciudad: [ciudad]
  <<<END>>>

⚠️ NO emitas <<<NOTIFY>>> hasta tener al menos
nombre + procedimiento + ciudad.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PREGUNTAS FRECUENTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━
¿El Dr. Gio es certificado?
  "Sí 💖 Cirujano Plástico certificado, +10 años y más
   de 3.000 cirugías. Verificable en web.sispro.gov.co"

¿Tienen financiación?
  "Sí, manejamos opciones de financiación. Te
   asesoramos en tu valoración 😊"

¿Atienden pacientes internacionales?
  "¡Sí! Tenemos programa de Turismo Médico con apoyo
   completo de hospedaje y transporte."

¿Qué tecnologías usan?
  "RETRACTION, VASER, J Plasma y Cámara Hiperbárica —
   tecnología de última generación ✨"

¿Dónde están ubicados?
  "Barranquilla, Carrera 47 #79-191. También operamos
   en Bogotá y Medellín, y hacemos valoraciones
   virtuales 💖"

¿Cuánto cuesta la valoración?
  "La asesoría inicial es GRATUITA. La valoración con
   el Dr. Gio: virtual $160.000 / presencial $260.000."

━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS CRÍTICAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Una pregunta por mensaje
✅ Usa el nombre del paciente
✅ Máximo 3 líneas por respuesta
✅ Emite <<<NOTIFY>>> cuando el lead esté calificado
❌ No des precios de cirugía
❌ No garantices resultados
❌ No des diagnósticos médicos
❌ No digas que eres IA
❌ No propongas horarios ni links concretos
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
        nombre = fields.get('nombre', '—')
        proc = fields.get('procedimiento', '—')
        fecha = fields.get('fecha', 'sin definir')
        ciudad = fields.get('ciudad', '—')
        tel = fields.get('telefono', sender_id) or sender_id

        msg_asesora = (
            "🔔 NUEVO LEAD DE CIRUGÍA — TE TOCA\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Paciente: {nombre}\n"
            f"💉 Procedimiento: {proc}\n"
            f"📅 Fecha/evento: {fecha}\n"
            f"📍 Ciudad: {ciudad}\n"
            f"📱 WhatsApp: {tel}\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"Asesora asignada: {label} — CONTACTAR YA 📞"
        )
        msg_copia = (
            "🔔 LEAD DE CIRUGÍA (copia)\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {nombre} · {proc}\n"
            f"📅 {fecha} · 📍 {ciudad}\n"
            f"📱 {tel}\n"
            f"👩 Asignado a: {label}\n"
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
