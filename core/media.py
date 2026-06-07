"""Media helper: descarga un archivo entrante de WhApi y lo re-hospeda en
Supabase Storage (bucket público 'conversaciones-media') para tener una URL
permanente (los links de WhApi expiran).

Best-effort: ante cualquier fallo devuelve None y el caller sigue con el flujo
normal (placeholder de texto), sin romper el webhook.
"""
import os
import json
import uuid
import urllib.request
import urllib.error

BUCKET = 'conversaciones-media'
_UA = 'Mozilla/5.0 (BOT440 media)'

_EXT_BY_MIME = {
    'image/jpeg': 'jpg', 'image/jpg': 'jpg', 'image/png': 'png',
    'image/webp': 'webp', 'image/gif': 'gif',
}


def _download(link, token):
    """Descarga el binario desde el link de WhApi (con Bearer token)."""
    req = urllib.request.Request(link, headers={
        'Authorization': f'Bearer {token}',
        'User-Agent': _UA,
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        data = r.read()
        ctype = r.headers.get('Content-Type', 'application/octet-stream')
        return data, ctype


def store_whapi_media(link, token, mime_type=None, prefix='wa'):
    """Descarga el media de WhApi y lo sube a Supabase Storage.

    Devuelve la URL pública permanente, o None si algo falla.
    """
    if not link:
        return None
    sb_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    sb_key = (os.environ.get('SUPABASE_SERVICE_KEY')
              or os.environ.get('SUPABASE_ANON_KEY', ''))
    if not sb_url or not sb_key:
        return None
    try:
        data, ctype = _download(link, token)
        mime = mime_type or ctype or 'application/octet-stream'
        ext = _EXT_BY_MIME.get(mime.split(';')[0].strip(), 'jpg')
        path = f"{prefix}/{uuid.uuid4().hex}.{ext}"
        up = urllib.request.Request(
            f"{sb_url}/storage/v1/object/{BUCKET}/{path}",
            data=data, method='POST',
            headers={
                'Authorization': f'Bearer {sb_key}',
                'apikey': sb_key,
                'Content-Type': mime,
                'x-upsert': 'true',
                'User-Agent': _UA,
            })
        with urllib.request.urlopen(up, timeout=20) as r:
            if r.status not in (200, 201):
                print(f"[MEDIA] upload status inesperado {r.status}", flush=True)
                return None
        public_url = f"{sb_url}/storage/v1/object/public/{BUCKET}/{path}"
        print(f"[MEDIA] stored {mime} -> {public_url}", flush=True)
        return public_url
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode()[:300]
        except Exception:
            pass
        print(f"[MEDIA] HTTPError {e.code} body={body!r}", flush=True)
        return None
    except Exception as e:
        print(f"[MEDIA] error: {e}", flush=True)
        return None
