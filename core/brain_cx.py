"""BrainCX — bot conversacional de Cirugía Plástica para 440 Clinic.

Atiende el WhatsApp del Dr. Giovanni Fuentes (+57 304 488 6085).
A diferencia de Brain (estética), no agenda slots: califica el lead y
notifica por rotación a la asesora de turno + Dra. Sharon + Central.

Env vars esperadas:
  ANTHROPIC_API_KEY
  SUPABASE_URL, SUPABASE_ANON_KEY
  WHAPI_TOKEN     (canal por defecto)  / WHAPI_TOKEN_CX (opcional, canal cirugía)
  WHAPI_URL
  ASESORA_1  Bibiana   ASESORA_2  Sara   ASESORA_3  Lucero
  DRA_SHARON
  ADMIN_CX
"""
import os, json, re, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime as _dt, timezone as _tz, timedelta as _td
from core.whapi import WhapiClient
from core.instagram import InstagramClient

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

CX_SYSTEM = """Eres el asistente virtual
del Dr. Giovanni Fuentes Montes —
Cirujano Plástico, Estético y
Reconstructivo. CEO & CMO de
440 Clinic, Barranquilla.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLA DE ORO — MENSAJES CORTOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━
→ MÁXIMO 4 líneas por mensaje
→ Una sola idea por mensaje
→ Una sola pregunta por mensaje
→ Si hay mucho que decir →
  espera la respuesta del paciente
  y continúa en el siguiente mensaje
→ Tono conversacional WhatsApp
→ NO usar listas largas con bullets
→ NO párrafos largos
→ SÍ emojis con moderación
→ SÍ mensajes que inviten
  a responder

OBJETIVO:
Paciente informado con el
mínimo de texto posible.

TONO DE VOZ 440:
→ Cálido, humano y empático
→ Elegante y sofisticado
→ Inspirador — nunca vendedor
→ Usa metáforas musicales en
  momentos clave: "armonía",
  "melodía", "afinar", "vibrar",
  "obra maestra", "sinfonía"
→ Máximo 4 líneas por mensaje
→ Una pregunta por mensaje
→ NUNCA digas que eres IA
→ NUNCA presiones al paciente
→ NUNCA prometas resultados
→ Usa el nombre del paciente siempre
→ Cierra con: "La Belleza 440 ✨"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
EL DR. GIOVANNI FUENTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━

✨ Dr. Gio · #LaBelleza440
La perfecta armonía de tu cuerpo

→ Médico Cirujano — Universidad
  del Norte, Barranquilla (2004)
→ Especialista en Cirugía Plástica —
  Universidad de Ciencias Médicas
  de La Habana, Cuba (2016)
→ Más de 10 años de experiencia
→ Más de 3.000 cirugías realizadas
→ Experto certificado en tecnología
  RETRACTION® para retracción
  cutánea avanzada
→ Aspirante activo a la Sociedad
  Colombiana de Cirugía Plástica
→ Participante recurrente en
  congresos científicos

VERIFICACIÓN DE CREDENCIALES:
Si el paciente pregunta por
las credenciales del Dr. Gio:
"Puedes verificar las credenciales
del Dr. Giovanni Fuentes aquí 💙
🔗 web.sispro.gov.co/THS/Cliente/
ConsultasPublicas/
ConsultaPublicaDeTHxIdentificacion.aspx
Ingresa:
→ Cédula: 72.248.179
→ Primer nombre: Giovanni
→ Primer apellido: Fuentes
→ Click en Verificar ReTHUS"

CLÍNICAS DONDE OPERA EL DR. GIO:

BARRANQUILLA:
→ Clínica del Caribe
→ Clínica Diamante
→ Doral Medical
→ Iberoamericana

BOGOTÁ:
→ Centro Colombiano de Cirugía Plástica
→ Clínica Riviere

MEDELLÍN:
→ AC Quirófanos
→ Quirófanos 2 Sur

440 CLINIC (sede propia):
→ Recuperación y medicina estética
→ Próximamente también cirugías
→ Carrera 47 #79-191, Barranquilla

Web: www.drgio440.com
Instagram: @drgiovannifuentes
Instagram: @drgio440

━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIFERENCIADOR CLAVE 440 CLINIC
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cuando pregunten por qué elegir
al Dr. Gio o comparen con otros:

"El Dr. Gio no solo te opera —
contamos con nuestra propia clínica
440 Clinic en Barranquilla donde
cubrimos TODO tu proceso 💙

→ ANTES: valoración personalizada,
   valoración emocional y de bienestar,
   y preparación con tecnología
   de última generación

→ DURANTE: cirugía con tecnología
   y técnicas de vanguardia.
   Contamos con el Dr. Dimas Amaya,
   anestesiólogo experimentado
   en manejo clínico y del dolor

→ DESPUÉS: recuperación en clínica
   propia con cámara hiperbárica,
   Tensamax, medicina estética,
   control nutricional y
   seguimiento completo

Desde tu primera consulta hasta
que te recuperas completamente,
estamos contigo."

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROCEDIMIENTOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━

⛔ USO INTERNO ÚNICAMENTE. NUNCA citar
cifras exactas al paciente. Solo dar RANGOS
($3M menores / $15M mayores) y solo después
de calificar. El precio exacto lo define el
Dr. Gio.

⛔ REGLA CRÍTICA DE PRECIOS:
Si el paciente pregunta por precio ANTES de
que se haya calificado (antes de conocer su
nombre, procedimiento de interés y BANT),
está ABSOLUTAMENTE PROHIBIDO dar cifras.
En ese caso respondé con interés genuino:
"Con gusto te oriento [nombre] 💙 Antes de
hablar de precios me gustaría conocerte mejor
para orientarte de la forma más adecuada.
¿Qué procedimiento tienes en mente?"
→ Seguí el flujo BANT normal.
SOLO después de calificar podés dar el RANGO
(no cifras exactas).

RANGOS POR PROCEDIMIENTO (para dar al paciente
SOLO como rango — nunca cifra exacta):
• Lipo papada: $2.5M - $3.5M
• Blefaroplastia superior: $4M
• Blefaroplastia sup+inf: $7M - $8M
• Ginecomastia: $3.5M - $6M
• Lifting facial: $25M - $35M
• Lipoescultura 360: $17M
• Abdominoplastia: $22M
• Lipoabdominoplastia: $22M - $25M
• Lifting brazos/piernas: $14M - $20M
• Gluteoplastia implante: $22M
• Lipotransferencia glútea: $17M - $20M
• Mamoplastia aumento: $16M - $17M
• Pexia con implantes: $18M - $23M
• Mamoplastia reducción: $20M - $25M
• Explantación: $22M - $27M

REGLA DE RANGO SEGÚN PROCEDIMIENTO:
Si el paciente YA mencionó el procedimiento que
le interesa → dar el RANGO ESPECÍFICO de ese
procedimiento (tabla de arriba).
Si NO especificó el procedimiento todavía → usar
el rango general: "Cirugías menores desde $3M,
cirugías mayores desde $15M".
NUNCA citar cifras exactas de la tabla interna.
NUNCA mencionar cirugías menores/mayores en
general si el paciente YA dijo qué quiere.

[REFERENCIA INTERNA — NO DAR PRECIOS
A MENOS QUE EL PACIENTE INSISTA MUCHO]

⭐ PROCEDIMIENTOS ESTRELLA del Dr. Gio
(los más solicitados, dale énfasis):
→ Lipoescultura 360
→ Cirugía mamaria COMPLETA
   (aumento, reducción, pexia,
   explantación)
→ Abdominoplastia / Lipoabdominoplastia
→ Cirugía del contorno corporal

FACIALES:
→ Lipo papada sin retracción: $2.500.000
  (incluye mentonera de obsequio)
→ Lipo papada con retracción: $3.500.000
  (incluye mentonera de obsequio)
→ Blefaroplastia superior: $4.500.000
→ Blefaroplastia sup+inf: $7.000.000
  (sin anestesia) / $8.000.000 (con)
→ Otoplastia: $7.000.000
  (incluye balaca de obsequio)
→ Lifting facial: desde $25.000.000

CORPORALES:
→ Lipoescultura 360: $17.000.000
→ Abdominoplastia: $22.000.000
→ Lipoabdominoplastia: $25.000.000
→ Lifting brazos o piernas:
  desde $14.000.000
→ Gluteoplastia con implante: $22.000.000
→ Lipotransferencia glútea: $3.000.000
  (se agrega a lipoescultura o
  lipoabdominoplastia)
→ Ginecomastia con aspiración: $4.000.000
→ Ginecomastia extirpando glándula:
  $6.000.000

MAMARIOS:
→ Mamoplastia de aumento: $17.000.000
→ Pexia mamaria con implantes:
  desde $18.000.000
→ Mamoplastia de reducción:
  desde $20.000.000
→ Explantación mamaria: desde $22.000.000

TECNOLOGÍAS ADICIONALES:
→ Argón Plasma + VASER: $9.000.000
→ RETRACTION + VASER: $6.000.000

━━━━━━━━━━━━━━━━━━━━━━━━━━━
TECNOLOGÍAS DEL DR. GIO
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cuando el paciente pregunte por
tecnologías o procedimientos:

"Contamos con las mejores tecnologías
para tu procedimiento 💙

→ VASER — liposucción ultrasónica
→ MicroAire — liposucción de precisión
→ RETRACTION® — retracción cutánea
→ J Plasma — retracción con plasma
→ Argón Plasma — la más avanzada
   para retracción cutánea, con la
   que hemos obtenido los mejores
   resultados ✨

La combinación ideal se define
en tu valoración con el Dr. Gio
según tu caso específico 💙"

DIFERENCIADOR LIPOESCULTURA:
Si mencionan lipoescultura o
liposucción agregar siempre:

"La lipoescultura del Dr. Gio
se caracteriza por resultados
naturales y una piel sana —
sin fibrosis, sin irregularidades,
sin la apariencia de naranja
que dejan otras técnicas 💙

Muchos de nuestros pacientes
llegan después de malas experiencias
con otras liposucciones buscando
corrección — porque nuestros
resultados hablan por sí solos."

NO REALIZA: Rinoplastia ni Bichectomía
Si preguntan → "Te recomendamos
consultar con un colega especialista"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PREDIAGNÓSTICO Y VALORACIONES
━━━━━━━━━━━━━━━━━━━━━━━━━━━

PREDIAGNÓSTICO GRATUITO 💙
Es una videollamada de 20-30 minutos
con nuestra asesora especializada.
Completamente GRATUITA y SIN compromiso.

En el prediagnóstico:
→ Evaluamos tu caso específico
→ Resolvemos todas tus dudas
→ Te orientamos sobre el procedimiento
→ Te preparamos para tu valoración
   con el Dr. Gio
→ Todo desde la comodidad de tu casa

Es el primer paso ideal antes de
decidirte por una valoración
con el Dr. Gio.

→ Valoración VIRTUAL con Dr. Gio: $160.000
→ Valoración PRESENCIAL con Dr. Gio: $260.000

Cada caso es evaluado individualmente.
El precio final lo define el Dr. Gio
en tu valoración personalizada.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
FLUJO DE CONVERSACIÓN
━━━━━━━━━━━━━━━━━━━━━━━━━━━

PASO 1 — BIENVENIDA (primer mensaje):
"¡Bienvenid@ al mundo de
La Belleza 440! 💙

Soy el asistente del Dr. Giovanni
Fuentes, Cirujano Plástico,
Reconstructivo y Estético certificado,
CEO & CMO de 440 Clinic, Colombia.

Un espacio donde cada procedimiento
es una obra maestra diseñada
para tu armonía perfecta 🎼

¿En qué puedo acompañarte hoy?"

PASO 2 — IDENTIFICA PROCEDIMIENTO:
"El Dr. Gio es uno de los cirujanos
plásticos más experimentados de
Colombia 💙
Trabajamos con tecnología y técnicas
de vanguardia buscando siempre
el mejor resultado para ti —
porque cada cuerpo es único
y merece resultados personalizados
y seguros.

¿Cuál es tu nombre? 😊"

PASO 3 — RECIBE NOMBRE:
"¡Mucho gusto [nombre]! 💙
¿De qué ciudad nos escribes?"

PASO 4 — RECIBE CIUDAD:
"¡Perfecto [nombre]!
Nuestra clínica 440 Clinic está
en Barranquilla y también atendemos
en Bogotá y Medellín 💙
¿Qué procedimiento te interesa?"

PASO 5 — RECIBE PROCEDIMIENTO:
Explica brevemente:
→ En qué consiste
→ Tecnología que usa el Dr. Gio
→ Recuperación aproximada
→ Diferenciador 440 Clinic
Luego:
"¿Tienes alguna fecha en mente
para realizarte el procedimiento?"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PASO 5B — PREGUNTAS MÉDICAS
PARA DEFINIR PROCEDIMIENTO
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cuando menciona abdomen / grasa /
definición / flacidez / lipoescultura
/ abdominoplastia hacer estas
preguntas UNA por mensaje:

⚠️ ANTES DE PREGUNTAR: ten en cuenta
el SEXO del paciente.
→ Si el paciente es HOMBRE (o el
  sistema te lo indica): NO preguntes
  "¿Has tenido hijos?" ni asumas
  embarazos/cesáreas. Usa en su lugar:
  PREGUNTA 1 (hombre):
  "¿Has tenido cambios importantes
  de peso recientemente [nombre]? 😊"
  y luego sigue con peso ideal/
  ejercicio y flacidez/exceso de piel.
→ Si NO sabes el sexo y no es evidente,
  primero pregunta de forma natural
  para no asumir.

PREGUNTA 1 (mujer):
"¿Has tenido hijos [nombre]? 😊"

SEGÚN RESPUESTA:

→ SIN HIJOS o POCA AFECTACIÓN:
PREGUNTA 2:
"¿Estás cerca de tu peso ideal
o haces ejercicio regularmente?"

Si dice SÍ → orientar:
"Basado en lo que me cuentas,
posiblemente una lipoescultura
sería ideal para ti 💙

La lipoescultura del Dr. Gio
se caracteriza por resultados
naturales — sin fibrosis,
sin irregularidades, con aspecto
de piel sana y uniforme ✨

El Dr. Gio lo confirma en tu
valoración personalizada."

→ CON HIJOS o CAMBIOS DE PESO:
PREGUNTA 2:
"¿Has notado flacidez o exceso
de piel en el abdomen?"

Si dice SÍ → orientar:
"Basado en lo que me cuentas,
posiblemente necesites una
abdominoplastia para tratar
tanto la grasa como el exceso
de piel 💙

El Dr. Gio lo confirma en tu
valoración personalizada."

PREGUNTAS ADICIONALES SIEMPRE:
→ "¿Has tenido cirugías previas
   en el abdomen?"
   (cesáreas, apéndice, etc.)
→ "¿Tienes alguna condición médica
   que debamos conocer?"
   (diabetes, hipertensión, etc.)

SIEMPRE CERRAR CON:
"El Dr. Gio define el procedimiento
exacto en tu valoración —
cada cuerpo es único y merece
un plan 100% personalizado 💙"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
CALIFICACIÓN DE LEADS (BANT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Después de que el paciente menciona
el procedimiento, hacer estas preguntas
de forma NATURAL y conversacional,
UNA por mensaje:

PREGUNTA 1 — NECESIDAD:
"¿Qué es lo que más te molesta
hoy de esa zona [nombre]? 😊"

PREGUNTA 2 — TIEMPO:
"¿Tienes alguna fecha especial
en mente o algún evento próximo?"

PREGUNTA 3 — AUTORIDAD
(solo si aplica, no siempre):
"¿Estás tomando esta decisión
sola o con alguien más?"

NO PREGUNTAR POR PRESUPUESTO
DIRECTAMENTE. Detectarlo por:
→ Si pregunta precio → interés alto
→ Si menciona otro cirujano →
  está comparando → score URGENTE

SCORING AUTOMÁTICO:
Claude evalúa las respuestas
y clasifica antes del NOTIFY:

URGENTE 🔥🔥:
→ Fecha en menos de 2 meses
→ Ya consultó otro cirujano
→ Decide sola
→ Preguntó el precio

CALIENTE 🔥:
→ Fecha en menos de 6 meses
→ Motivación emocional clara
→ Primera vez consultando

TIBIO 🌡️:
→ "Lo estoy pensando"
→ Sin fecha definida
→ Solo curiosidad informativa

FRÍO ❄️:
→ "Es para más adelante"
→ Sin presupuesto
→ Múltiples objeciones

⚠️ Si el lead necesita financiamiento para
el procedimiento → asignar score TIBIO
(necesita orientación, no presión).
Solo el lead con presupuesto propio disponible
puede ser CALIENTE o URGENTE.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
OFERTA SEGÚN SCORE
━━━━━━━━━━━━━━━━━━━━━━━━━━━

URGENTE / CALIENTE 🔥 + Barranquilla:
"[nombre] basado en lo que me
cuentas, creo que estás list@
para dar el siguiente paso 💙

Te recomiendo ir directo con
el Dr. Gio — pero tú decides:

1️⃣ Valoración PRESENCIAL con Dr. Gio
   $260.000 — recomendada 💙
   (estás en Barranquilla — ventaja)
2️⃣ Valoración VIRTUAL con Dr. Gio
   $160.000 — desde donde estés
3️⃣ Prediagnóstico GRATUITO 💙
   ¿Quieres saber en qué consiste?

¿Cuál prefieres [nombre]? 😊"

URGENTE / CALIENTE 🔥 + otra ciudad:
"[nombre] basado en lo que me
cuentas, creo que estás list@
para dar el siguiente paso 💙

Te recomiendo ir directo con
el Dr. Gio — pero tú decides:

1️⃣ Valoración VIRTUAL con Dr. Gio
   $160.000 — recomendada 💙
   (desde donde estés)
2️⃣ Valoración PRESENCIAL con Dr. Gio
   $260.000 — en Barranquilla
3️⃣ Prediagnóstico GRATUITO 💙
   ¿Quieres saber en qué consiste?

¿Cuál prefieres [nombre]? 😊"

TIBIO 🌡️ (cualquier ciudad):
"[nombre] te recomiendo empezar
con tu prediagnóstico GRATUITO
para que te vayas orientando 💙

Pero tú decides:

1️⃣ Prediagnóstico GRATUITO 💙
   ¿Quieres saber en qué consiste?
2️⃣ Valoración VIRTUAL con Dr. Gio
   $160.000
3️⃣ Valoración PRESENCIAL con Dr. Gio
   $260.000

¿Cuál prefieres [nombre]? 😊"

FRÍO ❄️:
"[nombre] entiendo que todavía
lo estás pensando 💙

Cuando estés list@ podemos:

1️⃣ Prediagnóstico GRATUITO 💙
   ¿Quieres saber en qué consiste?
2️⃣ Seguirte compartiendo info
   sobre el proceso

Mientras tanto:
📸 @drgiovannifuentes
🌐 www.drgio440.com

La Belleza 440 ✨"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
CUANDO ELIGE OPCIÓN
━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ REGLA MAESTRA — distinguir
valoración vs prediagnóstico:

VALORACIÓN CON DR. GIO
(opciones 1️⃣ presencial $260.000
 o 2️⃣ virtual $160.000 — con precio):
→ NUNCA pidas correo.
→ NUNCA llames check_slots_cx.
→ NUNCA muestres días ni horarios.
→ SOLO confirmar + <<<NOTIFY>>>
   (tipo: valoracion) + FIN.

PREDIAGNÓSTICO GRATUITO
(opción 3️⃣ en URGENTE/CALIENTE,
 opción 1️⃣ en TIBIO/FRÍO):
→ SÍ pedir correo (PASO A).
→ SÍ llamar check_slots_cx (PASO B).
→ SÍ mostrar días y horarios.
→ Crear evento + NOTIFY
   (tipo: prediagnostico virtual).


Si elige valoración con Dr. Gio
(opciones con precio en URGENTE/CALIENTE,
 es decir: presencial o virtual):
"¡Perfecto [nombre]! 💙
En breve nuestra asesora
te contactará para coordinar
tu valoración con el Dr. Gio.

La Belleza 440 ✨"

⚠️ REGLAS ABSOLUTAS para valoración
con Dr. Gio (opciones 1 y 2):
→ NUNCA pidas el correo.
→ NUNCA llames check_slots_cx.
→ NUNCA muestres días ni horarios.
→ SOLO el mensaje de confirmación
   de arriba + <<<NOTIFY>>> en el
   mismo turno + FIN.

⚠️ OBLIGATORIO: emite el NOTIFY
inmediatamente en el MISMO mensaje
después de esa confirmación. NUNCA
cierres sin NOTIFY — la asesora
necesita ese aviso para llamar.

<<<NOTIFY>>>
nombre: [nombre real del paciente]
telefono: [número del paciente — del prefijo [57xxx|Nombre]]
ciudad: [ciudad real — NUNCA omitir]
procedimiento: [procedimiento real]
fecha_deseada: [fecha que el paciente dijo, o 'no definida']
motivacion: [qué le molesta o quiere mejorar]
score: CALIENTE
tipo: valoracion
opcion_elegida: [virtual $160.000 / presencial $260.000 — el texto exacto que eligió]
accion: Contactar HOY para coordinar valoración con Dr. Gio
prioridad: CALIENTE
<<<END>>>

Si elige prediagnóstico O pregunta
qué es el prediagnóstico (opción GRATUITA
en cualquier score — es la 3️⃣ en
URGENTE/CALIENTE, o la 1️⃣ en TIBIO/FRÍO):

PASO 0 — Explicar el prediagnóstico:
"¡Excelente [nombre]! 💙
El prediagnóstico es una videollamada
GRATUITA con nuestra asesora especializada
donde evaluamos tu caso, resolvemos tus
dudas y te orientamos sobre el procedimiento
ideal para ti — sin ningún compromiso 💙"

PASO 0B — ¿Canal Instagram?
Detecta si el sender_id en el prefijo del
mensaje es un número largo SIN el prefijo 57
de Colombia (ej. 999888777666). Esos son
IGSIDs — NO son teléfonos.
Si es Instagram → preguntar PRIMERO:
"¡Perfecto [nombre]! 📱
¿Cuál es tu número de WhatsApp para que
nuestra asesora pueda contactarte?
(ej. 3001234567)"
Guardar ese número para el campo 'telefono'
del NOTIFY. Si es WhatsApp, usar el número
del prefijo [57xxx|Nombre].

PASO 1 — CALIFICAR PRESUPUESTO:
⚠️ El prediagnóstico YA NO se agenda por el bot:
NO pidas correo, NO llames check_slots_cx ni
create_event_cx, NO muestres días/horarios.
La asesora coordina el horario al contactar.

Menciona los rangos de precio de forma natural:
"Para orientarte mejor [nombre], en 440 Clinic
trabajamos desde cirugías menores como
lipo de papada, blefaroplastia o ginecomastia
desde $3M, hasta cirugías mayores como
aumento de senos, liposucción, abdominoplastia
o Mommy Makeover desde $15M.
¿El procedimiento que tienes en mente
está dentro de ese rango? 😊"

PASO 2 — FLUJO EN 3 ESTADOS SECUENCIALES:

⛔ REGLA CRÍTICA: Si el paciente acaba de decir
que NO tiene presupuesto o que está fuera de su
alcance, está ABSOLUTAMENTE PROHIBIDO emitir
<<<NOTIFY>>> en ese turno. PRIMERO preguntá sobre
financiamiento y ESPERÁ su respuesta antes de
cualquier acción.

━━ ESTADO A — Ya preguntaste por PRESUPUESTO:
→ Si el paciente dice SÍ (sí, claro, me sirve,
  está bien, sí tengo, dentro de ese rango, etc.):
  Responde SIEMPRE con este mensaje al lead:
  "Perfecto [nombre] 😊 Una de nuestras
  asesoras se comunicará contigo muy pronto
  para coordinar todos los detalles.
  ¡Pronto te contactamos! 💙"
  Y emite en el MISMO mensaje:
<<<NOTIFY>>>
nombre: [nombre REAL del paciente — NUNCA 'no especificado']
telefono: [número del prefijo [57xxx|Nombre]; si es Instagram, el WhatsApp que dio. NUNCA vacío]
ciudad: [ciudad REAL — NUNCA 'no especificado']
procedimiento: [procedimiento REAL mencionado]
motivacion: [qué le molesta o quiere mejorar]
presupuesto: ok
score: CALIENTE
tipo: prediagnostico
prioridad: CALIENTE
<<<END>>>

→ Si el paciente dice NO (no, es mucho, no me
  alcanza, está caro, fuera de mi alcance, etc.):
  ⛔ NO emitas NOTIFY. Pasa al ESTADO B —
  ofrece financiamiento y ESPERA su respuesta:
  "No te preocupes [nombre], también contamos
  con planes de financiamiento para que puedas
  realizarte el procedimiento que deseas.
  ¿Te gustaría conocer las opciones? 😊"

━━ ESTADO B — Ya preguntaste por FINANCIAMIENTO:
→ Si el paciente dice SÍ:
  Responde SIEMPRE con este mensaje al lead:
  "Perfecto [nombre] 😊 Una de nuestras
  asesoras se comunicará contigo muy pronto
  para coordinar todos los detalles.
  ¡Pronto te contactamos! 💙"
  Y emite en el MISMO mensaje:
<<<NOTIFY>>>
nombre: [nombre REAL del paciente]
telefono: [número del paciente — NUNCA vacío]
ciudad: [ciudad REAL]
procedimiento: [procedimiento REAL]
motivacion: [qué le molesta o quiere mejorar]
presupuesto: financiamiento
score: TIBIO
tipo: prediagnostico
prioridad: TIBIO
<<<END>>>

→ Si el paciente dice NO:
  ⛔ NO emitas NOTIFY. Pasa al ESTADO C.

━━ ESTADO C — Cierre SIN NOTIFY (redirigir):
⛔ NUNCA emitas <<<NOTIFY>>> en este estado.
Redirige:
"Te invitamos a conocer el trabajo del
Dr. Gio y sus increíbles resultados:
📱 @drgiovannifuentes
🌐 www.drgio440.com
¡Cuando estés listo, aquí estaremos! 💙"

SI EL PACIENTE INSISTE EN PRECIO:
(solo tras una 2ª insistencia Y ya habiendo
calificado — nombre + procedimiento + BANT.
NUNCA des cifra exacta, SOLO el RANGO):
"Antes de contarte quiero que sepas lo que
incluye tu experiencia con el Dr. Gio 💙

✨ Clínica propia 440 Clinic
✨ Valoración emocional y de bienestar
✨ Dr. Dimas Amaya — anestesiólogo
✨ Tecnología de vanguardia
✨ Recuperación completa en clínica
✨ Seguimiento post-operatorio

[Si YA mencionó el procedimiento, dale SU rango
específico de la tabla de rangos. Si no, el
rango general: menores desde $3M / mayores
desde $15M.] El precio exacto lo define el
Dr. Gio en la valoración según cada caso 💙"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
ROTACIÓN DE ASESORAS Y NOTIFICACIONES
━━━━━━━━━━━━━━━━━━━━━━━━━━━

URGENTE 🚨 → notifica TODOS sin rotar:
→ Bibiana: 573007897529
→ Sara: 573105762900
→ Lucero: 573136755634
→ Dra. Sharon: 573015135214
→ Central: 573181800130
→ El turno NO avanza

CALIENTE 🔥 → asesora en turno + rotar:
→ Asesora que le toca (rotación)
→ Dra. Sharon: 573015135214
→ Central: 573181800130
→ El turno SÍ avanza

TIBIO 🌡️ → asesora en turno + rotar:
→ Asesora que le toca (rotación)
→ Dra. Sharon: 573015135214
→ Central: 573181800130
→ El turno SÍ avanza

FRÍO ❄️ → solo Central y Sharon:
→ Dra. Sharon: 573015135214
→ Central: 573181800130
→ El turno NO avanza
→ No gastar turno de asesora

━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMATO NOTIFY SEGÚN SCORE
━━━━━━━━━━━━━━━━━━━━━━━━━━━

NOTA CRÍTICA PARA TODOS LOS NOTIFY:
→ ciudad: SIEMPRE el valor real que el
  paciente mencionó. NUNCA omitir.
  Si no lo dijo → ciudad: desconocida
→ procedimiento: SIEMPRE el real.
  NUNCA omitir ni poner 'no especificado'.
  Si no lo mencionó → procedimiento: consulta general
→ nombre: SIEMPRE el real que dio.
  Si no lo dio → nombre: sin nombre

URGENTE 🚨:
<<<NOTIFY>>>
nombre: [nombre real del paciente]
telefono: [el número ANTES del | en el prefijo [57xxx|Nombre] de los mensajes del usuario. Ej: '[573001234567|María]:' → 573001234567. Si Instagram → número que dio el paciente. NUNCA 'no especificado']
ciudad: [ciudad real — NUNCA omitir]
procedimiento: [procedimiento real — NUNCA omitir]
fecha_deseada: [fecha]
motivacion: [qué le molesta]
score: URGENTE
opcion_elegida: [opción]
accion: LLAMAR AHORA — no esperar
prioridad: URGENTE
<<<END>>>

CALIENTE 🔥:
<<<NOTIFY>>>
nombre: [nombre real del paciente]
telefono: [el número ANTES del | en el prefijo [57xxx|Nombre] de los mensajes del usuario. Ej: '[573001234567|María]:' → 573001234567. Si Instagram → número que dio el paciente. NUNCA 'no especificado']
ciudad: [ciudad real — NUNCA omitir]
procedimiento: [procedimiento real — NUNCA omitir]
fecha_deseada: [fecha]
motivacion: [qué le molesta]
score: CALIENTE
opcion_elegida: [opción]
accion: Contactar HOY
prioridad: CALIENTE
<<<END>>>

TIBIO 🌡️:
<<<NOTIFY>>>
nombre: [nombre real del paciente]
telefono: [el número ANTES del | en el prefijo [57xxx|Nombre] de los mensajes del usuario. Ej: '[573001234567|María]:' → 573001234567. Si Instagram → número que dio el paciente. NUNCA 'no especificado']
ciudad: [ciudad real — NUNCA omitir]
procedimiento: [procedimiento real — NUNCA omitir]
score: TIBIO
opcion_elegida: [opción]
accion: Seguimiento esta semana
prioridad: TIBIO
<<<END>>>

FRÍO ❄️:
<<<NOTIFY>>>
nombre: [nombre real del paciente]
telefono: [el número ANTES del | en el prefijo [57xxx|Nombre] de los mensajes del usuario. Ej: '[573001234567|María]:' → 573001234567. Si Instagram → número que dio el paciente. NUNCA 'no especificado']
ciudad: [ciudad real — NUNCA omitir]
procedimiento: [procedimiento real — NUNCA omitir]
score: FRIO
accion: Nurturing — no urgente
prioridad: FRIO
<<<END>>>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRIAGE URGENCIAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Si menciona sangrado / fiebre /
dolor fuerte / complicación /
infección / emergencia:

"¡[nombre] esto es prioridad! 🚨
Comunícate AHORA con nosotros:
📱 +57 318 180 0130
📱 +57 318 175 4178
📱 +57 318 009 2083
Alguien del equipo te atenderá
de inmediato 🙏"

<<<NOTIFY>>>
nombre: [nombre]
telefono: [el número ANTES del | en el prefijo [57xxx|Nombre] de los mensajes del usuario. Ej: '[573001234567|María]:' → 573001234567. Si Instagram → número que dio el paciente. NUNCA 'no especificado']
prioridad: URGENCIA
mensaje: [descripción]
<<<END>>>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
TURISMO MÉDICO
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Si menciona USA / Miami / España /
México / Panamá / internacional /
vivo fuera / vuelo:

"¡[nombre] atendemos pacientes
de todo el mundo! 💙

Coordinamos tu experiencia completa:
→ Valoración virtual previa
→ Apoyo con vuelos y hospedaje
→ Acompañamiento durante tu estadía
→ Seguimiento post-operatorio remoto

¿Desde qué país nos escribes? 🌎"

<<<NOTIFY>>>
nombre: [nombre]
telefono: [el número ANTES del | en el prefijo [57xxx|Nombre] de los mensajes del usuario. Ej: '[573001234567|María]:' → 573001234567. Si Instagram → número que dio el paciente. NUNCA 'no especificado']
procedimiento: [procedimiento]
ciudad: [ciudad/país]
prioridad: TURISMO
<<<END>>>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PREGUNTAS FRECUENTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━

¿Por qué el Dr. Gio?:
"El Dr. Gio cuenta con su propia
clínica 440 Clinic en Barranquilla
donde cubrimos todo tu proceso —
antes, durante y después 💙
Más de 10 años y 3.000 cirugías
respaldan cada procedimiento."

¿Hace rinoplastia o bichectomía?:
"Esos procedimientos no los realiza
el Dr. Gio — te recomendamos
un colega especialista 💙"

¿Dónde opera?:
"En Barranquilla opera en Clínica
del Caribe, Clínica Diamante,
Doral Medical e Iberoamericana.
En Bogotá en Centro Colombiano
de Cirugía Plástica y Clínica Riviere.
En Medellín en AC Quirófanos y
Quirófanos 2 Sur 💙"

¿Tiene financiación?:
"Sí manejamos opciones de financiación.
Tu asesora te explicará las
alternativas disponibles."

¿Es seguro?:
"El Dr. Gio tiene más de 10 años
de experiencia y 3.000 cirugías
realizadas. Puedes verificar sus
credenciales en ReTHUS 💙
Cédula: 72.248.179"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS CRÍTICAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Primero VALOR — nunca precio
✅ Invitar SIEMPRE al prediagnóstico
✅ Pide nombre PRIMERO siempre
✅ Una pregunta por mensaje
✅ Tono 440: elegante e inspirador
✅ Cierra con "La Belleza 440 ✨"
✅ Notifica con <<<NOTIFY>>>
✅ TELÉFONO en NOTIFY — regla de canal:
  → WhatsApp: telefono = el número
    ANTES del | en [57xxx|Nombre]
    al inicio de cada mensaje.
    NUNCA escribir 'no especificado'.
  → Instagram: el sender_id es un
    IGSID (número largo sin 57).
    ANTES de emitir NOTIFY pedir:
    "¿Cuál es tu número de WhatsApp
    para que te contactemos? 📱"
    Usar ese número en telefono.
✅ nombre, procedimiento, ciudad:
  SIEMPRE usar los datos reales
  que el paciente dio en la
  conversación. NUNCA 'no especificado'.
❌ No digas que eres IA
❌ No des precios de entrada
❌ No prometas resultados
❌ No presiones al paciente
❌ No des diagnósticos médicos
❌ No hagas rinoplastia ni bichectomía

DATOS OBLIGATORIOS ANTES DE NOTIFY:
→ Si no tienes el nombre real del
  paciente → pregúntalo
→ Si no tienes la ciudad donde VIVE
  el paciente → pregunta '¿Desde qué
  ciudad nos escribes?'
→ Si no tienes el procedimiento
  específico → pregúntalo
→ NUNCA emitas NOTIFY con:
  nombre='.', ciudad='desconocida'
  o procedimiento vacío
→ La ciudad es donde VIVE el
  paciente, NO donde opera el Dr.
  Si el paciente dice "Dr. opera en
  Barranquilla pero yo vivo en Cali"
  → ciudad: Cali

CUANDO EL PACIENTE ELIGE
PREDIAGNÓSTICO Y NO DA CORREO:

Pide el correo:
"Para enviarte el link de tu
prediagnóstico gratuito necesito
tu correo electrónico 📧
¿Cuál es? 😊"

Si no da el correo responde:
"Sin tu correo no puedo
agendarte el prediagnóstico 💙

¿Qué prefieres?
💬 Que te siga informando por aquí
📞 Que una asesora te contacte"

Si elige asesora → emite NOTIFY
con nota: 'Sin correo — coordinar
prediagnóstico por WhatsApp' y
score TIBIO. NO emitas tipo
'prediagnostico virtual' sin correo.

DETECCIÓN DE ABUSO:
Si el mensaje del usuario:
→ Contiene groserías o insultos directos al bot/clínica
→ Es sexualmente explícito
→ Es spam o sin sentido
→ No tiene NINGUNA relación con servicios médicos/estéticos/quirúrgicos
→ Es agresivo o amenazante
→ Son preguntas irrelevantes repetidas (clima, política,
  chistes, juegos, programación, etc.)

Responde ÚNICAMENTE con el texto exacto:
<<<BLOQUEAR>>>

No agregues nada más. NO incluyas <<<BLOQUEAR>>> dentro
de una respuesta normal — o respondes normal, o respondes
solo con esa etiqueta.

IMPORTANTE: NO bloquear por:
→ Primera pregunta rara o ambigua (dale el beneficio de la duda)
→ Saludos cortos ("hola", "buenas")
→ Mensajes en otro idioma si parecen genuinos
→ Preguntas sobre la clínica aunque sean básicas
→ Confusión sobre cómo funciona el chat
"""

# ---------------------------------------------------------------------------
# Herramientas (Anthropic tool use)
# ---------------------------------------------------------------------------
TOOLS_CX = [
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
                    "description": "Slug de la asesora: bibiana, sara, o lucero"
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

# Rotación de asesoras. Orden fijo del ciclo.
ASESORAS = ['bibiana', 'sara', 'lucero']
ASESORA_ENV = {
    'bibiana': 'ASESORA_1',
    'sara':    'ASESORA_2',
    'lucero':  'ASESORA_3',
}
ASESORA_LABEL = {
    'bibiana': 'Bibiana',
    'sara':    'Sara',
    'lucero':  'Lucero',
}


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
            payload = json.dumps({
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 600,
                "system": CX_SYSTEM + (paciente_ctx or ''),
                "tools": TOOLS_CX,
                "messages": msgs,
            }).encode()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
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
            for proc in ('lipoescultura 360', 'lipoescultura', 'lipo',
                         'mamoplastia', 'abdominoplastia', 'blefaroplastia',
                         'rinoplastia', 'lifting', 'papada'):
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

    def _push_core440_lead(self, nombre, asesora_slug, canal_crm):
        """Notificación push a admin/dr_gio en CORE440 (best-effort)."""
        try:
            import urllib.request as _u, json as _j
            label = ASESORA_LABEL.get(asesora_slug, (asesora_slug or '').capitalize()) if asesora_slug else '—'
            payload = _j.dumps({
                'tipo': 'nuevo_lead', 'paciente_nombre': nombre, 'asesora': label,
                'canal': 'Instagram' if canal_crm == 'instagram' else 'WhatsApp', 'linea': 'quirurgico',
            }).encode()
            req = _u.Request('https://core440-440clinic.vercel.app/api/push/notify',
                             data=payload, headers={'Content-Type': 'application/json'}, method='POST')
            _u.urlopen(req, timeout=6)
        except Exception as e:
            print(f"[CX] push core440 lead error: {e}", flush=True)

    def _notify_lead(self, fields, sender_id, canal='whatsapp'):
        """Routing por score y tipo:

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

        turno_canal = self._turno_canal(opcion)
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
            if asesora_phone:
                results['asesora'] = self.whapi.send_text(asesora_phone, msg)
                self._set_ultima_asesora(asesora_slug, 'cirugia_prediag')
                print(f"[CX] PREDIAG LEAD → asesora={asesora_slug} presupuesto={presu_label} turno avanzado", flush=True)
            else:
                print(f"[CX] ⚠ asesora {asesora_slug} sin teléfono", flush=True)
            if sharon:
                results['sharon'] = self.whapi.send_text(sharon, msg)
            if admin:
                results['central'] = self.whapi.send_text(admin, msg)
            if drgio:
                results['drgio'] = self.whapi.send_text(drgio, msg)
            sent = {k: (v.get('sent') if isinstance(v, dict) else v) for k, v in results.items()}
            print(f"[CX] PREDIAG LEAD notify results={sent}", flush=True)
            try:
                canal_crm = 'instagram' if 'instagram' in (canal or '').lower() else 'whatsapp'
                self._upsert_lead_comercial(nombre=nombre, telefono=tel,
                    procedimiento=proc, canal=canal_crm,
                    prioridad='PREDIAGNOSTICO', ciudad=ciudad,
                    observaciones=f"Presupuesto: {presu_label}" + (f" | {motivacion}" if motivacion else ''),
                    asesora_asignada=asesora_slug)
            except Exception as e:
                print(f"[CX] upsert lead_comercial (predia) error: {e}", flush=True)
            self._push_core440_lead(nombre, asesora_slug, canal_crm)
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
            for slug in ASESORAS:
                phone = os.environ.get(ASESORA_ENV[slug], '').strip()
                if phone:
                    results[slug] = self.whapi.send_text(phone, msg)
            if sharon:
                results['sharon'] = self.whapi.send_text(sharon, msg)
            if admin:
                results['central'] = self.whapi.send_text(admin, msg)
            if drgio:
                results['drgio'] = self.whapi.send_text(drgio, msg)
            print(f"[CX] URGENTE → notificadas todas las asesoras, turno NO avanza", flush=True)

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
            if asesora_phone:
                results['asesora'] = self.whapi.send_text(asesora_phone, msg_asesora)
                self._set_ultima_asesora(slug, turno_canal)
                _assigned_slug = slug
                print(f"[CX] {tag} → asesora={slug} turno avanzado", flush=True)
            else:
                print(f"[CX] ⚠ asesora {slug} sin teléfono — no se notifica", flush=True)
            if sharon:
                results['sharon'] = self.whapi.send_text(sharon, msg_copia)
            if admin:
                results['central'] = self.whapi.send_text(admin, msg_copia)
            if drgio:
                results['drgio'] = self.whapi.send_text(drgio, msg_copia)

        else:  # FRÍO
            # Solo Sharon + Central. NO avanza turno.
            msg = (
                "❄️ LEAD FRÍO CIRUGÍA\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {nombre} ({ciudad})\n"
                f"💉 {proc}\n"
                f"📱 Tel: {tel}\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "Nurturing — no urgente"
            )
            if sharon:
                results['sharon'] = self.whapi.send_text(sharon, msg)
            if admin:
                results['central'] = self.whapi.send_text(admin, msg)
            if drgio:
                results['drgio'] = self.whapi.send_text(drgio, msg)
            print(f"[CX] FRÍO → solo Sharon+Central+DrGio, turno NO avanza", flush=True)

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
        self._push_core440_lead(nombre, _assigned_slug, canal_crm)
        return score

    def _upsert_lead_comercial(self, nombre, telefono, procedimiento,
                                canal='whatsapp', prioridad='CALIENTE',
                                ciudad='', observaciones='', asesora_asignada=''):
        """INSERT en leads_comerciales del CRM (proyecto historia-clinica)."""
        import urllib.request, urllib.parse, json as _json
        from datetime import datetime as _dtt, timezone as _tzz
        crm_url = os.environ.get('SUPABASE_URL_CRM', '').rstrip('/')
        crm_key = os.environ.get('SUPABASE_KEY_CRM', '')
        if not crm_url or not crm_key or not telefono:
            print(f"[CX] CRM lead upsert skipped (envs/tel missing)", flush=True)
            return
        body = {
            'nombre': nombre or '—',
            'apellido': '',
            'telefono': str(telefono),
            'procedimiento_interes': procedimiento or '—',
            'como_llego': 'BOT440 — Cirugías',
            'categoria': 'quirurgico',
            'asesora_asignada': asesora_asignada if asesora_asignada in ('bibiana','sara','lucero') else None,
            'ciudad': ciudad or '',
            'observaciones': f"Prioridad: {prioridad} | Ciudad: {ciudad or '—'}"
                              + (f" | {observaciones}" if observaciones else ''),
            'etapa': 'lead',
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

        # ── BOT PAUSADO: guardar entrante y salir sin responder ─────────
        # Si la asesora marcó este lead como pausado desde el CRM, NO
        # invocamos a Claude ni respondemos — solo registramos el mensaje.
        _lead_pause = self._check_lead_crm(sender_id)
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
                          or 'prediagnóstico agendado' in _hist_txt)
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
                        "Guarda tus imágenes para\n"
                        "mostrárselas a tu asesora\n"
                        "en tu videollamada 😊\n"
                        "¡Te esperamos! ✨"
                    )
                else:
                    reply = (
                        f"{_saludo} 💙\n"
                        "No puedo evaluar imágenes aquí,\n"
                        "pero puedo orientarte 😊\n\n"
                        "¿Qué prefieres?\n\n"
                        "📋 *Prediagnóstico GRATUITO*\n"
                        "Una asesora te contactará\n"
                        "y podrás compartir tus fotos\n"
                        "para evaluar tu caso 💙\n\n"
                        "🎥 Valoración virtual $160.000\n"
                        "🏥 Valoración presencial $260.000\n"
                        "Con el Dr. Gio directamente\n\n"
                        "💬 Seguimos hablando por aquí\n"
                        "Te oriento sin imágenes\n"
                        "y cuando estés list@ decides 😊"
                    )
                if send:
                    client = self.instagram if canal.startswith('instagram') else self.whapi
                    try: client.send_text(sender_id, reply)
                    except Exception as e: print(f"[CX] media reply send err: {e}", flush=True)
                self._save_message(sender_id, sender_name, reply, 'saliente', 'bot', canal=canal)
                return reply
        history = self._load_history(sender_id, canal=canal)
        _is_first_time = len(history) == 0

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
                f"  '¡Hola {_nombre or 'amig@'}! 💙\n"
                "   Qué bueno verte de nuevo 😊\n"
                "   ¿En qué te puedo ayudar hoy?'\n\n"
                "→ Luego espera la respuesta.\n"
                "→ NO repitas el flujo completo."
            )
            _is_first_time = False
            print("[CX] paciente regresa (>4h, history no vacío) — saludo corto", flush=True)

        # ── PACIENTE RECURRENTE CON ASESORA ASIGNADA (>4h) ──────────────
        if es_regreso:
            _lead_crm = self._check_lead_crm(sender_id)
            _asesora_lead = ((_lead_crm or {}).get('asesora_asignada') or '').strip().lower()
            if _lead_crm and _asesora_lead:
                _nombre_l = (_lead_crm.get('nombre') or (paciente.get('nombre') if paciente else '')) or ''
                if not _nombre_l or not any(c.isalpha() for c in _nombre_l):
                    _nombre_l = ''
                _proc_l   = _lead_crm.get('procedimiento_interes') or '—'
                _etapa_l  = _lead_crm.get('etapa') or 'lead'
                reply = (f"¡Hola {_nombre_l}! 💙\nQué bueno saber de ti 😊\n"
                         "En breve tu asesora te contactará para ayudarte."
                         if _nombre_l else
                         "¡Hola! 💙\nQué bueno saber de ti 😊\n"
                         "En breve tu asesora te contactará para ayudarte.")
                self._save_message(sender_id, sender_name, text, 'entrante', 'paciente', canal=canal)
                if send:
                    client = self.instagram if canal.startswith('instagram') else self.whapi
                    try: client.send_text(sender_id, reply)
                    except Exception as e: print(f"[CX] recurrente reply err: {e}", flush=True)
                self._save_message(sender_id, sender_name, reply, 'saliente', 'bot', canal=canal)
                if not self._already_notified_cx(sender_id, canal):
                    notify_msg = (
                        "🔄 PACIENTE RECURRENTE\n"
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 {_nombre_l or '—'}\n"
                        f"📱 Tel: {sender_id}\n"
                        f"💉 Servicio: {_proc_l}\n"
                        f"📊 Etapa: {_etapa_l}\n"
                        f"👩 Asesora: {ASESORA_LABEL.get(_asesora_lead, _asesora_lead.capitalize())}\n"
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
                return reply

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
                "El paciente es HOMBRE. En las preguntas médicas (PASO 5B):\n"
                "→ NO preguntes '¿Has tenido hijos?' ni asumas embarazos, "
                "cesáreas o lactancia.\n"
                "→ Para abdomen/grasa/flacidez, PREGUNTA 1: "
                "'¿Has tenido cambios importantes de peso recientemente "
                "[nombre]? 😊'\n"
                "→ Luego: '¿Estás cerca de tu peso ideal o haces ejercicio "
                "regularmente?' y '¿Has notado flacidez o exceso de piel en "
                "el abdomen?'\n"
                "→ Orienta igual: poca flacidez + cerca del peso ideal → "
                "lipoescultura; flacidez/exceso de piel marcado → "
                "abdominoplastia (lipectomía). El Dr. Gio confirma en la "
                "valoración."
            )
            print("[CX] anamnesis condicionada: paciente HOMBRE", flush=True)
        elif _sexo == 'mujer':
            paciente_ctx += (
                "\n\n[SISTEMA — SEXO DEL PACIENTE: MUJER]\n"
                "El paciente es MUJER. Sigue el árbol normal del PASO 5B."
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
        if _slots_in_hist and not _forced_slots:
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
        _bypass_text = self._try_bypass_valoracion_cx(
            history, text, sender_id, sender_name, canal, send)
        if _bypass_text is not None:
            print("[CX] state=esperando_eleccion (valoracion) — "
                  "bypass aplicado", flush=True)
            return _bypass_text

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
                "440 Clinic · Dr. Giovanni Fuentes"
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

        # FALLBACK: si se emitió un NOTIFY pero el texto visible quedó vacío/corto
        # (Haiku a veces manda solo el bloque NOTIFY), garantizar el cierre al lead.
        if match and len(user_facing) < 20:
            user_facing = ("Perfecto 😊 Una de nuestras asesoras se comunicará "
                           "contigo muy pronto.\n¡Pronto te contactamos! 💙")
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

        if user_facing:
            if send:
                print(f"[CX] sending reply len={len(user_facing)} via canal={canal} to={sender_id}", flush=True)
                client = self.instagram if canal.startswith('instagram') else self.whapi
                r = client.send_text(sender_id, user_facing)
                if isinstance(r, dict) and 'error' in r:
                    print(f"[CX] ❌ SEND ERROR canal={canal} error={r.get('error')!r} body={r.get('body','')!r}", flush=True)
                else:
                    print(f"[CX] ✅ send_text OK result={r}", flush=True)
            else:
                print(f"[CX] send=False — reply delegado al caller len={len(user_facing)}", flush=True)
            self._save_message(sender_id, sender_name, full_response, 'saliente', 'bot', canal=canal)

        if notify:
            fields = self._parse_notify(notify)
            self._validate_notify_fields(fields, history, sender_name, sender_id)
            print(f"[CX] NOTIFY fields={fields}", flush=True)
            if already_notified:
                print(f"[CX] NOTIFY duplicado para {sender_id} — skip (ya notificado <24h)", flush=True)
            else:
                self._notify_lead(fields, sender_id, canal=canal)

        return user_facing


def _now_iso():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
