"""Aviso de fallas de la IA (API de Claude).

Cuando una llamada a Anthropic falla, se le cuenta a MedFiles (/api/entrada/alerta-ia, con la clave del bot).
MedFiles clasifica la falla (sin créditos, llave inválida, servicio caído, solicitud rechazada) y le manda un
WhatsApp al Dr. cuando corresponde: créditos y llave de inmediato; caídas solo si se repiten; cada tipo
máximo una vez cada 6 horas. Best-effort: nunca rompe el flujo del bot.
"""
import os, json, urllib.request


def revisar_error_ia(texto_error, origen='bot', status=None):
    """status: código HTTP de Anthropic, o None si no hubo conexión (timeout, red)."""
    try:
        base = (os.environ.get('MEDFILES_URL') or 'https://medfiles.drgiovannifuentes.com').strip().rstrip('/')
        clave = (os.environ.get('MEDFILES_BOT_CLAVE') or '').strip()
        if not clave:
            return
        req = urllib.request.Request(base + '/api/entrada/alerta-ia', method='POST',
                                     data=json.dumps({'origen': origen, 'status': status, 'error': str(texto_error or '')[:300]}).encode(),
                                     headers={'Content-Type': 'application/json', 'X-Clave': clave, 'User-Agent': 'BOT440/1.0'})
        with urllib.request.urlopen(req, timeout=8) as r:
            print(f"[ALERTA-IA] falla de IA reportada a MedFiles status={r.status}", flush=True)
    except Exception as e:
        print(f"[ALERTA-IA] no se pudo reportar: {e}", flush=True)
