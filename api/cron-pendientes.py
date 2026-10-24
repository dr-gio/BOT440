"""Cron (cada 10 min): quien pidió agendar (asesoría o valoración) y no terminó de dar sus datos en 30 min
→ se crea el lead con lo que haya, marcado ⚠️ datos incompletos, y la asesora recibe el aviso para completarlo.
Vercel lo llama con el encabezado Authorization: Bearer CRON_SECRET."""
from http.server import BaseHTTPRequestHandler
import json, os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.brain_cx import BrainCX


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        secreto = os.environ.get('CRON_SECRET', '')
        if not secreto or self.headers.get('Authorization', '') != f'Bearer {secreto}':
            return self._json(401, {'error': 'no autorizado'})
        try:
            hechos = BrainCX().crear_leads_pendientes(minutos=30)
            self._json(200, {'ok': True, 'leads': hechos})
        except Exception as e:
            print(f"[CX-PEND] error: {e}", flush=True)
            self._json(200, {'ok': False, 'error': str(e)})

    def _json(self, codigo, data):
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *a): pass
