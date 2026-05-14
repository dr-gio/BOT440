import os, json, urllib.request
from core.whapi import WhapiClient

KNOWLEDGE = """
440 CLINIC BY DR. GIOVANNI FUENTES
Dirección: Carrera 47 #79-191, Barranquilla
Tel recepción: +57 318 180 0130
Horario: Lunes-Viernes 8am-5pm / Sábados 8am-12pm

SERVICIOS MEDICINA ESTÉTICA:

DEPILACIÓN LÁSER REMOVALL TRIO
- Triple longitud de onda (755/810/1064nm)
- Punta zafiro -9°C — SIN DOLOR
- Todo tipo de piel
- Video: https://youtu.be/_9JcZgSNc8M

PRECIOS x6 sesiones:
• Axilas: $540.000 (1ra sesión: $90.000)
• Bigote: $570.000 (1ra: $95.000)
• Bikini parcial: $900.000 (1ra: $150.000) — SOLO área genital
• Bikini completo: $1.200.000 (1ra: $200.000) — área genital + intraglútea
• Glúteos: $900.000 (1ra: $150.000)
• Abdomen: $900.000 (1ra: $150.000)
• Espalda: $1.152.000 (1ra: $192.000)
• Pecho: $1.200.000 (1ra: $200.000)
• Barba: $1.200.000 (1ra: $200.000)
• Media pierna: $1.080.000 (1ra: $180.000) — tobillo a rodilla
• Pierna completa: $1.560.000 (1ra: $260.000) — tobillo a ingle

CÁMARA HIPERBÁRICA
• Sesión individual: $150.000
• Paquete x5: $700.000
• Duración: 60 minutos
• Tiene pantalla, audio y video

VALORACIONES GRATUITAS 15 min
• Katherine: Martes y Jueves 1pm-5pm
• Roxana: Miércoles y Viernes 1pm-5pm

CIRUGÍAS — NO dar precios, redirigir a wa.me/573044886085
"""

SYSTEM = f"""Eres el asistente virtual de 440 Clinic (canal estética +57 313 544 9024).

{KNOWLEDGE}

PERSONALIDAD:
- Cálida, profesional, empática
- Respuestas cortas (máximo 4 líneas)
- Una pregunta por mensaje
- NUNCA digas que eres IA
- NUNCA inventes precios

FLUJO NATURAL:
1. Saludo → pregunta en qué puedes ayudar
2. Menciona depilación → comparte el video + pregunta nombre y ciudad
3. Menciona hiperbárica → da info + precios
4. Quiere agendar → pide nombre, ciudad, preferencia de día/hora
5. Da datos → confirma y notifica al equipo

CUANDO QUIERAS NOTIFICAR AL EQUIPO agrega al final:
<<<NOTIFY>>>
nombre: [nombre]
telefono: [número o 'por WhatsApp']
servicio: [servicio]
<<<END>>>

REGLAS:
- Si pregunta por cirugía → wa.me/573044886085
- Si es de otra ciudad → puede venir a Barranquilla
- Esteticistas: Katherine Pertuz y Roxana Chegwin
"""

class Brain:
    def __init__(self):
        self.whapi = WhapiClient()
        self.api_key = os.environ.get('ANTHROPIC_API_KEY','')
        self.history = {}

    def process(self, sender_id, sender_name, text, canal='whatsapp'):
        print(f"[BRAIN] {sender_id}: {text[:50]}")
        if sender_id not in self.history:
            self.history[sender_id] = []
        self.history[sender_id].append({"role":"user","content":f"[{sender_name or sender_id}]: {text}"})
        if len(self.history[sender_id]) > 20:
            self.history[sender_id] = self.history[sender_id][-20:]
        response = self._call_claude(self.history[sender_id])
        text_resp, notify = self._parse(response)
        self.history[sender_id].append({"role":"assistant","content":text_resp})
        if text_resp.strip():
            self.whapi.send_text(sender_id, text_resp.strip())
        if notify:
            self._notify_admin(notify, sender_id)

    def _call_claude(self, messages):
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 500,
            "system": SYSTEM,
            "messages": messages
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())["content"][0]["text"]
        except Exception as e:
            print(f"[BRAIN] Claude error: {e}")
            return "Disculpa, tuve un problema técnico. ¿Puedes repetir? 😊"

    def _parse(self, response):
        import re
        notify = None
        match = re.search(r'<<<NOTIFY>>>(.*?)<<<END>>>', response, re.DOTALL)
        if match:
            notify = match.group(1).strip()
            response = re.sub(r'<<<NOTIFY>>>.*?<<<END>>>', '', response, flags=re.DOTALL).strip()
        return response, notify

    def _notify_admin(self, data, sender_id):
        admin = os.environ.get('ADMIN_WHATSAPP','573181800130')
        msg = f"🔔 LEAD ESTÉTICO\n━━━━━━━━━━━━━\n{data}\n📱 Canal: {sender_id}\n━━━━━━━━━━━━━"
        self.whapi.send_text(admin, msg)
