import os, json, urllib.request, urllib.error, urllib.parse
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
NO es definitiva al 100% — con el
tiempo pueden aparecer algunos vellos
muy finos. Se recomienda una sesión
de mantenimiento anual para mantener
los resultados perfectos.

Si preguntan si es definitiva:
"El Removall Trio elimina el 90-95%
del vello al completar las 6 sesiones 💖
Con el tiempo pueden aparecer algunos
vellos muy finos — por eso recomendamos
una sesión de mantenimiento anual
para mantener los resultados ✨"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
FLUJO DE CONVERSACIÓN
━━━━━━━━━━━━━━━━━━━━━━━━━━━

PASO 1 — PRIMER MENSAJE:
"¡Bienvenid@ a 440 Clinic! 💖
¿En qué te puedo ayudar hoy?"

PASO 2A — DEPILACIÓN LÁSER:
Si menciona depilación/láser/vello/
removall/axilas/bikini/piernas/barba:
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
Si menciona hiperbárica/oxígeno/cámara:
"¡La Cámara Hiperbárica es increíble!
Oxigenación profunda, acelera la
recuperación y retrasa el
envejecimiento ✨
¿Cuál es tu nombre y de qué ciudad
nos escribes? 😊"

PASO 3 — RECIBIR NOMBRE Y CIUDAD:
"¡Mucho gusto [nombre]! 😊"
Si es de Barranquilla: continúa normal
Si es de otra ciudad:
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

PASO 5 — CUANDO ELIGE ZONA (depilación):
"[Zona] x6 sesiones: $[total] 💕
Primera sesión: $[total÷6]

¿Cómo prefieres continuar?
1️⃣ Agendar mi sesión
2️⃣ Valoración gratuita (15 min)
3️⃣ Que me contacten por WhatsApp"

PASO 6 — SEGÚN ELECCIÓN:

Si elige 1️⃣ (agendar):
"¿Qué día y hora te queda mejor? 😊
Ejemplo: 'Viernes en la mañana'
o 'Sábado a las 10am'"
Cuando responde:
"¡Perfecto [nombre]! Nuestro equipo
te confirmará la cita muy pronto 💖"
Luego notifica:
<<<NOTIFY>>>
nombre: [nombre]
telefono: [número si lo tiene]
servicio: [servicio]
zona: [zona si aplica]
preferencia: [día/hora]
<<<END>>>

Si elige 2️⃣ (valoración gratuita):
"¡Tenemos valoraciones gratuitas
de 15 minutos! 💖

📅 Katherine: Martes y Jueves 1-5pm
📅 Roxana: Miércoles y Viernes 1-5pm

¿Qué día te queda mejor [nombre]?"
Cuando elige día:
"¡Perfecto! Nuestro equipo te
confirmará el horario exacto 💖"
<<<NOTIFY>>>
nombre: [nombre]
telefono: [número si lo tiene]
servicio: valoracion gratuita
preferencia: [día elegido]
<<<END>>>

Si elige 3️⃣ (contactar):
"¿Cuál es tu número de WhatsApp? 📱"
Cuando da el número:
"¡Listo [nombre]! 💖
En breve te escribiremos para
coordinar. ¡Hasta pronto! ✨"
<<<NOTIFY>>>
nombre: [nombre]
telefono: [número dado]
servicio: [servicio]
accion: contactar
<<<END>>>

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
✅ Notifica al equipo con <<<NOTIFY>>>
   cuando hay lead calificado
❌ No saltes pasos
❌ No inventes precios — usa SOLO
   los de arriba
❌ No digas que eres IA
❌ Si menciona cirugía → redirige a
   wa.me/573044886085 y NO sigas
   ese tema
"""

# Default headers including User-Agent (gate.whapi.cloud and supabase use
# Cloudflare which blocks Python-urllib UA with HTTP 403 / error 1010)
_BROWSER_UA = 'Mozilla/5.0 (compatible; BOT440/1.0; +https://440clinic.com)'


class Brain:
    def __init__(self):
        self.whapi = WhapiClient()
        self.api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        self.sb_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
        self.sb_key = os.environ.get('SUPABASE_ANON_KEY', '')
        self.history_limit = 10
        print(f"[BRAIN INIT] sb_url={self.sb_url!r} sb_key_len={len(self.sb_key)} anth_key_len={len(self.api_key)}", flush=True)

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
        """Read last N messages for this contact and return Anthropic-format messages[]."""
        if not self.sb_url or not self.sb_key:
            print(f"[BRAIN] supabase not configured — using empty history", flush=True)
            return []
        params = (
            f'contacto_telefono=eq.{urllib.parse.quote(sender_id)}'
            f'&canal=eq.{urllib.parse.quote(canal)}'
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
        # rows are newest-first → reverse for chronological order
        rows = list(reversed(rows or []))
        messages = []
        for row in rows:
            content = (row.get('mensaje') or '').strip()
            if not content:
                continue
            direccion = (row.get('direccion') or '').lower()
            remitente = (row.get('remitente') or '').lower()
            # Heuristics: entrante / paciente → user; saliente / bot|asistente|sistema → assistant
            if direccion == 'saliente' or remitente in ('bot', 'asistente', 'sistema'):
                role = 'assistant'
            else:
                role = 'user'
            messages.append({'role': role, 'content': content})
        print(f"[BRAIN] loaded {len(messages)} history msgs from supabase", flush=True)
        # Anthropic requires the first message to be a user turn — drop leading assistant turns if any
        while messages and messages[0]['role'] != 'user':
            messages.pop(0)
        # Collapse consecutive same-role turns (rare, defensive)
        collapsed = []
        for m in messages:
            if collapsed and collapsed[-1]['role'] == m['role']:
                collapsed[-1]['content'] = collapsed[-1]['content'] + '\n' + m['content']
            else:
                collapsed.append(dict(m))
        return collapsed

    def _save_message(self, sender_id, sender_name, canal, mensaje, direccion, remitente):
        """Insert a single message into conversaciones_440."""
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
    # Main flow
    # ------------------------------------------------------------------
    def process(self, sender_id, sender_name, text, canal='whatsapp'):
        print(f"[BRAIN] {sender_id}: {text[:50]}", flush=True)
        print(f"[BRAIN] api_key_len={len(self.api_key)} canal={canal}", flush=True)

        # 1. Load history from Supabase
        history = self._load_history(sender_id, canal)

        # 2. Append the new user message (with sender name prefix for context)
        user_content = f"[{sender_name or sender_id}]: {text}" if sender_name else text
        history.append({'role': 'user', 'content': user_content})

        # 3. Save user message to Supabase (fire before Claude call so it's
        #    captured even if the model call dies)
        self._save_message(sender_id, sender_name, canal, text,
                           direccion='entrante', remitente='paciente')

        # 4. Call Claude with history
        print(f"[BRAIN] calling Claude (history={len(history)} msgs)", flush=True)
        response = self._call_claude(history)
        print(f"[BRAIN] Claude responded len={len(response)} preview={response[:80]!r}", flush=True)
        text_resp, notify = self._parse(response)

        # 5. Send reply and persist
        if text_resp.strip():
            print(f"[BRAIN] sending reply to {sender_id} len={len(text_resp)}", flush=True)
            r = self.whapi.send_text(sender_id, text_resp.strip())
            print(f"[BRAIN] send_text result={r}", flush=True)
            self._save_message(sender_id, sender_name, canal, text_resp.strip(),
                               direccion='saliente', remitente='bot')
        else:
            print(f"[BRAIN] text_resp empty after parse — NOT sending", flush=True)

        if notify:
            print(f"[BRAIN] notify_admin trigger", flush=True)
            self._notify_admin(notify, sender_id)

    def _call_claude(self, messages):
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 500,
            "system": SYSTEM,
            "messages": messages
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
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())["content"][0]["text"]
        except urllib.error.HTTPError as e:
            body = ''
            try: body = e.read().decode()[:400]
            except: pass
            print(f"[BRAIN] Claude HTTPError {e.code} body={body!r}", flush=True)
            return "Disculpa, tuve un problema técnico. ¿Puedes repetir? 😊"
        except Exception as e:
            print(f"[BRAIN] Claude error: {e}", flush=True)
            return "Disculpa, tuve un problema técnico. ¿Puedes repetir? 😊"

    def _parse(self, response):
        import re
        notify = None
        match = re.search(r'<<<NOTIFY>>>(.*?)<<<END>>>', response, re.DOTALL)
        if match:
            notify = match.group(1).strip()
            response = re.sub(r'<<<NOTIFY>>>.*?<<<END>>>', '', response, flags=re.DOTALL).strip()
        return response, notify

    def _notify_admin(self, data, sender_id):
        admin = os.environ.get('ADMIN_WHATSAPP', '573181800130')
        msg = f"🔔 LEAD ESTÉTICO\n━━━━━━━━━━━━━\n{data}\n📱 Canal: {sender_id}\n━━━━━━━━━━━━━"
        self.whapi.send_text(admin, msg)
