"""WhatsApp webhook for the Cirugía Plástica channel (+57 304 488 6085).

Same WhApi payload shape as api/webhook.py, but routes every message
to BrainCX with canal='cirugia'.
"""
from http.server import BaseHTTPRequestHandler
import json, os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.brain_cx import BrainCX


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        print(f"[WEBHOOK-CX] POST recibido", flush=True)
        try:
            length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(length))
            messages = payload.get('messages', [])
            if not messages:
                print(f"[WEBHOOK-CX] no_messages", flush=True)
                self._ok({'status': 'no_messages'}); return
            msg = messages[0]
            if msg.get('from_me'):
                print(f"[WEBHOOK-CX] echo (from_me)", flush=True)
                self._ok({'status': 'echo'}); return
            sender_id = msg.get('from', '').replace('@s.whatsapp.net', '')
            text = msg.get('text', {}).get('body', '') if msg.get('type') == 'text' else '[MEDIA]'
            name = msg.get('from_name', '')
            print(f"[WEBHOOK-CX] sender={sender_id} name={name!r} text={text[:60]!r}", flush=True)
            if text and sender_id:
                BrainCX().process(sender_id, name, text, 'cirugia')
            print(f"[WEBHOOK-CX] Procesado OK", flush=True)
            self._ok({'status': 'ok'})
        except Exception as e:
            print(f"[WEBHOOK-CX] Error: {e}", flush=True)
            self._ok({'error': str(e)})

    def do_GET(self):
        self._ok({'status': 'BOT440-CX running'})

    def _ok(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *a): pass
