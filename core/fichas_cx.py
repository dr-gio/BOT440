# Fichas fijas de cada procedimiento (formato aprobado por el Dr. Gio): qué es, para quién es (✅),
# con qué se puede combinar, recuperación y quién lo realiza. La IA elige la ficha con <<<FICHA:clave>>>.
_PIE = "👨‍⚕️ La realiza el Dr. Gio con *anestesiólogo* y en *clínica certificada*"


def _ficha(titulo, que_es, ideal, combina, recuperacion, tecnologia=None):
    txt = f"{que_es} ✨\n\nPor lo general es ideal para ti si:\n" + "\n".join(f"✅ {x}" for x in ideal)
    if tecnologia:
        txt += f"\n\n🔬 {tecnologia}"
    if combina:
        txt += f"\n\n🔗 {combina}"
    return txt + f"\n\n⏱️ *Recuperación:* {recuperacion}\n{_PIE}"


FICHAS = {
    'abdominoplastia': _ficha('Abdominoplastia',
        "La *abdominoplastia* retira el *exceso de piel y grasa* del abdomen y, cuando es necesario, *repara los músculos* separados. El resultado es un abdomen *plano y firme*",
        ["Tienes *piel flácida o colgante*, por ejemplo después de *embarazos* o de *bajar mucho de peso*",
         "Notas el abdomen *abultado aunque hagas ejercicio*",
         "Tienes *estrías o piel sobrante* debajo del ombligo",
         "Estás en un *peso estable* y no piensas tener más embarazos pronto"],
        "Se puede *combinar* con *lipoescultura 360* (lipoabdominoplastia) para definir cintura y espalda, y con *lipotransferencia glútea* para dar volumen a los glúteos con tu propia grasa.",
        "actividades suaves en *2 a 3 semanas*; el Dr. Gio te da el plan exacto en la valoración"),
    'lipoabdominoplastia': _ficha('Lipoabdominoplastia',
        "La *lipoabdominoplastia* combina la *abdominoplastia* (retira piel y grasa sobrante y repara los músculos) con la *lipoescultura* de cintura, espalda y flancos, para un contorno *completo y armónico*",
        ["Tienes *piel sobrante* en el abdomen después de *embarazos* o *pérdida de peso*",
         "Además tienes *grasa localizada* en cintura, espalda o flancos",
         "Quieres un cambio *integral* del contorno en una sola cirugía",
         "Estás en un *peso estable*"],
        "Se puede *complementar* con *lipotransferencia glútea* para dar forma y volumen a los glúteos.",
        "actividades suaves en *2 a 3 semanas*; el Dr. Gio te da el plan exacto en la valoración"),
    'lipoescultura': _ficha('Lipoescultura 360',
        "La *lipoescultura 360* retira la *grasa localizada* de abdomen, cintura, espalda y flancos para *definir y armonizar tu silueta*",
        ["Tienes *grasa localizada* que no se va con dieta ni ejercicio",
         "Quieres *afinar la cintura* y definir tu figura",
         "Tienes *buena elasticidad de piel*",
         "Estás *cerca de tu peso ideal*"],
        "Se puede *combinar* con *lipotransferencia glútea* (tu propia grasa para dar volumen a los glúteos) y, si hay piel sobrante en el abdomen, con *abdominoplastia*.",
        "actividades suaves en *1 a 2 semanas* con faja y drenajes",
        "Se realiza con *tecnología*: *Argón Plasma*, la que más usa el Dr. Gio para ayudar a la *retracción de la piel*, y también *J Plasma*, *VASER* y *MicroAire*, según tu caso."),
    'lipotransferencia': _ficha('Lipotransferencia glútea',
        "La *lipotransferencia glútea* usa *tu propia grasa*, obtenida con lipoescultura, para dar *volumen y forma* a los glúteos de manera *natural*",
        ["Quieres *más volumen o proyección* en los glúteos",
         "Prefieres un resultado *natural, sin implantes*",
         "Tienes *grasa disponible* en abdomen, cintura o espalda",
         "Estás en un *peso estable*"],
        "Se realiza junto con la *lipoescultura 360* y se puede combinar con *abdominoplastia*.",
        "actividades suaves en *1 a 2 semanas*, con cuidados especiales al sentarte"),
    'mamoplastia_aumento': _ficha('Mamoplastia de aumento',
        "La *mamoplastia de aumento* aumenta el *volumen y mejora la forma* de los senos con *implantes*, elegidos según tu anatomía",
        ["Sientes que tus senos son *pequeños* para tu cuerpo",
         "Perdiste volumen después de *embarazos, lactancia* o *pérdida de peso*",
         "Tienes *asimetría* entre un seno y otro",
         "Quieres un escote más *lleno y armónico*"],
        "Si hay *caída* del seno se combina con *pexia* (levantamiento), y se puede hacer junto con *abdominoplastia* o *lipoescultura* (mommy makeover).",
        "actividades suaves en *1 semana*, con sostén postquirúrgico"),
    'pexia': _ficha('Pexia mamaria',
        "La *pexia mamaria* *levanta* los senos y reposiciona la areola; si se desea más volumen se hace *con implantes*",
        ["Tus senos están *caídos* o la areola apunta hacia abajo",
         "Hubo cambios después de *embarazos, lactancia* o *pérdida de peso*",
         "Quieres senos más *firmes y en su lugar*",
         "Estás en un *peso estable*"],
        "Se puede hacer *con implantes* para dar volumen, y combinar con *abdominoplastia* o *lipoescultura*.",
        "actividades suaves en *1 a 2 semanas*, con sostén postquirúrgico"),
    'reduccion': _ficha('Mamoplastia de reducción',
        "La *mamoplastia de reducción* disminuye el *tamaño y el peso* de los senos y los deja *levantados y proporcionados*",
        ["Tus senos son *muy grandes* para tu cuerpo",
         "Tienes *dolor de espalda, cuello u hombros* o marcas de los tirantes",
         "Te cuesta hacer ejercicio o encontrar ropa",
         "Quieres senos más *livianos y firmes*"],
        "Se puede combinar con *lipoescultura* o *abdominoplastia*.",
        "actividades suaves en *1 a 2 semanas*, con sostén postquirúrgico"),
    'explantacion': _ficha('Explantación mamaria',
        "La *explantación mamaria* retira los *implantes* (y la cápsula cuando es necesario) y *reconstruye el seno con tu propio tejido*, sin implantes",
        ["Quieres *retirar* tus implantes y volver a un resultado *natural*",
         "Tienes *molestias*, endurecimiento o cambios en los implantes",
         "Sientes síntomas que relacionas con los implantes (*síndrome de ASIA*)",
         "Ya no te sientes a gusto con el tamaño"],
        "Se puede complementar con *lipotransferencia de grasa* para dar volumen y, a veces, con *pexia* (levantamiento).",
        "actividades suaves en *1 a 2 semanas*, con sostén postquirúrgico"),
    'ginecomastia': _ficha('Ginecomastia',
        "La cirugía de *ginecomastia* retira la *grasa* y, si es necesario, el *tejido glandular* del pecho masculino para dejarlo *plano y definido*",
        ["Tienes *aumento del pecho* que no mejora con ejercicio",
         "Te incomoda usar camisetas o estar sin camisa",
         "Estás en un *peso estable*",
         "Quieres un pecho más *masculino y definido*"],
        "Se puede combinar con *lipoescultura* de abdomen y flancos.",
        "es *ambulatoria*; retomas actividades en *pocos días*, con chaleco compresivo"),
    'blefaroplastia': _ficha('Blefaroplastia',
        "La *blefaroplastia* retira el *exceso de piel y bolsas* de los párpados para una mirada *descansada y fresca*",
        ["Tienes *párpados caídos* o piel sobrante",
         "Tienes *bolsas* debajo de los ojos",
         "Te ves *cansada(o)* aunque hayas descansado",
         "En algunos casos la piel *molesta para ver*"],
        "Se puede combinar con *lipo de papada* u otros procedimientos faciales.",
        "inflamación leve por *1 a 2 semanas*"),
    'papada': _ficha('Lipo de papada',
        "La *lipo de papada* retira la *grasa acumulada* debajo del mentón para definir el *contorno del cuello y la mandíbula*",
        ["Tienes *papada* que no mejora con dieta ni ejercicio",
         "Quieres un *perfil* y una mandíbula más definidos",
         "Tienes *buena elasticidad* de piel (si no, se usa tecnología de retracción)",
         "Estás en un *peso estable*"],
        "Se puede combinar con *blefaroplastia* u otros procedimientos faciales.",
        "es *ambulatoria*; inflamación leve por *1 semana*, con mentonera"),
    'otoplastia': _ficha('Otoplastia',
        "La *otoplastia* corrige las *orejas despegadas* o con forma irregular para que queden *proporcionadas*",
        ["Tus orejas son *prominentes o despegadas*",
         "Hay *asimetría* entre una oreja y otra",
         "Te incomoda llevar el cabello recogido",
         "Quieres un perfil más *armónico*"],
        None,
        "actividades suaves en *pocos días*, con balaca protectora"),
    'abdominoplastia_inversa': _ficha('Abdominoplastia inversa',
        "La *abdominoplastia inversa* trata la *flacidez de la parte alta del abdomen*, por encima del ombligo, con la cicatriz escondida en el *surco debajo de los senos*",
        ["Tienes *piel suelta en la parte alta* del abdomen",
         "La parte baja del abdomen está *bien*",
         "Te vas a hacer o te interesa una *cirugía de senos*",
         "Estás en un *peso estable*"],
        "Se combina con frecuencia con *cirugía mamaria* y con *lipoescultura*.",
        "actividades suaves en *2 semanas*; el Dr. Gio te da el plan exacto en la valoración"),
    'mommy_makeover': _ficha('Mommy Makeover',
        "El *Mommy Makeover* combina en una sola cirugía los procedimientos que *devuelven la forma después de los embarazos*: abdomen, contorno y senos",
        ["Tuviste *embarazos* y notas cambios en abdomen y senos",
         "Tienes *piel sobrante* en el abdomen y *grasa localizada*",
         "Tus senos perdieron *volumen o firmeza*",
         "Ya *no piensas tener más embarazos*"],
        "Suele incluir *abdominoplastia*, *lipoescultura* y *mamoplastia* (aumento o pexia); se puede sumar *lipotransferencia glútea*.",
        "actividades suaves en *2 a 3 semanas*; el Dr. Gio te da el plan exacto en la valoración"),
    'lifting_extremidades': _ficha('Lifting de brazos o piernas',
        "El *lifting de brazos o piernas* retira la *piel sobrante y flácida* para que queden *firmes y definidos*",
        ["Tienes *piel colgante* en brazos o muslos",
         "Pasó después de *bajar mucho de peso*",
         "La flacidez *no mejora* con ejercicio",
         "Estás en un *peso estable*"],
        "Se puede combinar con *lipoescultura* de la zona.",
        "actividades suaves en *2 semanas*, con prendas compresivas"),
    'miniabdominoplastia': _ficha('Miniabdominoplastia',
        "La *miniabdominoplastia* corrige la *flacidez y el exceso de piel de la parte baja* del abdomen, debajo del ombligo, con una *cicatriz más corta* que la abdominoplastia completa",
        ["Tienes *piel sobrante o flacidez* solo *debajo del ombligo*",
         "La parte alta del abdomen está *bien*",
         "Notas un *abultamiento bajo* después de embarazos o cesárea",
         "Estás en un *peso estable*"],
        "Se puede *combinar* con *lipoescultura 360* y con *lipotransferencia glútea*.",
        "actividades suaves en *1 a 2 semanas*; el Dr. Gio te da el plan exacto en la valoración"),
    'lifting_facial': _ficha('Lifting facial',
        "El *lifting facial* reposiciona los tejidos de la cara y el cuello y retira la piel sobrante para una apariencia *más fresca y rejuvenecida*, conservando tu expresión natural",
        ["Notas *flacidez* en mejillas, mandíbula o cuello",
         "Se marcan los *surcos* y la *línea de la mandíbula* se perdió",
         "Quieres verte *descansada(o) y natural*, sin cambiar tu esencia",
         "Gozas de *buena salud* general"],
        "Se puede *combinar* con *blefaroplastia* y *lipo de papada*.",
        "inflamación leve por *2 a 3 semanas*; el Dr. Gio te da el plan exacto en la valoración"),
    'gluteoplastia_implante': _ficha('Gluteoplastia con implante',
        "La *gluteoplastia con implante* da *volumen y proyección* a los glúteos con *implantes* especiales",
        ["Quieres *más volumen* en los glúteos",
         "Tienes *poca grasa* para hacer lipotransferencia",
         "Buscas un cambio de *forma y proyección*",
         "Estás en un *peso estable*"],
        "Se puede combinar con *lipoescultura* para definir la cintura.",
        "cuidados especiales al sentarte durante las primeras *semanas*"),
}


def expandir_fichas(texto):
    """Reemplaza <<<FICHA:clave>>> por la ficha fija. Devuelve (texto, hubo_ficha)."""
    import re
    hubo = False

    def _rep(m):
        nonlocal hubo
        clave = m.group(1).strip().lower()
        if clave in FICHAS:
            hubo = True
            return FICHAS[clave]
        return ''
    texto = re.sub(r'<<<FICHA:([a-z_]+)>>>', _rep, texto)
    return texto, hubo


# Valor "desde" de cada ficha (mismos valores de la sección 5 del guion). Si el paciente pregunta el precio
# en el mismo mensaje en que sale la ficha, el código lo responde ANTES de la ficha (la ficha borra lo que escriba la IA).
PRECIOS_DESDE = {
    'lipoescultura': ('la *lipoescultura 360*', 'un valor *desde $17.000.000*'),
    'abdominoplastia': ('la *abdominoplastia*', 'un valor *desde $22.000.000*'),
    'lipoabdominoplastia': ('la *lipoabdominoplastia*', 'un valor *desde $25.000.000*'),
    'mamoplastia_aumento': ('la *mamoplastia de aumento*', 'un valor de *$18.000.000 todo incluido*'),
    'pexia': ('la *pexia mamaria con implantes*', 'un valor *desde $18.000.000*'),
    'reduccion': ('la *mamoplastia de reducción*', 'un valor *desde $20.000.000*'),
    'explantacion': ('la *explantación mamaria*', 'un valor *desde $22.000.000*'),
    'mommy_makeover': ('el *Mommy Makeover*', 'un valor *desde $30.000.000* (según los procedimientos que se combinen)'),
    'lipotransferencia': ('la *lipotransferencia glútea*', 'un valor *desde $3.000.000* adicionales a la lipoescultura o lipoabdominoplastia'),
    'gluteoplastia_implante': ('la *gluteoplastia con implantes*', 'un valor *desde $22.000.000*'),
    'lifting_extremidades': ('el *lifting de brazos o piernas*', 'un valor *desde $14.000.000*'),
    'lifting_facial': ('el *lifting facial*', 'un valor *desde $25.000.000*'),
    'ginecomastia': ('la *ginecomastia*', 'un valor *desde $4.000.000* (con aspiración) o *desde $6.000.000* (si se retira la glándula)'),
    'blefaroplastia': ('la *blefaroplastia*', 'un valor *desde $4.500.000* (párpados superiores) o *desde $7.000.000* (superiores e inferiores)'),
    'papada': ('la *lipo de papada*', 'un valor *desde $2.500.000* (con Retraction *desde $3.500.000*)'),
    'otoplastia': ('la *otoplastia*', 'un valor *desde $7.000.000*'),
}


def pide_precio(mensaje):
    """¿El paciente pregunta el precio en este mensaje?"""
    import re
    return bool(re.search(r'\b(presupuesto|cotizaci[oó]n|cotizar|precios?|valor(es)?|costos?|aproximado|cu[aá]nto (me )?(cuesta|vale|sale|cobra))\b',
                          mensaje or '', re.I))


def bloque_precio(claves):
    """Respuesta corta al precio para las fichas pedidas (las que tienen valor de referencia)."""
    partes = [PRECIOS_DESDE[c] for c in claves if c in PRECIOS_DESDE]
    if not partes:
        return ''
    if len(partes) == 1:
        nombre, valor = partes[0]
        frase = f"{nombre[0].upper() + nombre[1:]} tiene {valor}."
    else:
        frase = ' · '.join(f"{n[0].upper() + n[1:]}: {v.replace('un valor ', '')}" for n, v in partes)
    return ("¡Claro, con gusto te cuento! 💙 " + frase + " Sabemos que es una inversión importante en ti ✨ "
            "El valor exacto depende de tu caso: tu *presupuesto personalizado* se entrega en tu "
            "*asesoría virtual gratuita* 💻 o en tu *valoración con el Dr. Gio* 👨‍⚕️")
