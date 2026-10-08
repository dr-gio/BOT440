"""Inicia conversaciones de WhatsApp desde el bot de cirugías.

GET /iniciar-cx → envía los mensajes que estén en la cola public.bot_envios (estado 'pendiente').
Solo se envía lo que ya está en la cola (la base no deja escribirla desde afuera), y cada mensaje queda
en el historial del bot (conversaciones_440) para que, cuando la persona responda, el bot siga la conversación.
"""
from http.server import BaseHTTPRequestHandler
import json, os, sys, re, urllib.request

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.brain_cx import BrainCX


def _rpc(nombre, cuerpo):
    url = os.environ.get('SUPABASE_URL', '').rstrip('/') + f'/rest/v1/rpc/{nombre}'
    key = os.environ.get('SUPABASE_ANON_KEY', '')
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), method='POST', headers={
        'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'User-Agent': 'BOT440/1.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        txt = r.read()
        return json.loads(txt) if txt else None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        resultado = []
        try:
            pendientes = _rpc('bot_envios_tomar', {}) or []
            brain = BrainCX()
            for e in pendientes:
                tel = re.sub(r'\D', '', e.get('telefono') or '')
                try:
                    r = brain.whapi.send_text(tel, e['texto'])
                    ok = bool(isinstance(r, dict) and r.get('sent'))
                    if ok:
                        brain._save_message(tel, e.get('nombre') or None, e['texto'], 'saliente', 'bot', canal='cirugia')
                    _rpc('bot_envio_marcar', {'p_id': e['id'], 'p_ok': ok, 'p_error': None if ok else str(r)[:300]})
                    resultado.append({'telefono': tel, 'ok': ok})
                    print(f"[INICIAR-CX] {tel} ok={ok}", flush=True)
                except Exception as ex:
                    _rpc('bot_envio_marcar', {'p_id': e['id'], 'p_ok': False, 'p_error': str(ex)[:300]})
                    resultado.append({'telefono': tel, 'ok': False})
            self._json(200, {'enviados': resultado})
        except Exception as ex:
            print(f"[INICIAR-CX] error: {ex}", flush=True)
            self._json(500, {'error': str(ex)[:200]})

    def _json(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *a): pass
