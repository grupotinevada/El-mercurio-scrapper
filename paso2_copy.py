import re
import json
from typing import List

# --- Configuración de logger ---
from logger import get_logger, log_section, dbg

logger = get_logger("paso2", log_dir="logs", log_file="paso2.log")


def recortar_remates(texto: str):
    patron = "1616"

    pos = texto.find(patron)
    if pos != -1:
        texto_cortado = texto[pos:]
        
        # --- Parte temporal: guarda archivo (puedes borrar estas 3 líneas cuando no lo necesites) ---
        with open("remates_cortados.txt", "w", encoding="utf-8") as f:
            f.write(texto_cortado)
        # --------------------------------------------------------------------------------------------
        
        return texto_cortado
    else:
        print("[ERROR]❌ - No se encontró el patrón en el archivo.")
        return ""

def limpiar_encabezados_y_guardar(
    input_path: str,
    output_path: str = "remates_limpio.txt"
) -> str:
    logger.info(f"Iniciando limpieza de encabezados para: {input_path}")
    with open(input_path, "r", encoding="utf-8") as f:
        texto = f.read()
        
    texto_cortado = recortar_remates(texto) 
    texto_limpio = limpiar_encabezados(texto_cortado)
    texto_limpio = insertar_separadores(texto_limpio)
    texto_limpio = limpiar_lineas_vacias(texto_limpio)

    if output_path:
        logger.info("Vista previa del texto limpio (primeros 1000 caracteres):")
        logger.info("\n" + texto_limpio[:1000])
        input("\n🔍 Revisa el archivo, haz cambios si es necesario, y presiona Enter para continuar...")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(texto_limpio)
        logger.info(f"✅ Texto limpio y separado guardado en: {output_path}")

    return texto_limpio


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
    claves = [
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
    ]
    patron_frases = "|".join(claves)
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


def extraer_parrafos_remates(texto: str) -> List[str]:
    logger.debug("Extrayendo párrafos de remates...")
    parrafos_brutos = texto.split('\n\n')
    parrafos_limpios = []
    for p in parrafos_brutos:
        parrafo_procesado = " ".join(p.strip().splitlines())
        if parrafo_procesado:
            parrafos_limpios.append(parrafo_procesado)
    return parrafos_limpios


def procesar_remates(input_path: str, archivo_final: str = "remates_separados.json") -> None:
    #input_path "remates_extraidos.txt" ruta del procesar_remates("remates_extraidos.txt")
    logger.info(f"Procesando archivo de remates: {input_path}")
    texto_limpio = limpiar_encabezados_y_guardar(input_path, output_path="remates_limpio.txt")

    parrafos = extraer_parrafos_remates(texto_limpio)
    logger.info(f"Se han detectado {len(parrafos)} remates.")

    lista_remates = [{"id_remate": i, "remate": p.strip()} for i, p in enumerate(parrafos, 1)]
           
    logger.info("Vista previa del JSON (primeros 2 remates):")
    logger.info("\n" + json.dumps(lista_remates[:2], indent=4, ensure_ascii=False))
    input("\n🔍 Revisa el JSON, haz cambios si es necesario, y presiona Enter para continuar...")

    with open(archivo_final, "w", encoding="utf-8") as f:
        json.dump(lista_remates, f, indent=4, ensure_ascii=False)

    logger.info(f"✅ Archivo final en formato JSON guardado en: {archivo_final}")
    return archivo_final


if __name__ == "__main__":
    ruta_generada = procesar_remates("remates_extraidos.txt")
    logger.info(f"Prueba finalizada. Ruta del archivo generado: {ruta_generada}")
