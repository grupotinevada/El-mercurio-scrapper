import re
import json
from typing import List
import preview_archivos
# --- Configuración de logger ---
from logger import get_logger, log_section, dbg

logger = get_logger("paso2", log_dir="logs", log_file="paso2.log")

#ambas funciones pueden usar las mismas claves:
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
    # Patrón específico para el caso del ID 72 y 78
    r"JUEZ\s+PARTIDOR\s+[A-ZÁÉÍÓÚÑ]+",
    
]


def recortar_remates(texto: str):
    """
    Encuentra el bloque de texto que va desde el encabezado
    "1616 Remates de Propiedades" hasta justo antes de
    "1635 Personas buscadas y cosas perdidas".
    """
    patron_inicio = r"1616\s+REMATES\s+DE\s+PROPIEDADES"
    patron_fin = r"1635\s+PERSONAS\s+BUSCADAS\s+Y\s+COSAS\s+PERDIDAS"

    # Buscar inicio
    match_inicio = re.search(patron_inicio, texto, re.IGNORECASE)
    if not match_inicio:
        logger.error("[ERROR]❌ - No se encontró el encabezado de remates en el texto.")
        return ""

    pos_inicio = match_inicio.start()

    # Buscar fin (después del inicio)
    match_fin = re.search(patron_fin, texto[pos_inicio:], re.IGNORECASE)
    if not match_fin:
        logger.warning("[WARN]⚠️ - No se encontró el encabezado de fin, se usará todo el texto desde el inicio.")
        texto_cortado = texto[pos_inicio:]
    else:
        pos_fin = match_fin.start()
        texto_cortado = texto[pos_inicio:pos_inicio + pos_fin]

    # --- Parte temporal: guarda archivo ---
    with open("remates_cortados.txt", "w", encoding="utf-8") as f:
        f.write(texto_cortado)
    # --------------------------------------

    return texto_cortado

import re

def separador_inteligente(match: re.Match) -> str:
    """
    Esta función se ejecuta para CADA fusión encontrada.
    Decide cómo reemplazar el texto de forma segura.
    """
    # 1. RESCATAR LA INFORMACIÓN
    # Capturamos todas las piezas del texto que coincidió con el patrón.
    match_completo = match.group(0)  # El texto completo original (ej: "Secretaría REMATE")
    print("match",match_completo)
    grupo_cierre = match.group(1)    # El final del primer remate
    print("match",grupo_cierre)
    grupo_inicio = match.group(4)    # El inicio del segundo remate
    print("match",grupo_inicio)

    # 2. VERIFICAR QUE TODO CUMPLA
    # La condición es simple: ¿encontramos tanto el cierre como el inicio?
    if grupo_cierre and grupo_inicio:
        # Si la verificación es exitosa, aplicamos la separación.
        texto_separado = f"{grupo_cierre}\n\n{grupo_inicio}"
        logger.info(f"Separación exitosa: '{grupo_cierre}' | '{grupo_inicio}'")
        return texto_separado
    else:
        # 3. RECUPERAR SI ES NECESARIO
        # Si la verificación falla, no hacemos nada y devolvemos el texto original.
        # Aquí se incrusta la "palabra rescatada" (el texto completo) sin cambios.
        logger.warning(f"Separación fallida. Se recuperó el texto original: '{match_completo}'")
        return match_completo

# Suponiendo que 'logger' está configurado
def pre_separar_remates_fusionados(texto: str) -> str:
    """
    Busca patrones de remates fusionados y utiliza una función de reemplazo
    para separarlos de forma segura.
    """
    logger.debug("Buscando y separando remates fusionados (lógica básica)...")

    palabras_cierre = r"\b(Secretaría|Secretario\(a\)|La Actuaria|El Actuario)\b"
    patron_email = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    patron_telefono = r'(?:\+56\s?)?[29]\s?\d{4}\s?\d{4}'
    palabras_inicio = r"(?:REMATE\b|REMATE[:.]?|JUEZ PARTIDOR|JUEZ ARBITRO)"


    patron_fusion = re.compile(
        f"({palabras_cierre}|{patron_telefono}|{patron_email})"  
        r"(\s+)"                                                 
        f"({palabras_inicio})",                                   
        flags=re.IGNORECASE
    )
    
    # En lugar de un texto de reemplazo, pasamos la FUNCIÓN 'separador_inteligente'.
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

def limpiar_lineas_vacias(texto: str) -> str:
    logger.debug("Eliminando líneas vacías múltiples...")
    return re.sub(r"\n\s*\n+", "\n\n", texto).strip()


def es_encabezado(linea: str) -> bool:
    palabras = linea.strip().split()
    if len(palabras) < 3:
        return False
    mayusculas = sum(1 for c in linea if c.isupper() or c in "ÁÉÍÓÚÑÜ")
    total = sum(1 for c in linea if c.isalpha())
    return total > 0 and (mayusculas / total) > 0.8


def es_encabezado(linea: str) -> bool:
    palabras = linea.strip().split()
    if len(palabras) < 3:
        return False
    mayusculas = sum(1 for c in linea if c.isupper() or c in "ÁÉÍÓÚÑÜ")
    total = sum(1 for c in linea if c.isalpha())
    return total > 0 and (mayusculas / total) > 0.8


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
    texto_pre_separado = pre_separar_remates_fusionados(texto_limpio)
    texto_separado = insertar_separadores(texto_pre_separado)
    texto_final = limpiar_lineas_vacias(texto_separado) 

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
