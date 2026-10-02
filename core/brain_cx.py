"""BrainCX — bot conversacional de Cirugía Plástica (Centro de Atención del
Dr. Giovanni Fuentes).

Atiende el WhatsApp de cirugías del Dr. Gio (y el Instagram cirugía vía
api/webhook-ig-cx.py). No agenda: orienta con mensajes cortos y, cuando el
paciente deja sus datos y escoge asesoría virtual gratuita o valoración con
el Dr., envía el lead a MedFiles (CRM → Nuevo) y avisa a la asesora.
Guion aprobado: consultorio-app/docs/guion-bot-cirugias.md (2026-09-30).

Env vars esperadas:
  ANTHROPIC_API_KEY
  SUPABASE_URL, SUPABASE_ANON_KEY          (historial conversaciones_440)
  WHAPI_TOKEN     (canal por defecto)  / WHAPI_TOKEN_CX (opcional, canal cirugía)
  WHAPI_URL
  MEDFILES_URL          (default https://medfiles.drgiovannifuentes.com)
  MEDFILES_BOT_CLAVE    (header X-Clave para /api/entrada/bot; sin ella no se
                         envían leads ni se consulta la pausa)
  ASESORA_MEDFILES_TEL  (WhatsApp de la asesora para el aviso de nuevo lead;
                         vacío → sin aviso, MedFiles ya asigna el lead)
  CX_LEGACY_CRM=1       (opcional) re-activa la escritura al CRM viejo
                         (leads_comerciales + push CORE440). Por defecto OFF.
"""
import os, json, re, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime as _dt, timezone as _tz, timedelta as _td
from core.whapi import WhapiClient
from core.instagram import InstagramClient
from core.fichas_cx import FICHAS, expandir_fichas
from core.pasos_cx import decidir_paso, instruccion_paso, aplicar_paso

# Detección de mensajes "solo emojis" (👍😊🙏❤️✅, etc.).
_EMOJI_ONLY_RE_CX = re.compile(
    r'^[\s\.\,\!\?'
    r'⌀-⏿─-➿⬀-⯿'
    r'\U0001F300-\U0001FAFF\U0001F600-\U0001F64F'
    r'\U0001F680-\U0001F6FF\U0001F900-\U0001F9FF'
    r'‍️]+$'
)

def _is_emoji_only_cx(s: str) -> bool:
    if not s: return False
    if not _EMOJI_ONLY_RE_CX.match(s): return False
    return any(ord(c) > 0x2000 for c in s)

_BROWSER_UA = 'Mozilla/5.0 (compatible; BOT440-CX/1.0; +https://440clinic.com)'

# ── MedFiles (nuevo destino de leads) ───────────────────────────────────────
_MEDFILES_DEFAULT_URL = 'https://medfiles.drgiovannifuentes.com'
# CRM viejo (leads_comerciales + push CORE440) — desactivado por defecto.
_LEGACY_CRM = os.environ.get('CX_LEGACY_CRM', '').strip() == '1'
# Palabras clave de la pauta "Mamoplastia de aumento todo incluido".
_PAUTA_MAMO_KW = (
    'todo incluido', 'mamoplastia incluido', 'senos incluido',
    'promo mamoplastia', 'promo senos', '18 millones',
    'mamoplastia de aumento todo', 'paquete mamoplastia',
)
_PAUTA_MAMO_LABEL = 'Mamoplastia todo incluido'


def _sin_tildes(s: str) -> str:
    s = (s or '').lower()
    for a, b in (('á','a'),('é','e'),('í','i'),('ó','o'),('ú','u'),('ü','u'),('ñ','n')):
        s = s.replace(a, b)
    return s

CX_SYSTEM = """Eres el asistente virtual del Dr. Gio (Dr. Giovanni Fuentes),
Cirujano Plástico Estético y Reconstructivo certificado. Atiendes el
Centro de Atención del Dr. Giovanni Fuentes (cirugía plástica).

━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. TU MISIÓN
━━━━━━━━━━━━━━━━━━━━━━━━━━━
ORIENTAR al paciente con mensajes cortos, resolver sus dudas generales
y pasar a TODOS los interesados a nuestra asesora experta (asesoría
virtual gratuita) o a una valoración con el Dr. Gio, según lo que el
paciente ESCOJA. Hay UNA sola asesora comercial.
→ El bot NUNCA agenda citas ni muestra días u horarios. La asesora agenda.
→ El bot NUNCA garantiza ni promete resultados.
→ El bot NO da diagnósticos médicos.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. IDENTIDAD Y ESTILO
━━━━━━━━━━━━━━━━━━━━━━━━━━━
→ Te presentas como "el asistente virtual del Dr. Gio" 🤖.
→ El canal se llama "Centro de Atención del Dr. Giovanni Fuentes".
  NUNCA digas "WhatsApp" para referirte a este canal: di "por aquí".
→ NUNCA menciones "440 Clinic" ni "@440clinic".
→ Hashtag de marca: #LAbelleza440 · La perfecta armonía de tu cuerpo.
→ Mensajes de MÁXIMO 3–4 líneas (excepción: la bienvenida, la primera
  explicación de un procedimiento y el mensaje de opciones). Responde lo
  justo y deja espacio a la asesora.
→ 2–3 emojis por mensaje. Negrita con *asteriscos simples*.
→ Tono cálido, humano, elegante y profesional. Nunca vendedor ni presionas.
→ NUNCA uses apelativos ("amor", "linda", "corazón", "hermosa", "bella",
  "querida", "mi vida", etc.). Usa el nombre si lo tienes; si no, 💙.
→ NO pidas el nombre al inicio: solo al final, cuando pasa a la asesora.
→ Femenino por defecto ("lista", "bienvenida"); si el paciente es hombre
  usa "listo", "bienvenido". Si no sabes, "lista(o)" / "Bienvenida(o)".

━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. BIENVENIDA (primer mensaje de la conversación)
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Si el primer mensaje es un saludo o no menciona un procedimiento, usa
EXACTAMENTE este texto:

"¡Hola! 💙 Bienvenida(o) al *Centro de Atención del Dr. Giovanni Fuentes*.

👨‍⚕️ *Cirujano Plástico Estético y Reconstructivo certificado* · RETHUS CMC2017-222322
🏅 *Miembro de la Sociedad Colombiana de Cirugía Plástica*
⭐ *Más de 10 años de experiencia*

✨ *#LAbelleza440* · _La perfecta armonía de tu cuerpo_ ✨

📍 Operamos en *Barranquilla, Bogotá y Medellín*
🌎 Recibimos pacientes de *otras ciudades y países*
✈️ *Planes de turismo médico todo incluido*

Te está atendiendo *el asistente virtual del Dr. Gio* 🤖. Estoy aquí para orientarte antes de dar el siguiente paso.

Cuéntame, ¿qué procedimiento te interesa o qué te gustaría mejorar? 😊"

Si el PRIMER mensaje YA menciona un procedimiento: la bienvenida la agrega el
sistema; tú da la información del procedimiento (sección 4). Nunca escribas
frases como "Me cuentas que te interesa…".
Si en vez de responder pregunta algo (precio, recuperación…), respóndelo directamente.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. INFORMAR EL PROCEDIMIENTO
━━━━━━━━━━━━━━━━━━━━━━━━━━━
ORIENTAR ANTES DE RECOMENDAR (muy importante — conversa como una asesora, no
como un folleto): si el paciente DESCRIBE lo que le molesta ("tengo barriga",
"grasa en la cintura", "después de mis embarazos", "senos caídos", "flacidez")
o duda entre dos procedimientos, NO mandes ficha todavía. Primero valida lo que
siente en una frase cálida y haz 1 o 2 preguntas cortas para orientarlo:
• Abdomen/barriga (aunque haya dicho "lipo"): "¿Has tenido hijos o has bajado
  mucho de peso? ¿Sientes la piel del abdomen floja, con estrías o que cuelga,
  o es más grasa que se pellizca?"
• Senos: "¿Buscas más volumen, levantarlos, o ambas cosas? ¿Has lactado?"
• Glúteos: "¿Buscas más volumen o mejorar la forma? ¿Tienes grasa en otras zonas?"
Termina SOLO con esa pregunta (sin el bloque del siguiente paso).
Con su respuesta, explica en 2–3 líneas cuál le conviene y POR QUÉ, en su caso
(hijos/piel floja/estrías → abdominoplastia, o lipoabdominoplastia si además hay
grasa; solo grasa con buena piel → lipoescultura 360; volumen → aumento;
caídos → pexia) en 1–2 líneas y en la línea siguiente el marcador de la ficha
(<<<FICHA:clave>>>) — la información del procedimiento SIEMPRE va con la ficha
aprobada, nunca escrita por ti. Menciona AMBOS caminos para definirlo: "En tu
*asesoría virtual gratuita* nuestra asesora experta en cirugía plástica te
orienta según tu caso, y el Dr. Gio lo confirma en tu valoración". Nunca digas
que SOLO el Dr. puede definirlo: la asesora también orienta (gratis).
Si el paciente pide un procedimiento por su nombre sin describir nada, sí va
directo a la ficha.

PRIMERA VEZ que se habla de un procedimiento: NO escribas tú la información.
Responde con una frase corta de bienvenida al tema (opcional, ej. "¡Excelente! 💙")
y en la línea siguiente SOLO el marcador de la ficha, que el sistema reemplaza por
la información aprobada (qué es, para quién es con ✅, combinaciones, recuperación):
<<<FICHA:clave>>>
Claves disponibles: abdominoplastia, lipoabdominoplastia, lipoescultura, lipotransferencia, mamoplastia_aumento, pexia, reduccion, explantacion, ginecomastia, blefaroplastia, papada, otoplastia, abdominoplastia_inversa, mommy_makeover, lifting_extremidades, gluteoplastia_implante, miniabdominoplastia, lifting_facial.
Ej.: "lipo"/"liposucción" → lipoescultura; "cola"/"glúteos con mi grasa" → lipotransferencia;
"senos más grandes" → mamoplastia_aumento; "senos caídos" → pexia.
Si pide dos procedimientos, pon las dos fichas, una debajo de otra.
Si ningún procedimiento coincide, escríbelo tú con el mismo formato: qué es,
"Por lo general es ideal para ti si:" con 3–4 líneas ✅, recuperación y quién lo realiza.
El sistema agrega después la pregunta de dudas y las opciones del siguiente paso.

PROHIBIDO: mencionar tecnologías (VASER, Retraction, etc. — tienen costo
adicional; solo si el paciente pregunta, aclarando que son un complemento con
costo adicional) y prometer resultados ("sin irregularidades", "garantizado",
"perfecto"). Si ya saludaste antes en la conversación, NO vuelvas a saludar.

Si el paciente pregunta por la asesoría o la valoración, explícala y termina
preguntando si la quiere agendar ("¿Te gustaría agendar tu asesoría virtual
gratuita? 😊"). Si dice que sí, pasa a pedir los datos (sección 6).

DESPUÉS: respuestas CORTAS (3–4 líneas), cálidas y conversadas. Responde la
duda y NO escribas tú las opciones del siguiente paso ni "¿alguna otra duda?":
el sistema las agrega.

→ Di SIEMPRE "asesoría virtual gratuita" completo (nunca solo "asesoría").
→ Cuando digas quién define el caso, menciona primero que la *asesora experta en
  cirugía plástica* lo orienta en la *asesoría virtual gratuita* y que el Dr. Gio
  lo confirma en la valoración (no solo "el Dr. Gio te evalúa").
→ Si el paciente describe lo que quiere mejorar sin saber el nombre,
  orienta con preguntas (ver ORIENTAR ANTES DE RECOMENDAR) y luego tradúcelo:
  piel floja/hijos → abdominoplastia; solo grasa localizada → lipoescultura 360; más busto → mamoplastia de
  aumento; senos caídos → pexia mamaria; senos grandes/dolor de espalda →
  mamoplastia de reducción; más cola → lipotransferencia glútea; pecho en
  hombre → ginecomastia; papada → lipo de papada; párpados → blefaroplastia;
  orejas → otoplastia. Si no estás seguro, NO adivines: explica lo más
  probable, pregunta para confirmar o remite a la asesoría virtual gratuita.
→ Procedimiento o técnica que no esté en tu lista: no inventes si el Dr.
  lo hace; explica breve y remite a la asesoría virtual gratuita.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. PRECIO Y FINANCIACIÓN — SOLO SI LO PREGUNTAN
━━━━━━━━━━━━━━━━━━━━━━━━━━━
NUNCA des el precio si no lo preguntan (excepción: pauta Mamoplastia todo
incluido, sección 9). Si lo preguntan, en tono cálido y corto:
"¡Claro, con gusto te cuento! 💙 La [procedimiento] tiene un valor
*desde $X*. Sabemos que es una inversión importante en ti ✨ El valor
exacto depende de tu caso, y todo eso te lo explica nuestra asesora
experta en tu *asesoría virtual gratuita* 💻"
→ Sin detallar qué incluye, sin ofrecer otros procedimientos, sin
  preguntar "¿se ajusta a tu presupuesto?".
→ Si no ha dicho el procedimiento, pregunta cuál le interesa antes de dar
  un valor. NUNCA des un rango genérico.

Valores de referencia (SIEMPRE "desde"):
• Lipoescultura 360: desde $17.000.000
• Abdominoplastia: desde $22.000.000
• Lipoabdominoplastia: desde $25.000.000
• Mamoplastia de aumento: $18.000.000 todo incluido (ver sección 9)
• Pexia mamaria con implantes: desde $18.000.000
• Mamoplastia de reducción: desde $20.000.000
• Explantación mamaria: desde $22.000.000
• Mommy makeover: desde $30.000.000 (según los procedimientos combinados)
• Lipotransferencia glútea: desde $3.000.000 adicionales a la
  lipoescultura o lipoabdominoplastia
• Gluteoplastia con implantes: desde $22.000.000
• Lifting de brazos o piernas: desde $14.000.000
• Lifting facial: desde $25.000.000
• Ginecomastia: desde $4.000.000 (aspiración) / $6.000.000 (con glándula)
• Blefaroplastia: superiores desde $4.500.000 · sup. + inf. desde $7.000.000
• Lipo de papada: desde $2.500.000 (con Retraction desde $3.500.000)
• Otoplastia: desde $7.000.000
• Abdominoplastia inversa: SIN valor de referencia → no des cifra;
  remite a la asesoría virtual gratuita.
Consulta (valoración) con el Dr. Gio: presencial $260.000 · virtual $160.000.
La consulta es independiente del valor de la cirugía.

Financiación: SOLO si preguntan → "Sí, tenemos planes de financiación 💙
nuestra asesora te explica las opciones en tu asesoría virtual gratuita 😊"
Si dice "no me alcanza" / "es mucho": menciona los planes de financiación
y ofrece la asesoría virtual gratuita para conocerlos. Si acepta, sigue el
flujo de la opción 1 (marca financiacion: si en el NOTIFY). Si no quiere,
despedida amable (sección 8) sin pasar a la asesora.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
6. EL SIGUIENTE PASO — EL PACIENTE ESCOGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ofrece las dos opciones cuando: dice que no tiene más dudas, pregunta algo
que no puedes resolver (caso personal o médico, fotos), o pide cita,
asesoría o valoración. NO asumas la opción: que el paciente escoja.

"*¿Cómo te gustaría dar el siguiente paso?* 😊

1️⃣ *Asesoría virtual gratuita* 💻
Con nuestra asesora experta en cirugía plástica, por videollamada, desde donde estés y *sin ningún compromiso*.

2️⃣ *Valoración con el Dr. Gio* 👨‍⚕️
Consulta médica *presencial ($260.000)* o *virtual ($160.000)* para evaluar tu caso.

Respóndeme *1* o *2* 😊"

OPCIÓN 1 — ASESORÍA VIRTUAL GRATUITA. Explica SIEMPRE qué se hace en ella:
"¡Excelente elección! 💙 En tu *asesoría virtual gratuita* nuestra asesora experta:
✅ Resuelve *todas tus dudas* con calma
✅ Te orienta sobre el *procedimiento ideal* para ti
✅ Te explica el *valor*, las *formas de pago* y la *financiación*
✅ Te cuenta cómo sería *tu proceso paso a paso* (y el turismo médico si vienes de otra ciudad)
✅ Te ayuda a *agendar tu valoración* con el Dr. Gio cuando estés lista

¿Estás lista para ser parte de *#LAbelleza440*? ✨
Déjame tus datos y *nuestra asesora te contactará por aquí* para agendar tu asesoría virtual gratuita en el horario que mejor te quede:
👤 Nombre completo
📍 Ciudad
📧 Correo
Y confírmame: ¿te interesa la [procedimiento] o algún otro procedimiento? 😊"

OPCIÓN 2 — VALORACIÓN CON EL DR. GIO:
"¡Perfecto! 💙 En tu *valoración* el Dr. Gio evalúa tu caso personalmente, te indica la técnica ideal, resuelve tus dudas médicas y te entrega tu plan quirúrgico con cotización personalizada 👨‍⚕️
💰 Presencial *$260.000* · Virtual *$160.000*
📍 Presencial en: *Barranquilla* (Carrera 47 #79-191), *Bogotá* (Clínica Intercirugías) o *Medellín* (Clínica AC Quirófanos). La virtual, desde donde estés 💻
Para que nuestra asesora te la agende, déjame:
👤 Nombre completo · 📍 Ciudad · 📧 Correo · ¿*presencial* o *virtual*?"
→ Si pide directamente una valoración o consulta con el Dr., ve directo a
  la opción 2 (no ofrezcas la asesoría gratuita).

DATOS:
→ Nombre completo y ciudad son necesarios. El correo es deseable: si no lo
  da, NO insistas; si está mal escrito, pídelo UNA vez.
→ Si ya dijo el procedimiento, confírmalo y pregunta si le interesa otro.
→ La ciudad es donde VIVE el paciente.
→ Si falta el nombre o la ciudad, pídelo amablemente (una sola pregunta).

━━━━━━━━━━━━━━━━━━━━━━━━━━━
7. CIERRE + <<<NOTIFY>>> (cuando deja los datos)
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cuando ya tienes nombre + ciudad (correo si lo dio) y la opción escogida
(y para valoración, la modalidad si la dijo), responde:

Asesoría:
"¡Listo, [nombre]! 💙 En cuanto nuestra asesora esté disponible, *te contactará por aquí* para agendar tu *asesoría virtual gratuita* 😊
[si NO es de Barranquilla: una línea mencionando nuestros *planes de turismo médico todo incluido* ✈️, que la asesora le explicará]
*Ya eres parte de #LAbelleza440* ✨"

Valoración:
"¡Listo, [nombre]! 💙 En cuanto nuestra asesora esté disponible, *te contactará por aquí* para agendar tu *valoración [presencial/virtual] con el Dr. Gio* 😊
[si NO es de Barranquilla: línea de turismo médico]
*Ya eres parte de #LAbelleza440* ✨"

Y en ESE MISMO mensaje, al final, emite este bloque (el paciente no lo ve):
<<<NOTIFY>>>
nombre: [nombre completo real]
telefono: [número antes del | en el prefijo [57xxx|Nombre] del mensaje; en Instagram, el número de WhatsApp que dio el paciente]
email: [correo, o vacío si no lo dio]
ciudad: [ciudad donde vive]
procedimiento: [procedimiento de interés]
interes: [asesoria | valoracion]
modalidad: [presencial | virtual | vacío]
pauta: [Mamoplastia todo incluido si vino por esa pauta; si no, vacío]
financiacion: [si | no]
<<<END>>>
→ Emite el NOTIFY UNA sola vez por conversación. Si ya lo emitiste (está
  en el historial), NO lo repitas.
→ Si el paciente vuelve a escribir después del cierre:
  "¡Hola, [nombre]! 💙 Nuestra asesora ya tiene tus datos y te escribirá
  muy pronto 😊" y resuelve dudas cortas si las tiene.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
8. SI NO DECIDE CONTINUAR
━━━━━━━━━━━━━━━━━━━━━━━━━━━
("lo voy a pensar", "después", "no por ahora", "no me interesa")
"¡Entiendo perfectamente! 💙 Es una decisión importante y está bien tomarse el tiempo 😊
Mientras tanto, te invito a conocer más del trabajo del Dr. Gio: *resultados reales, testimonios y tips* ✨
📸 Instagram: *@drgiovannifuentes*
🌐 Web: *www.drgio440.com*
Cuando estés lista, escríbenos por aquí y con gusto te acompañamos. Tu *asesoría virtual gratuita* 💻 te estará esperando 🙌
✨ *#LAbelleza440* · _La perfecta armonía de tu cuerpo_ ✨"
⛔ En este caso NO emitas <<<NOTIFY>>>.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
9. PAUTA: MAMOPLASTIA DE AUMENTO TODO INCLUIDO
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Si el paciente llega por "todo incluido", "mamoplastia"+"incluido",
"18 millones", "promo senos": aquí SÍ va el precio de una vez.
*$18.000.000* — incluye: cirugía con el Dr. Gio, clínica certificada,
anestesiólogo, póliza de seguro, implantes Silimed Eurosilicone, brasier
postquirúrgico y 5 drenajes linfáticos. Disponible en Barranquilla,
Bogotá y Medellín, con sede de recuperación en cada ciudad.
→ Es SOLO para aumento (implantes). Pexia o reducción NO entran en el
  paquete: eso lo evalúa el Dr. Gio en la valoración.
→ NO incluye: laboratorios, valoración preanestésica ni la consulta con
  el Dr. Gio.
→ No ofrezcas otros procedimientos; resuelve dudas y sigue al paso 6.
→ En el NOTIFY: pauta: Mamoplastia todo incluido.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
10. TURISMO MÉDICO (solo idea general)
━━━━━━━━━━━━━━━━━━━━━━━━━━━
"¡Claro! 💙 Nuestros *planes de turismo médico todo incluido* te acompañan en tu cirugía y recuperación: *hospedaje* en recovery house u hotel, *alimentación*, *enfermería* y más ✈️
Nuestra *asesora experta* te explica el plan completo en tu *asesoría virtual gratuita* 😊"
No des más detalles (precios, vuelos, días): eso lo da la asesora.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
11. CONOCIMIENTO
━━━━━━━━━━━━━━━━━━━━━━━━━━━
SENOS (datos del Dr.):
• Implantes: marcas *Motiva*, *Silimed* y *Eurosilicone*. Técnica *Motiva Preservé*:
  aumento mínimamente invasivo que preserva los tejidos, incisión pequeña, recuperación más rápida.
  Plano: sobre el músculo (subglandular/subfascial) o detrás (submuscular/dual plane) según el caso.
  Vía: surco submamario o borde de la areola. Perfil, tamaño y volumen según la anatomía.
• Explantación: retira los implantes (y la cápsula si es necesario); el seno se reconstruye con su
  propio tejido, SIN implantes; se complementa con lipotransferencia de grasa y a veces pexia (técnicas
  periareolar, vertical, en L o en T). Muchas consultan por síntomas que asocian a los implantes
  (síndrome de ASIA / enfermedad del implante mamario): el Dr. evalúa si está indicado retirarlos.
  No prometas que los síntomas desaparecerán.
• Pexia y reducción — cicatriz según el caso, buscando la menor posible: periareolar (descensos
  leves), vertical (moderados), en L (sin cicatriz hacia el escote), en T invertida (descensos
  grandes o reducciones de mucho volumen).
EL DR. GIO: Médico Cirujano (Universidad del Norte, 2004), Especialista en
Cirugía Plástica (Universidad de Ciencias Médicas de La Habana, 2016),
más de 10 años de experiencia, miembro de la Sociedad Colombiana de
Cirugía Plástica. Si piden verificar credenciales: ReTHUS en
web.sispro.gov.co → Consulta pública de Talento Humano en Salud →
Cédula 72.248.179 (Giovanni Fuentes).
Tecnologías: la lipoescultura 360 se realiza con tecnología. *Argón Plasma* es la que
más usa el Dr. (retracción de la piel); también J Plasma, VASER y MicroAire. Retraction
la usa poco, en casos puntuales. La combinación ideal la define el Dr. en la valoración.
El valor de la tecnología lo explica la asesora (no des precios de tecnologías).

CLÍNICAS DONDE OPERA (solo si preguntan):
• Barranquilla: Clínica del Caribe, Clínica Diamante, Doral Medical, Iberoamericana
• Bogotá: Centro Colombiano de Cirugía Plástica, Clínica Riviere
• Medellín: AC Quirófanos, Quirófanos 2 Sur
"En todas las ciudades contamos con sedes de recuperación."

CONSULTA PRESENCIAL (dónde): Barranquilla: Carrera 47 #79-191 (solo la
dirección) · Bogotá: Clínica Intercirugías · Medellín: Clínica AC
Quirófanos. Ofrece siempre también la opción virtual.

PROCEDIMIENTOS (guía para explicar; recuperaciones aproximadas):
• Lipoescultura 360: retira grasa localizada de abdomen, cintura, espalda y
  flancos para definir la silueta. Para quien está cerca de su peso y tiene
  grasa que no sale con dieta ni ejercicio. Actividades livianas en 1–2
  semanas con faja y drenajes. Resultados naturales, sin irregularidades.
• Abdominoplastia: retira el exceso de piel y grasa del abdomen y repara la
  pared muscular. Ideal después de embarazos o pérdida de peso. Actividades
  livianas en 2–3 semanas.
• Lipoabdominoplastia: abdominoplastia + lipoescultura en una cirugía.
• Abdominoplastia inversa: SÍ la realiza; trata la flacidez del abdomen
  superior (por encima del ombligo).
• Mamoplastia de aumento: implantes para dar volumen y proyección.
  Actividades livianas en 1–2 semanas.
• Pexia mamaria: levanta los senos caídos (embarazos, lactancia, pérdida de
  peso); puede llevar implantes.
• Mamoplastia de reducción: reduce senos grandes que causan dolor de espalda
  o incomodidad.
• Explantación: retiro de implantes mamarios (con o sin pexia).
• Mommy makeover: combina abdominoplastia, cirugía mamaria y lipoescultura
  (y BBL si se desea). No es solo para mamás: para cualquier mujer con
  cambios por embarazos o pérdida de peso; ideal con peso estable.
• Lipotransferencia glútea (BBL): usa tu propia grasa de la lipo para dar
  volumen y forma a los glúteos.
• Gluteoplastia con implantes, lifting de brazos/piernas, lifting facial.
• Procedimientos menores (ambulatorios, ~1 hora, anestesia local, se va a
  casa el mismo día, recuperación ~1 semana): ginecomastia, blefaroplastia,
  lipo de papada (incluye mentonera), otoplastia (incluye balaca; desde los
  5 años).

NO REALIZA: rinoplastia ni bichectomía → "Ese procedimiento no lo realiza
el Dr. Gio; te recomendamos un colega especialista 💙".

━━━━━━━━━━━━━━━━━━━━━━━━━━━
12. URGENCIAS (pacientes operados)
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Si menciona sangrado, fiebre, dolor fuerte, infección, complicación:
"¡Esto es prioridad! 🚨 Comunícate AHORA con nosotros:
📱 +57 318 180 0130
📱 +57 318 175 4178
📱 +57 318 009 2083
Alguien del equipo te atenderá de inmediato 🙏"
y emite:
<<<NOTIFY>>>
nombre: [nombre si lo sabes]
telefono: [número del prefijo]
interes: urgencia
mensaje: [descripción corta]
<<<END>>>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
13. ABUSO / SPAM
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Si el mensaje contiene groserías o insultos, es sexualmente explícito, es
spam, es agresivo o amenazante, o son preguntas irrelevantes repetidas
(clima, política, chistes, programación…), responde ÚNICAMENTE:
<<<BLOQUEAR>>>
NO bloquees por: saludos cortos, una primera pregunta rara o ambigua,
mensajes en otro idioma que parezcan genuinos, preguntas básicas sobre el
Dr. o sus servicios, confusión sobre cómo funciona el chat.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS FINALES
━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Mensajes cortos, una pregunta por mensaje.
✅ "asesoría virtual gratuita" siempre completo.
✅ El paciente escoge entre asesoría y valoración.
✅ NOTIFY una sola vez, con datos reales (nunca "no especificado").
❌ No digas que eres una IA más allá de "asistente virtual del Dr. Gio".
❌ No digas "WhatsApp" ni "440 Clinic".
❌ No agendes ni muestres horarios. No garantices resultados.
❌ No des precio si no lo preguntan (salvo la pauta todo incluido).
"""

# ---------------------------------------------------------------------------
# Herramientas (Anthropic tool use)
# ---------------------------------------------------------------------------
# DESACTIVADAS: el bot ya no agenda (la asesora agenda desde MedFiles).
# Se conservan las definiciones legacy solo como referencia; a Claude se le
# envía TOOLS_CX = [] (sin herramientas).
_TOOLS_CX_LEGACY = [
    {
        "name": "check_slots_cx",
        "description": (
            "Consulta los slots disponibles para prediagnóstico. La asesora la asigna el sistema automáticamente. "
            "NO incluir asesora — el sistema de rotación la determina. "
            "Llamar cuando el paciente confirma que quiere agendar el prediagnóstico."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "preferencia": {
                    "type": "string",
                    "description": "Siempre usar 'proximo'"
                },
                "sender_id": {
                    "type": "string",
                    "description": "ID del remitente del mensaje"
                },
                "dia": {
                    "type": "string",
                    "description": "Día elegido por el paciente (ej. 'lunes 18 may'). Omitir en el primer llamado. Incluir en PASO C y D."
                },
                "jornada": {
                    "type": "string",
                    "description": "Jornada elegida: 'mañana' o 'tarde'. Omitir en PASO B y C. Incluir solo en PASO D."
                }
            },
            "required": ["preferencia", "sender_id"]
        }
    },
    {
        "name": "create_event_cx",
        "description": (
            "Crea el evento de prediagnóstico cuando el paciente elige un slot. "
            "Pasar el slot_id exacto devuelto por check_slots_cx, junto con iso_start e iso_end del slot elegido."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "asesora": {
                    "type": "string",
                    "description": "Slug de la asesora: bibiana, brian, o lucero"
                },
                "slot_id": {
                    "type": "string",
                    "description": "ID del slot elegido, tal como lo devolvió check_slots_cx"
                },
                "slot_label": {
                    "type": "string",
                    "description": "Etiqueta legible del slot (ej. 'Lunes 19 May 10:00 AM')"
                },
                "iso_start": {
                    "type": "string",
                    "description": "Fecha/hora inicio del slot en ISO 8601 con offset Bogotá (ej. '2026-05-18T08:00:00-05:00'). Extraer del slot elegido en <<<SLOTS>>>."
                },
                "iso_end": {
                    "type": "string",
                    "description": "Fecha/hora fin del slot en ISO 8601 con offset Bogotá (ej. '2026-05-18T08:30:00-05:00'). Extraer del slot elegido en <<<SLOTS>>>."
                },
                "sender_id": {
                    "type": "string",
                    "description": "ID del remitente"
                },
                "sender_name": {
                    "type": "string",
                    "description": "Nombre del paciente"
                },
                "correo_paciente": {
                    "type": "string",
                    "description": "Correo electrónico del paciente para enviar confirmación. Opcional."
                }
            },
            "required": ["asesora", "slot_id", "iso_start", "iso_end", "sender_id"]
        }
    }
]

TOOLS_CX = []

# Rotación de asesoras (LEGACY — ya no se usa en el flujo nuevo: hay una sola
# asesora y MedFiles asigna el lead). Se conserva para el modo CX_LEGACY_CRM.
ASESORAS = ['bibiana', 'vanessa', 'lucero']  # Angelica dada de baja.
ASESORA_ENV = {
    'bibiana':  'ASESORA_1',
    'lucero':   'ASESORA_3',
    'angelica': 'ASESORA_4',
    'vanessa':  'ASESORA_5',
}
ASESORA_LABEL = {
    'bibiana':  'Bibiana',
    'lucero':   'Lucero',
    'angelica': 'Angélica',
    'vanessa':  'Vanessa',
}


# ── Ajustes fijos sobre la respuesta de la IA (el guion aprobado no depende de que la IA lo recuerde) ──
BLOQUE_SIGUIENTE_PASO = (
    "Tu siguiente paso puede ser:\n\n"
    "✅ *Asesoría virtual gratuita* 💻\n"
    "Con nuestra asesora experta, por videollamada y sin compromiso. *Ampliamos la información* y resolvemos todas tus dudas.\n\n"
    "✅ *Valoración con el Dr. Gio* 👨‍⚕️\n"
    "Presencial *$260.000* · Virtual *$160.000*. El Dr. *evalúa tu caso* personalmente."
)
# Bienvenida completa (primer contacto). Texto fijo aprobado por el Dr.
BIENVENIDA_CABEZA = (
    "¡Hola! 💙 Bienvenida(o) al *Centro de Atención del Dr. Giovanni Fuentes*.\n\n"
    "👨‍⚕️ *Cirujano Plástico Estético y Reconstructivo certificado* · RETHUS CMC2017-222322\n"
    "🏅 *Miembro de la Sociedad Colombiana de Cirugía Plástica*\n"
    "⭐ *Más de 10 años de experiencia*\n\n"
    "✨ *#LAbelleza440* · _La perfecta armonía de tu cuerpo_ ✨\n\n"
    "📍 Operamos en *Barranquilla, Bogotá y Medellín*\n"
    "🌎 Recibimos pacientes de *otras ciudades y países*\n"
    "✈️ *Planes de turismo médico todo incluido*\n\n"
    "Te está atendiendo *el asistente virtual del Dr. Gio* 🤖. Estoy aquí para orientarte antes de dar el siguiente paso."
)
CIERRE_DUDAS = ("¿Tienes alguna otra *pregunta o duda* que te pueda resolver antes de dar el siguiente paso? 😊\n\n"
                + BLOQUE_SIGUIENTE_PASO)
BIENVENIDA_PREGUNTA = "Cuéntame, ¿qué procedimiento te interesa o qué te gustaría mejorar? 😊"
# Separa la respuesta en dos mensajes de WhatsApp (bienvenida / información) para que no quede un bloque enorme
PARTE = "\n\n<<<PARTE>>>\n\n"

_RE_TECNO = re.compile(r'\b(vaser|micro\s?aire|retraction|j\s?plasma|arg[oó]n)\b', re.I)
_RE_PROMESA = re.compile(r'[,;]?\s*(con (excelentes|los mejores) resultados|sin (dejar )?irregularidades|de forma natural y sin [^.,\n]*|resultados? garantizad[oa]s?|garantizad[oa]s?|te garantizamos[^.!\n]*)', re.I)


def ajustar_respuesta_cx(texto, history, mensaje_paciente):
    """Aplica las reglas del guion que no deben depender de la IA:
    - no repetir la bienvenida si ya hubo conversación;
    - no prometer resultados;
    - no mencionar tecnologías (con costo adicional) si el paciente no preguntó por ellas;
    - agregar el bloque aprobado del siguiente paso la primera vez que se invita a resolver dudas."""
    if not texto:
        return texto
    # Fichas fijas de procedimientos (formato ✅ aprobado)
    if '<<<FICHA:' in texto:
        # Saludo corto de la IA (si lo hay) + fichas en orden + la pregunta aprobada; lo demás que escriba la IA se descarta
        intro = texto.split('<<<FICHA:', 1)[0].strip()
        intro = intro if len(intro) <= 350 else ''
        intro = re.sub(r'[:,]?\s*(te cuento|aqu[ií] (va|tienes)|esta es)[^.!\n]*[:.]?\s*$', '', intro, flags=re.I).strip()
        fichas = [m.group(0) for m in re.finditer(r'<<<FICHA:[a-z_]+>>>', texto)]
        cuerpo, hubo_ficha = expandir_fichas('\n\n'.join(fichas))
        if hubo_ficha:
            texto = ((intro + '\n\n') if intro else '') + cuerpo + \
                '\n\n¿Tienes alguna *pregunta o duda* que te pueda resolver antes de dar el siguiente paso? 😊'
        else:
            texto = re.sub(r'<<<FICHA:[a-z_]+>>>', '', texto)
    hubo_bot = any(m.get('role') == 'assistant' for m in (history or []))
    previos = '\n'.join(m.get('content', '') for m in (history or []) if m.get('role') == 'assistant')
    lineas = texto.split('\n')
    # Quita el saludo/bienvenida que haya escrito la IA (la bienvenida la pone el código)
    # Solo líneas con el formato de la bienvenida (con su emoji); si el paciente PREGUNTA por turismo,
    # dónde operamos o la experiencia del Dr., la respuesta no se borra.
    _RE_SALUDO = (r'(bienvenid|centro de atenci[oó]n|te atiende el asistente|te est[aá] atendiendo|'
                  r'^\s*👨‍⚕️\s*\*?cirujano|^\s*🏅|^\s*⭐\s*\*?m[aá]s de|^\s*✨\s*\*?#labelleza440|'
                  r'^\s*📍\s*operamos en|^\s*🌎|^\s*✈️\s*\*?planes de turismo|^\s*¡?hola!?\s*💙?\s*$)')
    while lineas and (not lineas[0].strip() or re.search(_RE_SALUDO, lineas[0], re.I)):
        lineas.pop(0)
    texto = '\n'.join(lineas)
    texto = re.sub(r'^\s*[-—_*]{3,}\s*$', '', texto, flags=re.M)   # separadores tipo "---"
    texto = re.sub(r'\*\*([^*\n]+)\*\*', r'*\1*', texto)   # negrita de WhatsApp es *texto*, no **texto**
    texto = _RE_PROMESA.sub('', texto)
    texto = re.sub(r'\bes (perfect[ao]|lo mejor) para ti\b', 'puede ser una excelente opción', texto, flags=re.I)
    if not _RE_TECNO.search(mensaje_paciente or ''):
        # Elimina las frases que mencionan tecnologías si el paciente no preguntó por ellas
        # (línea por línea; las líneas 🔬 de las fichas aprobadas se respetan)
        nuevas = []
        for linea in texto.split('\n'):
            if '🔬' in linea or not _RE_TECNO.search(linea):
                nuevas.append(linea)
                continue
            frases = [f for f in re.split(r'(?<=[.!?])\s+', linea) if not _RE_TECNO.search(f)]
            if frases:
                nuevas.append(' '.join(frases))
        texto = '\n'.join(nuevas)
    if ('pregunta o duda' in texto and 'Tu siguiente paso puede ser' not in texto
            and 'Tu siguiente paso puede ser' not in previos):
        texto = texto.rstrip() + '\n\n' + BLOQUE_SIGUIENTE_PASO
    # Explicó la asesoría → cerrar invitando a agendarla (no con "¿alguna otra duda?")
    if re.search(r'asesor[ií]a virtual gratuita', texto, re.I) and re.search(r'resuelve.*todas tus dudas', texto, re.I | re.S) \
            and 'Tu siguiente paso puede ser' not in texto:
        texto = re.sub(r'\n*¿(alguna|tienes alguna) otra duda\?\s*😊?\s*$', '', texto.rstrip(), flags=re.I)
        if not re.search(r'te gustar[ií]a agendar', texto, re.I):
            texto += '\n\n¿Te gustaría agendar tu *asesoría virtual gratuita*? 😊'
        texto = re.sub(r'(te gustar[ií]a agendar[^?\n]*\?)\s*🤖', r'\1 😊', texto, flags=re.I)
    # El paciente pide directamente la valoración/consulta o la asesoría → directo al pedido de datos, sin más preguntas
    _msg = mensaje_paciente or ''
    _es_pregunta = '?' in _msg or re.search(r'\b(cu[aá]nto|precio|valor|qu[eé] es|c[oó]mo es|incluye)\b', _msg, re.I)
    if hubo_bot and not _es_pregunta and '<<<NOTIFY' not in texto and not re.search(r'nombre completo', texto, re.I):
        if re.search(r'\b(valoraci[oó]n|consulta(r)? (con|del|para)|cita con (el )?(dr|doctor))', _msg, re.I):
            texto = 'valoración · nombre completo · ciudad'
        elif re.search(r'asesor[ií]a', _msg, re.I):
            texto = 'asesoría virtual · nombre completo · ciudad'
    # Pedido de datos: texto fijo aprobado (#LAbelleza440 + "nuestra asesora te contactará" + correo sin "opcional")
    if re.search(r'nombre completo', texto, re.I) and re.search(r'ciudad', texto, re.I) and '<<<NOTIFY' not in texto:
        valoracion = bool(re.search(r'valoraci[oó]n', texto, re.I)) and not re.search(r'asesor[ií]a virtual', texto, re.I)
        dicho = ' '.join([m.get('content', '') for m in (history or []) if m.get('role') == 'user'] + [mensaje_paciente or ''])
        modalidad = 'virtual' if re.search(r'\bvirtual\b', dicho, re.I) else 'presencial' if re.search(r'\bpresencial\b', dicho, re.I) else ''
        listo = 'listo' if re.search(r'\b(listo para|el pr[oó]ximo|bienvenido)\b', texto, re.I) else 'lista'
        explica = ''
        if not valoracion:
            explica = ("En tu *asesoría virtual gratuita* 💻, nuestra *asesora experta en cirugía plástica* te atiende por videollamada, "
                       "desde donde estés y *sin ningún compromiso*:\n"
                       "✅ Resuelve *todas tus dudas* con calma\n"
                       "✅ Te orienta sobre el *procedimiento ideal* para ti\n"
                       "✅ Te explica el *valor*, las *formas de pago* y la *financiación*\n"
                       "✅ Te cuenta cómo sería *tu proceso paso a paso*\n"
                       "✅ Te ayuda a *agendar tu valoración* con el Dr. Gio cuando estés lista\n\n")
        else:
            explica = ("En tu *valoración con el Dr. Gio* 👨‍⚕️, el Dr. *evalúa tu caso personalmente*:\n"
                       "✅ Revisa tu cuerpo y tus expectativas\n"
                       "✅ Te indica la *técnica ideal* para ti\n"
                       "✅ Resuelve *todas tus dudas médicas*\n"
                       "✅ Te entrega tu *plan quirúrgico y cotización* personalizada\n\n"
                       "💰 *Presencial:* $260.000 · 💻 *Virtual:* $160.000\n"
                       "📍 *Consulta presencial:* Barranquilla (Carrera 47 #79-191) · Bogotá (Clínica Intercirugías) · Medellín (Clínica AC Quirófanos)\n\n")
        texto = (("¡Excelente decisión! 💙\n\n" + explica) if explica else "¡Listo! 💙 ") + (f"*¿Estás {listo} para ser parte de #LAbelleza440?* ✨\n\n"
                 "Déjame estos datos y *nuestra asesora te contactará por aquí* para agendar tu "
                 + ((f"*valoración {modalidad} con el Dr. Gio*" if modalidad else "*valoración con el Dr. Gio*") if valoracion else "*asesoría virtual gratuita*") + ":\n"
                 "👤 *Nombre completo*\n📍 *Ciudad*\n📧 *Correo electrónico*"
                 + "\n✨ *Procedimiento de interés*"
                 + ("\n💻 ¿La prefieres *presencial* o *virtual*?" if valoracion and not modalidad else ""))
    # Si la IA escribió sus propias opciones o su propio cierre, se quitan: el bloque aprobado va una sola vez
    if re.search(r'asesor[ií]a virtual gratuita.*valoraci[oó]n con el dr', texto, re.I | re.S) \
            and not re.search(r'nombre completo|<<<NOTIFY|drgio440\.com', texto, re.I):
        lineas_o = texto.split('\n')
        corte = next((i for i, l in enumerate(lineas_o) if re.search(
            r'(1️⃣|✅\s*\*?asesor[ií]a|siguiente paso|resp[oó]ndeme|alguna otra \*?(pregunta|duda))', l, re.I)), None)
        if corte is not None and corte > 0:
            texto = '\n'.join(lineas_o[:corte]).rstrip()
    # El paciente ya escogió (pide asesoría/valoración/agendar) o la IA le está preguntando presencial o virtual:
    # no se le vuelven a ofrecer las opciones
    _preg = '?' in (mensaje_paciente or '') or re.search(r'\b(cu[aá]nto|precio|valor|qu[eé] es|c[oó]mo es|incluye)\b', mensaje_paciente or '', re.I)
    ya_escogio = bool(not _preg and re.search(r'\b(valoraci[oó]n|asesor[ií]a|consulta|agendar|cita)\b', mensaje_paciente or '', re.I)) or \
        bool(re.search(r'presencial[^?\n]{0,60}virtual[^?\n]{0,20}\?', texto, re.I))
    # Quién define el caso: la asesora orienta (gratis) y el Dr. confirma — nunca solo "el Dr. te evalúa"
    if not re.search(r'nombre completo|<<<NOTIFY', texto, re.I) and not re.search(r'asesor[ií]a virtual gratuita[^\n]*orienta|asesora[^\n]*orienta', texto, re.I):
        texto = re.sub(r'[^.!\n]*\b(el )?dr\.? gio\b[^.!\n]*\b(defin|eval[uú]|confirm|determin|indic)\w*[^.!\n]*valoraci[oó]n[^.!\n]*[.!]?(\s*👨‍⚕️)?',
                       ' En tu *asesoría virtual gratuita* nuestra *asesora experta en cirugía plástica* te orienta según tu caso, y el Dr. Gio lo confirma en tu valoración 👨‍⚕️',
                       texto, count=1, flags=re.I).replace('  ', ' ')
    forzar_cierre = False
    _lt = texto.rstrip().split('\n')
    while _lt and not _lt[-1].strip():
        _lt.pop()
    if _lt and '?' in _lt[-1] and re.search(r'asesor', _lt[-1], re.I) and re.search(r'valoraci|dr\.? gio', _lt[-1], re.I):
        _lt.pop()
        texto = '\n'.join(_lt).rstrip()
        forzar_cierre = True
    ultima = next((l for l in reversed(texto.strip().split('\n')) if l.strip()), '')
    orientando = '?' in ultima and not re.search(r'(duda|otra \*?pregunta|siguiente paso|agendar|te cuento)', ultima, re.I)
    # Respuesta a una duda: siempre cierra preguntando por más dudas y nombrando el siguiente paso
    if hubo_bot and not ya_escogio and (forzar_cierre or not orientando) and not re.search(r'(Tu siguiente paso puede ser|nombre completo|te gustar[ií]a agendar|ya eres parte|drgio440\.com|'
                                  r'<<<NOTIFY|me cuentas que te interesa|asesora ya tiene tus datos|urgencias|l[ií]nea de emergencia)', texto, re.I):
        lineas_t = texto.rstrip().split('\n')
        while lineas_t and (not lineas_t[-1].strip() or re.search(r'\?\s*\S{0,3}\s*$', lineas_t[-1])
                            and re.search(r'(duda|pregunta|algo m[aá]s|ayudar|siguiente paso)', lineas_t[-1], re.I)):
            lineas_t.pop()
        texto = '\n'.join(lineas_t).rstrip() + '\n\n' + CIERRE_DUDAS
    if not hubo_bot:
        # Primer contacto: bienvenida completa siempre. Si la IA solo preguntaba qué le interesa, va la pregunta aprobada.
        resto = re.sub(r'^.*(qu[eé] procedimiento te interesa|qu[eé] te gustar[ií]a mejorar).*$', '', texto, flags=re.I | re.M).strip()
        # Si ya dijo el procedimiento, la IA solo confirma ("Me cuentas que te interesa… ¿Te cuento cómo es…?");
        # la información llega en el siguiente mensaje, cuando responda.
        proc = None
        if len(resto) > 40:
            m = re.search(r'\*([^*\n]{4,60})\*', resto)   # primer término en negrita = el procedimiento
            proc = m.group(1).strip() if m and not re.search(r'pregunta|duda|asesor|valoraci|dr\.? gio', m.group(1), re.I) else None
        if proc:
            texto = (BIENVENIDA_CABEZA + '\n\n'
                     f"Me cuentas que te interesa la *{proc}* 😊 ¿Te cuento cómo es y qué opciones tienes para dar el siguiente paso?")
        else:
            texto = BIENVENIDA_CABEZA + '\n\n' + (resto if len(resto) > 20 else BIENVENIDA_PREGUNTA)
    return re.sub(r'\n{3,}(?!<<<PARTE)', '\n\n', texto).strip()


class BrainCX:
    def __init__(self):
        # WhApi: usa WHAPI_TOKEN_CX si está seteado, si no cae en WHAPI_TOKEN.
        self.whapi = WhapiClient(
            token=os.environ.get('WHAPI_TOKEN_CX', os.environ.get('WHAPI_TOKEN', ''))
        )
        # InstagramClient — token se elige según cuenta_receptora en process().
        # Precargamos los tokens disponibles aquí.
        self._ig_tokens = {
            'drgiovannifuentes': (
                os.environ.get('IG_CX_PAGE_ACCESS_TOKEN', '').strip()
                or os.environ.get('IG_PAGE_ACCESS_TOKEN', '')
            ),
            'drgio440': (
                os.environ.get('IG_DRGIO440_TOKEN', '').strip()
                or os.environ.get('IG_CX_PAGE_ACCESS_TOKEN', '').strip()
            ),
        }
        self._ig_accounts = {
            'drgiovannifuentes': os.environ.get('IG_CX_ACCOUNT_ID', '17841400339315123').strip(),
            'drgio440': os.environ.get('DRGIO440_IG_ACCOUNT_ID', '17841476035768675').strip(),
        }
        # Default: @drgiovannifuentes (se sobreescribe en process() según cuenta_receptora)
        ig_cx_token = self._ig_tokens['drgiovannifuentes']
        ig_cx_account = self._ig_accounts['drgiovannifuentes']
        self.instagram = InstagramClient(
            token=ig_cx_token,
            account_id=ig_cx_account,
        )
        self._cuenta_receptora_activa = 'drgiovannifuentes'
        cx_token = os.environ.get('WHAPI_TOKEN_CX', '').strip()  # solo para el log
        self.api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        self.sb_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
        self.sb_key = os.environ.get('SUPABASE_ANON_KEY', '')
        self.history_limit = 30
        print(f"[CX INIT] sb_url={self.sb_url!r} sb_key_len={len(self.sb_key)} "
              f"anth_key_len={len(self.api_key)} cx_token={'custom' if cx_token else 'default'}", flush=True)

    # ------------------------------------------------------------------
    # Supabase helpers
    # ------------------------------------------------------------------
    def _sb_headers(self):
        return {
            'apikey': self.sb_key,
            'Authorization': f'Bearer {self.sb_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': _BROWSER_UA,
        }

    def _check_paciente_recurrente(self, sender_id):
        if not self.sb_url or not self.sb_key or not sender_id:
            return None
        try:
            params = (f'telefono=eq.{urllib.parse.quote(sender_id)}'
                      f'&select=nombre,email,servicios_interes,ultimo_contacto'
                      f'&limit=1')
            url = f'{self.sb_url}/rest/v1/pacientes_440?{params}'
            req = urllib.request.Request(url, headers=self._sb_headers(), method='GET')
            with urllib.request.urlopen(req, timeout=8) as r:
                rows = json.loads(r.read())
            return rows[0] if rows else None
        except Exception as e:
            print(f"[CX] check_paciente error: {e}", flush=True)
            return None

    def _check_lead_crm(self, sender_id):
        """Lee leads_comerciales buscando asesora_asignada y datos básicos
        del paciente. service_role bypassea RLS."""
        import urllib.request, urllib.parse as _up, json as _json
        crm_url = os.environ.get('SUPABASE_URL_CRM', '').rstrip('/')
        crm_key = os.environ.get('SUPABASE_KEY_CRM', '')
        if not crm_url or not crm_key or not sender_id:
            return None
        try:
            tel = _up.quote(str(sender_id))
            url = (f"{crm_url}/rest/v1/leads_comerciales?telefono=eq.{tel}"
                   f"&select=nombre,asesora_asignada,procedimiento_interes,etapa,bot_pausado"
                   f"&limit=1")
            req = urllib.request.Request(url, headers={
                'apikey': crm_key, 'Authorization': f'Bearer {crm_key}'},
                method='GET')
            with urllib.request.urlopen(req, timeout=5) as r:
                rows = _json.loads(r.read())
            return rows[0] if rows else None
        except Exception as e:
            print(f"[CX] check_lead_crm err: {e}", flush=True)
            return None

    def _already_notified_cx(self, sender_id, canal, hours=24):
        """True si ya hay un saliente con <<<NOTIFY>>> para este sender en
        las últimas N horas."""
        if not self.sb_url or not self.sb_key or not sender_id:
            return False
        try:
            since = (_dt.now(_tz.utc) - _td(hours=hours)).isoformat()
            params = (f'contacto_telefono=eq.{urllib.parse.quote(sender_id)}'
                      f'&canal=eq.{urllib.parse.quote(canal)}'
                      f'&direccion=eq.saliente'
                      f'&mensaje=ilike.*NOTIFY*'
                      f'&mensaje=not.ilike.*urgencia*'
                      f'&created_at=gte.{urllib.parse.quote(since)}'
                      f'&select=created_at&limit=1')
            url = f'{self.sb_url}/rest/v1/conversaciones_440?{params}'
            req = urllib.request.Request(url, headers=self._sb_headers(), method='GET')
            with urllib.request.urlopen(req, timeout=5) as r:
                rows = json.loads(r.read())
            return bool(rows)
        except Exception as e:
            print(f"[CX] already_notified err: {e}", flush=True)
            return False

    @staticmethod
    def _extract_name_from_turn(history, text):
        """Si el último msg del bot pidió el nombre y `text` parece un
        nombre real (≥2 letras, sin emojis ni dígitos ni @), devuelve
        el nombre limpio. Si no, None."""
        last_bot = ''
        for m in reversed(history):
            if m.get('role') == 'assistant':
                last_bot = (m.get('content') or '').lower()
                break
        asked = ('nombre' in last_bot and
                 ('?' in last_bot or 'cuál' in last_bot or 'cual' in last_bot
                  or 'cómo te llamas' in last_bot or 'como te llamas' in last_bot))
        if not asked:
            return None
        cand = (text or '').strip().strip('.,!?¿¡')
        if not cand or len(cand) > 60:
            return None
        if '@' in cand or any(ch.isdigit() for ch in cand):
            return None
        letters = sum(1 for ch in cand if ch.isalpha())
        if letters < 2:
            return None
        return cand[:60].title()

    @staticmethod
    def _safe_sender_name(sender_name):
        """sender_name (WhatsApp profile) solo es válido como nombre si
        tiene ≥2 letras. Si es emoji o tel, devolver None."""
        if not sender_name:
            return None
        letters = sum(1 for ch in sender_name if ch.isalpha())
        return sender_name if letters >= 2 else None

    def _upsert_paciente(self, sender_id, nombre=None, email=None,
                         canal=None, servicio=None, sexo=None):
        if not self.sb_url or not self.sb_key or not sender_id:
            return
        try:
            body = {
                'telefono': sender_id,
                'ultimo_contacto': _dt.now(_tz.utc).isoformat(),
            }
            if nombre:
                body['nombre'] = nombre
            if email:
                body['email'] = email
            if sexo:
                body['sexo'] = sexo
            if canal:
                body['canal'] = canal
            if servicio:
                body['servicios_interes'] = [servicio]
            url = f'{self.sb_url}/rest/v1/pacientes_440?on_conflict=telefono'
            headers = self._sb_headers()
            headers['Prefer'] = 'resolution=merge-duplicates,return=minimal'
            data = json.dumps(body).encode()
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=8) as r:
                print(f"[CX] upsert_paciente OK status={r.status}", flush=True)
        except Exception as e:
            print(f"[CX] upsert_paciente error: {e}", flush=True)

    # ------------------------------------------------------------------
    # Bloqueo por spam / contenido inapropiado (pacientes_440)
    # ------------------------------------------------------------------
    def _check_bloqueado(self, sender_id):
        """True si bot_bloqueado=true y bloqueado_hasta > NOW(). Si el
        bloqueo expiró, lo limpia y devuelve False. Fail-open en error."""
        if not self.sb_url or not self.sb_key or not sender_id:
            return False
        try:
            params = (f'telefono=eq.{urllib.parse.quote(sender_id)}'
                      f'&select=bot_bloqueado,bloqueado_hasta&limit=1')
            url = f'{self.sb_url}/rest/v1/pacientes_440?{params}'
            req = urllib.request.Request(url, headers=self._sb_headers(), method='GET')
            with urllib.request.urlopen(req, timeout=5) as r:
                rows = json.loads(r.read())
            if not rows or not rows[0].get('bot_bloqueado'):
                return False
            hasta_raw = rows[0].get('bloqueado_hasta')
            if not hasta_raw:
                return True
            hasta = _dt.fromisoformat(hasta_raw.replace('Z', '+00:00'))
            if hasta.tzinfo is None:
                hasta = hasta.replace(tzinfo=_tz.utc)
            if hasta > _dt.now(_tz.utc):
                return True
            self._set_bloqueado(sender_id, razon=None, bloquear=False)
            print(f"[CX] bloqueo expirado para {sender_id} — desbloqueado", flush=True)
            return False
        except Exception as e:
            print(f"[CX] check_bloqueado error: {e}", flush=True)
            return False

    def _set_bloqueado(self, sender_id, razon=None, hours=24, bloquear=True):
        if not self.sb_url or not self.sb_key or not sender_id:
            return
        try:
            body = {'telefono': sender_id}
            if bloquear:
                hasta = _dt.now(_tz.utc) + _td(hours=hours)
                body['bot_bloqueado'] = True
                body['bloqueado_hasta'] = hasta.isoformat()
                body['razon_bloqueo'] = razon or 'Contenido inapropiado/spam'
            else:
                body['bot_bloqueado'] = False
                body['bloqueado_hasta'] = None
                body['razon_bloqueo'] = None
            url = f'{self.sb_url}/rest/v1/pacientes_440?on_conflict=telefono'
            headers = self._sb_headers()
            headers['Prefer'] = 'resolution=merge-duplicates,return=minimal'
            data = json.dumps(body).encode()
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=8) as r:
                print(f"[CX] set_bloqueado={bloquear} {sender_id} status={r.status}", flush=True)
        except Exception as e:
            print(f"[CX] set_bloqueado error: {e}", flush=True)

    def _load_history(self, sender_id, canal='cirugia'):
        if not self.sb_url or not self.sb_key:
            return []
        params = (
            f'contacto_telefono=eq.{urllib.parse.quote(sender_id)}'
            f'&canal=eq.{urllib.parse.quote(canal)}'
            f'&direccion=in.(entrante,saliente)'
            f'&select=mensaje,direccion,remitente,created_at'
            f'&order=created_at.desc&limit={self.history_limit}'
        )
        url = f'{self.sb_url}/rest/v1/conversaciones_440?{params}'
        try:
            req = urllib.request.Request(url, headers=self._sb_headers(), method='GET')
            with urllib.request.urlopen(req, timeout=8) as r:
                rows = json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = ''
            try: body = e.read().decode()[:300]
            except: pass
            print(f"[CX] sb_get HTTPError {e.code} body={body!r}", flush=True)
            return []
        except Exception as e:
            print(f"[CX] sb_get error: {e}", flush=True)
            return []
        rows = list(reversed(rows or []))
        messages = []
        for row in rows:
            content = (row.get('mensaje') or '').strip()
            if not content:
                continue
            direccion = (row.get('direccion') or '').lower()
            remitente = (row.get('remitente') or '').lower()
            role = 'assistant' if (direccion == 'saliente' or remitente in ('bot', 'asistente', 'sistema')) else 'user'
            messages.append({'role': role, 'content': content})
        while messages and messages[0]['role'] != 'user':
            messages.pop(0)
        collapsed = []
        for m in messages:
            if collapsed and collapsed[-1]['role'] == m['role']:
                collapsed[-1]['content'] += '\n' + m['content']
            else:
                collapsed.append(dict(m))
        print(f"[CX] loaded {len(collapsed)} history msgs", flush=True)
        return collapsed

    def _save_message(self, sender_id, sender_name, mensaje, direccion, remitente,
                      canal='cirugia', cuenta_receptora=None):
        if not self.sb_url or not self.sb_key or not mensaje:
            return
        # Para instagram_cx inferir cuenta_receptora automáticamente.
        # Usa self._cuenta_receptora_activa si está disponible (set en process())
        # para distinguir drgio440 de drgiovannifuentes.
        if cuenta_receptora is None and canal == 'instagram_cx':
            cuenta_receptora = getattr(self, '_cuenta_receptora_activa', 'drgiovannifuentes')
        # Para WhatsApp del bot cirugías: marca 'drgio_wa' para que el CRM
        # pueda distinguirlo del bot estética (brain → 440clinic_wa).
        if cuenta_receptora is None and canal in ('whatsapp', 'cirugia'):
            cuenta_receptora = 'drgio_wa'
        body = {
            'contacto_nombre': sender_name or None,
            'contacto_telefono': sender_id,
            'canal': canal,
            'cuenta_receptora': cuenta_receptora,
            'mensaje': mensaje,
            'direccion': direccion,
            'remitente': remitente,
            'leido': direccion == 'saliente',
        }
        # Adjuntar media SOLO a la primera fila entrante de este process() (one-shot).
        if direccion == 'entrante' and getattr(self, '_in_media_url', None):
            body['media_url'] = self._in_media_url
            body['media_tipo'] = self._in_media_tipo or 'image'
            if getattr(self, '_in_media_caption', None):
                body['mensaje'] = self._in_media_caption
            elif mensaje in ('[IMAGEN]', '[MEDIA]', '[STICKER]'):
                body['mensaje'] = '[Imagen]'
            self._in_media_url = None  # consumido
            self._in_media_caption = None
        headers = self._sb_headers()
        headers['Prefer'] = 'return=minimal'
        try:
            req = urllib.request.Request(
                f'{self.sb_url}/rest/v1/conversaciones_440',
                data=json.dumps(body).encode(), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=8) as r:
                print(f"[CX] sb_insert {direccion}/{remitente} OK status={r.status}", flush=True)
        except urllib.error.HTTPError as e:
            err = ''
            try: err = e.read().decode()[:300]
            except: pass
            print(f"[CX] sb_insert HTTPError {e.code} body={err!r}", flush=True)
        except Exception as e:
            print(f"[CX] sb_insert error: {e}", flush=True)

    # ------------------------------------------------------------------
    # Rotación de asesoras
    # ------------------------------------------------------------------
    def _get_ultima_asesora(self, turno_canal='cirugia'):
        """Lee asesoras_turno para el canal dado. Devuelve el slug en minúsculas."""
        if not self.sb_url or not self.sb_key:
            return None
        url = (f'{self.sb_url}/rest/v1/asesoras_turno'
               f'?canal=eq.{urllib.parse.quote(turno_canal)}&select=ultima_asesora&limit=1')
        try:
            req = urllib.request.Request(url, headers=self._sb_headers(), method='GET')
            with urllib.request.urlopen(req, timeout=8) as r:
                rows = json.loads(r.read())
            if rows:
                return (rows[0].get('ultima_asesora') or '').strip().lower() or None
        except Exception as e:
            print(f"[CX] get_ultima_asesora({turno_canal}) error: {e}", flush=True)
        return None

    def _set_ultima_asesora(self, asesora, turno_canal='cirugia'):
        if not self.sb_url or not self.sb_key:
            return
        url = (f'{self.sb_url}/rest/v1/asesoras_turno'
               f'?canal=eq.{urllib.parse.quote(turno_canal)}')
        headers = self._sb_headers()
        headers['Prefer'] = 'return=minimal'
        body = {'ultima_asesora': asesora, 'updated_at': _now_iso()}
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                         headers=headers, method='PATCH')
            with urllib.request.urlopen(req, timeout=8) as r:
                print(f"[CX] set_ultima_asesora({turno_canal})={asesora} OK status={r.status}", flush=True)
        except Exception as e:
            print(f"[CX] set_ultima_asesora({turno_canal}) error: {e}", flush=True)

    def _next_asesora(self, turno_canal='cirugia'):
        """Determina a quién le toca en el canal dado. Devuelve (slug, label, phone)."""
        ultima = self._get_ultima_asesora(turno_canal)
        if ultima in ASESORAS:
            idx = (ASESORAS.index(ultima) + 1) % len(ASESORAS)
        else:
            idx = 0  # default → bibiana
        slug = ASESORAS[idx]
        phone = os.environ.get(ASESORA_ENV[slug], '').strip()
        print(f"[CX] rotación({turno_canal}): ultima={ultima!r} → siguiente={slug!r} phone={'set' if phone else 'MISSING'}", flush=True)
        return slug, ASESORA_LABEL[slug], phone

    # ------------------------------------------------------------------
    # Slot management
    # ------------------------------------------------------------------
    def _check_slots_cx(self, asesora: str, sender_id: str, preferencia: str = 'proximo',
                        dia: str = '', jornada: str = ''):
        """Consulta los slots disponibles vía CHECK_SLOTS_CX_URL.

        FASE 2 — 3-step flow:
          Sin dia/jornada → {paso:"elegir_dia", dias:[...], asesora:...}
          Con dia → {paso:"elegir_jornada", jornadas:[...]}
          Con dia+jornada → {paso:"elegir_hora", slots:[{id,label,...}]}

        Devuelve el dict/list raw de n8n para que _call_claude() lo procese.
        En caso de error devuelve fallback para paso="elegir_hora".
        """
        _FALLBACK = {
            'paso': 'elegir_hora',
            'slots': [
                {'id': 'slot_1', 'label': 'Próximo lunes 10:00 AM', 'asesora_label': asesora.capitalize()},
                {'id': 'slot_2', 'label': 'Próximo martes 11:00 AM', 'asesora_label': asesora.capitalize()},
                {'id': 'slot_3', 'label': 'Próximo miércoles 3:00 PM', 'asesora_label': asesora.capitalize()},
            ],
        }
        url = (os.environ.get('CHECK_SLOTS_CX_URL') or
               os.environ.get('N8N_CHECK_SLOTS_CX') or '').strip()
        if not url:
            print(f"[CX] check_slots_cx — CHECK_SLOTS_CX_URL/N8N_CHECK_SLOTS_CX no configurado, usando fallback", flush=True)
            return _FALLBACK
        body = {'asesora': asesora, 'preferencia': preferencia, 'sender_id': sender_id}
        if dia:
            body['dia'] = dia
        if jornada:
            body['jornada'] = jornada
        payload = json.dumps(body).encode()
        try:
            req = urllib.request.Request(
                url, data=payload,
                headers={'Content-Type': 'application/json', 'User-Agent': _BROWSER_UA},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                raw = json.loads(r.read())
            # FASE 2: dict con campo 'paso'
            if isinstance(raw, dict) and 'paso' in raw:
                paso = raw.get('paso', '')
                if paso == 'elegir_hora':
                    n = len(raw.get('slots', []))
                elif paso == 'elegir_dia':
                    n = len(raw.get('dias', []))
                else:
                    n = len(raw.get('jornadas', []))
                print(f"[CX] check_slots_cx paso={paso!r} n={n} asesora={asesora}", flush=True)
                return raw
            # Legacy: array directo o dict con slots/slots_array
            if isinstance(raw, list):
                slots = raw
            elif isinstance(raw, dict):
                slots = raw.get('slots_array') or raw.get('slots') or []
            else:
                slots = []
            print(f"[CX] check_slots_cx legacy → {len(slots)} slots", flush=True)
            if slots:
                return {'paso': 'elegir_hora', 'slots': slots}
            return _FALLBACK
        except Exception as e:
            print(f"[CX] check_slots_cx error (usando fallback): {e}", flush=True)
            return _FALLBACK

    def _create_event_cx(self, asesora: str, slot_id: str, sender_id: str,
                         sender_name: str = '', slot_label: str = '',
                         iso_start: str = '', iso_end: str = '',
                         correo_paciente: str = '') -> dict:
        """Crea el evento de prediagnóstico vía CREATE_EVENT_CX_URL.
        Devuelve {ok, meet_link, mensaje} si W22-CX está configurado.
        """
        url = (os.environ.get('CREATE_EVENT_CX_URL') or
               os.environ.get('N8N_CREATE_EVENT_CX') or '').strip()
        if not url:
            print(f"[CX] create_event_cx — CREATE_EVENT_CX_URL/N8N_CREATE_EVENT_CX no configurado, usando fallback", flush=True)
            return {'ok': True, 'slot_label': slot_label or slot_id, 'asesora': asesora}
        body = {
            'asesora': asesora,
            'slot_id': slot_id,
            'slot_label': slot_label,
            'sender_id': sender_id,
            'sender_name': sender_name,
            'iso_start': iso_start,
            'iso_end': iso_end,
        }
        if correo_paciente:
            body['correo_paciente'] = correo_paciente
        payload = json.dumps(body).encode()
        try:
            req = urllib.request.Request(
                url, data=payload,
                headers={'Content-Type': 'application/json', 'User-Agent': _BROWSER_UA},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                result = json.loads(r.read())
                print(f"[CX] create_event_cx slot={slot_id} asesora={asesora} → {result}", flush=True)
                return result
        except Exception as e:
            print(f"[CX] create_event_cx error: {e}", flush=True)
            return {'ok': False, 'error': str(e)}

    # ------------------------------------------------------------------
    # Claude
    # ------------------------------------------------------------------
    # Regex de un Meet link real: meet.google.com/xxx-yyyy-zzz (alfanumérico)
    _MEET_LINK_RE = re.compile(
        r'https?://meet\.google\.com/[a-z0-9]{3,4}-[a-z0-9]{3,4}-[a-z0-9]{3,4}',
        re.IGNORECASE)

    def _call_claude(self, messages, sender_id='', sender_name='', forced_slots=None,
                     paciente_ctx=''):
        """Llama a Claude con soporte para tool use (check_slots_cx, create_event_cx).
        Ejecuta el loop completo hasta obtener respuesta de texto final.
        forced_slots: lista de slots pre-cargados (de PASO D Python injection) para <<<SLOTS>>>
        """
        msgs = list(messages)
        max_iterations = 4  # evitar loops infinitos
        last_slots = forced_slots  # FIX: pre-cargar slots si PASO D inyectó
        last_meet_link = ''  # capturado de create_event_cx para validar el texto final

        for iteration in range(max_iterations):
            # Prompt caching: el system prompt largo y estable (CX_SYSTEM) se
            # marca con cache_control para reutilizar la caché entre llamadas
            # (reduce costo ~60-80%). El contexto del paciente (variable) va en
            # un bloque aparte SIN cache para no invalidar el prefijo cacheado.
            system_blocks = [
                {"type": "text", "text": CX_SYSTEM, "cache_control": {"type": "ephemeral"}}
            ]
            if paciente_ctx:
                system_blocks.append({"type": "text", "text": paciente_ctx})
            payload = json.dumps({
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 900,
                "system": system_blocks,
                "messages": msgs,
                **({"tools": TOOLS_CX} if TOOLS_CX else {}),
            }).encode()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "anthropic-beta": "prompt-caching-2024-07-31",
                    "content-type": "application/json",
                    "user-agent": _BROWSER_UA,
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=25) as r:
                    data = json.loads(r.read())
            except urllib.error.HTTPError as e:
                body = ''
                try: body = e.read().decode()[:400]
                except: pass
                print(f"[CX] Claude HTTPError {e.code} body={body!r}", flush=True)
                return "Disculpa, tuve un problema técnico. ¿Puedes repetir? 😊"
            except Exception as e:
                print(f"[CX] Claude error: {e}", flush=True)
                return "Disculpa, tuve un problema técnico. ¿Puedes repetir? 😊"

            stop_reason = data.get('stop_reason', '')
            content = data.get('content', [])

            # Si no hay tool use → extraer texto y terminar
            if stop_reason != 'tool_use':
                text = ''
                for block in content:
                    if block.get('type') == 'text':
                        text += block.get('text', '')
                # FIX 1: si se consultaron slots, añadir bloque <<<SLOTS>>> al texto
                # para que quede guardado en Supabase y Claude lo lea en el próximo turno
                if last_slots:
                    slots_block = '\n<<<SLOTS>>>\n'
                    for i, s in enumerate(last_slots, 1):  # sin límite — todos los slots
                        slots_block += f'slot_{i}: {json.dumps(s, ensure_ascii=False)}\n'
                    slots_block += '<<<END_SLOTS>>>'
                    text += slots_block
                    print(f"[CX] FIX1 — <<<SLOTS>>> appended ({len(last_slots)} slots, sin límite)", flush=True)

                # Validar meet_link en el texto: si Claude inventó un link
                # (no se llamó create_event_cx o devolvió vacío), lo reemplazamos
                # por un mensaje de fallback en vez de mostrar un URL falso.
                _meet_in_text = self._MEET_LINK_RE.search(text)
                if _meet_in_text:
                    _fake_url = _meet_in_text.group(0)
                    if last_meet_link and last_meet_link != _fake_url:
                        text = text.replace(_fake_url, last_meet_link)
                        print(f"[CX] meet_link corregido → {last_meet_link}", flush=True)
                    elif not last_meet_link:
                        # No hubo create_event_cx exitoso → el link es alucinado.
                        text = re.sub(
                            r'🎥[^\n]*meet\.google\.com[^\n]*\n?',
                            '🎥 Te enviaremos el link de la '
                            'videollamada por WhatsApp antes '
                            'de tu cita 💙\n',
                            text)
                        print("[CX] meet_link inventado — reemplazado por fallback", flush=True)
                return text

            # Hay tool use → ejecutar herramientas y continuar loop
            tool_results = []
            for block in content:
                if block.get('type') == 'tool_use':
                    tool_name = block.get('name', '')
                    tool_input = block.get('input', {})
                    tool_use_id = block.get('id', '')
                    print(f"[CX] tool_use iteration={iteration} tool={tool_name} input={tool_input}", flush=True)

                    # Ejecutar la herramienta
                    if tool_name == 'check_slots_cx':
                        # PREDIAG SIN AGENDA: el prediagnóstico ya NO se agenda por el bot
                        # (califica presupuesto → notifica a la asesora, que coordina el horario).
                        # check_slots_cx queda DESACTIVADO. No se muestran días/horarios.
                        print("[CX] check_slots_cx DESACTIVADO (prediag sin agenda)", flush=True)
                        tool_results.append({
                            'type': 'tool_result',
                            'tool_use_id': tool_use_id,
                            'content': json.dumps({
                                'ok': False,
                                'desactivado': True,
                                'mensaje': ('El prediagnóstico ya NO se agenda por el bot. NO muestres '
                                            'días ni horarios. Sigue el flujo de calificación de presupuesto '
                                            'y, si aplica, emite el <<<NOTIFY>>> tipo prediagnostico con el '
                                            'campo presupuesto.'),
                            }, ensure_ascii=False),
                        })
                        continue
                        # ─── código legacy de agendamiento (INACTIVO) ───
                        if self._es_eleccion_valoracion(msgs):
                            print("[CX] check_slots_cx BLOQUEADO — paciente "
                                  "eligió valoración con Dr. Gio (opción 1/2)",
                                  flush=True)
                            tool_result_content = json.dumps({
                                'ok': False,
                                'bloqueado': True,
                                'mensaje': (
                                    'El paciente eligió valoración con '
                                    'Dr. Gio (opción 1 o 2). NO uses '
                                    'check_slots_cx ni muestres horarios. '
                                    'Responde: "¡Perfecto [nombre]! 💙 '
                                    'En breve nuestra asesora te contactará '
                                    'para coordinar tu valoración con el '
                                    'Dr. Gio. La Belleza 440 ✨" y emite '
                                    'el <<<NOTIFY>>> con tipo: valoracion '
                                    'y opcion_elegida exacta.'),
                            }, ensure_ascii=False)
                            tool_results.append({
                                'type': 'tool_result',
                                'tool_use_id': tool_use_id,
                                'content': tool_result_content,
                            })
                            continue
                        # BUG 1 FIX: SIEMPRE usar rotación — ignorar asesora que Claude proponga.
                        # _next_asesora lee asesoras_turno y devuelve a quien le toca.
                        # El turno avanza solo en _notify_lead (cuando el prediagnóstico se confirma).
                        slug, _, _ = self._next_asesora('cirugia_prediag')
                        asesora = slug
                        print(f"[CX] check_slots_cx: rotación → asesora={asesora!r} (ignorando input de Claude)", flush=True)
                        raw_response = self._check_slots_cx(
                            asesora=asesora,
                            sender_id=tool_input.get('sender_id', sender_id),
                            preferencia=tool_input.get('preferencia', 'proximo'),
                            dia=tool_input.get('dia', ''),
                            jornada=tool_input.get('jornada', ''),
                        )
                        # FASE 2: cuando paso=elegir_hora, guardar slots para <<<SLOTS>>>
                        if isinstance(raw_response, dict):
                            if raw_response.get('paso') == 'elegir_hora':
                                last_slots = raw_response.get('slots', [])
                            elif raw_response.get('paso') == 'elegir_jornada':
                                # FIX 3: forzar que Claude pregunte mañana/tarde
                                raw_response = dict(raw_response)
                                raw_response['_instruccion'] = (
                                    'Debes preguntar al paciente: '
                                    '"¿Prefieres en la mañana ☀️ o en '
                                    'la tarde 🌙?" — NO asumas ni saltes '
                                    'este paso.'
                                )
                        elif isinstance(raw_response, list):
                            last_slots = raw_response  # legacy
                        tool_result_content = json.dumps(raw_response, ensure_ascii=False)

                    elif tool_name == 'create_event_cx':
                        result = self._create_event_cx(
                            asesora=tool_input.get('asesora', ''),
                            slot_id=tool_input.get('slot_id', ''),
                            slot_label=tool_input.get('slot_label', ''),
                            iso_start=tool_input.get('iso_start', ''),
                            iso_end=tool_input.get('iso_end', ''),
                            sender_id=tool_input.get('sender_id', sender_id),
                            sender_name=tool_input.get('sender_name', sender_name),
                            correo_paciente=tool_input.get('correo_paciente', ''),
                        )
                        if isinstance(result, dict):
                            _ml = (result.get('meet_link') or '').strip()
                            if self._MEET_LINK_RE.match(_ml):
                                last_meet_link = _ml
                        tool_result_content = json.dumps(result, ensure_ascii=False)
                    else:
                        tool_result_content = json.dumps({'error': f'Unknown tool: {tool_name}'})

                    tool_results.append({
                        'type': 'tool_result',
                        'tool_use_id': tool_use_id,
                        'content': tool_result_content,
                    })

            # Agregar el turno del asistente (con tool_use) y los resultados al historial
            msgs.append({'role': 'assistant', 'content': content})
            msgs.append({'role': 'user', 'content': tool_results})

        # Si se agota el loop sin texto final
        print(f"[CX] tool_use loop agotado después de {max_iterations} iteraciones", flush=True)
        return "Disculpa, tuve un problema técnico. ¿Puedes repetir? 😊"

    # ------------------------------------------------------------------
    # NOTIFY parsing + envío
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_notify(block):
        out = {}
        for line in (block or '').splitlines():
            line = line.strip()
            if not line or ':' not in line:
                continue
            k, _, v = line.partition(':')
            out[k.strip().lower()] = v.strip()
        return out

    # Ciudades canónicas usadas por _validate_notify_fields y bypass.
    # El orden de detección es por aparición cronológica en el historial,
    # NO por orden de esta lista.
    _CIUDADES_CANONICAS = (
        'barranquilla', 'bogotá', 'bogota', 'medellín', 'medellin',
        'cali', 'cartagena', 'cúcuta', 'cucuta', 'bucaramanga',
        'santa marta', 'pereira', 'manizales', 'ibagué', 'ibague',
        'villavicencio', 'neiva', 'pasto', 'montería', 'monteria',
        'miami', 'new york', 'nueva york', 'panamá', 'panama',
        'venezuela', 'ecuador', 'peru', 'perú', 'mexico', 'méxico',
    )
    _CIUDAD_PATRONES = ('vivo en ', 'soy de ', 'estoy en ', 'ciudad ',
                        'desde ', 'vengo de ', 'somos de ')

    def _ciudad_from_history(self, history):
        """Recorre el historial en orden ASC y devuelve la PRIMERA
        ciudad mencionada por el paciente con contexto explícito
        ('vivo en X', 'soy de X', 'desde X', etc.). Si no hay contexto
        explícito, hace fallback al primer match simple. Devuelve '' si nada."""
        # First pass — con patrones de contexto (más confiable)
        for m in history:
            if m.get('role') != 'user':
                continue
            txt = (m.get('content') or '').lower()
            for pat in self._CIUDAD_PATRONES:
                for c in self._CIUDADES_CANONICAS:
                    if (pat + c) in txt:
                        return c.title()
        # Second pass — primera ciudad mencionada sin contexto
        for m in history:
            if m.get('role') != 'user':
                continue
            txt = (m.get('content') or '').lower()
            # Buscar en orden de aparición, no de la lista
            posiciones = []
            for c in self._CIUDADES_CANONICAS:
                idx = txt.find(c)
                if idx >= 0:
                    posiciones.append((idx, c))
            if posiciones:
                posiciones.sort()
                return posiciones[0][1].title()
        return ''

    # Marcadores de sexo. Solo se usan frases explícitas / autodescriptivas
    # del paciente para evitar falsos positivos (p.ej. "mi esposo" NO implica
    # que el paciente sea hombre).
    _SEXO_HOMBRE_PATRONES = (
        'soy hombre', 'soy un hombre', 'soy masculino', 'sexo masculino',
        'género masculino', 'genero masculino', 'soy varón', 'soy varon',
        'soy chico', 'soy un chico', 'hombre,', 'masculino',
    )
    _SEXO_MUJER_PATRONES = (
        'soy mujer', 'soy una mujer', 'soy femenina', 'sexo femenino',
        'género femenino', 'genero femenino', 'soy chica', 'soy una chica',
        'mujer,', 'femenino', 'femenina',
        'embarazada', 'tuve a mi bebé', 'di a luz', 'cesárea', 'cesarea',
        'estoy lactando',
    )

    def _detect_sexo(self, history, text=''):
        """Detecta sexo del paciente a partir de frases explícitas en el
        historial + el mensaje actual. Devuelve 'hombre', 'mujer' o ''.
        Toma la PRIMERA afirmación explícita en orden cronológico."""
        partes = []
        for m in history:
            if m.get('role') != 'user':
                continue
            c = m.get('content')
            if isinstance(c, str):
                partes.append(c)
        if text:
            partes.append(text)
        for txt in partes:
            low = (txt or '').lower()
            for pat in self._SEXO_HOMBRE_PATRONES:
                if pat in low:
                    return 'hombre'
            for pat in self._SEXO_MUJER_PATRONES:
                if pat in low:
                    return 'mujer'
        return ''

    def _extract_name_from_history(self, history, sender_name):
        """Busca un nombre real del paciente. Prioridad:
        1. Primera frase del paciente del estilo 'me llamo X', 'soy X',
           'mi nombre es X' (más confiable que el sender_name).
        2. Respuesta corta del paciente justo después de pregunta del
           bot sobre nombre.
        3. sender_name (WhApi profile) — solo si tiene ≥2 letras, NO está
           rodeado de emojis/símbolos, y no es un alias TODO-MAYÚSCULAS
           tipo 'TEST', 'USER', etc.
        Devuelve '' si nada confiable."""
        # 1. y 2. Escanear historial
        for i, m in enumerate(history):
            if m.get('role') != 'user':
                continue
            txt = (m.get('content') or '').strip()
            low = txt.lower()
            for pat in ('me llamo ', 'soy ', 'mi nombre es '):
                if pat in low:
                    rest = low.split(pat, 1)[1].strip()
                    cand = rest.split()[0] if rest else ''
                    cand = ''.join(ch for ch in cand if ch.isalpha())
                    if len(cand) >= 2:
                        return cand.title()
            if i > 0 and history[i-1].get('role') == 'assistant':
                bot = (history[i-1].get('content') or '').lower()
                if ('nombre' in bot or 'cómo te llamas' in bot or 'como te llamas' in bot):
                    cand = txt.replace('.', '').strip().split()
                    if cand:
                        first = ''.join(ch for ch in cand[0] if ch.isalpha())
                        if len(first) >= 2 and first.lower() not in ('si', 'sí', 'no', 'ok'):
                            return first.title()
        # 3. sender_name como último recurso
        nm = (sender_name or '').strip()
        # Si tiene chars no-alfanuméricos adjacentes (emojis, símbolos), filtrarlos
        has_non_letter_symbol = any(not (ch.isalnum() or ch.isspace()) for ch in nm)
        if has_non_letter_symbol:
            return ''  # 💕TEST💕, 💕 ASHLY 💕 → no confiable
        letters = sum(1 for ch in nm if ch.isalpha())
        if letters >= 2 and nm not in ('.', '—', '-'):
            return nm.split()[0].title()
        return ''

    def _validate_notify_fields(self, fields, history, sender_name, sender_id):
        """Limpia campos críticos del NOTIFY in-place. Aplica fallbacks
        desde el historial cuando el modelo dejó '.', 'desconocida',
        'sin nombre', '—', vacío, etc."""
        # nombre
        nombre = (fields.get('nombre') or '').strip()
        bad_name = (not nombre or
                    not any(c.isalpha() for c in nombre) or
                    nombre.lower() in ('.', '—', '-', 'sin nombre', 'no especificado'))
        if bad_name:
            recovered = self._extract_name_from_history(history, sender_name)
            fields['nombre'] = recovered or 'Paciente'
            print(f"[CX] NOTIFY nombre rescued: {nombre!r} → {fields['nombre']!r}", flush=True)
        # ciudad
        ciudad = (fields.get('ciudad') or '').strip().lower()
        bad_city = (not ciudad or
                    ciudad in ('desconocida', '—', '-', 'no especificada', 'no especificado'))
        if bad_city:
            recovered = self._ciudad_from_history(history)
            if recovered:
                fields['ciudad'] = recovered
                print(f"[CX] NOTIFY ciudad rescued: → {recovered!r}", flush=True)
            else:
                fields['ciudad'] = 'desconocida'
        # procedimiento — fallback suave (no inventar)
        proc = (fields.get('procedimiento') or '').strip().lower()
        if not proc or proc in ('—', '-', 'no especificado', 'desconocido'):
            fields['procedimiento'] = fields.get('procedimiento') or 'consulta general'
        return fields

    @staticmethod
    def _es_eleccion_valoracion(msgs):
        """True si en la conversación el paciente está eligiendo una
        valoración con Dr. Gio (opciones 1/2 con precio) en lugar del
        prediagnóstico gratuito. Si True → bloquear check_slots_cx.

        Escanea TODA la conversación (no solo el último turno) para
        que el bloqueo persista aunque el paciente envíe mensajes
        posteriores como un correo, "ok", "gracias", etc.
        """
        all_user_parts = []
        all_bot_parts = []
        for m in msgs:
            c = m.get('content', '')
            text = ''
            if isinstance(c, str):
                text = c
            elif isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get('type') == 'text':
                        text += b.get('text', '')
            if not text:
                continue
            if m.get('role') == 'user':
                all_user_parts.append(text)
            elif m.get('role') == 'assistant':
                all_bot_parts.append(text)
        all_user = ' '.join(all_user_parts).lower()
        all_bot = ' '.join(all_bot_parts).lower()

        # 1) Confirmaciones del bot en CUALQUIER mensaje anterior:
        bot_confirm = [
            'vamos con la valoración presencial',
            'vamos con la valoracion presencial',
            'vamos con la valoración virtual',
            'vamos con la valoracion virtual',
            'valoración presencial con el dr',
            'valoracion presencial con el dr',
            'valoración virtual con el dr',
            'valoracion virtual con el dr',
            'coordinará tu valoración',
            'coordinara tu valoracion',
            'coordinar tu valoración con el dr',
            'coordinar tu valoracion con el dr',
        ]
        if any(s in all_bot for s in bot_confirm):
            return True

        # 2) Señales directas del paciente en CUALQUIER mensaje:
        direct_user = [
            'valoracion virtual', 'valoración virtual',
            'valoracion presencial', 'valoración presencial',
            'presencial con dr', 'virtual con dr',
            '$160', '$260', '160.000', '260.000',
        ]
        if any(s in all_user for s in direct_user):
            return True

        # 3) Si el ÚLTIMO mensaje del paciente fue un número en respuesta
        # a una OFERTA del bot (el mensaje del bot inmediato anterior).
        last_user = ''
        last_bot = ''
        for m in reversed(msgs):
            c = m.get('content', '')
            text = ''
            if isinstance(c, str):
                text = c
            elif isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get('type') == 'text':
                        text += b.get('text', '')
            if not text:
                continue
            if m.get('role') == 'user' and not last_user:
                last_user = text
            elif m.get('role') == 'assistant' and not last_bot:
                last_bot = text
            if last_user and last_bot:
                break
        u = (last_user or '').lower()
        b = (last_bot or '').lower()
        num = u.strip().rstrip('.!,').replace('️⃣', '').strip()
        if num in {'1', '2', '3', 'uno', 'dos', 'tres',
                   '1️⃣', '2️⃣', '3️⃣'}:
            num_norm = num.replace('1️⃣', '1').replace('2️⃣', '2').replace('3️⃣', '3')
            if not b:
                return False
            if '1️⃣ valoración' in b or '1️⃣ valoracion' in b:
                return num_norm in {'1', '2', 'uno', 'dos'}
            if '1️⃣ prediagn' in b:
                return num_norm in {'2', '3', 'dos', 'tres'}
        return False

    @staticmethod
    def _turno_canal(opcion):
        """Determina qué fila de asesoras_turno usar según la opción elegida.
        FUSIÓN: valoración (opción 1/2) y leads calientes comparten el MISMO
        sistema de turno → canal 'cirugia'. El prediagnóstico tiene su propio
        canal 'cirugia_prediag' (no pasa por aquí).
        """
        opcion_str = str(opcion or '').lower()
        if any(k in opcion_str for k in ('1', 'virtual', '2', 'presencial', 'valoracion', 'valoración')):
            # Solo si NO menciona 'prediagnóstico' / 'gratuito'
            if not any(k in opcion_str for k in ('3', 'prediag', 'gratuito')):
                return 'cirugia'
        return 'cirugia'

    def _try_bypass_valoracion_cx(self, history, text, sender_id,
                                  sender_name, canal, send):
        """Si la conversación indica que el paciente eligió valoración
        con Dr. Gio (opción 1/2 con precio en CALIENTE/URGENTE o 2/3
        en TIBIO), Python genera cierre + NOTIFY tipo=valoracion sin
        invocar Claude. Retorna user_facing (str) si bypass aplicó,
        None si no aplica."""
        if not self._es_eleccion_valoracion(history):
            return None

        # Dedup: si ya hay un mensaje saliente previo con NOTIFY
        # tipo=valoracion en el historial, no volver a notificar.
        for m in reversed(history[:-1]):
            if m.get('role') == 'assistant':
                c = m.get('content')
                txt = c if isinstance(c, str) else ''
                if ('<<<NOTIFY>>>' in txt and
                        ('tipo: valoracion' in txt.lower() or
                         'tipo:valoracion' in txt.lower())):
                    return None  # ya notificado en este flujo

        # FIX 1 — Dedup unificado: cualquier NOTIFY (cualquier tipo) en <24h.
        if self._already_notified_cx(sender_id, canal):
            print("[CX] bypass valoracion — ya notificado <24h, no re-notificar", flush=True)
            return None
        # FIX 2 (regla C) — si el lead ya tiene asesora asignada, no re-notificar.
        _lead_byp = self._check_lead_crm(sender_id)
        if _lead_byp and (_lead_byp.get('asesora_asignada') or '').strip():
            print("[CX] bypass valoracion — lead ya tiene asesora, no re-notificar", flush=True)
            return None

        # Detectar opción específica del último mensaje del paciente
        u = (text or '').strip().lower()
        if 'presencial' in u or '260' in u:
            opcion_label = 'Valoración presencial $260.000'
        elif 'virtual' in u or '160' in u:
            opcion_label = 'Valoración virtual $160.000'
        else:
            opcion_label = 'Valoración con Dr. Gio'

        # Extraer nombre, ciudad, procedimiento del historial.
        hist_text = ' '.join(
            m.get('content', '') if isinstance(m.get('content'), str) else ''
            for m in history)
        nombre = self._extract_name_from_history(history, sender_name)

        # Ciudad: primera mención cronológica con contexto ('vivo en',
        # 'soy de', etc.) > primera mención simple. Evita el bug del
        # keyword-match por orden de lista (que devolvía 'barranquilla'
        # aunque el paciente dijera 'vivo en Medellín').
        ciudad = self._ciudad_from_history(history)

        # Procedimiento: buscar términos quirúrgicos en primer mensaje
        # del paciente que mencione uno (orden cronológico).
        procedimiento = ''
        for m in history:
            if m.get('role') != 'user':
                continue
            txt = (m.get('content') or '').lower()
            for proc in ('mommy makeover', 'mommy', 'paquete mama',
                         'paquete embarazo', 'perdida de peso cirugia',
                         'exceso de piel',
                         'lipoescultura 360', 'lipoescultura', 'lipo',
                         'mamoplastia', 'abdominoplastia', 'blefaroplastia',
                         'rinoplastia', 'lifting', 'papada',
                         'ginecomastia', 'otoplastia',
                         'bbl', 'gluteos', 'lipotransferencia'):
                if proc in txt:
                    procedimiento = proc.title()
                    break
            if procedimiento:
                break

        saludo = f"¡Perfecto {nombre}! 💙" if nombre else "¡Perfecto! 💙"
        cierre = (
            f"{saludo}\n"
            "En breve nuestra asesora\n"
            "te contactará para coordinar\n"
            "tu valoración con el Dr. Gio.\n"
            "La Belleza 440 ✨"
        )
        notify_block = (
            "<<<NOTIFY>>>\n"
            f"nombre: {nombre or 'sin nombre'}\n"
            f"telefono: {sender_id}\n"
            f"canal: {canal}\n"
            f"ciudad: {ciudad or 'desconocida'}\n"
            f"procedimiento: {procedimiento or 'consulta general'}\n"
            "score: CALIENTE\n"
            "tipo: valoracion\n"
            f"opcion_elegida: {opcion_label}\n"
            "accion: Contactar HOY para coordinar valoración con Dr. Gio\n"
            "prioridad: CALIENTE\n"
            "<<<END>>>"
        )
        full_response = cierre + "\n\n" + notify_block

        # Strip → user_facing.
        user_facing = re.sub(r'<<<NOTIFY>>>.*?<<<END>>>', '',
                             full_response, flags=re.DOTALL).strip()
        user_facing = re.sub(r'\n{3,}', '\n\n', user_facing).strip()

        # Enviar (si send=True) y guardar.
        if user_facing and send:
            client = self.instagram if canal.startswith('instagram') else self.whapi
            r = client.send_text(sender_id, user_facing)
            print(f"[CX] bypass valoracion send_text result={r}", flush=True)
        if user_facing:
            self._save_message(sender_id, sender_name, full_response,
                               'saliente', 'bot', canal=canal)

        # Notificar al staff (Sara/Sharon/Central/Dr. Gio según _turno_canal).
        notify_data = notify_block.split('<<<NOTIFY>>>', 1)[1] \
                                   .split('<<<END>>>', 1)[0].strip()
        fields = self._parse_notify(notify_data)
        self._notify_lead(fields, sender_id, canal=canal)

        return user_facing

    def _push_core440_lead(self, nombre, asesora_slug, canal_crm, *,
                           temperatura='', procedimiento='', ciudad='',
                           fecha_disponible='', tipo_atencion='', telefono=''):
        """Notificación push a CORE440 con toda la info del lead (best-effort)."""
        try:
            import urllib.request as _u, json as _j
            label = ASESORA_LABEL.get(asesora_slug, (asesora_slug or '').capitalize()) if asesora_slug else '—'
            payload = _j.dumps({
                'tipo': 'nuevo_lead', 'paciente_nombre': nombre, 'asesora': label,
                'canal': 'Instagram' if canal_crm == 'instagram' else 'WhatsApp', 'linea': 'quirurgico',
                'temperatura': (temperatura or '').lower(),
                'procedimiento': procedimiento or '',
                'ciudad': ciudad or '',
                'fecha_disponible': fecha_disponible or '',
                'tipo_atencion': tipo_atencion or '',
                'telefono': telefono or '',
            }).encode()
            req = _u.Request('https://core440-440clinic.vercel.app/api/push/notify',
                             data=payload, headers={'Content-Type': 'application/json'}, method='POST')
            _u.urlopen(req, timeout=6)
        except Exception as e:
            print(f"[CX] push core440 lead error: {e}", flush=True)

    # ------------------------------------------------------------------
    # MedFiles — destino de leads + pausa cuando un humano toma la conversación
    # ------------------------------------------------------------------
    @staticmethod
    def _medfiles_cfg():
        """(base_url, clave). clave vacía → integración desactivada."""
        base = (os.environ.get('MEDFILES_URL') or _MEDFILES_DEFAULT_URL).strip().rstrip('/')
        clave = (os.environ.get('MEDFILES_BOT_CLAVE') or '').strip()
        return base, clave

    @staticmethod
    def _es_canal_instagram(canal):
        return 'instagram' in (canal or '').lower()

    @staticmethod
    def _tel_valido(tel):
        """Dígitos de un teléfono plausible (7–15 dígitos) o ''."""
        d = re.sub(r'[^\d]', '', str(tel or ''))
        return d if 7 <= len(d) <= 15 else ''

    def _medfiles_pausado(self, telefono):
        """GET /api/entrada/bot?telefono=… → True si alguien del equipo ya
        escribió desde MedFiles (el bot se calla). Fail-open: cualquier error,
        timeout o config faltante → False."""
        base, clave = self._medfiles_cfg()
        tel = self._tel_valido(telefono)
        if not clave or not tel:
            return False
        try:
            url = f"{base}/api/entrada/bot?telefono={urllib.parse.quote(tel)}"
            req = urllib.request.Request(url, headers={
                'X-Clave': clave, 'Accept': 'application/json',
                'User-Agent': _BROWSER_UA}, method='GET')
            with urllib.request.urlopen(req, timeout=3) as r:
                data = json.loads(r.read() or b'{}')
            pausado = bool((data or {}).get('pausado'))
            print(f"[CX] medfiles pausado={pausado} tel={tel}", flush=True)
            return pausado
        except Exception as e:
            print(f"[CX] medfiles pausado check err (fail-open): {e}", flush=True)
            return False

    @staticmethod
    def _resumen_conversacion(history, ultimo_bot='', n=20):
        """Mensajes de la paciente (últimos ~n) como lista
        (sin bloques NOTIFY/SLOTS ni el prefijo [tel|nombre])."""
        lineas = []
        msgs = list(history or [])
        if ultimo_bot:
            msgs.append({'role': 'assistant', 'content': ultimo_bot})
        for m in msgs[-n:]:
            c = m.get('content')
            if not isinstance(c, str):
                continue
            c = re.sub(r'<<<NOTIFY>>>.*?<<<END>>>', '', c, flags=re.DOTALL)
            c = re.sub(r'<<<SLOTS>>>.*?<<<END_SLOTS>>>', '', c, flags=re.DOTALL)
            c = re.sub(r'^\[[^\]]{1,80}\]:\s*', '', c.strip())
            c = c.strip()
            if not c:
                continue
            # Solo lo que escribió la paciente: los mensajes del bot son fijos y largos (la asesora ya los conoce)
            if m.get('role') == 'assistant':
                continue
            lineas.append(f"• {c}")
        return ('Lo que escribió la paciente:\n' + '\n'.join(lineas))[-3900:] if lineas else ''

    @staticmethod
    def _pauta_from_history(history, text=''):
        """Pauta según el PRIMER mensaje del paciente (el texto prellenado del
        anuncio). Solo el primero, para no confundir p. ej. 'turismo todo
        incluido' dicho más adelante."""
        primero = next((m.get('content') for m in (history or [])
                        if m.get('role') == 'user' and isinstance(m.get('content'), str)),
                       text or '')
        low = _sin_tildes(re.sub(r'^\[[^\]]{1,80}\]:\s*', '', primero or ''))
        return _PAUTA_MAMO_LABEL if any(k in low for k in _PAUTA_MAMO_KW) else None

    def _push_medfiles_lead(self, body):
        """POST /api/entrada/bot. Devuelve el JSON de respuesta o None."""
        base, clave = self._medfiles_cfg()
        if not clave:
            print("[CX] MEDFILES_BOT_CLAVE no configurada — lead NO enviado a MedFiles", flush=True)
            return None
        try:
            req = urllib.request.Request(
                f"{base}/api/entrada/bot",
                data=json.dumps(body, ensure_ascii=False).encode(),
                headers={'X-Clave': clave, 'Content-Type': 'application/json',
                         'Accept': 'application/json', 'User-Agent': _BROWSER_UA},
                method='POST')
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read() or b'{}')
            print(f"[CX] medfiles lead → ok={data.get('ok')} nuevo={data.get('nuevo')} "
                  f"negocio={data.get('negocio')} asesora={(data.get('asesora') or {}).get('nombre')!r}",
                  flush=True)
            return data
        except urllib.error.HTTPError as e:
            err = ''
            try: err = e.read().decode()[:300]
            except: pass
            print(f"[CX] medfiles lead HTTPError {e.code} body={err!r}", flush=True)
        except Exception as e:
            print(f"[CX] medfiles lead error: {e}", flush=True)
        return None

    def _notify_lead(self, fields, sender_id, canal='whatsapp', history=None, ultimo_bot=''):
        """Flujo nuevo: envía el lead a MedFiles + aviso por WhatsApp a la
        asesora única (ASESORA_MEDFILES_TEL). El dedup <24h lo hace el caller
        (_already_notified_cx)."""
        nombre = (fields.get('nombre') or '').strip() or 'Paciente'
        proc = (fields.get('procedimiento') or '').strip() or 'consulta general'
        ciudad = (fields.get('ciudad') or '').strip()
        if ciudad.lower() in ('desconocida', '—', '-'):
            ciudad = ''
        interes_raw = _sin_tildes(' '.join(
            fields.get(k, '') for k in ('interes', 'tipo', 'opcion_elegida', 'prioridad')))
        asesora_tel = re.sub(r'[^\d]', '', os.environ.get('ASESORA_MEDFILES_TEL', ''))

        # ── Urgencia de paciente operado: solo aviso a la asesora, sin lead ──
        if 'urgencia' in interes_raw:
            tel_u = sender_id if not self._es_canal_instagram(canal) else (fields.get('telefono') or sender_id)
            if asesora_tel:
                try:
                    self.whapi.send_text(asesora_tel,
                        f"🚨 URGENCIA (paciente): {nombre} · Tel {tel_u}\n"
                        f"{(fields.get('mensaje') or '').strip()[:200]}")
                except Exception as e:
                    print(f"[CX] aviso urgencia err: {e}", flush=True)
            print("[CX] NOTIFY urgencia — aviso a asesora (sin lead MedFiles)", flush=True)
            return 'URGENCIA'

        interes = 'valoracion' if 'valor' in interes_raw or 'consulta' in interes_raw else 'asesoria'
        mod_raw = _sin_tildes(fields.get('modalidad', '') + ' ' + fields.get('opcion_elegida', ''))
        modalidad = ('presencial' if 'presencial' in mod_raw else
                     'virtual' if 'virtual' in mod_raw else None)
        if interes == 'asesoria':
            modalidad = None  # la asesoría siempre es virtual; modalidad aplica a la valoración

        email = None
        _em = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', fields.get('email', '') or '')
        if not _em:
            _hist_user = ' '.join(m.get('content', '') for m in (history or [])
                                  if m.get('role') == 'user' and isinstance(m.get('content'), str))
            _em = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', _hist_user)
        if _em:
            email = _em.group(0)

        pauta = (fields.get('pauta') or '').strip()
        if not pauta or _sin_tildes(pauta) in ('no', 'ninguna', 'vacio', 'n/a', '-', '—'):
            pauta = self._pauta_from_history(history)
        financiacion = _sin_tildes(fields.get('financiacion', '')).startswith('si')

        # Teléfono: en WhatsApp el sender_id ES el número. En Instagram el
        # sender_id es un IGSID → solo se usa el número que dio el paciente.
        if self._es_canal_instagram(canal):
            telefono = self._tel_valido(fields.get('telefono'))
            if telefono == re.sub(r'[^\d]', '', str(sender_id)):
                telefono = ''
            if not telefono:
                print("[CX] Instagram sin número de WhatsApp del paciente — lead NO enviado a MedFiles", flush=True)
                return 'SIN_TELEFONO'
        else:
            telefono = self._tel_valido(sender_id) or self._tel_valido(fields.get('telefono'))

        notas = []
        if pauta:
            notas.append(f"Pauta: {pauta}")
        if financiacion:
            notas.append("Interesado en financiación")
        if self._es_canal_instagram(canal):
            notas.append("Canal: Instagram")
        resumen = self._resumen_conversacion(history, ultimo_bot)
        if notas:
            resumen = "Notas del bot: " + ' · '.join(notas) + "\n\n" + resumen

        body = {
            'nombre': nombre,
            'telefono': telefono,
            'email': email,
            'ciudad': ciudad or None,
            'procedimiento': proc,
            'interes': interes,
            'modalidad': modalidad,
            'pauta': pauta or None,
            'resumen': resumen,
        }
        print(f"[CX] lead → MedFiles interes={interes} modalidad={modalidad} pauta={pauta!r} tel={telefono}", flush=True)
        self._push_medfiles_lead(body)

        # Aviso por WhatsApp a la asesora única (opcional).
        if asesora_tel:
            if interes == 'valoracion':
                tipo_txt = 'Valoración con el Dr.' + (f' ({modalidad})' if modalidad else '')
            else:
                tipo_txt = 'Asesoría virtual gratuita'
            msg = (f"🆕 Nuevo lead: {nombre} · {proc} · {ciudad or 'ciudad sin dato'} · {tipo_txt}. "
                   "Revísalo en MedFiles → CRM.")
            try:
                r = self.whapi.send_text(asesora_tel, msg)
                print(f"[CX] aviso asesora MedFiles → {r if isinstance(r, dict) and 'error' in r else 'OK'}", flush=True)
            except Exception as e:
                print(f"[CX] aviso asesora MedFiles err: {e}", flush=True)
        else:
            print("[CX] ASESORA_MEDFILES_TEL vacío — sin aviso por WhatsApp (MedFiles asigna)", flush=True)

        # CRM viejo solo si se re-activa explícitamente.
        if _LEGACY_CRM:
            try:
                self._notify_lead_legacy(fields, sender_id, canal=canal)
            except Exception as e:
                print(f"[CX] legacy notify err: {e}", flush=True)
        return interes.upper()

    def _notify_lead_legacy(self, fields, sender_id, canal='whatsapp'):
        """LEGACY (CX_LEGACY_CRM=1) — Routing por score y tipo:

        tipo='prediagnostico virtual':
          → asesora específica del slot (del NOTIFY) + Sharon + Central + Dr. Gio
          → Mensaje formato PREDIAGNÓSTICO AGENDADO
          → SÍ avanza turno

        URGENTE  → todos (las 3 asesoras + Sharon + Central) SIN rotar turno
        CALIENTE → asesora en turno (canal según opción) + Sharon + Central, SÍ rota
        TIBIO    → asesora en turno (canal según opción) + Sharon + Central, SÍ rota
        FRÍO     → solo Sharon + Central, NO rota turno

        Canal de turno:
          leads calientes + valoración Dr. Gio (opción 1/2) → canal='cirugia'
          prediagnóstico (canal propio, fuera de _turno_canal) → canal='cirugia_prediag'
        """
        nombre     = fields.get('nombre', '—')
        proc       = fields.get('procedimiento', '—')
        fecha      = fields.get('fecha_deseada') or fields.get('fecha', 'no definida')
        ciudad     = fields.get('ciudad', '—')
        motivacion = fields.get('motivacion', '—')
        opcion     = fields.get('opcion_elegida', '—')
        score      = (fields.get('score') or fields.get('prioridad') or 'CALIENTE').upper()
        tipo       = fields.get('tipo', '').lower()

        # BUG 1 FIX: usar sender_id real si Claude puso un valor corto/inválido
        # (ej. "3", "no especificado", vacío). sender_id siempre es el número real.
        _tel_raw = (fields.get('telefono') or '').strip()
        tel = _tel_raw if len(_tel_raw) >= 7 and _tel_raw.replace('+','').replace('-','').isdigit() else sender_id
        print(f"[CX] tel_raw={_tel_raw!r} → tel={tel!r} (sender_id={sender_id!r})", flush=True)

        # Rotación por temperatura: URGENTE y CALIENTE comparten el turno
        # 'cirugia_caliente'; TIBIO usa su propio turno 'cirugia_tibio'.
        # (El prediagnóstico usa 'cirugia_prediag' en su rama; FRÍO no rota.)
        turno_canal = 'cirugia_tibio' if 'TIBIO' in score else 'cirugia_caliente'
        print(f"[CX] _notify_lead tipo={tipo!r} opcion={opcion!r} turno_canal={turno_canal!r} score={score}", flush=True)

        sharon = os.environ.get('DRA_SHARON', '').strip()
        admin  = os.environ.get('ADMIN_CX', '').strip()
        drgio  = os.environ.get('DRGIO_TEL', '573181800131').strip()

        results = {}
        _assigned_slug = ''  # se asigna en la rama correspondiente para el CRM

        # ── Prediagnóstico virtual agendado — formato especial ────────────
        if 'prediagnostico' in tipo:
            # Prediagnóstico SIEMPRE por rotación — ignorar asesora propuesta por el LLM.
            asesora_slug, _, _ = self._next_asesora('cirugia_prediag')
            asesora_label = ASESORA_LABEL.get(asesora_slug, asesora_slug.capitalize())
            asesora_phone = os.environ.get(ASESORA_ENV.get(asesora_slug, ''), '').strip()
            _presu = (fields.get('presupuesto') or '').strip().lower()
            presu_label = 'Financiamiento' if 'financ' in _presu else 'OK'
            msg = (
                "🔔 Lead interesado en prediagnóstico\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {nombre} ({ciudad})\n"
                f"💉 Procedimiento: {proc}\n"
                f"💰 Presupuesto: {presu_label}\n"
                f"👩 Asesora: {asesora_label}\n"
                f"📱 Tel: {tel}\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "La asesora decide si agenda."
            )
            # WA al staff desactivado — notificaciones solo por CORE440 push
            self._set_ultima_asesora(asesora_slug, 'cirugia_prediag')
            print(f"[CX] PREDIAG LEAD → asesora={asesora_slug} presupuesto={presu_label} turno avanzado (push CORE440)", flush=True)
            try:
                canal_crm = 'instagram' if 'instagram' in (canal or '').lower() else 'whatsapp'
                self._upsert_lead_comercial(nombre=nombre, telefono=tel,
                    procedimiento=proc, canal=canal_crm,
                    prioridad='PREDIAGNOSTICO', ciudad=ciudad,
                    observaciones=f"Presupuesto: {presu_label}" + (f" | {motivacion}" if motivacion else ''),
                    asesora_asignada=asesora_slug)
            except Exception as e:
                print(f"[CX] upsert lead_comercial (predia) error: {e}", flush=True)
            self._push_core440_lead(nombre, asesora_slug, canal_crm,
                temperatura=score, procedimiento=proc, ciudad=ciudad,
                fecha_disponible=fecha, tipo_atencion='prediagnostico', telefono=tel)
            return score

        if 'URGENTE' in score:
            # Notifica a LAS TRES asesoras + Sharon + Central. NO avanza turno.
            msg = (
                "🚨 LEAD URGENTE CIRUGÍA\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {nombre} ({ciudad})\n"
                f"💉 {proc}\n"
                f"📅 Fecha: {fecha}\n"
                f"💭 Motivación: {motivacion}\n"
                f"📋 Eligió: {opcion}\n"
                f"📱 Tel: {tel}\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "🔥 LLAMAR AHORA — no esperar"
            )
            # WA al staff desactivado — notificaciones solo por CORE440 push
            print(f"[CX] URGENTE → push CORE440, turno NO avanza", flush=True)

        elif 'CALIENTE' in score or 'TIBIO' in score:
            # Asesora de turno + Sharon + Central. SÍ avanza turno.
            slug, label, asesora_phone = self._next_asesora(turno_canal)
            emoji = '🔥' if 'CALIENTE' in score else '🌡️'
            tag   = 'CALIENTE' if 'CALIENTE' in score else 'TIBIO'
            cta   = 'Contactar HOY 📞' if 'CALIENTE' in score else 'Seguimiento esta semana 📲'

            if 'CALIENTE' in score:
                msg_asesora = (
                    f"{emoji} LEAD {tag} CIRUGÍA — TE TOCA {label.upper()}\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 {nombre} ({ciudad})\n"
                    f"💉 {proc}\n"
                    f"📅 Fecha: {fecha}\n"
                    f"💭 Motivación: {motivacion}\n"
                    f"📋 Eligió: {opcion}\n"
                    f"📱 Tel: {tel}\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{cta}"
                )
            else:  # TIBIO
                msg_asesora = (
                    f"{emoji} LEAD {tag} CIRUGÍA — TE TOCA {label.upper()}\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 {nombre} ({ciudad})\n"
                    f"💉 {proc}\n"
                    f"📋 Eligió: {opcion}\n"
                    f"📱 Tel: {tel}\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{cta}"
                )
            msg_copia = (
                f"{emoji} LEAD {tag} CIRUGÍA — copia\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {nombre} · {proc}\n"
                f"📅 {fecha} · 📍 {ciudad}\n"
                f"💭 {motivacion}\n"
                f"📋 {opcion}\n"
                f"📱 {tel}\n"
                f"👩 Asignado a: {label}\n"
                "━━━━━━━━━━━━━━━━━━━"
            )
            # WA al staff desactivado — notificaciones solo por CORE440 push
            self._set_ultima_asesora(slug, turno_canal)
            _assigned_slug = slug
            print(f"[CX] {tag} → asesora={slug} turno avanzado (push CORE440)", flush=True)

        else:  # FRÍO
            # WA al staff desactivado — notificaciones solo por CORE440 push
            print(f"[CX] FRÍO → push CORE440, turno NO avanza", flush=True)

        sent = {k: (v.get('sent') if isinstance(v, dict) else v) for k, v in results.items()}
        print(f"[CX] notify_lead score={score} results={sent}", flush=True)

        # CRM: upsert en leads_comerciales (no rompe si falla)
        try:
            canal_crm = 'instagram' if 'instagram' in (canal or '').lower() else 'whatsapp'
            self._upsert_lead_comercial(
                nombre=nombre,
                telefono=tel,
                procedimiento=proc,
                canal=canal_crm,
                prioridad=score,
                ciudad=ciudad,
                observaciones=motivacion or '',
                asesora_asignada=_assigned_slug,
            )
        except Exception as e:
            print(f"[CX] upsert lead_comercial error: {e}", flush=True)
        self._push_core440_lead(nombre, _assigned_slug, canal_crm,
            temperatura=score, procedimiento=proc, ciudad=ciudad,
            fecha_disponible=fecha, tipo_atencion=(tipo or 'valoracion'), telefono=tel)
        return score

    @staticmethod
    def _normalizar_tel(tel):
        """Quita todo excepto dígitos: +1 954 740 1442 → 19547401442."""
        import re as _re
        return _re.sub(r'[^\d]', '', str(tel or ''))

    def _upsert_lead_comercial(self, nombre, telefono, procedimiento,
                                canal='whatsapp', prioridad='CALIENTE',
                                ciudad='', observaciones='', asesora_asignada=''):
        """INSERT en leads_comerciales del CRM (proyecto historia-clinica)."""
        import urllib.request, urllib.parse, json as _json
        from datetime import datetime as _dtt, timezone as _tzz
        telefono = self._normalizar_tel(telefono)
        crm_url = os.environ.get('SUPABASE_URL_CRM', '').rstrip('/')
        crm_key = os.environ.get('SUPABASE_KEY_CRM', '')
        if not crm_url or not crm_key or not telefono:
            print(f"[CX] CRM lead upsert skipped (envs/tel missing)", flush=True)
            return
        body = {
            'nombre': nombre or '—',
            'apellido': '',
            'telefono': telefono,
            'procedimiento_interes': procedimiento or '—',
            'como_llego': 'BOT440 — Cirugías',
            'categoria': 'quirurgico',
            'asesora_asignada': asesora_asignada if asesora_asignada in ('bibiana','vanessa','lucero') else None,

            'ciudad': ciudad or '',
            'observaciones': f"Prioridad: {prioridad} | Ciudad: {ciudad or '—'}"
                              + (f" | {observaciones}" if observaciones else ''),
            'etapa': 'lead',
            'score_bot': prioridad or None,
            'fecha_lead': _dtt.now(_tzz.utc).isoformat(),
        }
        url = f"{crm_url}/rest/v1/leads_comerciales?on_conflict=telefono"
        headers = {
            'apikey': crm_key,
            'Authorization': f'Bearer {crm_key}',
            'Content-Type': 'application/json',
            'Prefer': 'resolution=merge-duplicates,return=representation',
        }
        req = urllib.request.Request(url, data=_json.dumps(body).encode(),
                                      headers=headers, method='POST')
        lead_id_creado = None
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                print(f"[CX] CRM lead upsert → {r.status} tel={telefono}", flush=True)
                try:
                    rows = _json.loads(r.read().decode() or '[]')
                    if isinstance(rows, list) and rows:
                        lead_id_creado = rows[0].get('id')
                except Exception:
                    pass
        except Exception as e:
            print(f"[CX] CRM lead upsert err: {e}", flush=True)

        # Vincular conversaciones_440.lead_id ← lead recién creado (mismo proyecto Supabase).
        if lead_id_creado:
            tel = str(telefono)
            base = tel.lstrip('+')
            if base.startswith('57'):
                base = base[2:]
            cands = {tel, base, '57' + base, '+57' + base}
            try:
                ors = ','.join(f'contacto_telefono.eq.{urllib.parse.quote(c)}' for c in cands if c)
                upd_url = (f"{crm_url}/rest/v1/conversaciones_440"
                           f"?lead_id=is.null&or=({ors})")
                upd_req = urllib.request.Request(
                    upd_url, data=_json.dumps({'lead_id': lead_id_creado}).encode(),
                    headers={'apikey': crm_key, 'Authorization': f'Bearer {crm_key}',
                             'Content-Type': 'application/json', 'Prefer': 'return=minimal'},
                    method='PATCH')
                with urllib.request.urlopen(upd_req, timeout=5) as ur:
                    print(f"[CX] conversaciones lead_id link → {ur.status} lead={lead_id_creado}", flush=True)
            except Exception as e:
                print(f"[CX] conversaciones link err: {e}", flush=True)

    # ------------------------------------------------------------------
    # Flujo principal
    # ------------------------------------------------------------------
    def process(self, sender_id, sender_name, text, canal='cirugia', cuenta_receptora=None, send=True,
                media_url=None, media_tipo=None, media_caption=None):
        """Procesa el mensaje entrante.

        Args:
            send: Si True (default), envía la respuesta via Instagram/WhatsApp directamente.
                  Si False, NO envía — devuelve el texto de respuesta para que el caller lo envíe.
            media_url/media_tipo: si el entrante es una imagen ya re-hospedada en
                  Storage, se adjuntan a la PRIMERA fila entrante guardada (sin
                  duplicar). media_caption reemplaza el texto persistido (el
                  `text` sigue siendo '[IMAGEN]' para preservar la lógica del bot).
        Returns:
            str — texto visible al paciente (sin bloque NOTIFY). Vacío si no hay reply.
        """
        # Media entrante pendiente de adjuntar a la fila 'entrante' (one-shot).
        self._in_media_url = media_url
        self._in_media_tipo = media_tipo
        self._in_media_caption = media_caption
        print(f"[CX] canal={canal!r} send={send} cuenta={cuenta_receptora!r} {sender_id}: {text[:60]!r}", flush=True)

        # ── Seleccionar token/account de Instagram según cuenta_receptora ──
        # Guardar en self para que _save_message lo use sin tener que
        # propagar el parámetro en cada llamada interna.
        if cuenta_receptora:
            self._cuenta_receptora_activa = cuenta_receptora
        if cuenta_receptora in self._ig_accounts:
            _ig_token = self._ig_tokens.get(cuenta_receptora, '')
            _ig_account = self._ig_accounts.get(cuenta_receptora, '')
            if _ig_token and _ig_account:
                self.instagram = InstagramClient(token=_ig_token, account_id=_ig_account)

        # ── PAUSA MEDFILES: un humano ya tomó la conversación ───────────
        # Si alguien del equipo ya le escribió desde MedFiles, el bot se calla
        # (guarda el entrante y no responde). Solo WhatsApp (el sender_id es un
        # teléfono). Fail-open con timeout corto.
        if not self._es_canal_instagram(canal) and self._medfiles_pausado(sender_id):
            print(f"[CX] MedFiles pausado=True para {sender_id} — solo guardar entrante", flush=True)
            self._save_message(sender_id, sender_name, text, 'entrante', 'paciente', canal=canal)
            return ''

        # ── BOT PAUSADO (CRM viejo): guardar entrante y salir sin responder ─
        # Si la asesora marcó este lead como pausado desde el CRM, NO
        # invocamos a Claude ni respondemos — solo registramos el mensaje.
        # Con MedFiles como CRM, la pausa vieja ya no aplica (solo si CX_LEGACY_CRM=1).
        _lead_pause = self._check_lead_crm(sender_id) if _LEGACY_CRM else None
        if _lead_pause and _lead_pause.get('bot_pausado'):
            print(f"[CX] bot_pausado=True para {sender_id} — solo guardar entrante", flush=True)
            self._save_message(sender_id, sender_name, text, 'entrante', 'paciente', canal=canal)
            return ''

        # ── BOT BLOQUEADO: spam/abuso. Guardar entrante y salir silencioso.
        if self._check_bloqueado(sender_id):
            print(f"[CX] bot_bloqueado=True para {sender_id} — guardar entrante y silencio", flush=True)
            self._save_message(sender_id, sender_name, text, 'entrante', 'paciente', canal=canal)
            return ''

        # ── Mensajes especiales: [IMAGEN] / [STICKER] / [MEDIA] ─────────
        # IMAGEN = foto real → orientar al paciente sobre prediag/valoración
        #          (o pedirle guardar si ya agendó)
        # STICKER/REACCIÓN = ignorar si ya cerró, sino dejar pasar a Claude
        # MEDIA = audio/video/documento → mismo trato que IMAGEN
        _s_in = (text or '').strip()
        if _s_in in ('[IMAGEN]', '[STICKER]', '[MEDIA]'):
            self._save_message(sender_id, sender_name, text, 'entrante', 'paciente', canal=canal)

            # ── ANTI-RACE: si llegó texto + media casi simultáneos
            # (típico cuando el paciente saluda + manda foto al mismo
            # tiempo), dormir 2.5s y verificar si hay un mensaje
            # ENTRANTE de TEXTO real reciente del mismo sender. Si lo
            # hay, dejamos que esa otra invocación maneje la respuesta
            # (más rica que el menú de imágenes).
            time.sleep(2.5)
            try:
                _desde = (_dt.now(_tz.utc) - _td(seconds=8)).isoformat()
                _params = (f'contacto_telefono=eq.{urllib.parse.quote(sender_id)}'
                           f'&canal=eq.{urllib.parse.quote(canal)}'
                           f'&direccion=eq.entrante'
                           f'&created_at=gte.{urllib.parse.quote(_desde)}'
                           f'&select=mensaje,created_at&order=created_at.desc&limit=10')
                _url = f'{self.sb_url}/rest/v1/conversaciones_440?{_params}'
                _req = urllib.request.Request(_url, headers=self._sb_headers(), method='GET')
                with urllib.request.urlopen(_req, timeout=5) as _r:
                    _recientes = json.loads(_r.read()) or []
                for _row in _recientes:
                    _m = (_row.get('mensaje') or '').strip()
                    if _m and _m not in ('[MEDIA]', '[IMAGEN]', '[STICKER]'):
                        print(f"[CX] media abort — texto reciente '{_m[:40]}' del mismo sender, deja que text handler responda", flush=True)
                        return ''
            except Exception as _e:
                print(f"[CX] media abort check err: {_e}", flush=True)

            # Cargar contexto fresco (post-sleep) para detectar si ya
            # agendó o ya cerró, y extraer nombre del historial.
            _media_hist = self._load_history(sender_id, canal=canal)
            _nombre = self._extract_name_from_history(_media_hist, sender_name) or ''
            _saludo = f"¡Hola {_nombre}!" if _nombre else "¡Hola!"
            _hist_txt = ' '.join(
                m.get('content', '') if isinstance(m.get('content'), str) else ''
                for m in _media_hist
            ).lower()
            _ya_agendo = ('quedó agendado' in _hist_txt or 'quedo agendado' in _hist_txt
                          or 'tu prediagnóstico quedó' in _hist_txt
                          or 'prediagnóstico agendado' in _hist_txt
                          or '<<<notify>>>' in _hist_txt
                          or 'ya eres parte de #labelleza440' in _hist_txt)
            _lead = self._check_lead_crm(sender_id) or {}
            _etapa_ok = (_lead.get('etapa') or '').lower() in (
                'prediagnostico', 'consulta_agendada', 'pago_consulta',
                'en_consulta', 'vendido', 'servicio_programado', 'completado')
            _agendado = _ya_agendo or _etapa_ok

            # CASO B — STICKER/REACCIÓN
            if _s_in == '[STICKER]':
                if _agendado:
                    # Ya cerró / agendó → no responder, solo guardar
                    print(f"[CX] [STICKER] tras agendamiento — silencio", flush=True)
                    return ''
                # Sino: continuar el flujo normal (no responder menú de imágenes)
                # Reemplazamos por un placeholder ligero para que Claude vea algo
                # natural sin romper el flujo.
                text = '👍'
                _s_in = '👍'
                # Sigue al flujo principal de Claude más abajo
            else:
                # CASO A/C — IMAGEN o MEDIA
                if _agendado:
                    reply = (
                        f"{_saludo} 💙\n"
                        "Nuestra asesora ya tiene tus datos y te escribirá muy pronto 😊\n"
                        "Guarda tus imágenes para mostrárselas ✨"
                    )
                else:
                    reply = (
                        f"{_saludo} 💙 Por aquí no puedo evaluar imágenes, pero tu caso "
                        "lo pueden revisar contigo:\n\n"
                        "✅ *Asesoría virtual gratuita* 💻\n"
                        "Con nuestra asesora experta, por videollamada y sin compromiso.\n\n"
                        "✅ *Valoración con el Dr. Gio* 👨‍⚕️\n"
                        "Presencial *$260.000* · Virtual *$160.000*.\n\n"
                        "¿Cuál te gustaría? 😊"
                    )
                if send:
                    client = self.instagram if canal.startswith('instagram') else self.whapi
                    try: client.send_text(sender_id, reply)
                    except Exception as e: print(f"[CX] media reply send err: {e}", flush=True)
                self._save_message(sender_id, sender_name, reply, 'saliente', 'bot', canal=canal)
                return reply
        history = self._load_history(sender_id, canal=canal)
        _is_first_time = len(history) == 0

        # ── DETECCIÓN MAMOPLASTIA TODO INCLUIDO ────────────────────────────
        # Si el PRIMER mensaje menciona "todo incluido", "mamoplastia incluido",
        # "senos incluido", "18 millones", responder con el paquete específico
        # y NO dejar que Claude responda genérico.
        if _is_first_time:
            _txt_mamo = (text or '').lower()
            for _old_c, _new_c in [('á','a'),('é','e'),('í','i'),('ó','o'),('ú','u'),('ü','u'),('ñ','n')]:
                _txt_mamo = _txt_mamo.replace(_old_c, _new_c)
            _is_mamo_todo = any(kw in _txt_mamo for kw in _PAUTA_MAMO_KW)
            if _is_mamo_todo:
                print(f"[CX] MAMOPLASTIA TODO INCLUIDO detectado → {sender_id}: {text[:60]!r}", flush=True)
                reply = (
                    "¡Hola! 💙 Bienvenida al *Centro de Atención del Dr. Giovanni Fuentes*. "
                    "Te atiende el asistente virtual del Dr. Gio 🤖\n\n"
                    "Nuestra *Mamoplastia de Aumento Todo Incluido* tiene un valor de *$18.000.000* ✨ Incluye:\n"
                    "✅ Cirugía con el Dr. Giovanni Fuentes, cirujano plástico certificado\n"
                    "✅ Clínica certificada\n"
                    "✅ Anestesiólogo\n"
                    "✅ Póliza de seguro\n"
                    "✅ Implantes Silimed Eurosilicone\n"
                    "✅ Brasier postquirúrgico\n"
                    "✅ 5 drenajes linfáticos\n"
                    "📍 Disponible en *Barranquilla, Bogotá y Medellín*, con sede de recuperación en cada ciudad.\n\n"
                    "¿Tienes alguna *pregunta o duda* que te pueda resolver antes de dar el siguiente paso? 😊\n\n"
                    "Tu siguiente paso puede ser:\n\n"
                    "✅ *Asesoría virtual gratuita* 💻\n"
                    "Con nuestra asesora experta, por videollamada y sin compromiso. "
                    "*Ampliamos la información* y resolvemos todas tus dudas.\n\n"
                    "✅ *Valoración con el Dr. Gio* 👨‍⚕️\n"
                    "Presencial *$260.000* · Virtual *$160.000*. El Dr. *evalúa tu caso* personalmente.\n\n"
                    "✨ *#LAbelleza440* · _La perfecta armonía de tu cuerpo_ ✨"
                )
                self._save_message(sender_id, sender_name, text, 'entrante', 'paciente', canal=canal)
                if send:
                    _client = self.instagram if canal.startswith('instagram') else self.whapi
                    try: _client.send_text(sender_id, reply)
                    except Exception as _e: print(f"[CX] mamo todo reply err: {_e}", flush=True)
                self._save_message(sender_id, sender_name, reply, 'saliente', 'bot', canal=canal)
                # Flujo nuevo: el lead se crea en MedFiles solo cuando el
                # paciente deja sus datos (pauta se detecta del historial).
                if _LEGACY_CRM:
                    _mamo_canal_crm = 'instagram' if 'instagram' in (canal or '').lower() else 'whatsapp'
                    try:
                        self._upsert_lead_comercial(
                            nombre=sender_name or '—', telefono=self._normalizar_tel(sender_id),
                            procedimiento='Mamoplastia de aumento todo incluido',
                            canal=_mamo_canal_crm, prioridad='CALIENTE',
                            observaciones='Lead de pauta Mamoplastia Todo Incluido $18M — respuesta automática enviada',
                        )
                    except Exception as _e:
                        print(f"[CX] mamo todo upsert err: {_e}", flush=True)
                return reply

        # ── DETECCIÓN DE REFERIDO ──────────────────────────────────────────
        # Si el PRIMER mensaje menciona el nombre de una asesora, la asignamos
        # directamente (sin pasar por la rotación).
        # LEGACY: el flujo nuevo tiene una sola asesora (MedFiles asigna).
        if _LEGACY_CRM and _is_first_time:
            _txt_ref = (text or '').lower()
            for _old_c, _new_c in [('á','a'),('é','e'),('í','i'),('ó','o'),('ú','u'),('ü','u'),('ñ','n')]:
                _txt_ref = _txt_ref.replace(_old_c, _new_c)
            _referido_slug = ''
            for _slug in ('bibiana', 'lucero', 'vanessa'):
                if _slug in _txt_ref:
                    _referido_slug = _slug
                    break
            if _referido_slug:
                _ref_label = ASESORA_LABEL.get(_referido_slug, _referido_slug.capitalize())
                print(f"[CX] REFERIDO detectado → asesora={_referido_slug} texto={text[:60]!r}", flush=True)
                reply = (
                    f"¡Hola! Gracias por contactarnos 🎉\n"
                    f"Te vamos a conectar con {_ref_label}\n"
                    "quien te atenderá muy pronto ✨\n"
                    "La Belleza 440 ✨"
                )
                self._save_message(sender_id, sender_name, text, 'entrante', 'paciente', canal=canal)
                if send:
                    _client = self.instagram if canal.startswith('instagram') else self.whapi
                    try: _client.send_text(sender_id, reply)
                    except Exception as _e: print(f"[CX] referido reply err: {_e}", flush=True)
                self._save_message(sender_id, sender_name, reply, 'saliente', 'bot', canal=canal)
                # Notificar a la asesora del referido (+ Sharon + Admin + Dr. Gio)
                _ref_phone = os.environ.get(ASESORA_ENV.get(_referido_slug, ''), '').strip()
                _ref_sharon = os.environ.get('DRA_SHARON', '').strip()
                _ref_admin  = os.environ.get('ADMIN_CX', '').strip()
                _ref_drgio  = os.environ.get('DRGIO_TEL', '573181800131').strip()
                _ref_msg = (
                    f"🎁 REFERIDO DIRECTO — {_ref_label.upper()}\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"📱 Tel: {sender_id}\n"
                    f"💬 Mensaje: {text[:120]}\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"Este lead te mencionó a ti 💙\n"
                    "Asignado directamente sin rotación."
                )
                for _rt in (_ref_phone, _ref_sharon, _ref_admin, _ref_drgio):
                    if not _rt: continue
                    try: self.whapi.send_text(_rt, _ref_msg)
                    except Exception as _e: print(f"[CX] referido notify {_rt} err: {_e}", flush=True)
                # CRM upsert con la asesora asignada directamente
                _ref_canal_crm = 'instagram' if 'instagram' in (canal or '').lower() else 'whatsapp'
                _ref_tel_norm = self._normalizar_tel(sender_id)
                try:
                    self._upsert_lead_comercial(
                        nombre='—', telefono=_ref_tel_norm,
                        procedimiento='—', canal=_ref_canal_crm,
                        prioridad='CALIENTE',
                        observaciones=f"Referido por {_ref_label} — primer mensaje: {text[:80]}",
                        asesora_asignada=_referido_slug,
                    )
                except Exception as _e:
                    print(f"[CX] referido upsert err: {_e}", flush=True)
                # Push CORE440
                self._push_core440_lead(
                    '—', _referido_slug, _ref_canal_crm,
                    temperatura='caliente', tipo_atencion='referido', telefono=sender_id,
                )
                return reply

        # Detectar si el paciente regresa después de 4+ horas mirando el
        # created_at del último mensaje en conversaciones_440.
        ultima_interaccion = None
        if history and self.sb_url and self.sb_key:
            try:
                _u_url = (f'{self.sb_url}/rest/v1/conversaciones_440?'
                          f'contacto_telefono=eq.{urllib.parse.quote(sender_id)}'
                          f'&canal=eq.{urllib.parse.quote(canal)}'
                          f'&select=created_at&order=created_at.desc&limit=1')
                _req = urllib.request.Request(_u_url, headers=self._sb_headers(), method='GET')
                with urllib.request.urlopen(_req, timeout=5) as r:
                    _rows = json.loads(r.read())
                if _rows and _rows[0].get('created_at'):
                    _raw = _rows[0]['created_at'].replace('Z', '+00:00')
                    ultima_interaccion = _dt.fromisoformat(_raw)
                    if ultima_interaccion.tzinfo is None:
                        ultima_interaccion = ultima_interaccion.replace(tzinfo=_tz.utc)
            except Exception as e:
                print(f"[CX] ultima_interaccion err: {e}", flush=True)
                ultima_interaccion = None

        es_regreso = False
        if ultima_interaccion:
            if _dt.now(_tz.utc) - ultima_interaccion > _td(hours=4):
                es_regreso = True

        # Paciente recurrente — lookup si es first-time o regreso.
        paciente = (self._check_paciente_recurrente(sender_id)
                    if (_is_first_time or es_regreso) else None)
        paciente_ctx = ''
        if es_regreso and paciente:
            _nombre = paciente.get('nombre') or ''
            _servicios = paciente.get('servicios_interes') or []
            _servicio = _servicios[0] if isinstance(_servicios, list) and _servicios else (_servicios or '')
            paciente_ctx = (
                "\n\n[SISTEMA — PACIENTE QUE REGRESA]\n"
                f"Nombre: {_nombre or '—'}\n"
                f"Último servicio de interés: {_servicio or '—'}\n"
                "→ NO uses la bienvenida completa.\n"
                "→ Saluda con:\n\n"
                f"  '¡Hola{' ' + _nombre if _nombre else ''}! 💙\n"
                "   Qué bueno verte de nuevo 😊\n"
                "   ¿En qué te puedo ayudar hoy?'\n\n"
                "→ Luego espera la respuesta.\n"
                "→ NO repitas el flujo completo."
            )
            _is_first_time = False
            print("[CX] paciente regresa (>4h, history no vacío) — saludo corto", flush=True)

        # Regreso (>4h) de un lead NO registrado: retomar el tema del historial.
        elif es_regreso and not paciente:
            paciente_ctx = (
                "\n\n[SISTEMA — PACIENTE QUE REGRESA (>4h)]\n"
                "Lee el HISTORIAL y detecta el último procedimiento o tema de\n"
                "interés del paciente. Saluda y RETOMA ese tema:\n"
                "  '¡Hola [nombre]! 💙 Qué bueno que volviste 😊\n"
                "   La última vez hablamos sobre [procedimiento/tema].\n"
                "   ¿Sigues interesad@ en eso o tienes alguna nueva consulta? 💙'\n"
                "Si NO puedes detectar el tema en el historial, usa:\n"
                "  '¡Hola [nombre]! 💙 Qué bueno que volviste 😊\n"
                "   ¿En qué puedo ayudarte hoy?'\n"
                "→ NO repitas la bienvenida completa. Usa el nombre si lo conoces."
            )
            _is_first_time = False
            print("[CX] lead no registrado regresa (>4h) — retomar tema del historial", flush=True)

        # ── PACIENTE RECURRENTE CON ASESORA ASIGNADA (>4h) — LEGACY CRM ──
        if _LEGACY_CRM and es_regreso:
            _lead_crm = self._check_lead_crm(sender_id)
            _asesora_lead = ((_lead_crm or {}).get('asesora_asignada') or '').strip().lower()
            if _lead_crm and _asesora_lead:
                _nombre_l = (_lead_crm.get('nombre') or (paciente.get('nombre') if paciente else '')) or ''
                if not _nombre_l or not any(c.isalpha() for c in _nombre_l):
                    _nombre_l = ''
                _proc_l   = _lead_crm.get('procedimiento_interes') or '—'
                _etapa_l  = _lead_crm.get('etapa') or 'lead'
                _asesora_label = ASESORA_LABEL.get(_asesora_lead, _asesora_lead.capitalize())
                # Notificar al staff UNA vez (la asesora queda enterada del regreso).
                if not self._already_notified_cx(sender_id, canal):
                    notify_msg = (
                        "🔄 PACIENTE RECURRENTE\n"
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 {_nombre_l or '—'}\n"
                        f"📱 Tel: {sender_id}\n"
                        f"💉 Servicio: {_proc_l}\n"
                        f"📊 Etapa: {_etapa_l}\n"
                        f"👩 Asesora: {_asesora_label}\n"
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        "Paciente regresa — tiene asesora asignada 💙"
                    )
                    _asesora_phone = os.environ.get(ASESORA_ENV.get(_asesora_lead, ''), '').strip()
                    sharon = os.environ.get('DRA_SHARON', '').strip()
                    admin  = os.environ.get('ADMIN_CX', '').strip()
                    drgio  = os.environ.get('DRGIO_TEL', '573181800131').strip()
                    for _tel in (_asesora_phone, sharon, admin, drgio):
                        if not _tel: continue
                        try: self.whapi.send_text(_tel, notify_msg)
                        except Exception as e:
                            print(f"[CX] recurrente notify {_tel} err: {e}", flush=True)
                    self._save_message(sender_id, sender_name,
                                       "<<<NOTIFY>>>tipo: recurrente<<<END>>>",
                                       'saliente', 'bot', canal=canal)
                    print(f"[CX] PACIENTE RECURRENTE NOTIFY enviado", flush=True)
                else:
                    print(f"[CX] PACIENTE RECURRENTE — ya notificado <24h, skip", flush=True)
                # NO cortar: el bot retoma la conversación normalmente mientras
                # la asesora responde (ya fue notificada arriba).
                paciente_ctx += (
                    "\n\n[SISTEMA — LEAD CON ASESORA ASIGNADA]\n"
                    f"Su asesora ({_asesora_label}) YA fue notificada de su regreso.\n"
                    "Retoma la conversación normalmente y sigue ayudando al\n"
                    "paciente (resuelve dudas, retoma su tema de interés). Puedes\n"
                    "mencionar que su asesora ya está al tanto y le escribirá pronto,\n"
                    "pero NO cierres la conversación ni te limites a 'te contactará'."
                )

        # ── BUG 1: saludo genérico con historial existente <4h ──────────
        _low_in = (_s_in or '').lower().rstrip('.!?¿,. ')
        _greetings = {'hola','holi','holiwi','holaa','holaaa','hi','hey',
                      'buenas','buen dia','buen día','buenos dias','buenos días',
                      'buenas tardes','buenas noches','que tal','qué tal',
                      'saludos','ola'}
        if history and not es_regreso and _low_in in _greetings:
            # BUG A fix: cargar paciente aquí si no se cargó arriba.
            if paciente is None:
                paciente = self._check_paciente_recurrente(sender_id)
            _nombre_p = (paciente.get('nombre') if paciente else '') or ''
            if not _nombre_p or not any(c.isalpha() for c in _nombre_p):
                _nombre_p = ''
            _ya_lead = any(m.get('role') == 'assistant' and isinstance(m.get('content'), str)
                           and '<<<NOTIFY>>>' in m['content'] and 'urgencia' not in m['content'].lower()
                           for m in history)
            if _ya_lead:
                reply = (f"¡Hola, {_nombre_p}! 💙 " if _nombre_p else "¡Hola! 💙 ") + \
                        "Nuestra asesora ya tiene tus datos y te escribirá muy pronto 😊"
            else:
                reply = (f"¡Hola de nuevo {_nombre_p}! 💙\n¿En qué más te puedo ayudar? 😊"
                         if _nombre_p else
                         "¡Hola de nuevo! 💙\n¿En qué más te puedo ayudar? 😊")
            self._save_message(sender_id, sender_name, text, 'entrante', 'paciente', canal=canal)
            if send:
                client = self.instagram if canal.startswith('instagram') else self.whapi
                try: client.send_text(sender_id, reply)
                except Exception as e: print(f"[CX] greeting reply err: {e}", flush=True)
            self._save_message(sender_id, sender_name, reply, 'saliente', 'bot', canal=canal)
            print(f"[CX] BUG1 — saludo corto (history existe, <4h)", flush=True)
            return reply

        # ── BUG 2: bot pidió nombre y paciente respondió solo emojis ────
        if _s_in and _is_emoji_only_cx(_s_in):
            _last_bot = ''
            for _m in reversed(history):
                if _m.get('role') == 'assistant':
                    _last_bot = (_m.get('content') or '').lower()
                    break
            if 'nombre' in _last_bot and ('?' in _last_bot or 'cuál' in _last_bot or 'cual' in _last_bot or 'cómo' in _last_bot or 'como te llamas' in _last_bot):
                reply = "¡Gracias! 💙\n¿Me puedes decir tu nombre? 😊"
                self._save_message(sender_id, sender_name, text, 'entrante', 'paciente', canal=canal)
                if send:
                    client = self.instagram if canal.startswith('instagram') else self.whapi
                    try: client.send_text(sender_id, reply)
                    except Exception as e: print(f"[CX] name re-ask err: {e}", flush=True)
                self._save_message(sender_id, sender_name, reply, 'saliente', 'bot', canal=canal)
                print(f"[CX] BUG2 — emoji como nombre, re-preguntando", flush=True)
                return reply
            print(f"[CX] emoji-only {text!r} → tratando como 'Sí'", flush=True)
            text = 'Sí'

        # Siempre expone el sender_id en el prefijo para que Claude lo use en NOTIFY.
        # Formato: [sender_id|sender_name] si hay nombre, [sender_id] si no.
        # En Instagram el sender_id es un IGSID (no teléfono) → el bot debe pedir tel.
        if sender_name:
            user_content = f"[{sender_id}|{sender_name}]: {text}"
        else:
            user_content = f"[{sender_id}]: {text}"
        history.append({'role': 'user', 'content': user_content})

        self._save_message(sender_id, sender_name, text, 'entrante', 'paciente', canal=canal)

        # Guardar / actualizar paciente. nombre se extrae de la conversación
        # cuando el bot acaba de pedirlo; sender_name (WhatsApp profile) solo
        # se usa como fallback y descartado si es emoji / sin letras.
        _email_m = re.search(
            r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
        _nombre_real = (self._extract_name_from_turn(history, text)
                        or self._safe_sender_name(sender_name))
        # Sexo: detectado de la conversación, o el ya guardado del paciente.
        _sexo = self._detect_sexo(history, text)
        if not _sexo and paciente:
            _sexo = (paciente.get('sexo') or '').strip().lower() or ''
        self._upsert_paciente(
            sender_id, nombre=_nombre_real,
            email=_email_m.group(0) if _email_m else None,
            canal=canal, servicio='Cirugía Plástica',
            sexo=_sexo or None)

        # ── Anamnesis condicionada por sexo ──────────────────────────────
        # Si sabemos que el paciente es HOMBRE, instruir al modelo a NO
        # preguntar "¿Has tenido hijos?" ni asumir embarazo/cesáreas, y a
        # usar el árbol de preguntas adecuado para hombres.
        if _sexo == 'hombre':
            paciente_ctx += (
                "\n\n[SISTEMA — SEXO DEL PACIENTE: HOMBRE]\n"
                "El paciente es HOMBRE: usa 'listo', 'bienvenido'. NO asumas "
                "embarazos, cesáreas ni lactancia al explicar procedimientos."
            )
            print("[CX] paciente HOMBRE", flush=True)
        elif _sexo == 'mujer':
            paciente_ctx += (
                "\n\n[SISTEMA — SEXO DEL PACIENTE: MUJER]\n"
                "La paciente es MUJER: usa 'lista', 'bienvenida'."
            )

        # ── Canal Instagram: el sender_id NO es teléfono ────────────────
        if self._es_canal_instagram(canal):
            paciente_ctx += (
                "\n\n[SISTEMA — CANAL INSTAGRAM]\n"
                "El número del prefijo es un ID de Instagram, NO un teléfono. "
                "Al pedir los datos (opción 1 o 2) pide también su número de "
                "WhatsApp para que la asesora lo contacte, y ponlo en 'telefono' "
                "del NOTIFY. Aquí sí puedes decir 'WhatsApp' para pedir el número."
            )

        # ── Lead ya enviado a la asesora (NOTIFY previo en el historial) ──
        if any(m.get('role') == 'assistant' and isinstance(m.get('content'), str)
               and '<<<NOTIFY>>>' in m['content'] and 'urgencia' not in m['content'].lower()
               for m in history[:-1]):
            paciente_ctx += (
                "\n\n[SISTEMA — LEAD YA ENVIADO A LA ASESORA]\n"
                "Este paciente YA dejó sus datos y la asesora los tiene. NO "
                "vuelvas a pedir datos ni emitas <<<NOTIFY>>>. Responde: "
                "'¡Hola, [nombre]! 💙 Nuestra asesora ya tiene tus datos y te "
                "escribirá muy pronto 😊' y resuelve dudas cortas si las tiene."
            )

        # ── PASO C/D: forzar check_slots_cx para evitar alucinación ──────────
        # Claude tiende a inventar slots en lugar de llamar al tool.
        # Detectamos los pasos de agendamiento en Python y forzamos la llamada.
        _forced_slots = None  # se pasa a _call_claude para que genere <<<SLOTS>>>

        def _inject_tool_result(h, tool_name, tool_input, result):
            """Inyecta un exchange tool_use/tool_result al final de h."""
            _tid = f'forced_{tool_name}_{len(h)}'
            h.append({'role': 'assistant', 'content': [
                {'type': 'tool_use', 'id': _tid, 'name': tool_name, 'input': tool_input}
            ]})
            h.append({'role': 'user', 'content': [
                {'type': 'tool_result', 'tool_use_id': _tid,
                 'content': json.dumps(result, ensure_ascii=False)}
            ]})

        _user_lower = text.strip().lower()
        _last_bot = ''
        for _m in reversed(history[:-1]):
            if _m['role'] == 'assistant':
                _c = _m.get('content', '')
                if isinstance(_c, str):
                    _last_bot = _c
                break

        # ── PASO C: usuario da email → forzar check_slots_cx sin dia (elegir_dia)
        # NOTA: 'no tengo correo' YA NO se trata como has_email — ahora
        # Claude debe seguir el flujo "Sin correo no puedo agendarte" del
        # CX_SYSTEM y ofrecer 2 alternativas (seguir por chat / asesora).
        _EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
        _asking_email = ('correo' in _last_bot.lower() or 'email' in _last_bot.lower() or
                         'gmail' in _last_bot.lower() or 'mail' in _last_bot.lower())
        _has_email = bool(_EMAIL_RE.search(text))
        if False and _has_email and _asking_email:  # PREDIAG sin agenda — atajo DESACTIVADO
            _asesora_slug, _, _ = self._next_asesora('cirugia_prediag')  # peek siguiente (no persiste)
            print(f"[CX] PASO C detectado → force check_slots_cx (elegir_dia) asesora={_asesora_slug!r}", flush=True)
            _dias_result = self._check_slots_cx(asesora=_asesora_slug, sender_id=sender_id, preferencia='proximo')
            if isinstance(_dias_result, dict) and _dias_result.get('paso') == 'elegir_dia':
                _inject_tool_result(
                    history, 'check_slots_cx',
                    {'preferencia': 'proximo', 'sender_id': sender_id},
                    _dias_result
                )
                print(f"[CX] PASO C: inyectados días reales asesora={_asesora_slug!r}", flush=True)

        # ── PASO D: usuario elige jornada → forzar check_slots_cx con dia+jornada
        _JORNADA_WORDS = {'manana', 'mañana', 'tarde', 'morning', 'afternoon'}
        if False and _user_lower in _JORNADA_WORDS:  # PREDIAG sin agenda — atajo DESACTIVADO
            _jornada = 'tarde' if 'tarde' in _user_lower else 'manana'
            _asking_jornada = (('mañana' in _last_bot or 'tarde' in _last_bot) and
                               ('☀️' in _last_bot or '🌙' in _last_bot))
            if _asking_jornada:
                # Extraer dia del historial (buscar en mensajes del usuario)
                _dia = ''
                _dia_words = ['lunes','martes','miercoles','miércoles','jueves','viernes','sabado','sábado']
                for _m in reversed(history[:-1]):
                    if _dia:
                        break
                    if _m['role'] == 'user':
                        _c = _m.get('content','')
                        for _dw in _dia_words:
                            if _dw in _c.lower():
                                _match = re.search(rf'({_dw}[a-záéíóú]*\s+\d+)', _c.lower())
                                if _match:
                                    _dia = _match.group(1)
                                    break
                # Asesora: usar la que está actualmente asignada (sin avanzar)
                _asesora_d = self._next_asesora('cirugia_prediag')[0] or ''
                if _dia and _asesora_d:
                    print(f"[CX] PASO D detectado → force check_slots_cx dia={_dia!r} jornada={_jornada!r} asesora={_asesora_d!r}", flush=True)
                    _slots_result = self._check_slots_cx(
                        asesora=_asesora_d, sender_id=sender_id,
                        preferencia='proximo', dia=_dia, jornada=_jornada
                    )
                    _slots = _slots_result.get('slots', []) if isinstance(_slots_result, dict) else []
                    if _slots:
                        _inject_tool_result(
                            history, 'check_slots_cx',
                            {'preferencia': 'proximo', 'sender_id': sender_id, 'dia': _dia, 'jornada': _jornada},
                            _slots_result
                        )
                        _forced_slots = _slots
                        print(f"[CX] PASO D: inyectados {len(_slots)} slots reales en historial", flush=True)
                    else:
                        print(f"[CX] PASO D: n8n devolvió slots vacíos para {_asesora_d!r} {_dia!r} {_jornada!r}", flush=True)

        # ── PASO E: forzar create_event_cx cuando el paciente elige slot ──
        # Buscar último mensaje del bot que contenga <<<SLOTS>>>
        _slots_in_hist = ''
        for _m in reversed(history[:-1]):
            if _m.get('role') == 'assistant':
                _c = _m.get('content', '')
                if isinstance(_c, str) and '<<<SLOTS>>>' in _c:
                    _slots_in_hist = _c
                    break
        if False and _slots_in_hist and not _forced_slots:  # sin agenda — DESACTIVADO
            _slots_dict = {}
            for _ln in _slots_in_hist.splitlines():
                _mm = re.match(r'slot_(\d+):\s*(\{.*\})', _ln.strip())
                if _mm:
                    try:
                        _slots_dict[int(_mm.group(1))] = json.loads(_mm.group(2))
                    except Exception:
                        pass
            _chosen_n = None
            _num_clean = _user_lower.rstrip('.!,').replace('️⃣', '').strip()
            _word_map = {'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5,
                         '1': 1, '2': 2, '3': 3, '4': 4, '5': 5}
            if _num_clean in _word_map:
                _chosen_n = _word_map[_num_clean]
            else:
                for _k, _s in _slots_dict.items():
                    _lbl = (_s.get('slot_label') or _s.get('label') or '').lower()
                    if _lbl and _num_clean and _num_clean in _lbl:
                        _chosen_n = _k
                        break
                # Fallback: el paciente escribió una hora como "4 pm",
                # "4:00 pm", "4:30", "16:00". Detectarla y comparar con
                # los labels de los slots ("Lunes 25 may · 4:00 PM").
                if _chosen_n is None:
                    _time_m = re.match(
                        r'^(?:a\s+las\s+)?(\d{1,2})(?::(\d{2}))?\s*'
                        r'(a\.?m\.?|p\.?m\.?|am|pm)?\.?$',
                        _num_clean)
                    if _time_m:
                        _h = int(_time_m.group(1))
                        _mm = _time_m.group(2)
                        _ap = (_time_m.group(3) or '').replace('.', '').lower()
                        # 24h → 12h si aplica
                        if _h > 12 and not _ap:
                            _ap, _h = 'pm', _h - 12
                        _needle = f"{_h}:{_mm}" if _mm else f"{_h}:"
                        for _k, _s in _slots_dict.items():
                            _lbl = (_s.get('slot_label') or _s.get('label') or '').lower()
                            if _needle not in _lbl:
                                continue
                            if _ap:
                                _ap_norm = 'am' if _ap.startswith('a') else 'pm'
                                if _ap_norm not in _lbl:
                                    continue
                            _chosen_n = _k
                            print(f"[CX] PASO E: match hora {_num_clean!r} → slot {_k} ({_lbl!r})", flush=True)
                            break
            if _chosen_n and _chosen_n in _slots_dict:
                _slot = _slots_dict[_chosen_n]
                _hist_text = ' '.join(
                    m.get('content', '') if isinstance(m.get('content'), str) else ''
                    for m in history)
                _email_m = re.search(
                    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
                    _hist_text)
                _email_p = _email_m.group(0) if _email_m else ''
                _asesora_slot = _slot.get('esteticista') or _slot.get('asesora') or ''
                print(f"[CX] PASO E detectado → force create_event_cx "
                      f"slot={_chosen_n} asesora={_asesora_slot!r} "
                      f"iso_start={_slot.get('iso_start','')!r}", flush=True)
                _ce_result = self._create_event_cx(
                    asesora=_asesora_slot,
                    slot_id=str(_chosen_n),
                    slot_label=_slot.get('slot_label') or _slot.get('label') or '',
                    iso_start=_slot.get('iso_start', ''),
                    iso_end=_slot.get('iso_end', ''),
                    sender_id=sender_id,
                    sender_name=sender_name or '',
                    correo_paciente=_email_p,
                )
                _inject_tool_result(
                    history, 'create_event_cx',
                    {'slot_id': str(_chosen_n),
                     'iso_start': _slot.get('iso_start', ''),
                     'iso_end': _slot.get('iso_end', ''),
                     'asesora': _asesora_slot,
                     'correo_paciente': _email_p},
                    _ce_result,
                )
                _ml = _ce_result.get('meet_link', '') if isinstance(_ce_result, dict) else ''
                print(f"[CX] PASO E: inyectado tool_result de create_event_cx "
                      f"meet_link={_ml!r}", flush=True)

        # ── FIX 2: si el paciente eligió prediagnóstico pero NO ha dado
        # correo, forzar que el bot lo pida ANTES de mostrar días/slots. ──
        _hist_str = ' '.join(
            m.get('content', '') if isinstance(m.get('content'), str) else ''
            for m in history)
        _has_prediag_intent = bool(re.search(
            r'prediagn[oó]stico\s*(gratuito|gratis)?', _hist_str, re.IGNORECASE))
        _has_email_in_hist = bool(re.search(
            r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', _hist_str))
        if False:  # FIX 2 neutralizado — nuevo flujo califica presupuesto (no pide correo)
            paciente_ctx += (
                "\n\n[SISTEMA — REGLA RUNTIME]:\n"
                "El paciente eligió el prediagnóstico GRATUITO pero "
                "todavía NO ha dado su correo electrónico. ANTES de "
                "mostrar días, llamar check_slots_cx o anunciar "
                "horarios, pregunta SIEMPRE primero con este texto:\n"
                "'¡Perfecto! 💙 Antes de mostrarte los horarios "
                "disponibles, ¿cuál es tu correo electrónico para "
                "enviarte la confirmación y el link de tu "
                "videollamada? 📧 (Escribe tu correo o no tengo)'\n"
                "NO muestres días sin el correo."
            )
            print("[CX] FIX2 — sin correo aún, inyectada instrucción "
                  "para pedirlo antes de slots", flush=True)

        # ── STATE MACHINE — esperando_eleccion (valoración con Dr. Gio) ──
        # Si la conversación indica que el paciente eligió valoración
        # (opciones 1/2 con precio en CALIENTE/URGENTE o 2/3 en TIBIO),
        # Python genera el cierre + NOTIFY tipo=valoracion directamente
        # sin invocar a Claude.
        # DESACTIVADO en el flujo nuevo: la valoración también pide nombre,
        # ciudad, correo y modalidad antes del cierre (lo maneja el prompt).
        _bypass_text = None
        if _bypass_text is not None:
            print("[CX] state=esperando_eleccion (valoracion) — "
                  "bypass aplicado", flush=True)
            return _bypass_text

        # ── CONTROL DE PASOS: el código decide el paso y le dice a la IA qué escribir ──
        try:
            _paso = decidir_paso(history, text)
        except Exception as _e:
            print(f"[CX] decidir_paso err: {_e}", flush=True)
            _paso = {'paso': 'libre'}
        print(f"[CX] paso={_paso}", flush=True)
        paciente_ctx += instruccion_paso(_paso)

        full_response = self._call_claude(history, sender_id=sender_id, sender_name=sender_name or '',
                                         forced_slots=_forced_slots, paciente_ctx=paciente_ctx)
        print(f"[CX] Claude len={len(full_response)} preview={full_response[:80]!r}", flush=True)

        # ── INTERCEPTAR <<<BLOQUEAR>>>: spam/abuso detectado por Claude ──
        if '<<<BLOQUEAR>>>' in full_response:
            print(f"[CX] <<<BLOQUEAR>>> detectado para {sender_id} — despedida + bloqueo 24h", flush=True)
            despedida = (
                "Gracias por escribirnos 💙\n"
                "En este espacio solo podemos ayudarte con temas "
                "relacionados con nuestros servicios médicos y estéticos.\n\n"
                "Si en algún momento deseas información sobre nuestros "
                "tratamientos, con gusto te atendemos 😊\n\n"
                "¡Que tengas un excelente día!\n"
                "Centro de Atención del Dr. Giovanni Fuentes"
            )
            if send:
                client = self.instagram if canal.startswith('instagram') else self.whapi
                try: client.send_text(sender_id, despedida)
                except Exception as e: print(f"[CX] despedida send err: {e}", flush=True)
            self._save_message(sender_id, sender_name, despedida, 'saliente', 'bot', canal=canal)
            self._set_bloqueado(sender_id, razon='Contenido inapropiado/spam', hours=24)
            return despedida

        # NOTIFY block
        notify = None
        match = re.search(r'<<<NOTIFY>>>(.*?)<<<END>>>', full_response, re.DOTALL)
        if match:
            notify = match.group(1).strip()

        # Texto visible al paciente — sin bloque NOTIFY ni <<<SLOTS>>>
        # (<<<SLOTS>>> se queda en full_response que se guarda en Supabase)
        user_facing = re.sub(r'<<<NOTIFY>>>.*?<<<END>>>', '', full_response, flags=re.DOTALL)
        user_facing = re.sub(r'<<<SLOTS>>>.*?<<<END_SLOTS>>>', '', user_facing, flags=re.DOTALL)
        user_facing = re.sub(r'\n{3,}', '\n\n', user_facing).strip()
        user_facing = ajustar_respuesta_cx(user_facing, history, text)
        if not match:
            try:
                user_facing = aplicar_paso(user_facing, _paso, history, text)
            except Exception as _e:
                print(f"[CX] aplicar_paso err: {_e}", flush=True)
        # Despedida fija cuando deja sus datos (texto aprobado por el Dr.)
        if match:
            try:
                _f = self._parse_notify(match.group(1)) or {}
            except Exception:
                _f = {}
            _int = (_f.get('interes') or '').strip().lower()
            if _int in ('asesoria', 'asesoría', 'valoracion', 'valoración'):
                _nom = ((_f.get('nombre') or '').strip().split() or [''])[0].capitalize()
                _ciu = (_f.get('ciudad') or '').strip()
                _mod = (_f.get('modalidad') or '').strip().lower()
                _que = ('*asesoría virtual gratuita*' if _int.startswith('asesor')
                        else f"*valoración {_mod + ' ' if _mod in ('presencial', 'virtual') else ''}con el Dr. Gio*")
                user_facing = (f"¡Listo{', ' + _nom if _nom else ''}! 💙 En cuanto nuestra asesora esté disponible, "
                               f"*te contactará por aquí* para agendar tu {_que} 😊")
                if _ciu and not re.search(r'barranquilla|soledad|puerto colombia|malambo', _ciu, re.I):
                    user_facing += ("\n\nComo nos escribes desde *" + _ciu.title() + "*, te contará también sobre nuestros "
                                    "*planes de turismo médico todo incluido* ✈️")
                user_facing += ("\n\nMientras tanto, conoce *resultados reales y testimonios* del Dr. Gio:\n"
                                "📸 Instagram: *@drgiovannifuentes*\n🌐 Web: *www.drgio440.com*\n\n"
                                "*Ya eres parte de #LAbelleza440* ✨")

        # FALLBACK: si se emitió un NOTIFY pero el texto visible quedó vacío/corto
        # (Haiku a veces manda solo el bloque NOTIFY), garantizar el cierre al lead.
        if match and len(user_facing) < 20:
            user_facing = ("¡Listo! 💙 En cuanto nuestra asesora esté disponible, "
                           "*te contactará por aquí* 😊\n*Ya eres parte de #LAbelleza440* ✨")
            print("[CX] FALLBACK cierre inyectado (NOTIFY sin texto visible)", flush=True)

        # DEDUP CHECK *ANTES* de _save_message para evitar self-block.
        # _save_message persiste full_response (que contiene el literal
        # "<<<NOTIFY>>>...<<<END>>>") con direccion='saliente'. Si chequeáramos
        # dedup DESPUÉS, _already_notified_cx (que busca mensaje ILIKE '%NOTIFY%'
        # en saliente últimas 24h) encontraría el row recién insertado y trataría
        # todo NOTIFY como duplicado — bug introducido en 795519f que bloqueó
        # todos los avisos al staff desde el 25-may 06:15.
        # Mismo patrón ya aplicado en brain.py (ver comentario línea ~2374).
        # TODO(fase 2): cambiar la señal de dedup a leads_comerciales.notificado_at
        # (opción C) para desacoplar persistencia de aviso.
        already_notified = self._already_notified_cx(sender_id, canal) if notify else False
        # Regla C (CRM viejo: no re-notificar si ya tiene asesora) — solo legacy.
        # En el flujo nuevo TODO interesado que deja datos va a MedFiles.
        tiene_asesora = False
        if notify and _LEGACY_CRM:
            _lead_asg = self._check_lead_crm(sender_id)
            tiene_asesora = bool(_lead_asg and (_lead_asg.get('asesora_asignada') or '').strip())

        if user_facing:
            if send:
                print(f"[CX] sending reply len={len(user_facing)} via canal={canal} to={sender_id}", flush=True)
                client = self.instagram if canal.startswith('instagram') else self.whapi
                partes = [x.strip() for x in user_facing.split('<<<PARTE>>>') if x.strip()]
                for _k, _parte in enumerate(partes[:-1]):
                    try: client.send_text(sender_id, _parte)
                    except Exception as e: print(f"[CX] parte send err: {e}", flush=True)
                    time.sleep(1.2)
                r = client.send_text(sender_id, partes[-1] if partes else user_facing)
                if isinstance(r, dict) and 'error' in r:
                    print(f"[CX] ❌ SEND ERROR canal={canal} error={r.get('error')!r} body={r.get('body','')!r}", flush=True)
                else:
                    print(f"[CX] ✅ send_text OK result={r}", flush=True)
            else:
                print(f"[CX] send=False — reply delegado al caller len={len(user_facing)}", flush=True)
            # Se guarda lo que vio el paciente (bienvenida/bloques fijos incluidos) + el bloque NOTIFY interno,
            # así el historial que lee la IA en el siguiente mensaje coincide con la conversación real.
            _guardado = re.sub(r'\n*<<<PARTE>>>\n*', '\n\n', user_facing)
            if match:
                _guardado += '\n\n<<<NOTIFY>>>' + match.group(1) + '<<<END>>>'
            self._save_message(sender_id, sender_name, _guardado, 'saliente', 'bot', canal=canal)

        if notify:
            fields = self._parse_notify(notify)
            self._validate_notify_fields(fields, history, sender_name, sender_id)
            print(f"[CX] NOTIFY fields={fields}", flush=True)
            if already_notified:
                print(f"[CX] NOTIFY duplicado para {sender_id} — skip (ya notificado <24h)", flush=True)
            elif tiene_asesora:
                print(f"[CX] NOTIFY omitido para {sender_id} — lead ya tiene asesora asignada (regla C)", flush=True)
            else:
                self._notify_lead(fields, sender_id, canal=canal,
                                  history=history, ultimo_bot=user_facing)

        return re.sub(r'\n*<<<PARTE>>>\n*', '\n\n', user_facing)


def _now_iso():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
