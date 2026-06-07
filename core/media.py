"""Media helper: descarga un archivo entrante de WhApi y lo re-hospeda en
Supabase Storage (bucket público 'conversaciones-media') para tener una URL
permanente (los links de WhApi expiran / a veces ni vienen).

WhApi puede entregar la media de dos formas en el webhook entrante:
  - image.link  → URL directa (no siempre presente)
  - image.id    → hay que pedirla a GET {WHAPI_URL}/media/{id} con Bearer token

Best-effort: ante cualquier fallo devuelve None y el caller sigue con el flujo
normal (placeholder de texto), sin romper el webhook.
"""
import os
import uuid
import urllib.request
import urllib.error

BUCKET = 'conversaciones-media'
_UA = 'Mozilla/5.0 (BOT440 media)'

_EXT_BY_MIME = {
    'image/jpeg': 'jpg', 'image/jpg': 'jpg', 'image/png': 'png',
    'image/webp': 'webp', 'image/gif': 'gif',
}


def _http_get(url, token):
    """GET binario con Bearer token. Devuelve (status, data, content_type)."""
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {token}',
        'User-Agent': _UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read(), r.headers.get('Content-Type', '')
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode()[:200]
        except Exception:
            pass
        print(f"[MEDIA] HTTPError {e.code} body={body!r}", flush=True)
        return e.code, None, ''
    except Exception as e:
        print(f"[MEDIA] GET error: {e}", flush=True)
        return 0, None, ''


def store_whapi_media(image_obj, token, prefix='wa'):
    """Descarga el media de WhApi (por link o por id) y lo sube a Storage.

    Devuelve la URL pública permanente, o None si algo falla.
    """
    if not image_obj:
        return None
    sb_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    sb_key = (os.environ.get('SUPABASE_SERVICE_KEY')
              or os.environ.get('SUPABASE_ANON_KEY', ''))
    if not sb_url or not sb_key:
        print("[MEDIA] sin SUPABASE_URL/KEY", flush=True)
        return None

    _link = image_obj.get('link')
    _id = image_obj.get('id')
    _mime = image_obj.get('mime_type') or 'image/jpeg'
    print(f"[MEDIA] link={_link!r} id={_id!r} mime={_mime!r}", flush=True)

    try:
        # 1) Descargar el binario: link primero, fallback a /media/{id}
        if _link:
            status, data, ctype = _http_get(_link, token)
        elif _id:
            whapi_url = os.environ.get('WHAPI_URL', 'https://gate.whapi.cloud').rstrip('/')
            status, data, ctype = _http_get(f"{whapi_url}/media/{_id}", token)
        else:
            print("[MEDIA] sin link ni id", flush=True)
            return None
        print(f"[MEDIA] descarga status={status} bytes={len(data) if data else 0}", flush=True)
        if status != 200 or not data:
            return None

        # 2) Subir a Supabase Storage
        mime = (_mime or ctype or 'image/jpeg').split(';')[0].strip()
        ext = _EXT_BY_MIME.get(mime, 'jpg')
        path = f"{prefix}/{(_id or uuid.uuid4().hex)}.{ext}"
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
        print(f"[MEDIA] upload HTTPError {e.code} body={body!r}", flush=True)
        return None
    except Exception as e:
        print(f"[MEDIA] error: {e}", flush=True)
        return None
