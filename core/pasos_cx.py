"""Control de pasos del bot de cirugías: el CÓDIGO decide en qué paso va la conversación
(no la IA), le dice a la IA qué escribir en este turno y arma el mensaje final con las
partes aprobadas (preguntas de orientación, fichas, cierre con el siguiente paso).

Pasos:
  bienvenida   primer contacto (lo arma ajustar_respuesta_cx)
  orientar     el paciente describe una zona (abdomen, senos, glúteos) → preguntas fijas
  recomendar   respondió las preguntas de orientación → por qué + ficha + cierre
  procedimiento nombra un procedimiento nuevo → ficha + cierre
  duda         cualquier pregunta o comentario → respuesta corta de la IA + cierre
  elige        pide la asesoría o la valoración → pedido de datos (ajustar_respuesta_cx)
  datos        responde al pedido de datos → flujo de NOTIFY de siempre
"""
import re
from core.fichas_cx import FICHAS, expandir_fichas

MARCA_ORIENTAR = 'Para orientarte mejor sobre el procedimiento ideal para ti'

ORIENTAR = {
    'abdomen': ("¡Te entiendo! 💙 Es algo muy común y tiene muy buena solución.\n\n"
                f"{MARCA_ORIENTAR}:\n"
                "👶 ¿Has tenido *hijos* o has *bajado mucho de peso*?\n"
                "🤏 ¿Sientes la *piel del abdomen floja*, con *estrías* o que cuelga, o es más *grasa que se pellizca*? 😊"),
    'senos': ("¡Te entiendo! 💙 Hay varias opciones según lo que buscas.\n\n"
              f"{MARCA_ORIENTAR}:\n"
              "👙 ¿Buscas más *volumen*, *levantarlos*, *reducir su tamaño* o una combinación?\n"
              "🤱 ¿Has *lactado* o has tenido *cambios de peso*? 😊"),
    'gluteos': ("¡Te entiendo! 💙 Tenemos muy buenas opciones para los glúteos.\n\n"
                f"{MARCA_ORIENTAR}:\n"
                "🍑 ¿Buscas más *volumen* o mejorar la *forma*?\n"
                "🤏 ¿Tienes *grasa localizada* en abdomen, cintura o espalda? 😊"),
}

TURISMO = ("¡Claro! 💙 Nuestros *planes de turismo médico todo incluido* te acompañan en tu cirugía y recuperación: "
           "*hospedaje* en recovery house u hotel, *alimentación*, *enfermería* y más ✈️\n\n"
           "Nuestra *asesora experta* te explica el plan completo en tu *asesoría virtual gratuita* 😊")

# Respuestas cortas por tema (si pregunta la marca, solo la marca; si pregunta la técnica, solo la técnica)
SENOS_TEMAS = {
    'marca': "🏷️ Trabajamos con implantes *Motiva*, *Silimed* y *Eurosilicone*, marcas reconocidas a nivel mundial.",
    'preserve': ("✨ La técnica *Motiva Preservé* es un aumento *mínimamente invasivo* que *preserva tus tejidos*: "
                 "*incisión pequeña*, menos inflamación y *recuperación más rápida*."),
    'plano': ("📐 El implante puede ir *sobre el músculo* (subglandular o subfascial) o *detrás del músculo* "
              "(submuscular o dual plane); el Dr. elige según tu tejido y el resultado que buscas."),
    'via': "✂️ El implante entra por el *surco* debajo del seno (la cicatriz queda escondida) o por el *borde de la areola*.",
    'tamano': "📏 El Dr. escoge el *perfil, tamaño y volumen* del implante según tu anatomía y lo que buscas.",
    'recuperacion': "⏱️ Con implantes retomas actividades suaves en *1 semana*, con sostén postquirúrgico.",
    'tecno_general': ("🔬 La *lipoescultura 360* se realiza con *tecnología*. La que más usa el Dr. Gio es *Argón Plasma*, "
                      "que ayuda a la *retracción de la piel*; también usa *J Plasma*, *VASER* y *MicroAire*. "
                      "La combinación ideal la define el Dr. según tu caso."),
    'argon': "🔬 *Argón Plasma* es la tecnología que más usa el Dr. Gio: energía de plasma que ayuda a la *retracción y firmeza de la piel* después de la lipo.",
    'jplasma': "🔬 *J Plasma* usa plasma frío para *tensar la piel desde adentro* y mejorar la firmeza.",
    'vaser': "🔬 *VASER* usa *ultrasonido* para *emulsionar la grasa* y retirarla con menos trauma, ayudando a *definir* la silueta.",
    'microaire': "🔬 *MicroAire* es una cánula con *vibración* que permite retirar la grasa de forma más *uniforme* y precisa.",
    'retraction': "🔬 *Retraction* es un láser que estimula la *retracción de la piel*; el Dr. lo usa en *casos puntuales*.",
    'tecno_precio': "💰 El valor de la tecnología depende de tu caso; nuestra *asesora experta* te lo explica en tu *asesoría virtual gratuita*.",
    'asia': ("🩺 Algunas pacientes consultan por síntomas que relacionan con sus implantes, como *cansancio*, *dolores articulares* "
             "o *molestias generales*; es lo que se conoce como *síndrome de ASIA* o enfermedad del implante mamario. "
             "El Dr. Gio evalúa tu caso y si está indicado *retirarlos (explantación)*."),
    'reconstruccion': ("🌸 En la explantación el seno se *reconstruye con tu propio tejido*, *sin implantes*. Se puede complementar con "
                       "*lipotransferencia de grasa* para dar volumen y, a veces, se requiere *pexia* (levantamiento) con la técnica "
                       "que corresponda a tu caso: *periareolar*, *vertical*, *en L* o *en T*."),
}

CICATRICES_SENOS = ("¡Claro! 💙 En el *levantamiento (pexia)* y la *reducción* la técnica depende de cada caso, "
                    "buscando siempre *la menor cicatriz posible*:\n\n"
                    "⭕ *Periareolar:* cicatriz solo *alrededor de la areola*. Para descensos leves.\n"
                    "📍 *Vertical:* alrededor de la areola y una *línea vertical* hacia abajo. Para descensos moderados.\n"
                    "↪️ *En L:* alrededor de la areola, vertical y una línea corta *hacia afuera*, *sin cicatriz hacia el escote*.\n"
                    "⊥ *En T invertida:* alrededor de la areola, vertical y en el *surco*. Para descensos grandes o reducciones de mucho volumen.\n\n"
                    "Si además quieres más volumen, la pexia se hace *con implantes*.")

VERIFICAR = ("¡Sí! 💙 El *Dr. Giovanni Fuentes* es *Cirujano Plástico, Estético y Reconstructivo certificado* "
             "y *Miembro de la Sociedad Colombiana de Cirugía Plástica* 🏅\n\n"
             "Puedes verificarlo aquí:\n\n"
             "🏅 *Sociedad Colombiana de Cirugía Plástica*\n"
             "https://cirugiaplastica.org.co/buscar-cirujano/\n"
             "Elige la ciudad *Barranquilla* y toca *Buscar*: aparece *Giovanni Fuentes*.\n\n"
             "🪪 *RETHUS — Ministerio de Salud* (registro oficial de profesionales de la salud)\n"
             "https://web.sispro.gov.co/THS/Cliente/ConsultasPublicas/ConsultaPublicaDeTHxIdentificacion.aspx\n"
             "En *Tipo de identificación* elige *Cédula de Ciudadanía*, escribe *72248179*, completa el código de la imagen "
             "y toca *Consultar*: aparece como especialista en *Cirugía Plástica* (RETHUS CMC2017-222322).")

RECORDAR_DATOS = ("Cuando quieras, déjame tus datos para que *nuestra asesora te contacte* 😊\n"
                  "👤 *Nombre completo* · 📍 *Ciudad* · 📧 *Correo* · ✨ *Procedimiento de interés*")

FRASE_ASESORA = ("En tu *asesoría virtual gratuita* nuestra *asesora experta en cirugía plástica* te orienta "
                 "según tu caso, y el Dr. Gio lo confirma en tu valoración 👨‍⚕️")

# Procedimiento → clave de ficha (lo más específico primero)
_CLAVES = [
    (r'abdominoplastia inversa', 'abdominoplastia_inversa'),
    (r'mini ?abdomino', 'miniabdominoplastia'),
    (r'lipo ?abdomino', 'lipoabdominoplastia'),
    (r'mommy|mam[aá] makeover', 'mommy_makeover'),
    (r'abdominoplast|abdomino\b|cirug[ií]a de abdomen', 'abdominoplastia'),
    (r'lipotransfer|\bbbl\b|gl[uú]teos? con (mi )?(propia )?grasa', 'lipotransferencia'),
    (r'gluteoplastia|implantes? de gl[uú]te', 'gluteoplastia_implante'),
    (r'explant|(retir|sac|quit)\w* (los |mis )?(implantes|pr[oó]tesis)', 'explantacion'),
    (r'reducci[oó]n (de senos|mamaria)|mamoplastia de reducci|reducir (los )?senos', 'reduccion'),
    (r'pexia|levantamiento de senos|levantar (los )?senos|senos ca[ií]dos', 'pexia'),
    (r'aumento de senos|mamoplastia( de aumento)?|implantes? mamari|implantes? de senos|aumentar (los )?senos', 'mamoplastia_aumento'),
    (r'ginecomast|tetillas?|pecho de (hombre|mujer)|senos de hombre|bubis de hombre', 'ginecomastia'),
    (r'blefaro|p[aá]rpados', 'blefaroplastia'),
    (r'papada', 'papada'),
    (r'otoplast|orejas', 'otoplastia'),
    (r'lifting facial|ritidoplast|ritidectom', 'lifting_facial'),
    (r'braquioplast|lifting (de )?(brazos|piernas|muslos)', 'lifting_extremidades'),
    (r'lipo(escultura|succi[oó]n|sucion)?\b|liposcultura|lipocultura', 'lipoescultura'),
]


def clave_de(texto):
    t = (texto or '').lower()
    for patron, clave in _CLAVES:
        if re.search(patron, t):
            return clave
    return None


def _titulo(clave):
    f = FICHAS.get(clave)
    m = re.search(r'\*([^*\n]+)\*', f) if f else None
    return m.group(1) if m else clave


_ZONAS = {
    'abdomen': (r'\b(barriga|barriguita|panza|abdomen|abdominal|est[oó]mago|vientre|pipa|llanta|gordito)\b',
                r'abdominoplast|abdomino\b|mini ?abdomino|lipo ?abdomino|mommy'),
    'senos': (r'\b(senos?|busto|pechos?|bubis|mamas?)\b',
              r'aument|implante|pexia|levant|reducc|reducir|explant|mamoplastia|ca[ií]dos|grandes|peque[ñn]os|retirar|'
              r'gineco|\bhombre\b|masculin|\bsoy un\b'),
    'gluteos': (r'\b(cola|colita|gl[uú]teos?|nalgas|pompis)\b',
                r'lipotransfer|implante|gluteoplastia|\bbbl\b'),
}


def zona_a_orientar(texto):
    t = (texto or '').lower()
    for zona, (si, no) in _ZONAS.items():
        if re.search(si, t) and not re.search(no, t):
            return zona
    return None


def _es_pregunta(t):
    return '?' in t or bool(re.search(r'\b(cu[aá]nto|precio|valor|qu[eé] es|c[oó]mo es|incluye|cu[aá]l es)\b', t, re.I))


def _es_eleccion(t):
    if _es_pregunta(t):
        return False
    return bool(re.search(r'\b(valoraci[oó]n|consulta(r)? (con|del|para)|cita con (el )?(dr|doctor)|asesor[ií]a)\b', t, re.I)
                or re.search(r'^\s*(la )?(primera|segunda|opci[oó]n \d)\s*$', t, re.I))


def _textos_bot(history):
    return [m.get('content') for m in (history or []) if m.get('role') == 'assistant' and isinstance(m.get('content'), str)]


def decidir_paso(history, texto):
    bots = _textos_bot(history)
    t = texto or ''
    if not bots:
        return {'paso': 'bienvenida'}
    ultimo = bots[-1]
    if re.search(r'sociedad|certificad|rethus|verific|registrad|avalad|es (cirujano|especialista|pl[aá]stico)|t[ií]tulo|idoneidad|es real', t, re.I):
        return {'paso': 'verificar', 'datos_pendientes': bool(re.search(r'nombre completo', ultimo, re.I))
                and not re.search(r'drgio440\.com', ultimo, re.I)}
    if re.search(r'nombre completo', ultimo, re.I) and not re.search(r'drgio440\.com', ultimo, re.I):
        return {'paso': 'datos'}
    if _es_eleccion(t):
        return {'paso': 'elige'}
    if re.search(r'turismo|hospedaje|alojamiento|recovery|hotel|d[oó]nde me (quedo|hospedo)|vengo de (otra|otro|fuera)', t, re.I):
        return {'paso': 'turismo'}
    # Preguntas técnicas de senos: se responde SOLO el tema preguntado (marca, Preservé, plano, vía, tamaño, cicatrices)
    contexto_senos = re.search(r'seno|busto|mama|pexia|levant|reducc|implante|pr[oó]tesis', t + '\n' + '\n'.join(bots[-2:]), re.I)
    pregunta_info = _es_pregunta(t) or re.search(r'\b(t[eé]cnicas?|marcas?|expl[ií]ca)', t, re.I)
    info = []
    # Tecnologías de la lipo: solo lo que pregunta
    tecno = []
    if re.search(r'argo[nń]|arg[oó]n', t, re.I): tecno.append('argon')
    if re.search(r'j\s?plasma|renuvion', t, re.I): tecno.append('jplasma')
    if re.search(r'vaser', t, re.I): tecno.append('vaser')
    if re.search(r'micro\s?aire', t, re.I): tecno.append('microaire')
    if re.search(r'retraction', t, re.I): tecno.append('retraction')
    if not tecno and re.search(r'tecnolog', t, re.I): tecno.append('tecno_general')
    if tecno and re.search(r'cu[aá]nto|precio|valor|cuesta|vale', t, re.I): tecno.append('tecno_precio')
    if tecno:
        return {'paso': 'info_senos', 'temas': tecno}
    contexto_explant = re.search(r'explant|retir\w* (los |mis )?implantes|sacar (los |mis )?implantes|asia|enfermedad del implante', t + '\n' + '\n'.join(bots[-2:]), re.I)
    if contexto_explant and (pregunta_info or re.search(r'asia|s[ií]ntomas', t, re.I)):
        if re.search(r'asia|enfermedad del implante|\bbii\b|s[ií]ntoma|autoinmun|cansancio|enferm', t, re.I): info.append('asia')
        if re.search(r'c[oó]mo (queda|quedan)|reconstru|sin implante|vac[ií]o|ca[ií]d|volumen|grasa|lipotransfer|pexia|t[eé]cnica|cicatri|forma', t, re.I):
            info.append('reconstruccion')
    elif pregunta_info and contexto_senos:
        if re.search(r'marca|motiva|silimed|eurosilicone', t, re.I): info.append('marca')
        if re.search(r'preserv', t, re.I): info.append('preserve')
        if re.search(r'plano|m[uú]sculo|submuscular|subglandular|subfascial|dual', t, re.I): info.append('plano')
        if re.search(r'v[ií]a|por d[oó]nde (entra|meten|ponen)|entrada', t, re.I): info.append('via')
        if re.search(r'tama[ñn]o|\bcc\b|perfil|qu[eé] tan grande', t, re.I): info.append('tamano')
        if re.search(r't[eé]cnica|cicatri|incisi[oó]n|corte|escote|\ben (l|t)\b|periareolar|vertical', t, re.I):
            pexia = re.search(r'pexia|levant|reducc|ca[ií]d', t + '\n' + '\n'.join(bots[-2:]), re.I)
            info.append('cicatrices' if pexia else 'preserve')
        info = list(dict.fromkeys(info))
    if info:
        return {'paso': 'info_senos', 'temas': info}
    if MARCA_ORIENTAR in ultimo and not _es_pregunta(t):
        zona = next((z for z, txt in ORIENTAR.items() if txt.split('\n')[-1] in ultimo), None)
        return {'paso': 'recomendar', 'zona': zona}
    todo_bot = '\n'.join(bots)
    zona = zona_a_orientar(t)
    if zona and ORIENTAR[zona] not in todo_bot and not _es_pregunta(t):
        return {'paso': 'orientar', 'zona': zona}
    clave = clave_de(t)
    m = re.search(r'Me cuentas que te interesa la \*([^*\n]+)\*', ultimo)
    if not clave and m and re.search(r'\b(s[ií]|claro|dale|ok|bueno|por favor|cu[eé]ntame)\b', t, re.I):
        clave = clave_de(m.group(1))
    if clave and not _es_pregunta(t) and _titulo(clave).lower() not in todo_bot.lower():
        return {'paso': 'procedimiento', 'clave': clave}
    return {'paso': 'duda'}


def instruccion_paso(paso):
    p = paso.get('paso')
    if p == 'recomendar':
        return ("\n\n[PASO ACTUAL — RECOMENDAR] El paciente respondió tus preguntas de orientación. "
                "Escribe en 1–2 líneas cuál procedimiento le conviene y POR QUÉ, según lo que contó "
                "(hijos/piel floja/estrías → abdominoplastia, o lipoabdominoplastia si además hay grasa; "
                "solo grasa con buena piel → lipoescultura; volumen → mamoplastia de aumento; caídos → pexia; "
                "grandes → reducción; volumen de glúteos con su grasa → lipotransferencia). "
                "En la línea siguiente SOLO el marcador <<<FICHA:clave>>>. Sin preguntas ni opciones.")
    if p == 'procedimiento':
        return (f"\n\n[PASO ACTUAL — INFORMAR] Responde '¡Excelente! 💙' y en la línea siguiente SOLO "
                f"<<<FICHA:{paso.get('clave')}>>>. Nada más.")
    if p == 'duda':
        return ("\n\n[PASO ACTUAL — RESPONDER] Responde SOLO lo que el paciente preguntó o comentó, cálido, "
                "en máximo 4 líneas. NO hagas preguntas, NO ofrezcas la asesoría ni la valoración ni opciones, "
                "NO preguntes '¿alguna otra duda?': el sistema agrega el cierre aprobado.")
    if p == 'orientar':
        return "\n\n[PASO ACTUAL — ORIENTAR] Responde solo '¡Te entiendo! 💙' (el sistema agrega las preguntas)."
    return ''


def _quitar_cierres(texto):
    """Quita el cierre aprobado (si ya está) y cualquier pregunta u oferta de opciones al final."""
    texto = texto.split('¿Tienes alguna otra *pregunta o duda*')[0]
    texto = texto.split('¿Tienes alguna *pregunta o duda*')[0]
    texto = texto.split('Tu siguiente paso puede ser')[0]
    lineas = texto.rstrip().split('\n')
    while lineas and (not lineas[-1].strip()
                      or '?' in lineas[-1]
                      or re.search(r'(1️⃣|2️⃣|✅\s*\*?(asesor|valoraci)|resp[oó]ndeme|siguiente paso)', lineas[-1], re.I)):
        lineas.pop()
    return '\n'.join(lineas).rstrip()


def _ficha(clave):
    cuerpo, ok = expandir_fichas(f'<<<FICHA:{clave}>>>')
    return cuerpo if ok else ''


def _clave_recomendada(texto_ia, mensaje, zona):
    clave = clave_de(texto_ia)
    if clave:
        return clave
    m = (mensaje or '').lower()
    if zona == 'abdomen':
        piel = re.search(r'(hijo|embaraz|piel|floj|estr[ií]a|cuelg|baj[eé]|bajado)', m) and not re.search(r'\bno (tengo|he tenido) hijos\b', m)
        grasa = re.search(r'grasa', m)
        return ('lipoabdominoplastia' if grasa else 'abdominoplastia') if piel else 'lipoescultura'
    if zona == 'senos':
        if re.search(r'reduc|grandes|pesad|espalda', m):
            return 'reduccion'
        if re.search(r'levant|ca[ií]d', m):
            return 'pexia'
        return 'mamoplastia_aumento'
    if zona == 'gluteos':
        return 'lipotransferencia'
    return None


def aplicar_paso(texto, paso, history, mensaje):
    """Marco final del mensaje según el paso que decidió el código."""
    from core.brain_cx import CIERRE_DUDAS
    p = paso.get('paso')
    if p == 'orientar':
        return ORIENTAR[paso['zona']]
    if p == 'verificar':
        return VERIFICAR + '\n\n' + (RECORDAR_DATOS if paso.get('datos_pendientes') else CIERRE_DUDAS)
    if p == 'turismo':
        return TURISMO + '\n\n' + CIERRE_DUDAS
    if p == 'info_senos':
        temas = paso['temas']
        partes = [CICATRICES_SENOS.replace('¡Claro! 💙 ', '') if x == 'cicatrices' else SENOS_TEMAS[x] for x in temas]
        return '¡Claro! 💙\n\n' + '\n'.join(partes) + '\n\n' + CIERRE_DUDAS
    if p not in ('recomendar', 'procedimiento', 'duda'):
        return texto
    # Mensajes que tienen su propio cierre aprobado: no se tocan
    if re.search(r'(nombre completo|<<<NOTIFY|drgio440\.com|urgencias|l[ií]nea de emergencia|asesora ya tiene tus datos)', texto, re.I):
        return texto
    tiene_ficha = 'Por lo general es ideal para ti si' in texto
    # Describió algo y la IA reconoció el procedimiento (ej. "tetillas" → ginecomastia): va la ficha aprobada
    if p == 'duda' and not tiene_ficha and not _es_pregunta(mensaje or ''):
        clave = clave_de(texto)
        if clave and _titulo(clave).lower() not in '\n'.join(_textos_bot(history)).lower():
            p, paso = 'procedimiento', {'paso': 'procedimiento', 'clave': clave, 'intro_ia': True}
    if p in ('recomendar', 'procedimiento') and not tiene_ficha:
        clave = paso.get('clave') if p == 'procedimiento' else _clave_recomendada(texto, mensaje, paso.get('zona'))
        ficha = _ficha(clave) if clave else ''
        if ficha:
            intro = _quitar_cierres(texto)
            if (p == 'procedimiento' and not paso.get('intro_ia')) or len(intro) > 400:
                intro = '¡Excelente! 💙'
            texto = intro + '\n\n' + ficha
    cuerpo = _quitar_cierres(texto)
    if p == 'recomendar' and 'asesora' not in cuerpo.lower():
        cuerpo += '\n\n' + FRASE_ASESORA
    return (cuerpo + '\n\n' + CIERRE_DUDAS).strip()
