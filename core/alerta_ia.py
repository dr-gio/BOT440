"""Aviso de créditos agotados de la API de Claude.

Si Anthropic responde que el saldo no alcanza ("credit balance is too low"),
se le pide a MedFiles (/api/entrada/alerta-ia, con la clave del bot) que le
mande un WhatsApp al Dr. MedFiles controla que sea máximo una vez cada 6 horas.
Best-effort: nunca rompe el flujo del bot.
"""
import os, re, json, urllib.request

_SIN_CREDITOS = re.compile(r'credit balance is too low|insufficient.{0,20}credit', re.I)


def revisar_error_ia(texto_error, origen='bot'):
    try:
        if not texto_error or not _SIN_CREDITOS.search(str(texto_error)):
            return
        base = (os.environ.get('MEDFILES_URL') or 'https://medfiles.drgiovannifuentes.com').strip().rstrip('/')
        clave = (os.environ.get('MEDFILES_BOT_CLAVE') or '').strip()
        if not clave:
            return
        req = urllib.request.Request(base + '/api/entrada/alerta-ia', method='POST',
                                     data=json.dumps({'origen': origen, 'error': str(texto_error)[:300]}).encode(),
                                     headers={'Content-Type': 'application/json', 'X-Clave': clave, 'User-Agent': 'BOT440/1.0'})
        with urllib.request.urlopen(req, timeout=8) as r:
            print(f"[ALERTA-IA] aviso de créditos enviado a MedFiles status={r.status}", flush=True)
    except Exception as e:
        print(f"[ALERTA-IA] no se pudo avisar: {e}", flush=True)
