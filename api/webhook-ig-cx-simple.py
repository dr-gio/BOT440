import json
import os
import urllib.request
import urllib.parse
import urllib.error
from http.server import BaseHTTPRequestHandler
import anthropic

IG_CX_TOKEN = os.environ.get('IG_CX_PAGE_ACCESS_TOKEN','')
IG_CX_ACCOUNT_ID = os.environ.get('IG_CX_ACCOUNT_ID','17841400339315123')

SYSTEM_SIMPLE = """Eres el community
manager de @drgiovannifuentes —
el Dr. Giovanni Fuentes, Cirujano
Plástico, CEO & CMO de 440 Clinic,
Barranquilla, Colombia.

TONO:
→ Cálido, humano y cercano
→ Elegante pero natural
→ Como una persona real —
  no un bot
→ Sigue la conversación de
  forma natural
→ Usa emojis con moderación
→ Máximo 3-4 líneas
→ NUNCA digas que eres IA
→ Cierra con "La Belleza 440 ✨"
  solo cuando aplique

━━━━━━━━━━━━━━━━━━━━━━━━━━━
TIPOS DE MENSAJE Y CÓMO RESPONDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. INTERÉS EN CIRUGÍA/PROCEDIMIENTO:
Palabras clave: información, info,
precio, costo, cuánto, cita,
consulta, operación, cirugía,
procedimiento, lipoescultura, lipo,
mamoplastia, abdominoplastia,
blefaroplastia, lifting, papada,
valoración, me quiero operar,
me interesa, quisiera saber,
quiero hacerme, doctor, Dr. Gio

→ Para DM responde:
"¡Hola [nombre si lo sabes]! 💙
Para asesorarte sobre
[procedimiento que mencionó]
con el Dr. Gio, escríbenos
por WhatsApp:
📱 wa.me/573137917168?text=Hola!+Me+interesa+[procedimiento]
¡Te esperamos! 💙
La Belleza 440 ✨"

→ Para COMENTARIO responde
públicamente:
"¡Hola [nombre]! 💙
Con gusto te orientamos sobre
[procedimiento].
Te escribimos por DM para
darte toda la información 😊"
Y envía DM con el link de WhatsApp.

2. ADMIRACIÓN / RESULTADO BONITO:
"qué linda lipo", "increíble resultado",
"me encanta ese trabajo", etc.

→ Responde de forma cálida y natural:
Genera una respuesta única según
el comentario específico.
Ejemplos:
"¡Gracias! 💙 Cada resultado
es una obra maestra diseñada
con amor ✨🙏"
"¡Nos alegra tanto! 💙
Eso nos motiva a seguir
dando lo mejor 🙏✨"

3. SALUDO DESDE OTRO LUGAR/PAÍS:
"saludos desde Nueva York",
"hola desde Miami", etc.

→ Sigue la conversación natural:
"¡[ciudad]! 🗽💙
Qué alegría saber que nos
sigues desde allá.
¡Aquí te esperamos cuando
quieras visitarnos! ✈️
La Belleza 440 ✨"

4. SALUDO DE AMIGO/CONOCIDO:
"hola Gio", "qué más crack",
"saludos", etc.

→ Responde cálido y natural:
"¡Hola! 😊💙
Gracias por pasarte por acá.
¡Un abrazo! 🙏"

5. COMENTARIO NEUTRO/EMOJI:
Solo emojis o palabras sueltas.
→ Responde con emoji cálido:
"💙🙏" o "😊💙"

6. NEGATIVO/CRÍTICA/SPAM:
→ NO responder.
Devuelve texto vacío: ""

━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS CRÍTICAS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━
→ NUNCA digas que eres IA o bot
→ NUNCA uses plantillas robóticas
→ SÍ sigue la conversación natural
→ SÍ usa el nombre si lo conoces
→ Máximo 4 líneas siempre
→ Si hay interés en cirugía →
  SIEMPRE redirige a WhatsApp
→ Para todo lo demás →
  respuesta humana y cálida
"""

# Palabras clave de interés en cirugía
CIRUGIA_KEYWORDS = [
    'información','informacion','info','precio','costo','cuánto','cuanto',
    'cita','consulta','operación','operacion','cirugía','cirugia',
    'procedimiento','lipoescultura','lipo','mamoplastia','abdominoplastia',
    'blefaroplastia','lifting','papada','valoración','valoracion',
    'me quiero operar','me interesa','quisiera saber','quiero hacerme',
    'doctor','dr. gio','dr gio',
]

# Procedimientos para personalizar el texto del link de WhatsApp
PROCEDIMIENTOS = [
    'lipoescultura','mamoplastia','abdominoplastia','blefaroplastia',
    'rinoplastia','lifting','papada','lipo',
]


def _detecta_interes(text):
    t = (text or '').lower()
    return any(kw in t for kw in CIRUGIA_KEYWORDS)


def _procedimiento_mencionado(text):
    t = (text or '').lower()
    for p in PROCEDIMIENTOS:
        if p in t:
            return p
    return ''


def _wa_link(text):
    proc = _procedimiento_mencionado(text)
    if proc:
        q = urllib.parse.quote_plus(f'Hola! Me interesa {proc}')
    else:
        q = urllib.parse.quote_plus('Hola! Quiero información')
    return f'wa.me/573137917168?text={q}'


def _dm_interes(text):
    proc = _procedimiento_mencionado(text) or 'tu procedimiento'
    return (f'¡Hola! 💙\n'
            f'Para asesorarte sobre {proc} con el Dr. Gio, '
            f'escríbenos por WhatsApp:\n'
            f'📱 {_wa_link(text)}\n'
            f'¡Te esperamos! 💙\n'
            f'La Belleza 440 ✨')


def _graph_post(path, data):
    """POST a graph.instagram.com con el token CX."""
    url = f'https://graph.instagram.com/v21.0/{path}'
    body = urllib.parse.urlencode({**data, 'access_token': IG_CX_TOKEN}).encode()
    req = urllib.request.Request(url, data=body, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return {'error': e.read().decode()[:300]}
        except Exception:
            return {'error': f'http {e.code}'}
    except Exception as e:
        return {'error': str(e)}


def _send_dm(recipient, text):
    """Envía DM. recipient = {'id': igsid} o {'comment_id': cid}."""
    url = f'https://graph.instagram.com/v21.0/{IG_CX_ACCOUNT_ID}/messages'
    payload = json.dumps({'recipient': recipient,
                          'message': {'text': text}}).encode()
    req = urllib.request.Request(
        url, data=payload, method='POST',
        headers={'Content-Type': 'application/json',
                 'Authorization': f'Bearer {IG_CX_TOKEN}'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return {'error': e.read().decode()[:300]}
        except Exception:
            return {'error': f'http {e.code}'}
    except Exception as e:
        return {'error': str(e)}


def _claude_reply(text):
    client = anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY',''))
    response = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=200,
        system=SYSTEM_SIMPLE,
        messages=[{'role': 'user', 'content': text}],
    )
    return response.content[0].text.strip()


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._respond(200, {'status': 'BOT440-IG-CX-SIMPLE running'})

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))

            tipo = (body.get('tipo', '') or 'dm').lower()
            sender_id = body.get('sender_id', '')
            text = body.get('text', '') or body.get('message', '')
            comment_id = body.get('comment_id', '') or body.get('id', '')

            if not text:
                self._respond(200, {'status': 'ok', 'reply': ''})
                return

            interes = _detecta_interes(text)

            # ── COMENTARIO DEL FEED ──────────────────────────────────
            if tipo in ('comment', 'comentario'):
                reply = _claude_reply(text)
                result = {'status': 'ok', 'tipo': 'comment', 'reply': ''}
                if comment_id and reply:
                    # respuesta pública en el comentario
                    result['public'] = _graph_post(
                        f'{comment_id}/replies', {'message': reply})
                if interes and comment_id:
                    # DM privado con el link de WhatsApp
                    result['dm'] = _send_dm(
                        {'comment_id': comment_id}, _dm_interes(text))
                self._respond(200, result)
                return

            # ── DM ───────────────────────────────────────────────────
            if not sender_id:
                self._respond(200, {'status': 'ok', 'reply': ''})
                return

            if interes:
                # link personalizado garantizado
                reply = _dm_interes(text)
            else:
                reply = _claude_reply(text)

            self._respond(200, {'status': 'ok', 'tipo': 'dm', 'reply': reply})

        except Exception:
            self._respond(200, {'status': 'ok', 'reply': ''})

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *args):
        pass
