"""Batería de conversaciones del bot de cirugías. Correr ANTES de cada publicación:

    python3 tests/conversaciones_cx.py            # todas
    python3 tests/conversaciones_cx.py precio     # solo las que contengan "precio" en el nombre

Usa la IA de verdad (ANTHROPIC_API_KEY del entorno o de ~/BOT440/.env.test); Supabase, WhatsApp
y MedFiles se simulan en memoria (no se envía nada). Revisa reglas del guion en cada respuesta y
termina con código 1 si alguna falla.
"""
import sys, os, re, io, json, urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
if not os.environ.get('ANTHROPIC_API_KEY'):
    env = os.path.expanduser('~/BOT440/.env.test')
    if os.path.exists(env):
        for l in open(env):
            if l.startswith('ANTHROPIC_API_KEY='):
                os.environ['ANTHROPIC_API_KEY'] = l.split('=', 1)[1].strip().strip('"')
os.environ.update({'SUPABASE_URL': 'https://sim.invalid', 'SUPABASE_ANON_KEY': 'sim', 'SUPABASE_KEY': 'sim',
                   'MEDFILES_URL': 'https://medfiles.sim', 'MEDFILES_BOT_CLAVE': 'sim', 'ASESORA_MEDFILES_TEL': '',
                   'WHAPI_TOKEN': 'sim', 'WHAPI_TOKEN_CX': 'sim', 'WHAPI_URL': 'https://whapi.sim'})

LEADS = []


class _R(io.BytesIO):
    status = 200
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def getcode(self): return 200


_real = urllib.request.urlopen
def _falso(req, *a, **k):
    url = req.full_url if hasattr(req, 'full_url') else str(req)
    if 'api.anthropic.com' in url:
        return _real(req, *a, **k)
    if 'medfiles.sim/api/entrada/bot' in url:
        if (req.get_method() if hasattr(req, 'get_method') else 'GET') == 'GET':
            return _R(b'{"pausado": false}')
        LEADS.append(json.loads(req.data.decode()))
        return _R(b'{"ok": true, "nuevo": true, "asesora": null}')
    if 'whapi.sim' in url:
        return _R(b'{"sent": true, "message": {"id": "sim"}}')
    return _R(b'[]')
urllib.request.urlopen = _falso

import core.brain_cx as bx  # noqa: E402

FILAS = []
def _cargar(self, sender_id, canal='cirugia'):
    msgs = []
    for f in FILAS:
        rol = 'assistant' if f[0] == 'saliente' else 'user'
        if msgs and msgs[-1]['role'] == rol:
            msgs[-1]['content'] += '\n' + f[1]
        else:
            msgs.append({'role': rol, 'content': f[1]})
    while msgs and msgs[0]['role'] != 'user':
        msgs.pop(0)
    return msgs
def _guardar(self, sender_id, sender_name, mensaje, direccion, remitente, canal='cirugia', cuenta_receptora=None):
    if mensaje:
        FILAS.append((direccion, mensaje))
bx.BrainCX._load_history = _cargar
bx.BrainCX._save_message = _guardar
bx.BrainCX._medfiles_pausado = lambda self, tel: False
bx.BrainCX._check_bloqueado = lambda self, s: False

CIERRE = 'Tu siguiente paso puede ser'
FICHA = 'Por lo general es ideal para ti si'

# ── Reglas que se revisan en TODAS las respuestas ──
def reglas_generales(r):
    fallas = []
    if r.count(CIERRE) > 1: fallas.append('bloque de siguiente paso repetido')
    if r.count('Asesoría virtual gratuita') > 1 and CIERRE in r and 'Excelente decisión' not in r:
        fallas.append('opciones repetidas')
    if re.search(r'1️⃣|2️⃣|resp[oó]ndeme \*?1', r, re.I): fallas.append('opciones numeradas escritas por la IA')
    if re.search(r'irregularidades|garantiz|resultados? perfect', r, re.I): fallas.append('promesa de resultados')
    if re.search(r'\*\*', r): fallas.append('negrita doble **')
    if re.search(r'^\s*[-—_]{3,}\s*$', r, re.M): fallas.append('separador ---')
    if r.count('Bienvenida(o) al *Centro de Atención') > 1: fallas.append('bienvenida repetida')
    if re.search(r'el dr\.? gio (te )?(define|eval[uú]a)[^.\n]*valoraci', r, re.I) and not re.search(r'asesora[^\n]*orienta', r, re.I):
        fallas.append('dice que solo el Dr. define (sin la asesora)')
    if CIERRE in r and '?' in r.split('¿Tienes alguna')[0].rstrip().split('\n')[-1]:
        fallas.append('pregunta propia de la IA antes del cierre')
    return fallas

# Chequeos por turno: (mensaje del paciente, [condiciones sobre la respuesta])
def tiene(*t): return ('contiene ' + ' / '.join(t), lambda r: all(x.lower() in r.lower() for x in t))
def no_tiene(*t): return ('NO contiene ' + ' / '.join(t), lambda r: not any(x.lower() in r.lower() for x in t))
def con_cierre(): return ('termina con el bloque aprobado', lambda r: r.rstrip().endswith('personalmente.') and CIERRE in r)
def sin_cierre(): return ('sin bloque de siguiente paso', lambda r: CIERRE not in r)
def con_ficha(): return ('trae la ficha aprobada', lambda r: FICHA in r)
def pide_datos(): return ('pide nombre, ciudad, correo y procedimiento', lambda r: all(x in r for x in ('Nombre completo', 'Ciudad', 'Correo electrónico', 'Procedimiento de interés')))

ESCENARIOS = {
    'lipo_directo': [
        ('Hola', [tiene('Bienvenida(o)', 'RETHUS'), sin_cierre()]),
        ('Quiero una lipo', [con_ficha(), tiene('Lipoescultura'), con_cierre()]),
        ('Cuánto vale', [tiene('17.000.000'), con_cierre(), no_tiene('Por lo general')]),
        ('Quiero la asesoría', [pide_datos(), sin_cierre()]),
        ('María Pérez\nBarranquilla\nmaria@gmail.com\nlipo', [tiene('drgio440.com'), sin_cierre()]),
    ],
    'abdomen_hijos': [
        ('Hola', [sin_cierre()]),
        ('Quiero mejorar mi abdomen, tengo barriga', [tiene('hijos', 'piel'), sin_cierre(), no_tiene(FICHA)]),
        ('Si tengo 2 hijos y la piel floja con estrías', [con_ficha(), tiene('abdominoplastia', 'te orienta'), con_cierre()]),
        ('Pero no sé si necesito lipo o abdominoplastia', [con_cierre()]),
    ],
    'abdomen_grasa': [
        ('Hola', []),
        ('Tengo barriga y grasa en la cintura', [tiene('hijos'), sin_cierre()]),
        ('No tengo hijos, es grasa que se pellizca', [con_ficha(), tiene('lipoescultura'), con_cierre()]),
        ('Incluye marcación abdominal?', [con_cierre()]),
    ],
    'pide_valoracion_directo': [
        ('Hola', []),
        ('Hola quisiera consultar para una valoración por favor', [pide_datos(), tiene('valoración'), sin_cierre()]),
    ],
    'valoracion_virtual': [
        ('Hola', []),
        ('quiero valoración virtual con el dr', [pide_datos(), tiene('valoración virtual'), no_tiene('presencial* o *virtual')]),
    ],
    'senos': [
        ('Hola', []),
        ('Me interesa operarme los senos', [tiene('volumen', 'levantarlos'), sin_cierre()]),
        ('Quiero más volumen, no he lactado', [con_ficha(), tiene('aumento'), con_cierre()]),
    ],
    'no_me_alcanza': [
        ('Hola', []),
        ('Quiero abdominoplastia', [con_ficha(), con_cierre()]),
        ('cuanto cuesta', [con_cierre()]),
        ('uy no me alcanza', [con_cierre()]),
    ],
    'otra_ciudad': [
        ('Hola', []),
        ('Soy de Cali, quiero lipotransferencia glútea', [con_ficha(), con_cierre()]),
        ('quiero la asesoria gratuita', [pide_datos()]),
        ('Ana Ruiz\nCali\nana@gmail.com\nlipotransferencia', [tiene('turismo')]),
    ],
    'que_es_asesoria': [
        ('Hola', []),
        ('Quiero una lipo', [con_ficha()]),
        ('Que es la asesoria virtual gratuita?', [tiene('asesora')]),
    ],
    'turismo_y_datos_del_dr': [
        ('Hola', []),
        ('Quiero abdominoplastia', [con_ficha()]),
        ('Tienes plan de turismo médico?', [tiene('recovery house', 'alimentación', 'enfermería'), con_cierre()]),
        ('El doctor pertenece a la sociedad colombiana de cirugia plastica?', [tiene('Sociedad Colombiana'), con_cierre()]),
        ('Donde operan?', [tiene('Barranquilla'), con_cierre()]),
    ],
    'pauta_mamoplastia': [
        ('Hola estoy interesado en todo incluido de mamoplastia', [tiene('18.000.000')]),
    ],
    'hombre_gineco': [
        ('Hola', []),
        ('Soy hombre y tengo pecho grande, ginecomastia', [con_ficha(), con_cierre()]),
    ],
    'hombre_palabras_propias': [
        ('Hola', []),
        ('Tengo muchas tetillas', [con_ficha(), tiene('ginecomastia'), con_cierre()]),
    ],
    'senos_tecnicas': [
        ('Hola', []),
        ('Quiero levantamiento de senos', [con_ficha(), tiene('Pexia')]),
        ('Que tecnicas usan? me preocupa la cicatriz en el escote', [tiene('En L', 'T invertida', 'Periareolar', 'Vertical'), con_cierre()]),
        ('Y que marca de implantes usan?', [tiene('Motiva', 'Silimed'), no_tiene('Preservé', 'Plano', 'surco'), con_cierre()]),
        ('que es preserve?', [tiene('Preservé'), no_tiene('Silimed'), con_cierre()]),
    ],
    'explantacion': [
        ('Hola', []),
        ('Quiero sacarme los implantes', [con_ficha(), tiene('propio tejido'), con_cierre()]),
        ('Tengo síntomas, creo que es síndrome de ASIA', [tiene('ASIA'), con_cierre()]),
        ('Y cómo quedan los senos sin implantes?', [tiene('propio tejido', 'lipotransferencia', 'pexia'), no_tiene('Motiva'), con_cierre()]),
    ],
    'tecnologia_lipo': [
        ('Hola', []),
        ('Quiero lipo 360', [con_ficha(), tiene('Argón Plasma', 'VASER', 'MicroAire'), con_cierre()]),
        ('Que tecnologia usan?', [tiene('Argón Plasma'), no_tiene('Retraction'), con_cierre()]),
        ('Y que es el vaser?', [tiene('ultrasonido'), no_tiene('MicroAire'), con_cierre()]),
        ('cuanto vale el argon plasma?', [tiene('asesora'), no_tiene('7.000.000', '9.000.000'), con_cierre()]),
    ],
    'dudas_seguidas': [
        ('Hola', []),
        ('Quiero lipo', [con_ficha()]),
        ('cuanto dura la recuperacion?', [con_cierre()]),
        ('y donde opera el doctor?', [con_cierre()]),
        ('tienen financiacion?', [con_cierre()]),
    ],
}


def correr(nombre, turnos):
    FILAS.clear(); LEADS.clear()
    bot = bx.BrainCX()
    fallas = []
    for i, (msg, checks) in enumerate(turnos, 1):
        try:
            r = bot.process('573009998877', 'Paciente Prueba', msg, canal='cirugia', send=False) or ''
        except Exception as e:
            fallas.append(f'turno {i} "{msg[:30]}": ERROR {e}')
            continue
        for f in reglas_generales(r):
            fallas.append(f'turno {i} "{msg[:30]}": {f}')
        for desc, ok in checks:
            if not ok(r):
                fallas.append(f'turno {i} "{msg[:30]}": falta → {desc}')
        if os.environ.get('VER'):
            print(f'\n--- [{nombre}] PACIENTE: {msg}\n{r}')
    return fallas


if __name__ == '__main__':
    filtro = sys.argv[1] if len(sys.argv) > 1 else ''
    total = 0
    for nombre, turnos in ESCENARIOS.items():
        if filtro and filtro not in nombre:
            continue
        fallas = correr(nombre, turnos)
        total += len(fallas)
        print(('✅ ' if not fallas else '❌ ') + nombre)
        for f in fallas:
            print('     · ' + f)
    print(f'\n{"TODO BIEN" if not total else f"{total} FALLAS"}')
    sys.exit(1 if total else 0)
