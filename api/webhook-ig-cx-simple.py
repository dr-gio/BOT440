import json
import os
from http.server import BaseHTTPRequestHandler
import anthropic

IG_CX_TOKEN = os.environ.get('IG_CX_PAGE_ACCESS_TOKEN','')
IG_CX_ACCOUNT_ID = os.environ.get('IG_CX_ACCOUNT_ID','17841400339315123')

SYSTEM_SIMPLE = """Eres el asistente de
@drgiovannifuentes en Instagram.

Analiza el mensaje y responde según:

INTERÉS EN CIRUGÍA/PROCEDIMIENTO:
El mensaje contiene CUALQUIERA de
estas palabras clave:
"información", "info", "hola quiero",
"me interesa", "quisiera saber",
"cuánto cuesta", "precio",
"cita", "consulta", "operación",
"cirugía", "procedimiento",
"lipoescultura", "lipo",
"mamoplastia", "abdominoplastia",
"blefaroplastia", "lifting",
"rinoplastia", "papada",
"Dr. Gio", "doctor", "valoración"

SI el mensaje contiene CUALQUIERA
de esas palabras → es INTERÉS
EN CIRUGÍA, sin importar si
también dice "hola".
→ Responde EXACTAMENTE:
"¡Hola! 💙
Para orientarte mejor sobre
tu proceso con el Dr. Gio,
escríbenos por WhatsApp:
📱 wa.me/573137917168
¡Te esperamos! 💙
La Belleza 440 ✨"

SALUDO / ADMIRACIÓN / COMENTARIO POSITIVO:
(hola, buenos días, qué bonito,
me encanta, felicitaciones, etc.)
SALUDO PURO solo cuando el mensaje
NO contiene ninguna de las palabras
clave de INTERÉS EN CIRUGÍA.
→ Responde EXACTAMENTE:
"¡Gracias por escribirnos! 💙🙏
La Belleza 440 ✨"

PREGUNTA GENERAL:
→ Responde MUY brevemente
  en máximo 2 líneas y agrega:
"Para más información:
📱 wa.me/573137917168 💙"

REGLAS:
→ Máximo 5 líneas
→ Nunca digas que eres IA
→ Nunca hagas preguntas
→ Siempre cierra con
  "La Belleza 440 ✨"
"""

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._respond(200, {'status': 'BOT440-IG-CX-SIMPLE running'})

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))

            # Extraer datos del mensaje
            sender_id = body.get('sender_id','')
            text = body.get('text','') or body.get('message','')
            name = body.get('username','') or body.get('name','')

            if not text or not sender_id:
                self._respond(200, {'status':'ok','reply':''})
                return

            # Llamar a Claude
            client = anthropic.Anthropic(
                api_key=os.environ.get('ANTHROPIC_API_KEY','')
            )
            response = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=200,
                system=SYSTEM_SIMPLE,
                messages=[{'role':'user','content':text}]
            )
            reply = response.content[0].text.strip()

            self._respond(200, {'status':'ok','reply':reply})

        except Exception as e:
            self._respond(200, {'status':'ok','reply':''})

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *args):
        pass
