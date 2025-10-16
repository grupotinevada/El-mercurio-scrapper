import re
import json
from typing import List
import preview_archivos
# --- Configuración de logger ---
from logger import get_logger, log_section, dbg

logger = get_logger("paso2", log_dir="logs", log_file="paso2.log")

#ambas funciones pueden usar las mismas claves:
CLAVES_SEPARADORES = [
    # --- Patrones Originales ---
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
    r"VIG[ÉE]SIMO\s+(?:PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[ÉE]PTIMO|OCTAVO|NOVENO)\s+JUZGADO\s+CIVIL"
]


def recortar_remates(texto: str):
    """
    Versión más explícita de la lógica de recorte.
    """
    patron_inicio = r"1616\s+REMATES\s+DE\s+PROPIEDADES|1616"
    
    # --- LÍNEA MODIFICADA ---
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

import re

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


def pre_separar_remates_fusionados(texto: str) -> str:
    """
    Busca patrones de remates fusionados y los separa de forma segura.
    """
    logger.debug("Buscando y separando remates fusionados...")

    bloque_manual = [
        r"REMATE\b",
        r"REMATE[:.]?",
        r"JUEZ PARTIDOR",
        r"JUEZ ARBITRO",
        r"LICITACI[ÓO]N\s+REMATE"
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




def limpiar_encabezados(texto: str) -> str:
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
    ]
    for patron in patrones_eliminar:
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
        texto = re.sub(patron, reemplazo, texto, flags=re.IGNORECASE)
    
    

    return texto


def insertar_separadores(texto: str) -> str:
    logger.debug("Insertando separadores entre avisos...")
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




def extraer_parrafos_remates(texto: str) -> List[str]:
    logger.debug("Extrayendo párrafos de remates...")
    parrafos_brutos = texto.split('\n\n')
    parrafos_limpios = []
    for p in parrafos_brutos:
        parrafo_procesado = " ".join(p.strip().splitlines())
        if parrafo_procesado:
            parrafos_limpios.append(parrafo_procesado)
    return parrafos_limpios

def limpiar_encabezados_y_guardar(
    cancel_event,
    input_path: str,
    output_path: str = "remates_limpio.txt"
) -> str:
    logger.info(f"Iniciando limpieza de encabezados para: {input_path}")
    with open(input_path, "r", encoding="utf-8") as f:
        texto = f.read()
        
    texto_cortado = recortar_remates(texto) 
    texto_limpio = limpiar_encabezados(texto_cortado)
    texto_clean = limpieza(texto_limpio)
    texto_pre_separado = pre_separar_remates_fusionados(texto_clean)
    
    texto_final = insertar_separadores(texto_pre_separado)
    #texto_final = limpieza(texto_separado) 

    if output_path:
        logger.info("Limpieza terminada")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(texto_final)
            
        preview_archivos.mostrar_preview_html(output_path, cancel_event)
        
        if cancel_event.is_set():
            return None
        
        logger.info(f"✅ Texto limpio y separado guardado en: {output_path}")

        with open(output_path, "r", encoding="utf-8") as f:
            texto_modificado = f.read()
        
    return texto_modificado

def procesar_remates(cancel_event, input_path: str, archivo_final: str = "remates_separados.json") -> None:
    logger.info(f"Procesando archivo de remates: {input_path}")
    
    # Limpieza de encabezados y guardado
    texto_limpio = limpiar_encabezados_y_guardar(cancel_event, input_path, output_path="remates_limpio.txt")
    if cancel_event.is_set() or texto_limpio is None:
        logger.warning("🛑 Proceso cancelado por el usuario antes de extraer párrafos.")
        return None
    
    # Extraer párrafos
    parrafos = extraer_parrafos_remates(texto_limpio)
    if cancel_event.is_set():
        logger.warning("🛑 Proceso cancelado por el usuario durante la extracción de párrafos.")
        return None

    logger.info(f"Se han detectado {len(parrafos)} remates.")
    
    lista_remates = [{"id_remate": i, "remate": p.strip()} for i, p in enumerate(parrafos, 1)]
    logger.info("Vista previa del JSON (primeros 2 remates):")
    logger.info("\n" + json.dumps(lista_remates[:2], indent=4, ensure_ascii=False))
    
    if cancel_event.is_set():
        logger.warning("🛑 Proceso cancelado por el usuario antes de guardar JSON.")
        return None
    
    # Guardar JSON final
    with open(archivo_final, "w", encoding="utf-8") as f:
        json.dump(lista_remates, f, indent=4, ensure_ascii=False)
    
    preview_archivos.mostrar_preview_html(archivo_final, cancel_event)
    if cancel_event.is_set():
        logger.warning("🛑 Proceso cancelado por el usuario después de generar el archivo final.")
        return None
    
    logger.info(f"✅ Archivo final en formato JSON guardado en: {archivo_final}")
    return archivo_final

if __name__ == "__main__":
    ruta_generada = procesar_remates("remates_extraidos.txt")
    logger.info(f"Prueba finalizada. Ruta del archivo generado: {ruta_generada}")
