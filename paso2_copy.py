import re
import json
from typing import List
import preview_archivos
import revision
# --- Configuración de logger ---
from logger import get_logger, log_section, dbg

logger = get_logger("paso2", log_dir="logs", log_file="paso2.log")

KEYWORDS_INMUEBLES = [
    "DEPARTAMENTO", "CASA", "PARCELA", "SITIO", "TERRENO", "PATIO", 
    "CONDOMINIO", "BODEGA", "GALPÓN", "GALPON", "LOTEO", "ESTACIONAMIENTO", 
    "OFICINA", "INMUEBLE", "PROPIEDAD", "PREDIO", "HIJUELA", "FUNDO", 
    "VIVIENDA", "LOCAL", "LOTE"
]

CLAVES_SEPARADORES = [
    r"REMATE",
    r"EXTRACTO",
    r"JUZGADO\s+DE\s+POLIC[ÍI]A\s+LOCAL",
    r"JUZGADO\s+DE\s+LETRAS",
    r"JUEZ\s+ARBITRO",
    r"LICITACI[ÓO]N\s+REMATE",
    r"EN\s+JUICIO\s+PARTICI[ÓO]N",
    r"OFERTA\s+REMATE",
    r"VENTA\s+EN\s+REMATE",
    r"ANTE\s+EL\s+\d{1,2}°?\s+JUZGADO\s+CIVIL",
    r"\d{1,2}°?\s+JUZGADO\s+CIVIL",
    r"VIG[ÉE]SIMO",
    r"D[ÉE]CIMO",
    r"EN\s+CAUSA\s+ROL",
    r"JUEZ\s+PARTIDOR\s+DON\s+[A-ZÁÉÍÓÚÑ]+",
    r"REMATE,\s+ANTE\s+JUEZ\s+PARTIDOR",
    r"REMATE:\s+VIG[ÉE]SIMO\s+JUZGADO\s+CI",
    r"REMATE\s+ANTE\s+JUEZ\s+ARBITRO,?",
    r"REMATE[.,]?\s+VIG[ÉE]SIMO\s+SEGUNDO\s+JUZGADO",
    r"JUEZ\s+PARTIDOR\s+[A-ZÁÉÍÓÚÑ]+",
    r"SEGUNDO\s+REMATE\s+PARTICI[ÓO]N",
    r"ANTE\s+JUEZ\s+PARTIDOR",
    r"INMUEBLE\s+COMUNA\s+QUILL[ÓO]N\.[A-ZÁÉÍÓÚÑ]",
    r"LICITACI[ÓO]N\s+REMATE\.\s+CONVENIO",
    r"CON\s+FECHA\s+.*HORAS",
    r"\d°?\s+JUZGADO\s+DE\s+LETRAS\s+DE\s+SAN\s+B",
    r"ANTE\s+JUEZ\s+[ÁA]RBITRO\s+LIQUIDADOR",
    r"REMATE:\s+SEGUNDO\s+JUZGADO\s+CI",
    r"UNDECIMO\s+JUZGADO\s+CIVIL\s+SAN",
    r"ÁRBITRO\s+PARTIDOR\s+IVÁN\s+MOSCOSO",
    r"(JUEZ|ÁRBITRO)\s+PARTIDOR\s+(DON\s+)?[A-ZÁÉÍÓÚÑ]+(?:\s+[A-ZÁÉÍÓÚÑ]+)*",
    r"(?:\d{1,2}|PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|SÉPTIMO|OCTAVO|NOVENO|DÉCIMO|UNDÉCIMO|DUODÉCIMO)\s+JUZGADO\s+CIVIL(?:\s+[A-ZÁÉÍÓÚÑ]+)?",
    r"(REMATE|LICITACI[ÓO]N\s+REMATE|OFERTA\s+REMATE|VENTA\s+EN\s+REMATE)",
    r"JUEZ\s+[ÁA]RBITRO\s+[A-ZÁÉÍÓÚÑ\s]+",
    r"REMATE\s+ANTE\s+JUEZ\s+PARTIDOR",
    r"VIG[ÉE]SIMO\s+(?:PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO|OCTAVO|NOVENO)\s+JUZGADO\s+CIVIL",
    r"NOTIFICACI[ÓO]N[.:]?\s+VIG[ÉE]SIMO\s+S[ÉE]PTIMO",
    r"\bPARTIDOR\b",
    r"CUARTO\s+REMATE\s+P[ÚU]BLICO[,;]?\s*NUEVO"
]

CLAVES_SEPARADORES_IQQ = [
    r"REMATE",
    r"EXTRACTO",
    r"Extracto",
    r"JUZGADO\s+DE\s+POLIC[ÍI]A\s+LOCAL",
    r"JUZGADO\s+DE\s+LETRAS",
    r"JUEZ\s+ARBITRO",
    r"LICITACI[ÓO]N\s+REMATE",
    r"EN\s+JUICIO\s+PARTICI[ÓO]N",
    r"OFERTA\s+REMATE",
    r"VENTA\s+EN\s+REMATE",
    r"ANTE\s+EL\s+\d{1,2}°?\s+JUZGADO\s+CIVIL",
    r"\d{1,2}°?\s+JUZGADO\s+CIVIL",
    r"VIG[ÉE]SIMO",
    r"D[ÉE]CIMO",
    r"EN\s+CAUSA\s+ROL",
    r"JUEZ\s+PARTIDOR\s+DON\s+[A-ZÁÉÍÓÚÑ]+",
    r"REMATE,\s+ANTE\s+JUEZ\s+PARTIDOR",
    r"REMATE:\s+VIG[ÉE]SIMO\s+JUZGADO\s+CI",
    r"REMATE\s+ANTE\s+JUEZ\s+ARBITRO,?",
    r"REMATE[.,]?\s+VIG[ÉE]SIMO\s+SEGUNDO\s+JUZGADO",
    r"JUEZ\s+PARTIDOR\s+[A-ZÁÉÍÓÚÑ]+",
    r"SEGUNDO\s+REMATE\s+PARTICI[ÓO]N",
    r"ANTE\s+JUEZ\s+PARTIDOR",
    r"INMUEBLE\s+COMUNA\s+QUILL[ÓO]N\.[A-ZÁÉÍÓÚÑ]",
    r"LICITACI[ÓO]N\s+REMATE\.\s+CONVENIO",
    r"CON\s+FECHA\s+.*HORAS",
    r"\d°?\s+JUZGADO\s+DE\s+LETRAS\s+DE\s+SAN\s+B",
    r"ANTE\s+JUEZ\s+[ÁA]RBITRO\s+LIQUIDADOR",
    r"REMATE:\s+SEGUNDO\s+JUZGADO\s+CI",
    r"UNDECIMO\s+JUZGADO\s+CIVIL\s+SAN",
    r"ÁRBITRO\s+PARTIDOR\s+IVÁN\s+MOSCOSO",
    r"(JUEZ|ÁRBITRO)\s+PARTIDOR\s+(DON\s+)?[A-ZÁÉÍÓÚÑ]+(?:\s+[A-ZÁÉÍÓÚÑ]+)*",
    r"(?:\d{1,2}|PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|SÉPTIMO|OCTAVO|NOVENO|DÉCIMO|UNDÉCIMO|DUODÉCIMO)\s+JUZGADO\s+CIVIL(?:\s+[A-ZÁÉÍÓÚÑ]+)?",
    r"(REMATE|LICITACI[ÓO]N\s+REMATE|OFERTA\s+REMATE|VENTA\s+EN\s+REMATE)",
    r"JUEZ\s+[ÁA]RBITRO\s+[A-ZÁÉÍÓÚÑ\s]+",
    r"REMATE\s+ANTE\s+JUEZ\s+PARTIDOR",
    r"VIG[ÉE]SIMO\s+(?:PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO|OCTAVO|NOVENO)\s+JUZGADO\s+CIVIL",
    r"NOTIFICACI[ÓO]N[.:]?\s+VIG[ÉE]SIMO\s+S[ÉE]PTIMO",
    r"\bPARTIDOR\b",
    r"CUARTO\s+REMATE\s+P[ÚU]BLICO[,;]?\s*NUEVO"
]


def recortar_remates(texto: str):
    """
    Versión más explícita de la lógica de recorte.
    """
    patron_inicio = r"1616\s+REMATES\s+DE\s+PROPIEDADES|1616"
    
    # Se añaden los nuevos códigos de fin al patrón, escapando los caracteres especiales [ y ]
    patron_fin = r"(1635\s+PERSONAS\s+BUSCADAS\s+Y\s+COSAS\s+PERDIDAS|1640\s+CITAN\s+A\s+REUNIÓN\s+INSTITUCIONES|\[CODE:1630\]|\[CODE:1635\]|\[CODE:1640\]|\[CODE:1300\]|\[CODE:1309\]|\[CODE:1312\]|\[CODE:1316\])"

    # Buscar patrones
    match_inicio = re.search(patron_inicio, texto, re.IGNORECASE)
    match_fin = re.search(patron_fin, texto, re.IGNORECASE)      
        
    # Casos posibles
    if match_inicio is not None and match_fin is not None:
        # Caso 1: Se encontraron ambos patrones
        pos_inicio = match_inicio.start()
        pos_fin = match_fin.start()
        
        if pos_fin > pos_inicio:
            logger.info("[INFO]✅ - Caso 1: Ambos patrones encontrados, recortando entre ellos.")
            texto_cortado = texto[pos_inicio:pos_fin]
        else:
            logger.warning("[WARN]⚠️ - Caso 1b: Fin antes que inicio, usando desde inicio al final.")
            texto_cortado = texto[pos_inicio:]
            
    elif match_inicio is not None and match_fin is None:
        # Caso 2: Solo se encontró el inicio
        pos_inicio = match_inicio.start()
        logger.warning("[WARN]⚠️ - Caso 2: Solo inicio encontrado, usando desde inicio al final.")
        texto_cortado = texto[pos_inicio:]
        
    elif match_inicio is None and match_fin is not None:
        # Caso 3: Solo se encontró el fin
        pos_fin = match_fin.start()
        logger.warning("[WARN]⚠️ - Caso 3: Solo fin encontrado, usando desde el principio al fin.")
        texto_cortado = texto[:pos_fin]
        
    else:
        # Caso 4: No se encontró ningún patrón
        logger.warning("[WARN]⚠️ - Caso 4: Ningún patrón encontrado, usando todo el texto.")
        texto_cortado = texto
        
    # Logging de información
    logger.info(f"[INFO]📊 - Longitud original: {len(texto)}")
    logger.info(f"[INFO]📊 - Longitud recortado: {len(texto_cortado)}")
    if match_inicio:
        logger.info(f"[INFO] Frase detectada como inicio: '{match_inicio.group()}'")
        logger.info(f"[INFO]📊 - Inicio encontrado en posición: {match_inicio.start()}")
    if match_fin:
        logger.info(f"[INFO]📊 - Fin encontrado en posición: {match_fin.start()}")
        logger.info(f"[INFO] Frase detectada como fin: '{match_fin.group()}'")
        
    # Guardar archivo temporal
    with open("remates_cortados.txt", "w", encoding="utf-8") as f:
        f.write(texto_cortado)

    return texto_cortado

def separador_inteligente(match: re.Match) -> str:
    """
    Reemplaza la fusión detectada de remates por separación segura.
    """
    match_completo = match.group(0)
    grupo_cierre = match.group(1)
    grupo_espacios = match.group(2)
    grupo_inicio = match.group(3)

    if grupo_cierre and grupo_inicio:
        # Evitar doble salto si ya hay salto
        if "\n" in grupo_espacios:
            texto_separado = f"{grupo_cierre}{grupo_espacios}{grupo_inicio}"
        else:
            texto_separado = f"{grupo_cierre}\n\n{grupo_inicio}"
        logger.info(f"Separación exitosa: '{grupo_cierre}' | '{grupo_inicio}'")
        return texto_separado
    else:
        logger.warning(f"Separación fallida. Se recuperó el texto original: '{match_completo}'")
        return match_completo


def pre_separar_remates_fusionados(texto: str, region) -> str:
    """
    Busca patrones de remates fusionados y los separa de forma segura.
    """
    logger.debug(f"Buscando y separando remates fusionados para {region}...")
    if region == "iquique":
        CLAVES_SEPARADORES = CLAVES_SEPARADORES_IQQ
    else:
        CLAVES_SEPARADORES = CLAVES_SEPARADORES
    
    bloque_manual = [
        r"REMATE\b",
        r"REMATE[:.]?",
        r"JUEZ PARTIDOR",
        r"JUEZ ARBITRO",
        r"LICITACI[ÓO]N\s+REMATE",
        r"POR RESOLUCI[ÓO]N\sDEL\s4°\sJUZGADO",
        r"NOTIFICACI[ÓO]N[.:]?\s+VIG[ÉE]SIMO\s+S[ÉE]PTIMO",
        r"\bPARTIDOR\b",
        r"CUARTO\s+REMATE\s+P[ÚU]BLICO[,;]?\s*NUEVO"
    ]

    
    # CLAVES_SEPARADORES debería ser otra lista definida previamente
    todos_los_inicios = bloque_manual + CLAVES_SEPARADORES  

    palabras_cierre = r"\b(?:Secretaría|Secretario\(a\)|La Actuaria|El Actuario)\b"
    patron_email = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    patron_telefono = r'(?:\+56\s?)?[29]\s?\d{4}\s?\d{4}'
    palabras_inicio = r"(?:{})".format("|".join(todos_los_inicios))

    # Patrón final: cierre + espacios + inicio
    patron_fusion = re.compile(
        f"({palabras_cierre}|{patron_telefono}|{patron_email})"  # grupo 1: cierre
        r"(\s+)"                                                # grupo 2: espacios (pueden incluir saltos)
        f"({palabras_inicio})"                                   # grupo 3: inicio
    )

    texto_corregido = patron_fusion.sub(separador_inteligente, texto)
    return texto_corregido


# --- CORRECCIÓN 1: Agregar cancel_event ---
def limpiar_encabezados(texto: str, cancel_event) -> str:
    logger.debug("Eliminando encabezados conocidos...")
    patrones_eliminar = [
        r"---\s+PÁGINA\s+\d+\s+---\s*\n\d+\s*\n",
        r"^(?:LUNES|MARTES|MIÉRCOLES|JUEVES|VIERNES|SÁBADO|DOMINGO)\s+\d{1,2}\s+DE\s+[A-ZÁÉÍÓÚÑ]+\s+DE\s+\d{4}$",
        r"1611\s+JUDICIALES",
        r"1612\s+REMATES",
        r"1616\s+REMATES\s+DE\s+PROPIEDADES",
        r"1635\s+PERSONAS\s+BUSCADAS\s+Y\s+COSAS\s+PERDIDAS",
        r"1640\s+CITAN\s+A\s+REUNIÓN\s+INSTITUCIONES",
        r"\bECONÓMICOS\s+CLASIFICADOS\b",
        r"---\s+Página\s+\d+\s+---",
        r"^\s*\d+\s*$"
        r"^\s*EL\s+MERCURIO\s+DE\s+VALPARA[ÍI]SO\s*$"
    ]
    for patron in patrones_eliminar:
        
        if cancel_event.is_set():
            logger.info("🛑 Proceso cancelado por usuario.")
            return None # Retorna None para abortar
        texto = re.sub(patron, "", texto, flags=re.IGNORECASE | re.MULTILINE)

    patrones_union = [
        (r"(\w+)-\s*\n\s*(\w+)", r"\1\2"),
        (r"([a-zA-Z0-9_.-])\s*\n\s*(@)", r"\1\2"),
        (r"(:)\s*\n\s*([a-zA-Z0-9])", r"\1 \2"),
        (r'\b(N|N°|Nº|Departamento|Depto|Oficina|Of|Bodega|Estacionamiento|Rol|Piso)\s*\n\s*(\d+)', r'\1 \2'),
        (r"(\d)\s*\n\s*([a-z])", r"\1 \2"),
        (r"([a-z0-9,])\s*\n\s*([A-Z][a-z])", r"\1 \2")
    ]
    for patron, reemplazo in patrones_union:
        
        if cancel_event.is_set():
            logger.info("🛑 Proceso cancelado por usuario.")
            return None
        texto = re.sub(patron, reemplazo, texto, flags=re.IGNORECASE)
    
    return texto


def insertar_separadores(texto: str, region) -> str:
    logger.debug("Insertando separadores entre avisos...")
    if region == "iquique":
        CLAVES_SEPARADORES = CLAVES_SEPARADORES_IQQ
    else:
        CLAVES_SEPARADORES = CLAVES_SEPARADORES

    patron_frases = "|".join(CLAVES_SEPARADORES)
    patron_separador = rf"""
        \n
        (?=
            \s*
            (?:{patron_frases})
            (?:\s+[A-ZÁÉÍÓÚÑ\d]+)*
        )
    """
    return re.sub(patron_separador, "\n\n", texto, flags=re.MULTILINE | re.VERBOSE)

def limpieza(texto: str) -> str:
    logger.debug("[LIMPIEZA] - Eliminando líneas vacías múltiples y códigos...")

    # 1. Eliminar códigos específicos
    texto = re.sub(r'\[CODE:1616\]', '', texto)
    texto = re.sub(r'\[CODE:1612\]', '', texto)
    texto = re.sub(r'\[CODE:', '', texto)
    texto = re.sub(r'\[CODE:', '', texto)
    texto = re.sub(r'1616\]', '', texto)
    
    # 2. Compactar saltos de línea excesivos
    texto = re.sub(r"\n\s*\n+", "\n\n", texto)
    # 3. Unificar puntos suspensivos
    texto = re.sub(r"\s*\.\.\s*", " ", texto)
    # 4. Normalizar espacios múltiples
    texto = re.sub(r"\s{2,}", " ", texto)
    # 5. Corregir espacios antes de signos de puntuación
    texto = re.sub(r"\s+([,.;:])", r"\1", texto)
    # 7. Normalizar horas con espacios
    texto = re.sub(r"(\d{1,2}):\s*(\d{2})", r"\1:\2", texto)
    # 8. Corregir formato de montos en pesos
    texto = re.sub(r"\$\s*([\d\.]+)\s*-\s*", r"$\1", texto)
    texto = re.sub(r"\s{2,}", " ", texto)

    return texto


# --- CORRECCIÓN 2: Agregar cancel_event ---
def extraer_parrafos_remates(texto: str, cancel_event) -> List[str]:
    logger.debug("Extrayendo párrafos de remates...")
    parrafos_brutos = texto.split('\n\n')
    parrafos_limpios = []
    for p in parrafos_brutos:
        
        if cancel_event.is_set():
            logger.info("🛑 Proceso cancelado por usuario.")
            return None
        parrafo_procesado = " ".join(p.strip().splitlines())
        if parrafo_procesado:
            parrafos_limpios.append(parrafo_procesado)
    return parrafos_limpios

def limpiar_encabezados_y_guardar(
    cancel_event,
    region,
    input_path: str,
    output_path: str = "remates_limpio.txt"
) -> str:
    logger.info(f"Iniciando limpieza de encabezados para: {input_path} para {region}")
    with open(input_path, "r", encoding="utf-8") as f:
        texto = f.read()
    
    texto_cortado = recortar_remates(texto) 
    region = region
    # CORRECCIÓN: Pasar cancel_event
    texto_limpio = limpiar_encabezados(texto_cortado, cancel_event)
    if texto_limpio is None: return None # Check de cancelación

    texto_clean = limpieza(texto_limpio)
    texto_pre_separado = pre_separar_remates_fusionados(texto_clean, region)
    texto_final = insertar_separadores(texto_pre_separado, region)
    #texto_final = limpieza(texto_separado) 

    if output_path:
        logger.info("Limpieza terminada")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(texto_final)
            
        preview_archivos.mostrar_preview_html(output_path, cancel_event)
        
        if cancel_event.is_set():
            logger.info("🛑 Proceso cancelado por usuario.")
            return None
        
        logger.info(f"✅ Texto limpio y separado guardado en: {output_path}")

        with open(output_path, "r", encoding="utf-8") as f:
            texto_modificado = f.read()
        
    return texto_modificado

# ==========================================
# 🔍 NUEVA FUNCIÓN DE FILTRADO (Autos vs Casas)
# ==========================================
# --- CORRECCIÓN 3: Agregar cancel_event ---
def filtrar_remates_inmuebles(lista_remates: List[dict], cancel_event) -> tuple[List[dict], List[dict]]:
    """
    Recorre la lista de remates y separa los que contienen palabras clave de inmuebles
    de los que no (posibles autos, muebles, etc.).
    """
    validos = []     # Casas, deptos, terrenos...
    descartados = [] # Autos, camiones, otros...

    logger.info("🕵️ Filtrando remates por tipo de bien (Inmuebles vs Otros)...")
    
    for item in lista_remates:
        
        if cancel_event.is_set():
            logger.info("🛑 Proceso cancelado por usuario.")
            return None, None
        texto = item['remate'].upper()
        
        # Estrategia LISTA BLANCA:
        # Si contiene AL MENOS UNA palabra clave de inmueble, se queda.
        # Si no tiene ninguna, se descarta (probablemente es auto o mueble).
        es_inmueble = False
        for kw in KEYWORDS_INMUEBLES:
            if cancel_event.is_set():
                return None, None
            # Buscamos la palabra completa o parte de ella (ej: DEPARTAMENTO)
            if kw in texto:
                es_inmueble = True
                break
        
        if es_inmueble:
            validos.append(item)
        else:
            descartados.append(item)

    logger.info(f"📊 Resultado Filtrado: {len(validos)} Inmuebles válidos | {len(descartados)} Descartados (No inmuebles)")
    return validos, descartados

def procesar_remates(cancel_event, region, input_path: str, archivo_final: str = "remates_separados.json") -> str:
    logger.info(f"Procesando archivo de remates: {input_path} para {region}")
    
    # 1. Limpieza y Texto Plano
    texto_limpio = limpiar_encabezados_y_guardar(cancel_event,region, input_path, output_path="remates_limpio.txt")
    if cancel_event.is_set() or texto_limpio is None:
        return None
    
    # 2. Extracción de Párrafos
    parrafos = extraer_parrafos_remates(texto_limpio, cancel_event)
    if cancel_event.is_set() or parrafos is None:
        return None

    logger.info(f"Se han detectado {len(parrafos)} bloques de texto.")
    
    # 3. Creación de lista cruda
    lista_cruda = [{"id_remate": i, "remate": p.strip()} for i, p in enumerate(parrafos, 1)]
    
    # 4. FILTRADO (NUEVO)
    resultado_filtrado = filtrar_remates_inmuebles(lista_cruda, cancel_event)
    if resultado_filtrado is None or resultado_filtrado[0] is None:
        return None
    
    lista_validos, lista_descartados = resultado_filtrado
    
    if cancel_event.is_set():
        return None
    
    logger.info("👀 Abriendo ventana de revisión humana...")
    
    # Llamamos a la ventana bloqueante
    lista_validos_final, lista_descartados_final = revision.mostrar_revision(
        lista_validos, 
        lista_descartados, 
        cancel_event
    )

    if cancel_event.is_set():
        logger.warning("🛑 Proceso cancelado durante la revisión humana.")
        return None
        
    logger.info(f"👌 Revisión completada. Final: {len(lista_validos_final)} Válidos | {len(lista_descartados_final)} Descartados.")
    
    # 5. Guardado de Archivos
    # A) JSON VÁLIDO (Inmuebles) -> Este sigue al Paso 3 (IA)
    with open(archivo_final, "w", encoding="utf-8") as f:
        json.dump(lista_validos_final, f, indent=4, ensure_ascii=False)
    
    # B) JSON DESCARTADO (Autos, etc) -> Se guarda por si acaso, pero no se procesa
    archivo_descarte = archivo_final.replace(".json", "_descartados.json")
    with open(archivo_descarte, "w", encoding="utf-8") as f:
        json.dump(lista_descartados_final, f, indent=4, ensure_ascii=False)
        logger.info(f"🗑️ Remates descartados guardados en: {archivo_descarte}")

    # Preview HTML del válido
    preview_archivos.mostrar_preview_html(archivo_final, cancel_event)
    
    logger.info(f"✅ Archivo final (INMUEBLES) guardado en: {archivo_final}")
    return archivo_final

if __name__ == "__main__":
    # Dummy run
    import threading
    procesar_remates(threading.Event(), "remates_extraidos.txt")