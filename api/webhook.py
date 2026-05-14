from http.server import BaseHTTPRequestHandler
import json, os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.brain import Brain

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(length))
            messages = payload.get('messages', [])
            if not messages:
                self._ok({'status': 'no_messages'}); return
            msg = messages[0]
            if msg.get('from_me'):
                self._ok({'status': 'echo'}); return
            sender_id = msg.get('from','').replace('@s.whatsapp.net','')
            text = msg.get('text',{}).get('body','') if msg.get('type')=='text' else '[MEDIA]'
            name = msg.get('from_name','')
            if text and sender_id:
                Brain().process(sender_id, name, text, 'whatsapp')
            self._ok({'status': 'ok'})
        except Exception as e:
            print(f"Error: {e}"); self._ok({'error': str(e)})
    def do_GET(self):
        self._ok({'status': 'BOT440 running'})
    def _ok(self, data):
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    def log_message(self, *a): pass
