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
import os, json, re, urllib.request, urllib.error, urllib.parse
from core.whapi import WhapiClient
from core.instagram import InstagramClient

_BROWSER_UA = 'Mozilla/5.0 (compatible; BOT440-CX/1.0; +https://440clinic.com)'

CX_SYSTEM = """Eres el asistente virtual
del Dr. Giovanni Fuentes Montes —
Cirujano Plástico, Estético y
Reconstructivo. CEO & CMO de
440 Clinic, Barranquilla.

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

[REFERENCIA INTERNA — NO DAR PRECIOS
A MENOS QUE EL PACIENTE INSISTA MUCHO]

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

→ Prediagnóstico GRATUITO con asesora
→ Valoración VIRTUAL con Dr. Gio: $160.000
→ Valoración PRESENCIAL con Dr. Gio: $260.000

Cada caso es evaluado individualmente.
El precio final lo define el Dr. Gio
en tu valoración personalizada.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
FLUJO DE CONVERSACIÓN
━━━━━━━━━━━━━━━━━━━━━━━━━━━

PASO 1 — BIENVENIDA (primer mensaje):
"Bienvenid@ 💙
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

PREGUNTA 1:
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

━━━━━━━━━━━━━━━━━━━━━━━━━━━
OFERTA SEGÚN SCORE
━━━━━━━━━━━━━━━━━━━━━━━━━━━

URGENTE / CALIENTE 🔥:
"[nombre] basado en lo que me
cuentas, creo que estás list@
para dar el siguiente paso 💙

Te recomiendo ir directo con
el Dr. Giovanni Fuentes — pero
tú decides lo que más te acomoda:

1️⃣ Valoración VIRTUAL con Dr. Gio
   $160.000 — desde donde estés
2️⃣ Valoración PRESENCIAL con Dr. Gio
   $260.000 — en Barranquilla
3️⃣ Prediagnóstico GRATUITO
   con nuestra asesora primero

¿Cuál prefieres [nombre]? 😊"

TIBIO 🌡️:
"[nombre] te recomiendo empezar
con tu prediagnóstico GRATUITO
para que te vayas orientando 💙

Pero tú decides:

1️⃣ Prediagnóstico GRATUITO
   con nuestra asesora
   (recomendado para tu caso)
2️⃣ Valoración VIRTUAL con Dr. Gio
   $160.000
3️⃣ Valoración PRESENCIAL con Dr. Gio
   $260.000

¿Cuál prefieres [nombre]? 😊"

FRÍO ❄️:
"[nombre] entiendo que todavía
lo estás pensando 💙

Cuando estés list@ podemos:

1️⃣ Prediagnóstico GRATUITO
   con nuestra asesora
2️⃣ Seguirte compartiendo info
   sobre el proceso

Mientras tanto:
📸 @drgiovannifuentes
🌐 www.drgio440.com

La Belleza 440 ✨"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
CUANDO ELIGE OPCIÓN
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Si elige valoración con Dr. Gio
(opción 1️⃣ o 2️⃣ en score URGENTE/CALIENTE):
"¡Perfecto [nombre]! 💙
En breve una de nuestras asesoras
te contactará para coordinar
tu valoración con el Dr. Gio.

La Belleza 440 ✨"

Si elige prediagnóstico (opción 3️⃣
en URGENTE/CALIENTE, o 1️⃣ en FRÍO/TIBIO):
→ INMEDIATAMENTE llama a check_slots_cx
  con preferencia='proximo' y el sender_id
  SIN hacer preguntas adicionales de día/hora
→ Muestra los 3 slots así:
  "¡Perfecto [nombre]! 💙
  Estos son los próximos horarios
  disponibles con tu asesora:

  1️⃣ [slot 1 label]
  2️⃣ [slot 2 label]
  3️⃣ [slot 3 label]

  ¿Cuál prefieres? 😊"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
CUANDO EL HISTORIAL TIENE <<<SLOTS>>>
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Si en el historial del asistente aparece
un bloque <<<SLOTS>>>...<<<END_SLOTS>>>:
→ YA mostraste los slots disponibles
→ Si el paciente responde "1", "2" o "3"
  (o cualquier número o variación):
  - Extrae los datos del slot_N del bloque
  - Llama INMEDIATAMENTE a create_event_cx
    con slot_id, slot_label y asesora
    del slot elegido
  - NO vuelvas a llamar check_slots_cx
  - NO hagas más preguntas
→ Confirma la cita:
"✅ ¡Tu prediagnóstico quedó agendado!
📅 [slot_label]
👩 Con: [asesora]
📍 440 Clinic, Barranquilla

En breve [asesora] te contactará
para coordinar los detalles.

La Belleza 440 ✨"

→ Después de confirmar, emite siempre:
<<<NOTIFY>>>
nombre: [nombre]
telefono: [número exacto del remitente — el sender_id que aparece al inicio del mensaje entre corchetes]
ciudad: [ciudad]
procedimiento: [procedimiento]
asesora: [asesora slug]
fecha: [slot_label]
score: CALIENTE
opcion_elegida: prediagnostico gratuito
accion: Contactar HOY
prioridad: CALIENTE
<<<END>>>

SI EL PACIENTE INSISTE EN PRECIO:
"Antes de contarte el precio
quiero que sepas lo que incluye
tu experiencia con el Dr. Gio 💙

✨ Clínica propia 440 Clinic
✨ Valoración emocional y de bienestar
✨ Dr. Dimas Amaya — anestesiólogo
✨ Tecnología de vanguardia
✨ Recuperación completa en clínica
✨ Seguimiento post-operatorio

[Procedimiento] tiene un precio
desde $[X] 💙

El precio final lo define el Dr. Gio
en tu valoración — porque cada
caso es único."

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

URGENTE 🚨:
<<<NOTIFY>>>
nombre: [nombre]
telefono: [número exacto del remitente — el sender_id que aparece al inicio del mensaje entre corchetes]
ciudad: [ciudad]
procedimiento: [procedimiento]
fecha_deseada: [fecha]
motivacion: [qué le molesta]
score: URGENTE
opcion_elegida: [opción]
accion: LLAMAR AHORA — no esperar
prioridad: URGENTE
<<<END>>>

CALIENTE 🔥:
<<<NOTIFY>>>
nombre: [nombre]
telefono: [número exacto del remitente — el sender_id que aparece al inicio del mensaje entre corchetes]
ciudad: [ciudad]
procedimiento: [procedimiento]
fecha_deseada: [fecha]
motivacion: [qué le molesta]
score: CALIENTE
opcion_elegida: [opción]
accion: Contactar HOY
prioridad: CALIENTE
<<<END>>>

TIBIO 🌡️:
<<<NOTIFY>>>
nombre: [nombre]
telefono: [número exacto del remitente — el sender_id que aparece al inicio del mensaje entre corchetes]
ciudad: [ciudad]
procedimiento: [procedimiento]
score: TIBIO
opcion_elegida: [opción]
accion: Seguimiento esta semana
prioridad: TIBIO
<<<END>>>

FRÍO ❄️:
<<<NOTIFY>>>
nombre: [nombre]
telefono: [número exacto del remitente — el sender_id que aparece al inicio del mensaje entre corchetes]
ciudad: [ciudad]
procedimiento: [procedimiento]
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
📱 +57 313 791 7168
Alguien del equipo te atenderá
de inmediato 🙏"

<<<NOTIFY>>>
nombre: [nombre]
telefono: [número exacto del remitente — el sender_id que aparece al inicio del mensaje entre corchetes]
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
telefono: [número exacto del remitente — el sender_id que aparece al inicio del mensaje entre corchetes]
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
❌ No digas que eres IA
❌ No des precios de entrada
❌ No prometas resultados
❌ No presiones al paciente
❌ No des diagnósticos médicos
❌ No hagas rinoplastia ni bichectomía
"""

# ---------------------------------------------------------------------------
# Herramientas (Anthropic tool use)
# ---------------------------------------------------------------------------
TOOLS_CX = [
    {
        "name": "check_slots_cx",
        "description": (
            "Consulta los 3 próximos slots disponibles para prediagnóstico con la asesora asignada. "
            "Llamar INMEDIATAMENTE cuando el paciente elige prediagnóstico, SIN preguntar día/hora."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "asesora": {
                    "type": "string",
                    "description": "Slug de la asesora en turno: bibiana, sara, o lucero"
                },
                "preferencia": {
                    "type": "string",
                    "description": "Siempre usar 'proximo' para mostrar los próximos slots disponibles"
                },
                "sender_id": {
                    "type": "string",
                    "description": "ID del remitente del mensaje"
                }
            },
            "required": ["asesora", "preferencia", "sender_id"]
        }
    },
    {
        "name": "create_event_cx",
        "description": (
            "Crea el evento de prediagnóstico cuando el paciente elige un slot. "
            "Pasar el slot_id exacto devuelto por check_slots_cx."
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
                "sender_id": {
                    "type": "string",
                    "description": "ID del remitente"
                },
                "sender_name": {
                    "type": "string",
                    "description": "Nombre del paciente"
                }
            },
            "required": ["asesora", "slot_id", "sender_id"]
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
        # InstagramClient para @drgiovannifuentes — usa IG_CX_PAGE_ACCESS_TOKEN si existe,
        # si no cae en IG_PAGE_ACCESS_TOKEN (fallback).
        ig_cx_token = os.environ.get('IG_CX_PAGE_ACCESS_TOKEN', '').strip()
        ig_cx_account = os.environ.get('IG_CX_ACCOUNT_ID', '17841400339315123').strip()
        self.instagram = InstagramClient(
            token=ig_cx_token or os.environ.get('IG_PAGE_ACCESS_TOKEN', ''),
            account_id=ig_cx_account,
        )
        cx_token = os.environ.get('WHAPI_TOKEN_CX', '').strip()  # solo para el log
        self.api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        self.sb_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
        self.sb_key = os.environ.get('SUPABASE_ANON_KEY', '')
        self.history_limit = 12
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
        # Para instagram_cx inferir cuenta_receptora automáticamente
        if cuenta_receptora is None and canal == 'instagram_cx':
            cuenta_receptora = 'drgiovannifuentes'
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
    def _check_slots_cx(self, asesora: str, sender_id: str, preferencia: str = 'proximo') -> list:
        """Consulta los próximos slots disponibles vía CHECK_SLOTS_CX_URL.
        Devuelve lista de dicts [{id, label, asesora_label}, ...]
        """
        url = os.environ.get('CHECK_SLOTS_CX_URL', '').strip()
        if not url:
            print(f"[CX] check_slots_cx — CHECK_SLOTS_CX_URL no configurado, usando fallback", flush=True)
            return [
                {'id': 'slot_1', 'label': 'Próximo lunes 10:00 AM', 'asesora_label': asesora.capitalize()},
                {'id': 'slot_2', 'label': 'Próximo martes 11:00 AM', 'asesora_label': asesora.capitalize()},
                {'id': 'slot_3', 'label': 'Próximo miércoles 3:00 PM', 'asesora_label': asesora.capitalize()},
            ]
        payload = json.dumps({
            'asesora': asesora,
            'preferencia': preferencia,
            'sender_id': sender_id,
        }).encode()
        try:
            req = urllib.request.Request(
                url, data=payload,
                headers={'Content-Type': 'application/json', 'User-Agent': _BROWSER_UA},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                slots = json.loads(r.read())
                print(f"[CX] check_slots_cx asesora={asesora} → {len(slots)} slots", flush=True)
                return slots
        except Exception as e:
            print(f"[CX] check_slots_cx error: {e}", flush=True)
            return []

    def _create_event_cx(self, asesora: str, slot_id: str, sender_id: str,
                         sender_name: str = '', slot_label: str = '') -> dict:
        """Crea el evento de prediagnóstico vía CREATE_EVENT_CX_URL."""
        url = os.environ.get('CREATE_EVENT_CX_URL', '').strip()
        if not url:
            print(f"[CX] create_event_cx — CREATE_EVENT_CX_URL no configurado, usando fallback", flush=True)
            return {'ok': True, 'slot_label': slot_label or slot_id, 'asesora': asesora}
        payload = json.dumps({
            'asesora': asesora,
            'slot_id': slot_id,
            'slot_label': slot_label,
            'sender_id': sender_id,
            'sender_name': sender_name,
        }).encode()
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
    def _call_claude(self, messages, sender_id='', sender_name=''):
        """Llama a Claude con soporte para tool use (check_slots_cx, create_event_cx).
        Ejecuta el loop completo hasta obtener respuesta de texto final.
        """
        msgs = list(messages)
        max_iterations = 4  # evitar loops infinitos
        last_slots = None  # FIX 1: rastrear slots para persistir en historial

        for iteration in range(max_iterations):
            payload = json.dumps({
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 600,
                "system": CX_SYSTEM,
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
                    for i, s in enumerate(last_slots[:3], 1):
                        slots_block += f'slot_{i}: {json.dumps(s, ensure_ascii=False)}\n'
                    slots_block += '<<<END_SLOTS>>>'
                    text += slots_block
                    print(f"[CX] FIX1 — <<<SLOTS>>> appended ({len(last_slots)} slots)", flush=True)
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
                        asesora = tool_input.get('asesora', '')
                        if not asesora:
                            # Obtener asesora en turno si Claude no la especificó
                            slug, _, _ = self._next_asesora('cirugia')
                            asesora = slug
                        slots = self._check_slots_cx(
                            asesora=asesora,
                            sender_id=tool_input.get('sender_id', sender_id),
                            preferencia=tool_input.get('preferencia', 'proximo'),
                        )
                        last_slots = slots  # FIX 1: guardar para bloque <<<SLOTS>>>
                        tool_result_content = json.dumps(slots, ensure_ascii=False)

                    elif tool_name == 'create_event_cx':
                        result = self._create_event_cx(
                            asesora=tool_input.get('asesora', ''),
                            slot_id=tool_input.get('slot_id', ''),
                            slot_label=tool_input.get('slot_label', ''),
                            sender_id=tool_input.get('sender_id', sender_id),
                            sender_name=tool_input.get('sender_name', sender_name),
                        )
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

    @staticmethod
    def _turno_canal(opcion):
        """Determina qué fila de asesoras_turno usar según la opción elegida.
        Opción 1 (virtual) o 2 (presencial) → valoración con Dr. Gio → 'cirugia_valoracion'
        Opción 3 (prediagnóstico) o cualquier otra → 'cirugia'
        """
        opcion_str = str(opcion or '').lower()
        if any(k in opcion_str for k in ('1', 'virtual', '2', 'presencial', 'valoracion', 'valoración')):
            # Solo si NO menciona 'prediagnóstico' / 'gratuito'
            if not any(k in opcion_str for k in ('3', 'prediag', 'gratuito')):
                return 'cirugia_valoracion'
        return 'cirugia'

    def _notify_lead(self, fields, sender_id):
        """Routing por score:
          URGENTE  → todos (las 3 asesoras + Sharon + Central) SIN rotar turno
          CALIENTE → asesora en turno (canal según opción) + Sharon + Central, SÍ rota
          TIBIO    → asesora en turno (canal según opción) + Sharon + Central, SÍ rota
          FRÍO     → solo Sharon + Central, NO rota turno

        Canal de turno:
          opción 1/2 (valoración Dr. Gio) → asesoras_turno canal='cirugia_valoracion'
          opción 3 (prediagnóstico)        → asesoras_turno canal='cirugia'
        """
        nombre     = fields.get('nombre', '—')
        proc       = fields.get('procedimiento', '—')
        fecha      = fields.get('fecha_deseada') or fields.get('fecha', 'no definida')
        ciudad     = fields.get('ciudad', '—')
        tel        = fields.get('telefono', sender_id) or sender_id
        motivacion = fields.get('motivacion', '—')
        opcion     = fields.get('opcion_elegida', '—')
        score      = (fields.get('score') or fields.get('prioridad') or 'CALIENTE').upper()

        turno_canal = self._turno_canal(opcion)
        print(f"[CX] _notify_lead opcion={opcion!r} turno_canal={turno_canal!r} score={score}", flush=True)

        sharon = os.environ.get('DRA_SHARON', '').strip()
        admin  = os.environ.get('ADMIN_CX', '').strip()
        drgio  = os.environ.get('DRGIO_TEL', '573181800131').strip()

        results = {}

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
        return score

    # ------------------------------------------------------------------
    # Flujo principal
    # ------------------------------------------------------------------
    def process(self, sender_id, sender_name, text, canal='cirugia', cuenta_receptora=None, send=True):
        """Procesa el mensaje entrante.

        Args:
            send: Si True (default), envía la respuesta via Instagram/WhatsApp directamente.
                  Si False, NO envía — devuelve el texto de respuesta para que el caller lo envíe.
        Returns:
            str — texto visible al paciente (sin bloque NOTIFY). Vacío si no hay reply.
        """
        print(f"[CX] canal={canal!r} send={send} {sender_id}: {text[:60]!r}", flush=True)

        history = self._load_history(sender_id, canal=canal)
        user_content = f"[{sender_name or sender_id}]: {text}" if sender_name else text
        history.append({'role': 'user', 'content': user_content})

        self._save_message(sender_id, sender_name, text, 'entrante', 'paciente', canal=canal)

        full_response = self._call_claude(history, sender_id=sender_id, sender_name=sender_name or '')
        print(f"[CX] Claude len={len(full_response)} preview={full_response[:80]!r}", flush=True)

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
            print(f"[CX] NOTIFY fields={fields}", flush=True)
            self._notify_lead(fields, sender_id)

        return user_facing


def _now_iso():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
