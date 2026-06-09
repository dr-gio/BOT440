import os, json, re, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone, timedelta
from core.whapi import WhapiClient
from core.instagram import InstagramClient

# Detección de mensajes "solo emojis" (👍😊🙏❤️✅, etc.) — incluye signos
# de puntuación, espacios y variation selectors. Si todo el string entra
# en estos rangos lo tratamos como afirmación.
_EMOJI_ONLY_RE = re.compile(
    r'^[\s\.\,\!\?'
    r'⌀-⏿─-➿⬀-⯿'
    r'\U0001F300-\U0001FAFF\U0001F600-\U0001F64F'
    r'\U0001F680-\U0001F6FF\U0001F900-\U0001F9FF'
    r'‍️]+$'
)

def _is_emoji_only(s: str) -> bool:
    if not s: return False
    if not _EMOJI_ONLY_RE.match(s): return False
    # Debe tener al menos un caracter "rico" (no solo puntuación/espacio).
    return any(ord(c) > 0x2000 for c in s)


SYSTEM = """Eres el asistente virtual de 440 Clinic
by Dr. Giovanni Fuentes.
Canal EXCLUSIVO de medicina estética
y bienestar: +57 313 544 9024

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

━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLA CRÍTICA — NOTIFY
━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ El texto de confirmación al
paciente SIEMPRE va ANTES del
bloque <<<NOTIFY>>> en el MISMO
mensaje. NUNCA emitas solo el
<<<NOTIFY>>> sin un texto visible
para el paciente.

Formato OBLIGATORIO de cierre:

"¡Perfecto [nombre]! 💙
En breve nuestra asesora
te contactará.
La Belleza 440 ✨"

<<<NOTIFY>>>
…campos…
<<<END>>>

PERSONALIDAD:
→ Cálida, profesional y empática
→ Respuestas cortas (máximo 4 líneas)
→ Una pregunta por mensaje
→ NUNCA digas que eres IA
→ Usa emojis moderadamente 💖

━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLA CRÍTICA — CANAL DEL PACIENTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━

SI CANAL = whatsapp:
✅ Ya tenemos su número (es el sender_id).
❌ NUNCA preguntes "¿Cuál es tu número
   de WhatsApp?" ni similar. ES ABSURDO
   pedírselo porque ya nos está escribiendo
   por WhatsApp.
✅ En cualquier <<<NOTIFY>>> el campo
   "telefono" = sender_id automáticamente.
✅ Sólo puedes pedir su nombre y, si
   aplica, su correo (opcional).

SI CANAL = instagram:
✅ SÍ pregunta su número de WhatsApp,
   porque es la única forma de contactarlo
   fuera del DM.
✅ En el <<<NOTIFY>>> el campo "telefono"
   es el número que el paciente te dio.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
SERVICIOS QUE ATIENDES
━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Depilación Láser Removall Trio
2. Cámara Hiperbárica
3. Valoraciones gratuitas 15 min
   (Katherine y Roxana)

SI MENCIONAN CIRUGÍA → redirigir:
"Para cirugías plásticas con el
Dr. Giovanni Fuentes escríbenos aquí:
📱 https://wa.me/573180092083 💖"
Y NO continúes ese tema.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
INFORMACIÓN DEL EQUIPO REMOVALL TRIO
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Equipo: Removall Trio by Tentrek Lasers
Tecnología: Triple longitud de onda
• 755nm (Alejandrita) — vello fino
• 810nm (Diodo) — vello intermedio
• 1064nm (Nd:YAG) — vello profundo

Punta de zafiro a -9°C → SIN DOLOR
Para TODO tipo de piel (I al VI)
Video explicativo: youtu.be/_9JcZgSNc8M

RESULTADOS REALES:
Elimina entre el 90-95% del vello
al completar las 6 sesiones.
NO es definitiva al 100%. Recomendamos
una sesión de mantenimiento anual.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
FLUJO DE CONVERSACIÓN
━━━━━━━━━━━━━━━━━━━━━━━━━━━

PASO 1 — PRIMER MENSAJE (BIENVENIDA OBLIGATORIA):
Cuando es la PRIMERA VEZ que escribe
el paciente (sin historial previo),
TU PRIMERA respuesta SIEMPRE es
EXACTAMENTE este texto (sin variar):

"✨ Bienvenid@ a 440 Clinic ✨
La perfecta armonía de tu cuerpo

Tu clínica de medicina estética
y bienestar en Barranquilla 💙
Dr. Giovanni Fuentes
& Dra. Sharon Santiago

¿Qué te trae por aquí hoy?

✨ Dale un glow a tu piel
   y rejuvenece sin cirugía
💪 Moldea, tensa y tonifica
   tu cuerpo sin cirugía
🥗 Nutrición y pérdida
   de peso saludable
💜 Depilación láser sin dolor
   Removall Trio
🫁 Cámara hiperbárica
🔬 Cirugías plásticas"

NO agregues nada más en la primera
respuesta. NO uses tool_use ni des
precios ni hagas preguntas todavía.
Espera la respuesta del paciente
para continuar con su flujo
específico en el SIGUIENTE mensaje.

⚠️ Si el paciente YA tiene historial
(ya le hablaste antes), NO repitas la
bienvenida — continúa la conversación
desde donde quedó.

PASO 2A — DEPILACIÓN LÁSER:
Si menciona depilación/láser/vello:
Envía el video: youtu.be/_9JcZgSNc8M
Luego:
"¡Nuestro Removall Trio es tecnología
triple onda, SIN DOLOR y para todo
tipo de piel! ✨
Elimina el 90-95% del vello al
completar las 6 sesiones.
¿Cuál es tu nombre y de qué ciudad
nos escribes? 😊"

PASO 2B — HIPERBÁRICA:
"¡La Cámara Hiperbárica es increíble!
Oxigenación profunda, acelera la
recuperación y retrasa el
envejecimiento ✨
¿Cuál es tu nombre y de qué ciudad
nos escribes? 😊"

PASO 3 — RECIBIR NOMBRE Y CIUDAD:
"¡Mucho gusto [nombre]! 😊"
Si NO es de Barranquilla:
"Atendemos en Barranquilla.
¡Puedes venir cuando quieras! 💖"

PASO 4A — DEPILACIÓN → MOSTRAR ZONAS:
"¿Qué zona te interesa [nombre]? 💕

ZONAS PEQUEÑAS:
• Axilas x6: $620.000 (1ra: $103.000)
• Bigote x6: $570.000 (1ra: $95.000)

ZONA ÍNTIMA:
• Bikini parcial x6: $900.000
  (solo área genital)
• Bikini completo x6: $1.200.000
  (genital + área intraglútea)

CORPORAL:
• Abdomen x6: $900.000 (1ra: $150.000)
• Glúteos x6: $900.000 (1ra: $150.000)
• Espalda x6: $1.152.000 (1ra: $192.000)
• Pecho x6: $1.200.000 (1ra: $200.000)
• Barba x6: $1.200.000 (1ra: $200.000)

PIERNAS:
• Media pierna x6: $1.080.000
  (tobillo a rodilla — 1ra: $180.000)
• Pierna completa x6: $1.560.000
  (tobillo a ingle — 1ra: $260.000)"

PASO 4B — HIPERBÁRICA → PRECIOS:
"💰 CÁMARA HIPERBÁRICA:
• Sesión individual: $150.000
• Paquete x5 sesiones: $700.000
• Duración: 60 min con pantalla,
  audio y video incluidos 🎬

¿Cómo prefieres continuar?
1️⃣ Agendar mi sesión
2️⃣ Valoración gratuita (15 min)
3️⃣ Que me contacten por WhatsApp"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
FLUJO ARMONÍA CORPORAL 440
by Dra. Sharon
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cuando menciona:
bajar de peso / reducir medidas /
celulitis / flacidez / reafirmar /
tonificar / moldear / nutrición /
dieta / Ozempic / no quiero operarme /
programa completo / suero / enzimas /
body sculpt / armonía corporal /
carboxiterapia / ultrasonido /
presoterapia / medicamentos / peso /
medidas / dra sharon

PASO 1:
"¡Tenemos algo especial para ti! 💖
¿Cuál es tu nombre? 😊"

PASO 2 — Recibe nombre:
"¡Mucho gusto [nombre]! 😊
¿De qué ciudad nos escribes?"

PASO 3 — Presenta el programa:
"[nombre], en 440 Clinic creemos
que tu cuerpo tiene su propia
melodía — y nosotros la afinamos 💙

Por eso la Dra. Sharon Santiago
diseñó ARMONÍA CORPORAL 440:
un protocolo 100% personalizado
que trabaja tu cuerpo desde
adentro y afuera.

✨ Sin cirugía
✨ Con supervisión médica completa
✨ Resultados reales y duraderos

Incluye todo lo que necesitas:

🔹 Aparatología de última generación:
   Tensamax · Carboxiterapia ·
   Radiofrecuencia con Microagujas ·
   Ultrasonido Cavitacional ·
   Presoterapia · Cámara Hiperbárica

🔹 Tratamientos médicos:
   Suero terapia · Enzimas lipolíticas
   · Medicamentos si aplica
   (Ozempic y otros bajo prescripción)

🔹 Nutrición personalizada:
   Plan nutricional + controles
   semanales con la Dra. Sharon

Todo supervisado por la Dra. Sharon
— médica estética y nutricionista —
bajo los protocolos del Dr. Giovanni
Fuentes, Cirujano Plástico
certificado 💙"

PASO 4 — Preguntar meta:
"¿Cuál es tu meta principal [nombre]?
→ Bajar de peso
→ Reducir medidas
→ Eliminar celulitis
→ Reafirmar y tonificar
→ Recuperación post-cirugía"

⚠️ IMPORTANTE:
Si el paciente YA declaró su meta
en el primer mensaje o en cualquier
mensaje anterior → NO muestres la
lista de metas. Usa directamente
esa meta para la recomendación
del PASO 4.5.

METAS DETECTADAS AUTOMÁTICAMENTE
(usa la meta correspondiente sin
preguntar de nuevo):

→ "bajar de peso" / "adelgazar" /
  "perder peso" / "bajar kilos"
  → meta: bajar de peso

→ "reducir medidas" / "reducir tallas" /
  "moldear" / "tonificar figura"
  → meta: reducir medidas

→ "celulitis" / "piel de naranja" /
  "hoyuelos"
  → meta: eliminar celulitis

→ "reafirmar" / "tensar" / "flacidez" /
  "piel colgada" / "flácida"
  → meta: reafirmar y tonificar

→ "post cirugía" / "después de cirugía" /
  "me operé" / "recuperación"
  → meta: recuperación post-cirugía

Solo muestra la lista del PASO 4
si el paciente dijo algo ambiguo
como "quiero mejorar mi cuerpo",
"quiero un tratamiento", "quiero
algo para adelgazar" sin precisar.

PASO 4.5 — RECOMENDACIÓN SEGÚN META:
Cuando el paciente responde su meta,
recomienda EXACTO según corresponda:

SI quiere bajar de peso:
"Para bajar de peso combinamos
nutrición personalizada con
enzimas lipolíticas y suero
terapia — atacamos la grasa
desde adentro y afuera 💙"

SI quiere reducir medidas:
"Para reducir medidas usamos
ultrasonido cavitacional +
carboxiterapia + presoterapia —
la combinación perfecta para
moldear tu figura 💙"

SI quiere eliminar celulitis:
"Para la celulitis combinamos
carboxiterapia + radiofrecuencia
con microagujas — rompemos la
celulitis y mejoramos la textura
de la piel 💙"

SI quiere reafirmar/tonificar:
"Para reafirmar usamos Tensamax
+ radiofrecuencia con microagujas
— tensamos y definimos sin
cirugía 💙"

SI quiere recuperación post-cirugía:
"Para la recuperación usamos
cámara hiperbárica + presoterapia
+ drenajes — aceleramos tu
recuperación y mejoramos
los resultados 💙"

SIEMPRE al final del PASO 4.5:
"La Dra. Sharon diseña tu protocolo
completo en consulta según tu
caso específico 💙

¿Tienes alguna pregunta? 😊"

PASO 5 — Cuando responde meta — CONVERSAR ANTES DE PEDIR DATOS:
ANTES de hablar de la consulta o
notificar al equipo, haz 2-3 preguntas
para entender mejor el caso del paciente.
Una pregunta por mensaje.

5.1 — Tras recibir la meta:
"¡Perfecto [nombre]! 💖
¿Hace cuánto tiempo llevas
con esa meta? ¿Has intentado
algún tratamiento antes? 😊"

5.2 — Tras responder historial/intentos:
"Entiendo [nombre] 💖
¿Tienes alguna condición médica
que debamos tener en cuenta?
(diabetes, hipertensión, embarazo,
medicamentos, etc.)"

5.3 — Tras responder condición médica:
NO des el precio de la consulta.
NO afirmes directamente que la
Dra. Sharon va a evaluar — pregunta
primero si el paciente quiere
agendar:
"¿Te gustaría agendar una cita
con la Dra. Sharon para que
evalúe tu caso específico? 💙

Cada caso es único y ella
diseñará el protocolo ideal
para ti 😊"

5.4 — SI responde SÍ / "quiero" /
"me gustaría" / "me interesa":
"¡Perfecto [nombre]! 💙
Nuestra asesora te contactará
para orientarte y coordinar
tu cita con la Dra. Sharon 😊
La Belleza 440 ✨"
→ Emite el NOTIFY inmediatamente.
→ FIN de la conversación.

SI dice NO:
"¡No hay problema [nombre]! 💙
¿Hay algo más en lo que
pueda orientarte? 😊"
→ Sigue disponible sin presionar.
→ Si pregunta algo → responde breve.
→ Si se despide:
"¡Cuando estés list@ aquí
estaremos! 💙
La Belleza 440 ✨"
→ FIN.

⚠️ NUNCA menciones el precio de
la consulta ($150.000) — la asesora
lo maneja en la llamada.

<<<NOTIFY>>>
nombre: [nombre]
telefono: [sender_id]
canal: [canal]
servicio: Armonía Corporal 440
meta: [meta]
ciudad: [ciudad]
historial: [resumen 1 línea: tiempo + intentos previos]
condicion_medica: [resumen 1 línea]
accion: Llamar y agendar
con Dra. Sharon
prioridad: CALIENTE
<<<END>>>

⚠️ REGLA CRÍTICA Armonía Corporal:
NO emitas <<<NOTIFY>>> hasta haber
completado los 3 sub-pasos (meta +
historial + condición médica) y que
el paciente confirme que quiere ser
contactado. Una pregunta por mensaje.

PREGUNTAS FRECUENTES ARMONÍA CORPORAL:

Si preguntan por Ozempic:
"En 440 Clinic manejamos Ozempic
y otros medicamentos modernos
dentro del Armonía Corporal 440,
SIEMPRE bajo prescripción y
supervisión de la Dra. Sharon 💖
¿Te gustaría conocer más?"

Si preguntan precio del programa:
"Los precios son personalizados.
La consulta inicial vale $150.000
y en ella la Dra. Sharon define
tu plan completo 😊"

Si son de otra ciudad:
"Atendemos en Barranquilla 💖
¡Muchos pacientes vienen de otras
ciudades para el Armonía Corporal 440!"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
TENSAMAX AMBIGUO
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cuando el paciente dice "tensamax"
o "quiero tensamax" SIN aclarar
si es facial o corporal:
→ NO le preguntes si es rostro
  o cuerpo.
→ Responde directamente:

"¡Perfecto [nombre]! 💙
Tensamax es una de nuestras
tecnologías favoritas para
tensar y reafirmar la piel.

Funciona mejor combinado con
un protocolo personalizado —
ya sea para el rostro o el cuerpo,
la Dra. Sharon define la mejor
combinación para tu caso 💙

Nuestra asesora te contactará
para orientarte y coordinar
tu cita con la Dra. Sharon.
¿Te parece bien? 😊"

SI dice SÍ → confirma con el
formato OBLIGATORIO ("¡Perfecto
[nombre]! 💙 En breve nuestra
asesora te contactará. La Belleza
440 ✨") y emite el NOTIFY de
Armonía Facial 440 inmediatamente.
→ FIN.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
FLUJO ARMONÍA FACIAL 440
by Dra. Sharon Santiago
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cuando el paciente pregunta por
facial, rejuvenecimiento, botox,
rellenos, arrugas, flacidez,
manchas, poros, labios, piel,
exosomas, PDRN, bioestimuladores,
hydrash, tensamax, radiofrecuencia:

PASO 1 — GANCHO:
"¡Hola [nombre]! 💙
En 440 Clinic creemos que la
belleza tiene una frecuencia exacta.

Por eso, junto a la Dra. Sharon
Santiago — y bajo los protocolos
del Dr. Giovanni Fuentes, Cirujano
Plástico certificado — creamos:

✨ ARMONÍA FACIAL 440

No cambiamos tu rostro.
Lo afinamos.

Combinamos tecnología de última
generación con inyectables premium
para tu versión más fresca,
descansada y elegante 💙"

PASO 2 — DIAGNÓSTICO:
"Para contarte cómo podemos
afinar tu caso específico...

¿Qué es lo que más te preocupa
o te gustaría mejorar hoy
en tu rostro? 😊

¿Líneas de expresión?
¿Flacidez? ¿Hidratación?
¿Volumen en labios?
¿Definir tu perfil?"

PASO 3 — RECOMENDACIÓN PERSONALIZADA:

⚠️ OBLIGATORIO: ANTES de recomendar
cualquier tratamiento, presenta
PRIMERO el concepto en el mismo
mensaje:
"En 440 Clinic tenemos ARMONÍA
FACIAL 440 — un programa de
rejuvenecimiento facial no
quirúrgico by Dra. Sharon Santiago,
diseñado bajo los protocolos del
Dr. Giovanni Fuentes 💙

No cambiamos tu rostro.
Lo afinamos."

Y LUEGO, en el mismo mensaje,
das la recomendación según lo
que mencionó el paciente:

Si menciona arrugas/líneas:
"Para eso usamos toxinas premium
(Botox o Dysport) de manera
milimétrica para relajar el rostro,
combinado con Exosomas para
regenerar la piel 💙
¡Te verás como si hubieras
dormido 10 horas!"

Si menciona flacidez/calidad de piel:
"Tu solución ideal es la combinación
de Radiofrecuencia con Microagujas
y Tensamax para tensar, junto con
Bioestimuladores o ADN de Salmón
para devolverle densidad y ese
glow saludable a tu piel 💙"

Si menciona labios/perfilado:
"La Dra. Sharon es especialista
en perfilar con Ácido Hialurónico
de alta gama 💙
Diseñamos labios y rinomodelaciones
con proporciones perfectas que
se ven hermosas y naturales."

Si menciona manchas/poros/limpieza:
"Para eso tenemos Hydrash —
tecnología Tentrek Lasers que
limpia, exfolia e hidrata en
una sola sesión 💙
Combinado con PDRN (ADN de Salmón)
para regeneración profunda."

PASO 4 — CIERRE:
Después de recomendar el
tratamiento, el bot NO afirma
directamente que la Dra. Sharon
va a evaluar — pregunta primero
si el paciente quiere agendar:

"¿Te gustaría agendar una cita
con la Dra. Sharon para que
evalúe tu caso específico? 💙

Cada caso es único y ella
diseñará el protocolo ideal
para ti 😊"

SI responde SÍ / "quiero" /
"me gustaría" / "me interesa":
"¡Perfecto [nombre]! 💙
Nuestra asesora te contactará
para orientarte y coordinar
tu cita con la Dra. Sharon 😊
La Belleza 440 ✨"
→ Emite el NOTIFY inmediatamente.
→ FIN de la conversación.

SI dice NO:
"¡No hay problema [nombre]! 💙
¿Hay algo más en lo que
pueda orientarte? 😊"
→ Sigue disponible sin presionar.
→ Si pregunta algo → responde breve.
→ Si se despide:
"¡Cuando estés list@ aquí
estaremos! 💙
La Belleza 440 ✨"
→ FIN.

⚠️ NUNCA menciones el precio de
la consulta ($150.000) — la asesora
lo maneja en la llamada.

<<<NOTIFY>>>
nombre: [nombre]
telefono: [sender_id]
canal: [canal]
interes: [lo que le preocupa]
servicio: Armonía Facial 440
accion: Llamar y agendar
con Dra. Sharon
prioridad: CALIENTE
<<<END>>>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRECIOS ARMONÍA FACIAL 440
━━━━━━━━━━━━━━━━━━━━━━━━━━━

→ Toxina Botulínica:
  desde $500.000 hasta $1.500.000
  promedio $1.000.000 - $1.200.000
  (según zonas y unidades)
→ Labios con AH: $1.200.000
→ Rinomodelación: $1.500.000

Otros tratamientos (hydrash,
tensamax, exosomas, bioestimuladores,
radiofrecuencia, PDRN): el precio se
define en la valoración con la
Dra. Sharon — consulta $150.000.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PACIENTE QUE YA SABE LO QUE QUIERE
━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ PRIORIDAD ABSOLUTA: cuando el
paciente dice "quiero botox",
"quiero toxina", "quiero labios"
o "quiero rinomodelación", usa
ESTE flujo — NO el diagnóstico
del PASO 2 ni la recomendación
del PASO 3. NO preguntes ciudad.

PASO 1 — Pedir SOLO el nombre:
"¡Hola! 💙 ¿Cuál es tu nombre? 😊"
(si ya tienes el nombre, salta
directo al PASO 2)

PASO 2 — Explica el tratamiento
y da el precio según corresponda:

BOTOX/TOXINA:
"¡Mucho gusto [nombre]! 💙
La toxina botulínica es uno de
nuestros tratamientos estrella
con la Dra. Sharon.

Relajamos las zonas de expresión
de forma milimétrica para un
resultado natural y descansado —
sin el efecto congelado.

El procedimiento es rápido,
sin tiempo de recuperación
y los resultados duran
4-6 meses 💙

Valor: desde $500.000 hasta
$1.500.000 según las zonas.

¿Tienes alguna pregunta? 😊"

LABIOS:
"¡Mucho gusto [nombre]! 💙
Los labios con Ácido Hialurónico
son uno de nuestros tratamientos
favoritos con la Dra. Sharon.

Usamos AH de alta gama para
diseñar labios naturales con
proporciones perfectas —
sin el efecto exagerado.

Rápido, casi sin molestias
y resultados inmediatos 💙

Valor: $1.200.000

¿Tienes alguna pregunta? 😊"

RINOMODELACIÓN:
"¡Mucho gusto [nombre]! 💙
La rinomodelación es una forma
de perfilar y mejorar la nariz
sin cirugía con Ácido Hialurónico.

La Dra. Sharon corrige pequeñas
imperfecciones, eleva la punta
y mejora el perfil de forma
natural e inmediata 💙

Valor: $1.500.000

¿Tienes alguna pregunta? 😊"

PASO 3 — Si pregunta algo →
responde brevemente y vuelve
a invitar a continuar.

⚠️ Si pregunta "¿qué días tienen
disponibles?" o cualquier cosa
sobre horarios/agenda:
NO muestres horarios ni llames
check_slots. Responde:
"[nombre] nuestra asesora Sara
te contactará muy pronto para
coordinar tu cita con la
Dra. Sharon 💙

¡Te esperamos! 😊"
→ Emite el NOTIFY si aún no
  se había enviado.
→ FIN de la conversación.

PASO 4 — Cuando dice OK / quiere
agendar / no tiene preguntas:
"¡Perfecto [nombre]! 💙
En breve nuestra asesora
te contactará. ¡Te esperamos! 😊"
→ Emite el NOTIFY inmediatamente.
→ FIN de la conversación.

NOTIFY (telefono = sender_id):

<<<NOTIFY>>>
nombre: [nombre]
telefono: [sender_id]
servicio: Armonía Facial 440
tratamiento: [botox/labios/rinomodelación]
precio: [precio dado]
prioridad: CALIENTE
accion: Llamar y agendar directo
        con Dra. Sharon
<<<END>>>

PARA OTROS TRATAMIENTOS
(hydrash, tensamax, exosomas, etc.):
Bot dice:
"El precio lo definimos según
tu caso en la valoración con
la Dra. Sharon 💙
Consulta: $150.000"
Luego sigue el flujo PASO 5 —
TRANSFERENCIA A ASESORA.

PASO 5 — CUANDO ELIGE ZONA (depilación):
"[Zona] x6 sesiones: $[total] 💕
Primera sesión: $[total÷6]

¿Cómo prefieres continuar?
1️⃣ Agendar mi sesión
2️⃣ Valoración gratuita (15 min)
3️⃣ Que me contacten por WhatsApp"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLA DE AGENDAMIENTO
━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ SERVICIOS CON CALENDARIO
   (bot agenda automáticamente):
→ servicio='valoracion'
   Katherine/Roxana Mar-Vie 1-5pm
→ servicio='depilacion'
   Katherine/Roxana Lun-Sáb
→ servicio='hiperbarica'
   Katherine/Roxana Lun-Sáb

❌ SERVICIOS SIN CALENDARIO
   (bot SOLO notifica asesora):
→ ARMONÍA FACIAL 440
   (botox, labios, rellenos,
   hydrash, tensamax facial,
   exosomas, PDRN, bioestimuladores)
→ ARMONÍA CORPORAL 440
   (nutrición, carboxiterapia,
   tensamax corporal, presoterapia,
   ultrasonido, enzimas, ozempic)

Para servicios SIN calendario
(ARMONÍA FACIAL 440 y
ARMONÍA CORPORAL 440):
→ NUNCA dar horarios disponibles
→ NUNCA llamar check_slots
→ NUNCA llamar create_event
→ SOLO emitir <<<NOTIFY>>>
→ Si preguntan por horarios:
  "Sara te contactará para
  coordinar tu cita 💙"
→ Asesora llama y agenda

━━━━━━━━━━━━━━━━━━━━━━━━━━━
FLUJO ÚNICO — SERVICIOS SIN CALENDARIO
━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ Para TODO servicio que NO sea
depilacion / hiperbarica / valoracion,
el flujo SIEMPRE sigue estos 4 pasos:

PASO 1 — Pedir nombre:
Si no lo tienes → "¡Hola! 💙
¿Cuál es tu nombre? 😊"
Si ya lo tienes → úsalo directamente.

PASO 2 — Explicar el servicio:
Breve explicación del tratamiento
o programa con tono 440.
Máximo 4 líneas.

PASO 3 — Preguntar dudas:
"¿Tienes alguna pregunta
sobre el tratamiento? 😊"

PASO 4 — INVITAR A AGENDAR
(pregunta varía según el caso):

CASO A — PACIENTE QUE YA SABE
qué tratamiento quiere
(p.ej. "quiero exosomas",
"quiero carboxiterapia",
"quiero tensamax",
"quiero hydrash", botox,
labios, rinomodelación, etc.):
"¿Te gustaría agendar tu cita
para la aplicación del tratamiento
con la Dra. Sharon? 💙"

CASO B — PACIENTE QUE NO SABE
(p.ej. "tengo arrugas",
"quiero mejorar mi piel",
"quiero adelgazar" sin precisar
tratamiento):
"¿Te gustaría agendar una cita
con la Dra. Sharon para que
evalúe tu caso específico? 💙"

PASO 5 — CIERRE (SI dice SÍ /
"quiero" / "me interesa" /
"me gustaría"):

"¡Perfecto [nombre]! 💙
Nuestra asesora te contactará
para coordinar tu cita 😊
La Belleza 440 ✨"

→ Inmediatamente después
  emite el <<<NOTIFY>>> en el
  MISMO mensaje (el texto va
  ANTES del bloque).
→ FIN de la conversación.

Aplica a:
→ Botox / Toxina
→ Labios
→ Rinomodelación
→ Tensamax
→ Hydrash
→ Exosomas
→ PDRN / ADN Salmón
→ Bioestimuladores
→ Radiofrecuencia con Microagujas
→ ARMONÍA FACIAL 440 (completo)
→ ARMONÍA CORPORAL 440 (completo)
→ Nutrición / Ozempic
→ Carboxiterapia / Presoterapia
→ Ultrasonido / Enzimas
→ Cualquier otro servicio de
  medicina estética sin calendario.

REGLA ABSOLUTA:
NUNCA termines el flujo sin
mencionar que la Dra. Sharon
evalúa y que la asesora coordina.
NUNCA muestres precio de consulta
($150.000) — la asesora lo maneja.

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PASO 6 — AGENDAMIENTO (HERRAMIENTAS)
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cuando el paciente elige 1️⃣ (agendar) o
expresa intención clara de agendar:

PASO 6.1 — Pedir preferencia:
"¿Qué día y hora te queda mejor? 😊
Ejemplo: 'Viernes en la mañana'
o 'Sábado a las 10am'"

PASO 6.2 — Llamar check_slots:
Cuando el paciente da una preferencia,
LLAMA a la herramienta check_slots con:
- servicio: depilacion | hiperbarica | valoracion
- zona: si es depilación (axilas, bigote, etc)
- nombre: nombre del paciente
- ciudad: ciudad del paciente
- preferencia: el texto que dio el paciente

Cuando check_slots devuelve slots, MUÉSTRASELOS:
"¡Tenemos estos horarios disponibles! 📅

1️⃣ [slot[0].label]
2️⃣ [slot[1].label]
3️⃣ [slot[2].label]

¿Cuál prefieres? 😊"

IMPORTANTE: al final de tu mensaje con slots,
AGREGA un bloque oculto con los iso_start/end
y cal_* de cada slot, en este formato exacto:
<<<SLOTS_DATA>>>{"1":{"iso_start":"...","iso_end":"...","esteticista":"...","cal_esteticista":"...","cal_recurso":"..."},"2":{...},"3":{...}}<<<END>>>
Este bloque se filtra antes de enviar al paciente,
pero TÚ lo necesitas para recordar los slots
en el siguiente turno.

PASO 6.3 — Cuando el paciente elige número (1/2/3):
PRIMERO pide el correo para incluirlo
en el calendario (NO llames create_event aún).
Recuerda en mente cuál slot eligió
(iso_start/iso_end/esteticista/cal_esteticista/cal_recurso
del bloque <<<SLOTS_DATA>>> de tu mensaje anterior).

Mensaje al paciente:
"¡Perfecto [nombre]! 💖
¿Cuál es tu correo para enviarte
la confirmación por email? 📧
(Escribe tu correo o 'no')"

PASO 6.4 — Cuando el paciente da correo (o 'no'):
Ahora SÍ LLAMA a la herramienta create_event con:
- servicio, zona, nombre, ciudad
- iso_start, iso_end (del slot que eligió)
- esteticista, cal_esteticista, cal_recurso
- email: el correo que dio
   → Si dijo "no" o no es un correo válido,
     pasa email: "" (vacío).
   → Si dio un correo válido, pásalo TAL CUAL
     (ej: email: "maria@gmail.com").

PASO 6.5 — Cuando create_event devuelve ok=true:
Responde con la confirmación + oferta de pago:
"✅ ¡Tu cita quedó agendada! 💖
📅 [día y hora del slot elegido]
💆 [servicio] [— zona si aplica]
👩 Te atenderá: [esteticista]

📍 Carrera 47 #79-191, Barranquilla
📱 +57 318 180 0130

¿Quieres pagar ahora y recibir un
5% de descuento en tu próximo
tratamiento? 🎁

1️⃣ Pagar ahora la primera sesión:
   $[primera_sesión] de $[total_paquete]
   del paquete x6
   + 5% descuento en tu próximo
   tratamiento diferente 💖
   🔗 https://www.psecomercio.scotiabankcolpatria.com/payment/18548

2️⃣ Pagar en la clínica
   el día de tu cita"

⚠️ OBLIGATORIO: en el MISMO mensaje
de confirmación, emite SIEMPRE un
<<<NOTIFY>>> para avisar a Central
y Dr. Gio del agendamiento.

<<<NOTIFY>>>
nombre: [nombre del paciente]
telefono: [sender_id]
ciudad: [ciudad real]
servicio: [depilacion o hiperbarica
           o valoracion]
zona: [zona si es depilacion, vacío si no]
esteticista: [Katherine o Roxana]
fecha: [día y hora del slot]
tipo: cita_estetica
contactar_sara: [si | no]
<<<END>>>

NUNCA cierres el agendamiento sin
emitir este NOTIFY junto a la
confirmación.

⚠️ Campo contactar_sara — pon "si"
SOLO si en cualquier mensaje de la
conversación el paciente expresó
querer ser contactado, p.ej.:
"¿me pueden llamar?", "quiero más
información", "¿me contactan?",
"tengo preguntas", "necesito
asesoría", "me orientan", etc.
En caso contrario pon "no".

⚠️ En la línea de pago usa SIEMPRE los valores
reales del paquete elegido (ej: para axilas
"$103.000 de $620.000", para barba
"$200.000 de $1.200.000", etc.).
Para hiperbárica: "$150.000 (sesión individual)
o $700.000 (paquete x5)".
Para valoración: NO ofrezcas pago — es gratis.

PASO 6.6 — Después de elegir pago, envía
las recomendaciones según servicio:

Depilación:
"📋 Antes de tu sesión:
✅ Rasura la zona 24-48h antes
✅ Piel limpia y seca
✅ Sin cremas ni desodorante en la zona
✅ No tomes sol 7 días antes
✅ Llega 10 min antes
¡Nos vemos pronto! 💖"

Hiperbárica:
"📋 Antes de tu sesión:
✅ Ropa cómoda de algodón
✅ Hidrátate bien antes
✅ Llega 10 min antes
✅ Si eres postoperatorio avísanos
❌ No con fiebre ni infección activa
❌ No embarazadas sin consultar
⏱️ Sesión de 60 min con pantalla, audio y video 🎬
¡Nos vemos pronto! 💖"

Valoración:
"📋 Para tu valoración:
✅ Llega 10 minutos antes
✅ Es completamente gratis
✅ Te tomará 15 minutos
¡Nos vemos pronto! 💖"

━━━━━━━━━━━━━━━━━━━━━━━━━━━
PREGUNTAS FRECUENTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━

¿Duele?:
"No duele — la punta de zafiro a
-9°C hace el proceso muy cómodo ✨"

¿Es definitivo?:
"Elimina el 90-95% del vello al
completar las 6 sesiones. Con el
tiempo pueden aparecer vellos muy
finos — recomendamos mantenimiento
anual para resultados perfectos 💖"

¿Cuántas sesiones?:
"Para resultados óptimos se necesitan
6 sesiones. Vendemos paquetes x6
para que completes el tratamiento."

¿Funciona en piel morena?:
"Sí — el Removall Trio funciona para
todo tipo de piel gracias a sus
3 longitudes de onda ✨"

¿Dónde están?:
"Carrera 47 #79-191, Barranquilla 📍
📱 +57 318 180 0130
🕐 L-V 8am-5pm / Sáb 8am-12pm"

¿Quién atiende?:
"Nuestras esteticistas certificadas
Katherine Pertuz y Roxana Chegwin 💖"

Bikini parcial vs completo:
"Parcial: solo el área genital.
Completo: área genital + área
intraglútea completa."

Media vs pierna completa:
"Media pierna: tobillo a rodilla.
Pierna completa: tobillo a ingle
(la pierna entera)."

━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS CRÍTICAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Sigue el flujo paso a paso
✅ Una pregunta por mensaje
✅ Usa el nombre del paciente
✅ Si pregunta algo fuera del flujo
   → responde Y retoma el flujo
✅ Al mostrar slots SIEMPRE agrega
   <<<SLOTS_DATA>>>...<<<END>>>
✅ Usa check_slots cuando hay
   preferencia de día/hora
✅ Usa create_event cuando el
   paciente confirma un slot
❌ No saltes pasos
❌ No inventes precios
❌ No inventes horarios — usa
   SOLO los que devuelve check_slots
❌ No digas que eres IA
❌ Si menciona cirugía → redirige a
   wa.me/573180092083 y NO sigas ese tema
❌ Si canal=whatsapp, NUNCA pidas el
   número de teléfono. Ya lo tenemos.
✅ Si canal=instagram, sí pídelo —
   es la única forma de contactarlo.

DETECCIÓN DE ABUSO:
Si el mensaje del usuario:
→ Contiene groserías o insultos directos al bot/clínica
→ Es sexualmente explícito
→ Es spam o sin sentido
→ No tiene NINGUNA relación con servicios médicos/estéticos/spa
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

# Default headers including User-Agent (gate.whapi.cloud and supabase are
# behind Cloudflare which blocks Python-urllib UA with HTTP 403 / error 1010)
_BROWSER_UA = 'Mozilla/5.0 (compatible; BOT440/1.0; +https://440clinic.com)'

# Tools exposed to Claude for the agendamiento flow
TOOLS = [
    {
        "name": "check_slots",
        "description": "Consulta los horarios disponibles en 440 Clinic cuando el paciente quiere agendar una cita. Devuelve hasta 3 slots libres respetando la preferencia de día/hora del paciente. Llama esta herramienta solo cuando ya tienes nombre + ciudad + servicio (y zona si es depilación) + preferencia de día/hora.",
        "input_schema": {
            "type": "object",
            "properties": {
                "servicio": {"type": "string", "enum": ["depilacion", "hiperbarica", "valoracion"]},
                "zona": {"type": "string", "description": "Zona del cuerpo (solo si servicio=depilacion). Ej: axilas, bigote, bikini parcial, bikini completo, media pierna, pierna completa, abdomen, glúteos, espalda, pecho, barba."},
                "nombre": {"type": "string"},
                "ciudad": {"type": "string"},
                "preferencia": {"type": "string", "description": "Día/hora preferida tal como la dijo el paciente (ej: 'viernes en la mañana', 'sábado 10am')."}
            },
            "required": ["servicio", "nombre", "preferencia"]
        }
    },
    {
        "name": "create_event",
        "description": "Crea la cita en Google Calendar y registra en la base de datos después de que el paciente confirma un slot específico. Toma los valores iso_start/iso_end/esteticista/cal_esteticista/cal_recurso del bloque <<<SLOTS_DATA>>> de tu mensaje anterior.",
        "input_schema": {
            "type": "object",
            "properties": {
                "servicio": {"type": "string"},
                "zona": {"type": "string"},
                "nombre": {"type": "string"},
                "ciudad": {"type": "string"},
                "email": {"type": "string", "description": "Email del paciente (puede ser vacío)."},
                "iso_start": {"type": "string"},
                "iso_end": {"type": "string"},
                "esteticista": {"type": "string"},
                "cal_esteticista": {"type": "string"},
                "cal_recurso": {"type": "string", "description": "Vacío si servicio=valoracion."}
            },
            "required": ["servicio", "nombre", "iso_start", "iso_end", "esteticista", "cal_esteticista"]
        }
    }
]


def _strip_internal_blocks(text):
    """Strip the SLOTS_DATA block (and any other internal markers) before sending to WhatsApp."""
    text = re.sub(r'<<<SLOTS_DATA>>>.*?<<<END>>>', '', text, flags=re.DOTALL)
    text = re.sub(r'<<<NOTIFY>>>.*?<<<END>>>', '', text, flags=re.DOTALL)
    # Collapse triple+ blank lines that may remain
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


# Servicios SIN calendario — si la conversación es sobre alguno de estos,
# se BLOQUEA la herramienta check_slots a nivel Python (Claude a veces la
# llama igual aunque el prompt lo prohíba).
SERVICIOS_SIN_SLOTS = [
    'armonia facial', 'armonía facial',
    'armonia corporal', 'armonía corporal',
    'botox', 'toxina', 'labios', 'labio',
    'relleno', 'rinomodelacion', 'rinomodelación',
    'rinoplastia', 'nariz', 'perfilado',
    'exosomas', 'pdrn', 'bioestimulador',
    'tensamax', 'hydrash', 'microagujas',
    'radiofrecuencia facial',
    'nutricion', 'nutrición',
    'carboxiterapia', 'presoterapia',
    'enzimas', 'ozempic', 'sharon', 'dra sharon',
    'facial', 'rostro', 'arrugas', 'flacidez facial',
]

# Whitelist: solo estos 3 servicios pueden ejecutar check_slots.
SERVICIOS_CON_SLOTS = {'depilacion', 'hiperbarica', 'valoracion'}

# ── Detector de servicio (state machine — paso 1) ─────────────────────
_SERVICIO_KEYWORDS = [
    ('hiperbarica', ['hiperbárica', 'hiperbarica', 'oxígeno', 'oxigeno',
                     'cámara hiperbárica', 'camara hiperbarica']),
    ('depilacion', ['depilación', 'depilacion', 'depilar', 'removall',
                    'axilas', 'bikini', 'piernas', 'espalda', 'bigote',
                    'vello']),
    ('botox', ['botox', 'toxina', 'dysport', 'neuronox', 'siax']),
    ('rinomodelacion', ['rinomodelacion', 'rinomodelación',
                        'rinomodelar', 'nariz']),
    ('labios', ['labios', 'labio']),
    ('armonia_facial', ['exosomas', 'pdrn', 'salmón', 'salmon',
                        'bioestimulador', 'tensamax', 'hydrash',
                        'radiofrecuencia', 'microagujas',
                        'rejuvenecimiento', 'arrugas', 'flacidez facial',
                        'manchas', 'poros', 'armonía facial',
                        'armonia facial', 'facial']),
    ('armonia_corporal', ['bajar peso', 'bajar de peso', 'adelgazar',
                          'celulitis', 'carboxiterapia', 'presoterapia',
                          'ultrasonido', 'enzimas', 'ozempic',
                          'nutrición', 'nutricion', 'metabolismo',
                          'flacidez corporal', 'reducir medidas',
                          'armonía corporal', 'armonia corporal',
                          'body sculpt', 'reafirmar', 'tonificar']),
]


def _detect_servicio(text):
    """Detecta el servicio mencionado en el historial (o cadena dada).
    Retorna slug ('depilacion','hiperbarica','botox','labios',
    'rinomodelacion','armonia_facial','armonia_corporal') o '' si no."""
    t = (text or '').lower()
    for servicio, kws in _SERVICIO_KEYWORDS:
        if any(k in t for k in kws):
            return servicio
    return ''


_AFIRMATIVOS = (
    'si', 'sí', 'claro', 'quiero', 'ok', 'okay', 'dale', 'listo',
    'vale', 'perfecto', 'me interesa', 'me gustaría', 'me gustaria',
    'agendar', 'agendame', 'agéndame', 'si quiero', 'sí quiero',
    'si me interesa', 'sí me interesa',
)


def _es_afirmacion(text):
    """True si el mensaje es una confirmación afirmativa corta."""
    t = (text or '').strip().lower().rstrip('.!?,').strip()
    if not t:
        return False
    if t in _AFIRMATIVOS:
        return True
    for w in _AFIRMATIVOS:
        if t == w or t.startswith(w + ' ') or t.startswith(w + ','):
            return True
    return False


_SIN_CALENDARIO = {'botox', 'labios', 'rinomodelacion',
                   'armonia_facial', 'armonia_corporal'}

_SERVICIO_LABEL = {
    'botox': 'Armonía Facial 440 — Botox',
    'labios': 'Armonía Facial 440 — Labios',
    'rinomodelacion': 'Armonía Facial 440 — Rinomodelación',
    'armonia_facial': 'Armonía Facial 440',
    'armonia_corporal': 'Armonía Corporal 440',
}


def _conversacion_texto(messages):
    """Texto plano (minúsculas) de todos los mensajes para detección."""
    partes = []
    for m in messages or []:
        c = m.get('content')
        if isinstance(c, str):
            partes.append(c)
        elif isinstance(c, list):
            for b in c:
                if isinstance(b, dict):
                    if b.get('type') == 'text':
                        partes.append(b.get('text', ''))
                    elif b.get('type') == 'tool_result':
                        tc = b.get('content', '')
                        if isinstance(tc, str):
                            partes.append(tc)
    return ' '.join(partes).lower()


class Brain:
    def __init__(self):
        self.whapi = WhapiClient()
        self.instagram = InstagramClient()
        self.api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        self.sb_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
        self.sb_key = os.environ.get('SUPABASE_ANON_KEY', '')
        self.n8n_check_slots = os.environ.get('N8N_CHECK_SLOTS', '')
        self.n8n_create_event = os.environ.get('N8N_CREATE_EVENT', '')
        self.history_limit = 10
        self.max_tool_iters = 5
        print(f"[BRAIN INIT] sb_url={self.sb_url!r} sb_key_len={len(self.sb_key)} anth_key_len={len(self.api_key)} check_slots_url={bool(self.n8n_check_slots)} create_event_url={bool(self.n8n_create_event)}", flush=True)

    # ------------------------------------------------------------------
    # Supabase memory: conversaciones_440
    # ------------------------------------------------------------------
    def _sb_headers(self):
        return {
            'apikey': self.sb_key,
            'Authorization': f'Bearer {self.sb_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': _BROWSER_UA,
        }

    def _load_history(self, sender_id, canal):
        if not self.sb_url or not self.sb_key:
            print(f"[BRAIN] supabase not configured — using empty history", flush=True)
            return []
        params = (
            f'contacto_telefono=eq.{urllib.parse.quote(sender_id)}'
            f'&canal=eq.{urllib.parse.quote(canal)}'
            f'&direccion=in.(entrante,saliente)'
            f'&select=mensaje,direccion,remitente,created_at'
            f'&order=created_at.desc'
            f'&limit={self.history_limit}'
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
            print(f"[BRAIN] sb_get HTTPError {e.code} body={body!r}", flush=True)
            return []
        except Exception as e:
            print(f"[BRAIN] sb_get error: {e}", flush=True)
            return []
        rows = list(reversed(rows or []))
        messages = []
        for row in rows:
            content = (row.get('mensaje') or '').strip()
            if not content:
                continue
            direccion = (row.get('direccion') or '').lower()
            remitente = (row.get('remitente') or '').lower()
            if direccion == 'saliente' or remitente in ('bot', 'asistente', 'sistema'):
                role = 'assistant'
            else:
                role = 'user'
            messages.append({'role': role, 'content': content})
        print(f"[BRAIN] loaded {len(messages)} history msgs from supabase", flush=True)
        while messages and messages[0]['role'] != 'user':
            messages.pop(0)
        collapsed = []
        for m in messages:
            if collapsed and collapsed[-1]['role'] == m['role']:
                collapsed[-1]['content'] = collapsed[-1]['content'] + '\n' + m['content']
            else:
                collapsed.append(dict(m))
        return collapsed

    def _save_message(self, sender_id, sender_name, canal, mensaje, direccion, remitente, cuenta_receptora=None):
        if not self.sb_url or not self.sb_key:
            return
        if not mensaje:
            return
        # Para WhatsApp del bot estética: marca '440clinic_wa' para que
        # el CRM pueda distinguirlo del bot de cirugías (brain_cx → drgio_wa).
        if cuenta_receptora is None and canal == 'whatsapp':
            cuenta_receptora = '440clinic_wa'
        body = {
            'contacto_nombre': sender_name or None,
            'contacto_telefono': sender_id,
            'canal': canal,
            'mensaje': mensaje,
            'direccion': direccion,
            'remitente': remitente,
            'leido': direccion == 'saliente',
        }
        if cuenta_receptora:
            body['cuenta_receptora'] = cuenta_receptora
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
        url = f'{self.sb_url}/rest/v1/conversaciones_440'
        headers = self._sb_headers()
        headers['Prefer'] = 'return=minimal'
        data = json.dumps(body).encode()
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=8) as r:
                print(f"[BRAIN] sb_insert {direccion}/{remitente} OK status={r.status}", flush=True)
        except urllib.error.HTTPError as e:
            err = ''
            try: err = e.read().decode()[:300]
            except: pass
            print(f"[BRAIN] sb_insert HTTPError {e.code} body={err!r}", flush=True)
        except Exception as e:
            print(f"[BRAIN] sb_insert error: {e}", flush=True)

    # ------------------------------------------------------------------
    # Supabase: pacientes_440 (pacientes recurrentes)
    # ------------------------------------------------------------------
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
            print(f"[BRAIN] check_paciente error: {e}", flush=True)
            return None

    def _check_lead_crm(self, sender_id):
        """Lee leads_comerciales (proyecto historia-clinica) buscando
        nombre, asesora_asignada, procedimiento_interes, etapa para el
        teléfono dado. Usa SUPABASE_KEY_CRM (service_role) para bypassear
        RLS. Devuelve dict o None."""
        import urllib.request, urllib.parse, json as _json
        crm_url = os.environ.get('SUPABASE_URL_CRM', '').rstrip('/')
        crm_key = os.environ.get('SUPABASE_KEY_CRM', '')
        if not crm_url or not crm_key or not sender_id:
            return None
        try:
            tel = urllib.parse.quote(str(sender_id))
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
            print(f"[BRAIN] check_lead_crm err: {e}", flush=True)
            return None

    def _already_notified(self, sender_id, canal, hours=24):
        """True si ya hay un mensaje saliente con <<<NOTIFY>>> para este
        sender_id en las últimas `hours` horas. Evita enviar el lead
        duplicado a las asesoras cuando Claude emite NOTIFY 2 veces."""
        if not self.sb_url or not self.sb_key or not sender_id:
            return False
        try:
            since = (datetime.now(timezone.utc) -
                     timedelta(hours=hours)).isoformat()
            params = (
                f'contacto_telefono=eq.{urllib.parse.quote(sender_id)}'
                f'&canal=eq.{urllib.parse.quote(canal)}'
                f'&direccion=eq.saliente'
                f'&mensaje=ilike.*NOTIFY*'
                f'&created_at=gte.{urllib.parse.quote(since)}'
                f'&select=created_at&limit=1'
            )
            url = f'{self.sb_url}/rest/v1/conversaciones_440?{params}'
            req = urllib.request.Request(url, headers=self._sb_headers(), method='GET')
            with urllib.request.urlopen(req, timeout=8) as r:
                rows = json.loads(r.read())
            return bool(rows)
        except Exception as e:
            print(f"[BRAIN] already_notified error: {e}", flush=True)
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
                         canal=None, servicio=None):
        if not self.sb_url or not self.sb_key or not sender_id:
            return
        try:
            body = {
                'telefono': sender_id,
                'ultimo_contacto': datetime.now(timezone.utc).isoformat(),
            }
            if nombre:
                body['nombre'] = nombre
            if email:
                body['email'] = email
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
                print(f"[BRAIN] upsert_paciente OK status={r.status}", flush=True)
        except Exception as e:
            print(f"[BRAIN] upsert_paciente error: {e}", flush=True)

    # ------------------------------------------------------------------
    # Bloqueo por spam / contenido inapropiado (pacientes_440)
    # ------------------------------------------------------------------
    def _check_bloqueado(self, sender_id):
        """True si el paciente tiene bot_bloqueado=true y bloqueado_hasta
        > NOW(). Si el bloqueo expiró, lo limpia y devuelve False.
        Cualquier error → False (fail-open: mejor responder que dejar
        a un paciente legítimo sin atención)."""
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
                return True  # bloqueo sin expiración → mantener
            hasta = datetime.fromisoformat(hasta_raw.replace('Z', '+00:00'))
            if hasta.tzinfo is None:
                hasta = hasta.replace(tzinfo=timezone.utc)
            if hasta > datetime.now(timezone.utc):
                return True
            # Expirado — desbloquear
            self._set_bloqueado(sender_id, razon=None, bloquear=False)
            print(f"[BRAIN] bloqueo expirado para {sender_id} — desbloqueado", flush=True)
            return False
        except Exception as e:
            print(f"[BRAIN] check_bloqueado error: {e}", flush=True)
            return False

    def _set_bloqueado(self, sender_id, razon=None, hours=24, bloquear=True):
        """Upsert pacientes_440 con bot_bloqueado / bloqueado_hasta /
        razon_bloqueo. Si bloquear=False, limpia los 3 campos."""
        if not self.sb_url or not self.sb_key or not sender_id:
            return
        try:
            body = {'telefono': sender_id}
            if bloquear:
                hasta = datetime.now(timezone.utc) + timedelta(hours=hours)
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
                print(f"[BRAIN] set_bloqueado={bloquear} {sender_id} status={r.status}", flush=True)
        except Exception as e:
            print(f"[BRAIN] set_bloqueado error: {e}", flush=True)

    # ------------------------------------------------------------------
    # Validación/rescate de campos NOTIFY (portado de brain_cx.py)
    # ------------------------------------------------------------------
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
        ('vivo en X', 'soy de X', etc.). Fallback a primera mención simple."""
        for m in history:
            if m.get('role') != 'user':
                continue
            txt = (m.get('content') or '').lower()
            for pat in self._CIUDAD_PATRONES:
                for c in self._CIUDADES_CANONICAS:
                    if (pat + c) in txt:
                        return c.title()
        for m in history:
            if m.get('role') != 'user':
                continue
            txt = (m.get('content') or '').lower()
            posiciones = []
            for c in self._CIUDADES_CANONICAS:
                idx = txt.find(c)
                if idx >= 0:
                    posiciones.append((idx, c))
            if posiciones:
                posiciones.sort()
                return posiciones[0][1].title()
        return ''

    def _extract_name_from_history(self, history, sender_name):
        """Busca nombre real del paciente. Prioridad:
        1. 'me llamo X' / 'soy X' / 'mi nombre es X' del historial.
        2. Respuesta corta tras pregunta del bot sobre nombre.
        3. sender_name (sin emojis/símbolos adyacentes)."""
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
        nm = (sender_name or '').strip()
        has_non_letter_symbol = any(not (ch.isalnum() or ch.isspace()) for ch in nm)
        if has_non_letter_symbol:
            return ''
        letters = sum(1 for ch in nm if ch.isalpha())
        if letters >= 2 and nm not in ('.', '—', '-'):
            return nm.split()[0].title()
        return ''

    def _validate_notify_fields(self, fields, history, sender_name, sender_id):
        """Limpia/rescata campos críticos del NOTIFY in-place.
        Aplica a los 3 templates de estética (cita_estetica,
        armonia_facial, armonia_corporal): nombre y ciudad."""
        # nombre
        nombre = (fields.get('nombre') or '').strip()
        bad_name = (not nombre or
                    not any(c.isalpha() for c in nombre) or
                    nombre.lower() in ('.', '—', '-', 'sin nombre', 'no especificado'))
        if bad_name:
            recovered = self._extract_name_from_history(history, sender_name)
            fields['nombre'] = recovered or 'Paciente'
            print(f"[BRAIN] NOTIFY nombre rescued: {nombre!r} → {fields['nombre']!r}", flush=True)
        # ciudad — solo si el template la usa (cita_estetica + corporal sí; facial no la pide)
        if 'ciudad' in fields or any(k in fields for k in ('servicio', 'tratamiento', 'meta')):
            ciudad = (fields.get('ciudad') or '').strip().lower()
            bad_city = (not ciudad or
                        ciudad in ('desconocida', '—', '-', 'no especificada', 'no especificado'))
            if bad_city:
                recovered = self._ciudad_from_history(history)
                if recovered:
                    fields['ciudad'] = recovered
                    print(f"[BRAIN] NOTIFY ciudad rescued: → {recovered!r}", flush=True)
                elif not fields.get('ciudad'):
                    fields['ciudad'] = ''  # facial no la pide → dejar vacío en vez de 'desconocida'
        return fields

    # ------------------------------------------------------------------
    # W21 webhook callers (tools)
    # ------------------------------------------------------------------
    def _post_json(self, url, payload):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data, method='POST',
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': _BROWSER_UA,
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = ''
            try: body = e.read().decode()[:400]
            except: pass
            print(f"[W21] HTTPError {e.code} body={body!r}", flush=True)
            return {'ok': False, 'error': f'HTTP {e.code}', 'body': body}
        except Exception as e:
            print(f"[W21] error: {e}", flush=True)
            return {'ok': False, 'error': str(e)}

    def _exec_tool(self, name, tool_input, sender_id):
        print(f"[TOOL] {name} input={json.dumps(tool_input, ensure_ascii=False)[:200]}", flush=True)
        if name == 'check_slots':
            if not self.n8n_check_slots:
                return {'ok': False, 'error': 'N8N_CHECK_SLOTS env var missing'}
            payload = dict(tool_input)
            payload['sender_id'] = sender_id
            result = self._post_json(self.n8n_check_slots, payload)
            print(f"[TOOL] check_slots → ok={result.get('ok')} slots={len(result.get('slots',[]) or [])}", flush=True)
            return result
        if name == 'create_event':
            if not self.n8n_create_event:
                return {'ok': False, 'error': 'N8N_CREATE_EVENT env var missing'}
            payload = dict(tool_input)
            payload['sender_id'] = sender_id
            result = self._post_json(self.n8n_create_event, payload)
            print(f"[TOOL] create_event → ok={result.get('ok')} evento_id={result.get('evento_id','')}", flush=True)
            return result
        return {'ok': False, 'error': f'unknown tool {name}'}

    # ------------------------------------------------------------------
    # Claude tool-use loop
    # ------------------------------------------------------------------
    def _call_claude_raw(self, messages, system_extra=''):
        # Prompt caching: SYSTEM (largo y estable) se marca con cache_control
        # para reutilizar la caché entre llamadas (reduce costo ~60-80%). El
        # contexto extra (variable) va en un bloque aparte SIN cache.
        system_blocks = [
            {"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}
        ]
        if system_extra:
            system_blocks.append({"type": "text", "text": system_extra})
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 800,
            "system": system_blocks,
            "tools": TOOLS,
            "messages": messages,
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
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = ''
            try: body = e.read().decode()[:400]
            except: pass
            print(f"[BRAIN] Claude HTTPError {e.code} body={body!r}", flush=True)
            return None
        except Exception as e:
            print(f"[BRAIN] Claude error: {e}", flush=True)
            return None

    def _claude_loop(self, history, sender_id, is_first_time=False, canal='whatsapp',
                     paciente_ctx=''):
        """Run Claude with tool_use loop. Returns final assistant text."""
        messages = [dict(m) for m in history]  # shallow copy
        # Always tell Claude the channel + sender_id explicitly so it
        # follows the canal-specific rules (e.g. don't ask for phone on WA).
        canal_note = (
            f"\n\nCONTEXTO RUNTIME:\n"
            f"- Canal actual: {canal}\n"
            f"- sender_id (teléfono/IGSID): {sender_id}\n"
        )
        if canal == 'whatsapp':
            canal_note += (
                "- El paciente ya nos escribe por WhatsApp → NO le preguntes "
                "su número de teléfono bajo NINGUNA circunstancia. "
                f"En cualquier <<<NOTIFY>>> usa telefono: {sender_id}.\n"
            )
        else:
            canal_note += (
                "- El paciente nos escribe por Instagram → para coordinarlo "
                "fuera del DM SÍ debes pedirle su número de WhatsApp.\n"
            )
        if paciente_ctx:
            canal_note += paciente_ctx
        system_extra = canal_note
        if is_first_time:
            system_extra += (
                "\n\n⚠️ CONTEXTO: Esta es la PRIMERA INTERACCIÓN con este "
                "paciente (no hay historial previo). Tu PRIMERA respuesta "
                "DEBE comenzar EXACTAMENTE así:\n\n"
                "✨ Bienvenid@ a 440 Clinic ✨\n"
                "La perfecta armonía de tu cuerpo\n\n"
                "Tu clínica de medicina estética\n"
                "y bienestar en Barranquilla 💙\n"
                "Dr. Giovanni Fuentes\n"
                "& Dra. Sharon Santiago\n\n"
                "¿Qué te trae por aquí hoy?\n\n"
                "✨ Dale un glow a tu piel\n"
                "   y rejuvenece sin cirugía\n"
                "💪 Moldea, tensa y tonifica\n"
                "   tu cuerpo sin cirugía\n"
                "🥗 Nutrición y pérdida\n"
                "   de peso saludable\n"
                "💜 Depilación láser sin dolor\n"
                "   Removall Trio\n"
                "🫁 Cámara hiperbárica\n"
                "🔬 Cirugías plásticas\n\n"
                "Después de esa bienvenida, si el paciente mencionó un "
                "servicio específico, continúa con su flujo en el SIGUIENTE "
                "mensaje. NO uses tool_use en esta primera respuesta — solo "
                "presenta la clínica y espera la respuesta del paciente."
            )
        # Tracking entre iteraciones del tool loop: el último servicio/zona
        # con que el modelo llamó a check_slots. Usado para forzar coherencia
        # cuando create_event llega con un servicio distinto (p.ej. el modelo
        # confunde la opción y manda valoracion siendo depilacion).
        last_servicio = ''
        last_zona = ''
        for it in range(self.max_tool_iters):
            print(f"[BRAIN] Claude iter {it} (history={len(messages)}) first_time={is_first_time} canal={canal}", flush=True)
            # Always inject canal_note; first-time block only on iter 0.
            iter_extra = system_extra if it == 0 else canal_note
            resp = self._call_claude_raw(messages, system_extra=iter_extra)
            if not resp:
                return "Disculpa, tuve un problema técnico. ¿Puedes repetir? 😊"
            stop = resp.get('stop_reason')
            content = resp.get('content', [])
            print(f"[BRAIN] Claude stop={stop} blocks={[b.get('type') for b in content]}", flush=True)
            # Append the assistant turn with the FULL content (text + tool_use blocks)
            messages.append({'role': 'assistant', 'content': content})

            if stop == 'tool_use':
                tool_results = []
                convo_txt = _conversacion_texto(messages)
                for block in content:
                    if block.get('type') == 'tool_use':
                        tname = block.get('name', '')
                        tinput = block.get('input', {}) or {}
                        # BLOQUEO Python — 2 capas:
                        # 1) servicio del payload no está en la whitelist
                        # 2) la conversación menciona un servicio sin calendario
                        _bloquear = False
                        if tname == 'check_slots':
                            _serv = (tinput.get('servicio') or '').lower().strip()
                            if _serv and _serv not in SERVICIOS_CON_SLOTS:
                                _bloquear = True
                                print(f"[BRAIN] check_slots BLOQUEADO — "
                                      f"servicio={_serv!r} no está en whitelist "
                                      f"{SERVICIOS_CON_SLOTS}", flush=True)
                            elif any(s in convo_txt for s in SERVICIOS_SIN_SLOTS):
                                _bloquear = True
                                print("[BRAIN] check_slots BLOQUEADO — "
                                      "conversación menciona servicio sin calendario",
                                      flush=True)
                        if _bloquear:
                            result = {
                                'ok': False,
                                'bloqueado': True,
                                'mensaje': ('Este servicio no se agenda con '
                                            'horarios. Responde al paciente: '
                                            '"Nuestra asesora te contactará para '
                                            'coordinar tu cita con la Dra. Sharon '
                                            '💙" y emite el <<<NOTIFY>>>.'),
                            }
                        else:
                            # Track del servicio/zona de check_slots para
                            # mantener coherencia en create_event posterior.
                            if tname == 'check_slots':
                                _new_serv = (tinput.get('servicio') or '').lower().strip()
                                if _new_serv:
                                    last_servicio = _new_serv
                                _new_zona = (tinput.get('zona') or '').strip()
                                if _new_zona:
                                    last_zona = _new_zona
                            elif tname == 'create_event':
                                # Forzar coherencia: el servicio y la zona
                                # de create_event deben coincidir con los
                                # de check_slots. Si Claude pasa cualquier
                                # otro valor (valoracion, depilacion siendo
                                # hiperbarica, etc.), se sobreescribe con
                                # last_servicio/last_zona.
                                _ce_serv = (tinput.get('servicio') or '').lower().strip()
                                if last_servicio and _ce_serv != last_servicio:
                                    print(f"[BRAIN] create_event: forzando "
                                          f"servicio {_ce_serv!r} → "
                                          f"{last_servicio!r}", flush=True)
                                    tinput['servicio'] = last_servicio
                                if not (tinput.get('zona') or '').strip() and last_zona:
                                    print(f"[BRAIN] create_event: forzando "
                                          f"zona={last_zona!r} (vacía en input)",
                                          flush=True)
                                    tinput['zona'] = last_zona
                            result = self._exec_tool(tname, tinput, sender_id)
                        tool_results.append({
                            'type': 'tool_result',
                            'tool_use_id': block.get('id', ''),
                            'content': json.dumps(result, ensure_ascii=False),
                        })
                if not tool_results:
                    # malformed — bail out
                    break
                messages.append({'role': 'user', 'content': tool_results})
                continue

            # end_turn or other → extract text
            final_text = ''.join(
                b.get('text', '') for b in content if b.get('type') == 'text'
            )
            return final_text
        return "Disculpa, tuve un problema agendando. ¿Quieres reintentar? 😊"

    # ------------------------------------------------------------------
    # Main flow
    # ------------------------------------------------------------------
    def process(self, sender_id, sender_name, text, canal='whatsapp', cuenta_receptora=None,
                media_url=None, media_tipo=None, media_caption=None):
        """cuenta_receptora — slug del IG account ('440clinic'/'drgiovannifuentes')
        cuando canal=='instagram'. Para WhatsApp queda None.
        media_url/media_tipo/media_caption — imagen entrante re-hospedada en
        Storage; se adjunta a la primera fila 'entrante' (one-shot, sin duplicar)."""
        self._in_media_url = media_url
        self._in_media_tipo = media_tipo
        self._in_media_caption = media_caption
        print(f"[BRAIN] {sender_id}: {text[:50]} canal={canal} cuenta={cuenta_receptora!r}", flush=True)

        # ── BOT PAUSADO: guardar entrante y salir sin responder ─────────
        # Si la asesora marcó este lead como pausado desde el CRM, NO
        # invocamos a Claude ni respondemos — solo registramos el mensaje.
        _lead_pause = self._check_lead_crm(sender_id)
        if _lead_pause and _lead_pause.get('bot_pausado'):
            print(f"[BRAIN] bot_pausado=True para {sender_id} — solo guardar entrante", flush=True)
            self._save_message(sender_id, sender_name, canal, text,
                               direccion='entrante', remitente='paciente',
                               cuenta_receptora=cuenta_receptora)
            return

        # ── BOT BLOQUEADO: spam/abuso. Guardar entrante y salir silencioso.
        # Si bloqueado_hasta expiró, _check_bloqueado lo desbloquea solo.
        if self._check_bloqueado(sender_id):
            print(f"[BRAIN] bot_bloqueado=True para {sender_id} — guardar entrante y silencio", flush=True)
            self._save_message(sender_id, sender_name, canal, text,
                               direccion='entrante', remitente='paciente',
                               cuenta_receptora=cuenta_receptora)
            return

        # ── Mensajes especiales: [MEDIA] / solo emojis ──────────────────
        _s_in = (text or '').strip()
        if _s_in == '[MEDIA]':
            _nombre = (sender_name or '').split()[0] if sender_name else ''
            _saludo = f"¡Hola {_nombre}!" if _nombre else "¡Hola!"
            reply = (
                f"{_saludo} 💙\n"
                "No puedo ver imágenes aquí, pero puedes compartírsela "
                "directamente a nuestra asesora cuando te contacte 😊\n\n"
                "¿Hay algo en lo que pueda ayudarte mientras tanto?"
            )
            self._save_message(sender_id, sender_name, canal, text,
                               direccion='entrante', remitente='paciente',
                               cuenta_receptora=cuenta_receptora)
            client = self.instagram if canal == 'instagram' else self.whapi
            try: client.send_text(sender_id, reply)
            except Exception as e: print(f"[BRAIN] media reply send err: {e}", flush=True)
            self._save_message(sender_id, sender_name, canal, reply,
                               direccion='saliente', remitente='bot',
                               cuenta_receptora=cuenta_receptora)
            return reply
        history = self._load_history(sender_id, canal)
        is_first_time = len(history) == 0
        print(f"[BRAIN] is_first_time={is_first_time}", flush=True)

        # Detectar si el paciente regresa después de 4+ horas mirando el
        # created_at del último mensaje en conversaciones_440 (no del row
        # de pacientes_440, que puede estar desactualizado o vacío).
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
                    ultima_interaccion = datetime.fromisoformat(_raw)
                    if ultima_interaccion.tzinfo is None:
                        ultima_interaccion = ultima_interaccion.replace(tzinfo=timezone.utc)
            except Exception as e:
                print(f"[BRAIN] ultima_interaccion err: {e}", flush=True)
                ultima_interaccion = None

        es_regreso = False
        if ultima_interaccion:
            if datetime.now(timezone.utc) - ultima_interaccion > timedelta(hours=4):
                es_regreso = True

        # Paciente recurrente — lookup si es first-time o regreso.
        paciente = (self._check_paciente_recurrente(sender_id)
                    if (is_first_time or es_regreso) else None)
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
            is_first_time = False
            print(f"[BRAIN] paciente regresa (>4h, history no vacío) — saludo corto", flush=True)

        # ── PACIENTE RECURRENTE CON ASESORA ASIGNADA (>4h) ──────────────
        # Si ya hay un lead en el CRM con asesora_asignada Y el historial
        # es de hace más de 4h → saludo breve + NOTIFY de "regresa" a la
        # asesora + Sharon + Central + Dr. Gio. Cierra el flujo aquí.
        if es_regreso:
            _lead_crm = self._check_lead_crm(sender_id)
            _asesora_lead = ((_lead_crm or {}).get('asesora_asignada') or '').strip().lower()
            if _lead_crm and _asesora_lead:
                _nombre_l = (_lead_crm.get('nombre') or paciente.get('nombre') if paciente else '') or ''
                if not _nombre_l or not any(c.isalpha() for c in _nombre_l):
                    _nombre_l = ''
                _proc_l   = _lead_crm.get('procedimiento_interes') or '—'
                _etapa_l  = _lead_crm.get('etapa') or 'lead'
                reply = (f"¡Hola {_nombre_l}! 💙\nQué bueno saber de ti 😊\n"
                         "En breve tu asesora te contactará para ayudarte."
                         if _nombre_l else
                         "¡Hola! 💙\nQué bueno saber de ti 😊\n"
                         "En breve tu asesora te contactará para ayudarte.")
                self._save_message(sender_id, sender_name, canal, text,
                                   direccion='entrante', remitente='paciente',
                                   cuenta_receptora=cuenta_receptora)
                client = self.instagram if canal == 'instagram' else self.whapi
                try: client.send_text(sender_id, reply)
                except Exception as e: print(f"[BRAIN] recurrente reply err: {e}", flush=True)
                self._save_message(sender_id, sender_name, canal, reply,
                                   direccion='saliente', remitente='bot',
                                   cuenta_receptora=cuenta_receptora)
                # NOTIFY al staff — solo si no se envió en las últimas 24h.
                if not self._already_notified(sender_id, canal):
                    notify_msg = (
                        "🔄 PACIENTE RECURRENTE\n"
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 {_nombre_l or '—'}\n"
                        f"📱 Tel: {sender_id}\n"
                        f"💆 Servicio: {_proc_l}\n"
                        f"📊 Etapa: {_etapa_l}\n"
                        f"👩 Asesora: {_asesora_lead.capitalize()}\n"
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        "Paciente regresa — tiene asesora asignada 💙"
                    )
                    # Para estética la asesora siempre es Sara → SARA_TEL.
                    _asesora_phone = self.SARA_TEL if _asesora_lead == 'sara' else ''
                    destinatarios = [_asesora_phone, self.DRA_SHARON_TEL,
                                     self.CENTRAL_TEL, self.DR_GIO_TEL]
                    for _tel in destinatarios:
                        if not _tel: continue
                        try:
                            self.whapi.send_text(_tel, notify_msg)
                        except Exception as e:
                            print(f"[BRAIN] recurrente notify {_tel} err: {e}", flush=True)
                    # Guardar marca de NOTIFY (dedup) en conversaciones_440.
                    self._save_message(sender_id, sender_name, canal,
                                       f"<<<NOTIFY>>>tipo: recurrente<<<END>>>",
                                       direccion='saliente', remitente='bot',
                                       cuenta_receptora=cuenta_receptora)
                    print(f"[BRAIN] PACIENTE RECURRENTE NOTIFY enviado", flush=True)
                else:
                    print(f"[BRAIN] PACIENTE RECURRENTE — ya notificado <24h, skip", flush=True)
                return reply

        # ── BUG 1: saludo genérico con historial existente <4h ──────────
        # No repetir bienvenida completa; responder corto "Hola de nuevo".
        _low_in = (_s_in or '').lower().rstrip('.!?¿,. ')
        _greetings = {'hola','holi','holiwi','holaa','holaaa','hi','hey',
                      'buenas','buen dia','buen día','buenos dias','buenos días',
                      'buenas tardes','buenas noches','que tal','qué tal',
                      'saludos','ola'}
        if history and not es_regreso and _low_in in _greetings:
            # BUG A fix: cargar paciente aquí si no se cargó arriba (el bloque
            # de memoria solo lo hace si is_first_time o es_regreso).
            if paciente is None:
                paciente = self._check_paciente_recurrente(sender_id)
            _nombre_p = (paciente.get('nombre') if paciente else '') or ''
            if not _nombre_p or not any(c.isalpha() for c in _nombre_p):
                _nombre_p = ''
            reply = (f"¡Hola de nuevo {_nombre_p}! 💙\n¿En qué más te puedo ayudar? 😊"
                     if _nombre_p else
                     "¡Hola de nuevo! 💙\n¿En qué más te puedo ayudar? 😊")
            self._save_message(sender_id, sender_name, canal, text,
                               direccion='entrante', remitente='paciente',
                               cuenta_receptora=cuenta_receptora)
            client = self.instagram if canal == 'instagram' else self.whapi
            try: client.send_text(sender_id, reply)
            except Exception as e: print(f"[BRAIN] greeting reply err: {e}", flush=True)
            self._save_message(sender_id, sender_name, canal, reply,
                               direccion='saliente', remitente='bot',
                               cuenta_receptora=cuenta_receptora)
            print(f"[BRAIN] BUG1 — saludo corto (history existe, <4h)", flush=True)
            return reply

        # ── BUG 2: si el bot acaba de pedir el nombre y el paciente
        # responde solo emojis → NO guardar emoji, pedirlo de nuevo.
        if _s_in and _is_emoji_only(_s_in):
            _last_bot = ''
            for _m in reversed(history):
                if _m.get('role') == 'assistant':
                    _last_bot = (_m.get('content') or '').lower()
                    break
            if 'nombre' in _last_bot and ('?' in _last_bot or 'cuál' in _last_bot or 'cual' in _last_bot or 'cómo' in _last_bot or 'como te llamas' in _last_bot):
                reply = "¡Gracias! 💙\n¿Me puedes decir tu nombre? 😊"
                self._save_message(sender_id, sender_name, canal, text,
                                   direccion='entrante', remitente='paciente',
                                   cuenta_receptora=cuenta_receptora)
                client = self.instagram if canal == 'instagram' else self.whapi
                try: client.send_text(sender_id, reply)
                except Exception as e: print(f"[BRAIN] name re-ask err: {e}", flush=True)
                self._save_message(sender_id, sender_name, canal, reply,
                                   direccion='saliente', remitente='bot',
                                   cuenta_receptora=cuenta_receptora)
                print(f"[BRAIN] BUG2 — emoji como nombre, re-preguntando", flush=True)
                return reply
            print(f"[BRAIN] emoji-only {text!r} → tratando como 'Sí'", flush=True)
            text = 'Sí'

        user_content = f"[{sender_name or sender_id}]: {text}" if sender_name else text
        history.append({'role': 'user', 'content': user_content})

        self._save_message(sender_id, sender_name, canal, text,
                           direccion='entrante', remitente='paciente',
                           cuenta_receptora=cuenta_receptora)

        # Guardar / actualizar paciente. nombre se extrae de la conversación
        # cuando el bot acaba de pedirlo; sender_name (WhatsApp profile) solo
        # se usa como fallback y descartado si es emoji / sin letras.
        _email_match = re.search(
            r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
        _nombre_real = (self._extract_name_from_turn(history, text)
                        or self._safe_sender_name(sender_name))
        self._upsert_paciente(
            sender_id, nombre=_nombre_real,
            email=_email_match.group(0) if _email_match else None,
            canal=canal)

        # ── STATE MACHINE — esperando_confirmacion (sin calendario) ────
        # Si el bot ya preguntó "¿Te gustaría agendar?" y el paciente
        # respondió afirmativamente sobre un servicio SIN calendario,
        # Python emite el cierre + NOTIFY directamente sin invocar Claude.
        _bypass = self._try_bypass_close(
            history, text, sender_id, sender_name, canal, cuenta_receptora)
        if _bypass:
            print("[BRAIN] state=esperando_confirmacion — bypass aplicado",
                  flush=True)
            return

        full_response = self._claude_loop(history, sender_id, is_first_time=is_first_time,
                                          canal=canal, paciente_ctx=paciente_ctx)
        print(f"[BRAIN] Claude final len={len(full_response)} preview={full_response[:100]!r}", flush=True)

        # ── INTERCEPTAR <<<BLOQUEAR>>>: spam/abuso detectado por Claude ──
        if '<<<BLOQUEAR>>>' in full_response:
            print(f"[BRAIN] <<<BLOQUEAR>>> detectado para {sender_id} — despedida + bloqueo 24h", flush=True)
            despedida = (
                "Gracias por escribirnos 💙\n"
                "En este espacio solo podemos ayudarte con temas "
                "relacionados con nuestros servicios médicos y estéticos.\n\n"
                "Si en algún momento deseas información sobre nuestros "
                "tratamientos, con gusto te atendemos 😊\n\n"
                "¡Que tengas un excelente día!\n"
                "440 Clinic · Dr. Giovanni Fuentes"
            )
            client = self.instagram if canal == 'instagram' else self.whapi
            try: client.send_text(sender_id, despedida)
            except Exception as e: print(f"[BRAIN] despedida send err: {e}", flush=True)
            self._save_message(sender_id, sender_name, canal, despedida,
                               direccion='saliente', remitente='bot',
                               cuenta_receptora=cuenta_receptora)
            self._set_bloqueado(sender_id, razon='Contenido inapropiado/spam', hours=24)
            return

        # NOTIFY block (legacy lead notifications still supported)
        notify = None
        match = re.search(r'<<<NOTIFY>>>(.*?)<<<END>>>', full_response, re.DOTALL)
        if match:
            notify = match.group(1).strip()

        # Deduplicar NOTIFY: si ya enviamos uno para este sender en las
        # últimas 24h, no volvemos a notificar a las asesoras.
        should_notify = bool(notify)
        if notify and self._already_notified(sender_id, canal):
            print("[BRAIN] NOTIFY duplicado — ya hay uno en las últimas 24h, "
                  "skip notify_admin", flush=True)
            should_notify = False

        # Strip internal blocks before sending to the patient via WhApi
        user_facing = _strip_internal_blocks(full_response)

        if user_facing:
            print(f"[BRAIN] sending reply len={len(user_facing)} via {canal}", flush=True)
            client = self.instagram if canal == 'instagram' else self.whapi
            r = client.send_text(sender_id, user_facing)
            print(f"[BRAIN] send_text result={r}", flush=True)
            # Save the FULL response (with SLOTS_DATA) to Supabase so the
            # next turn can decode slot picks.
            self._save_message(sender_id, sender_name, canal, full_response,
                               direccion='saliente', remitente='bot',
                               cuenta_receptora=cuenta_receptora)
        else:
            print(f"[BRAIN] empty response after strip — NOT sending", flush=True)

        if should_notify:
            print(f"[BRAIN] notify_admin trigger", flush=True)
            self._notify_admin(notify, sender_id, canal=canal, history=history)

    # Destinatarios fijos de las notificaciones de leads
    SARA_TEL = '573105762900'
    DRA_SHARON_TEL = '573015135214'
    CENTRAL_TEL = '573181800130'
    DR_GIO_TEL = '573181800131'

    def _try_bypass_close(self, history, text, sender_id, sender_name,
                          canal, cuenta_receptora):
        """Si el último mensaje del bot preguntó '¿Te gustaría agendar?'
        y el paciente confirma afirmativamente sobre un servicio SIN
        calendario, emite cierre + NOTIFY directamente (sin Claude).
        Retorna True si bypass se aplicó."""
        # Último mensaje del bot
        last_bot = ''
        for m in reversed(history[:-1]):
            if m.get('role') == 'assistant':
                c = m.get('content')
                if isinstance(c, str):
                    last_bot = c
                    break
        last_bot_l = last_bot.lower()
        # Solo aplica si el bot acaba de preguntar por agendar.
        if not any(s in last_bot_l for s in (
                '¿te gustaría agendar', 'te gustaria agendar',
                'gustaría agendar', 'gustaria agendar')):
            return False
        if not _es_afirmacion(text):
            return False
        # Detectar servicio en toda la conversación.
        hist_text = ' '.join(
            m.get('content', '') if isinstance(m.get('content'), str) else ''
            for m in history)
        servicio = _detect_servicio(hist_text)
        if servicio not in _SIN_CALENDARIO:
            return False  # depilación/hiperbárica/valoración → no bypass

        # ── Construir cierre + NOTIFY ────────────────────────────────
        nombre = sender_name or ''
        saludo = f"¡Perfecto {nombre}! 💙" if nombre else "¡Perfecto! 💙"
        cierre = (
            f"{saludo}\n"
            "Nuestra asesora te contactará\n"
            "para coordinar tu cita 😊\n"
            "La Belleza 440 ✨"
        )
        servicio_label = _SERVICIO_LABEL.get(servicio, servicio)
        # Ciudad / email — extracción simple del historial.
        _email_m = re.search(
            r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', hist_text)
        correo = _email_m.group(0) if _email_m else ''
        notify_block = (
            "<<<NOTIFY>>>\n"
            f"nombre: {nombre or 'sin nombre'}\n"
            f"telefono: {sender_id}\n"
            f"canal: {canal}\n"
            f"servicio: {servicio_label}\n"
            + (f"correo: {correo}\n" if correo else '')
            + "prioridad: CALIENTE\n"
            "accion: Llamar y coordinar cita con Dra. Sharon\n"
            "<<<END>>>"
        )
        full_response = cierre + "\n\n" + notify_block

        # 1) Verificar dedup ANTES de guardar (si guardamos primero,
        #    _already_notified encuentra el mensaje recién insertado).
        should_notify = not self._already_notified(sender_id, canal)

        # 2) Si no fue notificado en las últimas 24h → notify_admin.
        if should_notify:
            notify_data = notify_block.split('<<<NOTIFY>>>', 1)[1] \
                                       .split('<<<END>>>', 1)[0].strip()
            self._notify_admin(notify_data, sender_id, canal=canal)
        else:
            print("[BRAIN] bypass: ya notificado, skip notify_admin",
                  flush=True)

        # 3) Strip + enviar al paciente + guardar (después del notify).
        user_facing = _strip_internal_blocks(full_response)
        if user_facing:
            client = self.instagram if canal == 'instagram' else self.whapi
            r = client.send_text(sender_id, user_facing)
            print(f"[BRAIN] bypass send_text result={r}", flush=True)
            self._save_message(sender_id, sender_name, canal, full_response,
                               direccion='saliente', remitente='bot',
                               cuenta_receptora=cuenta_receptora)
        return True

    def _notify_admin(self, data, sender_id, canal='whatsapp', history=None):
        fields = self._parse_notify_fields(data)
        # Rescate de nombre/ciudad si Claude los dejó vacíos o con '.', etc.
        if history is None:
            try: history = self._load_history(sender_id, canal)
            except Exception: history = []
        self._validate_notify_fields(fields, history or [], sender_name='', sender_id=sender_id)

        servicio_raw = (fields.get('servicio') or '').lower()
        tipo = (fields.get('tipo') or '').lower()
        combo = f"{tipo} {servicio_raw}"

        # Servicio "display": para cita_estetica mapeamos slug a nombre
        # legible y agregamos zona. Para los demás usamos el tratamiento
        # si está presente, o el servicio crudo.
        is_cita = ('cita_estetica' in tipo or 'cita estetica' in tipo or 'cita estética' in tipo)
        if is_cita:
            _label = {
                'depilacion': 'Depilación Láser',
                'hiperbarica': 'Cámara Hiperbárica',
                'valoracion': 'Valoración Gratuita',
            }.get(servicio_raw, fields.get('servicio', '—'))
            _zona = (fields.get('zona') or '').strip()
            servicio_display = f"{_label} — {_zona}" if _zona else _label
        else:
            servicio_display = (fields.get('tratamiento')
                                or fields.get('servicio') or '—')

        nombre = fields.get('nombre', '—')
        ciudad = (fields.get('ciudad') or '').strip()
        telefono = fields.get('telefono', sender_id)

        # Mensaje según tipo: cita_estetica usa formato "CITA AGENDADA"
        # con CTA explícito para Sara; resto usa formato genérico.
        if is_cita:
            esteticista = fields.get('esteticista', '—')
            fecha = fields.get('fecha', '—')
            ciudad_line = f"📍 440 Clinic · {ciudad}" if ciudad else "📍 440 Clinic · Barranquilla"
            msg = (
                "📅 CITA AGENDADA — ESTÉTICA\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {nombre}\n"
                f"📱 {telefono}\n"
                f"💆 {servicio_display}\n"
                f"📅 {fecha}\n"
                f"👩 Esteticista: {esteticista}\n"
                f"{ciudad_line}\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Sara: contacta para confirmar\n"
                "y hacer la gestión comercial 💙"
            )
        else:
            msg = self._build_notify_message(nombre, servicio_display,
                                              telefono, ciudad)

        # Routing — Sara SIEMPRE recibe el NOTIFY (incluyendo cita_estetica)
        # para que pueda hacer la gestión comercial post-agendamiento.
        # contactar_sara queda obsoleto pero se respeta si por alguna razón
        # se quisiera escalar (Sara igual ya está).
        _fijos = [self.SARA_TEL, self.DRA_SHARON_TEL, self.CENTRAL_TEL, self.DR_GIO_TEL]
        destinatarios = list(_fijos)

        for tel in destinatarios:
            if not tel:
                continue
            try:
                r = self.whapi.send_text(tel, msg)
                print(f"[BRAIN] notify → {tel} result={r}", flush=True)
            except Exception as e:
                print(f"[BRAIN] notify → {tel} error: {e}", flush=True)

        # CRM: upsert en leads_comerciales (no rompe si falla)
        try:
            self._upsert_lead_comercial(
                nombre=nombre,
                telefono=telefono,
                procedimiento=servicio_display,
                canal=canal,
                prioridad=(fields.get('prioridad') or fields.get('score') or 'CALIENTE').upper(),
                ciudad=ciudad,
                observaciones=fields.get('motivacion') or fields.get('meta') or '',
            )
        except Exception as e:
            print(f"[BRAIN] upsert lead_comercial error: {e}", flush=True)

    def _upsert_lead_comercial(self, nombre, telefono, procedimiento,
                                canal='whatsapp', prioridad='CALIENTE',
                                ciudad='', observaciones=''):
        """INSERT en leads_comerciales del CRM (proyecto historia-clinica)."""
        import urllib.request, json as _json
        from datetime import datetime as _dt, timezone as _tz
        crm_url = os.environ.get('SUPABASE_URL_CRM', '').rstrip('/')
        crm_key = os.environ.get('SUPABASE_KEY_CRM', '')
        if not crm_url or not crm_key or not telefono:
            print(f"[BRAIN] CRM lead upsert skipped (envs/tel missing)", flush=True)
            return
        body = {
            'nombre': nombre or '—',
            'apellido': '',
            'telefono': str(telefono),
            'procedimiento_interes': procedimiento or '—',
            'como_llego': 'BOT440 — Estética',
            'categoria': 'estetica',
            'asesora_asignada': 'sara',
            'ciudad': ciudad or '',
            'observaciones': f"Prioridad: {prioridad} | Ciudad: {ciudad or '—'}"
                              + (f" | {observaciones}" if observaciones else ''),
            'etapa': 'lead',
            'fecha_lead': _dt.now(_tz.utc).isoformat(),
        }
        url = f"{crm_url}/rest/v1/leads_comerciales?on_conflict=telefono"
        headers = {
            'apikey': crm_key,
            'Authorization': f'Bearer {crm_key}',
            'Content-Type': 'application/json',
            'Prefer': 'resolution=ignore-duplicates,return=minimal',
        }
        req = urllib.request.Request(url, data=_json.dumps(body).encode(),
                                      headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                print(f"[BRAIN] CRM lead upsert → {r.status} tel={telefono}", flush=True)
        except Exception as e:
            print(f"[BRAIN] CRM lead upsert err: {e}", flush=True)

    @staticmethod
    def _build_notify_message(nombre, servicio, telefono, ciudad=''):
        """Formato unificado de notificación WhatsApp al staff (Sara,
        Sharon, Central, Dr. Gio). Misma forma para cualquier servicio
        estético — sin precios ni metadatos extra."""
        nombre = nombre or '—'
        servicio = servicio or '—'
        nom_line = f"👤 {nombre} ({ciudad})" if ciudad else f"👤 {nombre}"
        return (
            "💉 PACIENTE LISTA\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"{nom_line}\n"
            f"💆 Tratamiento: {servicio}\n"
            f"📱 Tel: {telefono}\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Llamar para coordinar cita\n"
            "con Dra. Sharon 💙"
        )

    @staticmethod
    def _build_cita_estetica_notify(fields, sender_id):
        nombre = fields.get('nombre', '—')
        ciudad = fields.get('ciudad', '—')
        telefono = fields.get('telefono', sender_id)
        servicio = fields.get('servicio', '—')
        zona = fields.get('zona', '') or ''
        esteticista = fields.get('esteticista', '—')
        fecha = fields.get('fecha', '—')
        servicio_label = {
            'depilacion': 'Depilación Láser',
            'hiperbarica': 'Cámara Hiperbárica',
            'valoracion': 'Valoración Gratuita',
        }.get(servicio.lower(), servicio)
        return (
            "📅 CITA AGENDADA\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {nombre} ({ciudad})\n"
            f"💆 {servicio_label}{' — ' + zona if zona else ''}\n"
            f"📅 {fecha}\n"
            f"👩 {esteticista}\n"
            f"📱 Tel: {telefono}\n"
            "━━━━━━━━━━━━━━━━━━━"
        )

    @staticmethod
    def _build_facial_notify(fields, sender_id):
        nombre = fields.get('nombre', '—')
        ciudad = fields.get('ciudad', '—')
        telefono = fields.get('telefono', sender_id)
        tratamiento = fields.get('tratamiento') or fields.get('interes', '—')
        precio = fields.get('precio', '—')
        return (
            "💉 PACIENTE LISTA\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {nombre} ({ciudad})\n"
            f"💋 Tratamiento: {tratamiento}\n"
            f"💰 Precio referencial: {precio}\n"
            f"📱 Tel: {telefono}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Llamar para agendar directo\n"
            "con Dra. Sharon 💙"
        )

    @staticmethod
    def _parse_notify_fields(data):
        """Extract key: value pairs from a NOTIFY block body."""
        out = {}
        for line in (data or '').splitlines():
            line = line.strip()
            if not line or ':' not in line:
                continue
            k, _, v = line.partition(':')
            out[k.strip().lower()] = v.strip()
        return out

    @staticmethod
    def _build_body_sculpt_notify(fields, sender_id):
        nombre = fields.get('nombre', '—')
        telefono = fields.get('telefono', sender_id)
        meta = fields.get('meta', '—')
        historial = fields.get('historial', '—')
        condicion = fields.get('condicion_medica') or fields.get('condicion', '—')
        info_parts = []
        if historial and historial != '—':
            info_parts.append(historial)
        if condicion and condicion != '—':
            info_parts.append(condicion)
        info = ' | '.join(info_parts) if info_parts else '—'
        valor = fields.get('valor', '$150.000')
        ciudad = fields.get('ciudad', '—')
        return (
            "🔔 LEAD ARMONÍA CORPORAL 440\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Nombre: {nombre}\n"
            f"📱 Tel: {telefono}\n"
            f"🎯 Meta: {meta}\n"
            f"📋 Info: {info}\n"
            f"💰 Consulta: {valor}\n"
            f"📍 Ciudad: {ciudad}\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "CONTACTAR YA 📞"
        )
