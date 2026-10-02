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
    (r'explant|retir(ar|o) (los )?implantes', 'explantacion'),
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
    if re.search(r'nombre completo', ultimo, re.I) and not re.search(r'drgio440\.com', ultimo, re.I):
        return {'paso': 'datos'}
    if _es_eleccion(t):
        return {'paso': 'elige'}
    if re.search(r'turismo|hospedaje|alojamiento|recovery|hotel|d[oó]nde me (quedo|hospedo)|vengo de (otra|otro|fuera)', t, re.I):
        return {'paso': 'turismo'}
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
    if p == 'turismo':
        return TURISMO + '\n\n' + CIERRE_DUDAS
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
