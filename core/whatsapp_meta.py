"""WhatsApp Cloud API (oficial de Meta) para la línea de atención del bot.

Mismo uso que WhapiClient (send_text, send_image, numero_de_lid) para que BrainCX no cambie.
Variables: WA_META_TOKEN (token del usuario del sistema «medfiles» con whatsapp_business_messaging)
y WA_META_PHONE_ID (identificador del número en WhatsApp Manager). Se activa con WHATSAPP_PROVEEDOR=meta.
Regla de Meta: fuera de las 24 h desde el último mensaje de la persona solo se puede enviar una plantilla.
"""
import os, json, re, urllib.request, urllib.error

GRAPH = 'https://graph.facebook.com/v21.0'


class WhatsAppMetaClient:
    def __init__(self, token=None, phone_id=None):
        self.token = token or os.environ.get('WA_META_TOKEN', '')
        self.phone_id = phone_id or os.environ.get('WA_META_PHONE_ID', '')
        print(f"[WA-META INIT] phone_id={self.phone_id!r} token_len={len(self.token)}", flush=True)

    @staticmethod
    def _destino(to):
        return re.sub(r'\D', '', str(to or '').split('@')[0])

    def send_text(self, to, text):
        return self._post({'to': self._destino(to), 'type': 'text', 'text': {'body': text, 'preview_url': True}})

    def send_image(self, to, url, caption=''):
        img = {'link': url}
        if caption:
            img['caption'] = caption
        return self._post({'to': self._destino(to), 'type': 'image', 'image': img})

    def send_template(self, to, nombre, idioma='es', variables=None):
        """Plantilla aprobada (para escribir primero o fuera de las 24 h). variables = textos del cuerpo en orden."""
        comp = [{'type': 'body', 'parameters': [{'type': 'text', 'text': str(v)} for v in (variables or [])]}] if variables else []
        return self._post({'to': self._destino(to), 'type': 'template',
                           'template': {'name': nombre, 'language': {'code': idioma}, **({'components': comp} if comp else {})}})

    def numero_de_lid(self, lid):
        # La API oficial siempre entrega el número real: no existen los LID (números ocultos)
        return ''

    def _post(self, payload):
        payload = {'messaging_product': 'whatsapp', 'recipient_type': 'individual', **payload}
        url = f'{GRAPH}/{self.phone_id}/messages'
        print(f"[WA-META] POST to={payload.get('to')} type={payload.get('type')}", flush=True)
        try:
            req = urllib.request.Request(url, json.dumps(payload).encode(), {
                'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json',
                'User-Agent': 'BOT440/1.0 (servidor)'}, method='POST')
            with urllib.request.urlopen(req, timeout=15) as r:
                resp = json.loads(r.read() or b'{}')
                mid = ((resp.get('messages') or [{}])[0]).get('id', '')
                print(f"[WA-META] OK id={mid}", flush=True)
                # Misma forma que WHAPI para quien lea la respuesta
                return {'sent': True, 'message': {'id': mid}, **resp}
        except urllib.error.HTTPError as e:
            body = ''
            try: body = e.read().decode()[:400]
            except Exception: pass
            print(f"[WA-META] HTTPError {e.code} body={body!r}", flush=True)
            return {'error': f'HTTP {e.code}', 'body': body}
        except Exception as e:
            print(f'[WA-META] Error: {e}', flush=True)
            return {'error': str(e)}


def media_url_meta(media_id, token=None):
    """URL temporal de descarga de un archivo recibido (Meta pide primero GET /{media_id})."""
    token = token or os.environ.get('WA_META_TOKEN', '')
    try:
        req = urllib.request.Request(f'{GRAPH}/{media_id}', headers={'Authorization': f'Bearer {token}', 'User-Agent': 'BOT440/1.0 (servidor)'})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read() or b'{}').get('url', '')
    except Exception as e:
        print(f"[WA-META] media {media_id}: {e}", flush=True)
        return ''
