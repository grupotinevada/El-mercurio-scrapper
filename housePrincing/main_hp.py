import os
import json


# Importamos los módulos de lógica
from housePrincing import paso1_hp, paso2_hp




# Configuración
CARPETA_PDFS = "./input_pdfs"
ARCHIVO_INTERMEDIO = "data_paso1.json"
ARCHIVO_FINAL = "reporte_final_housepricing.json"

from logger import get_logger, log_section, dbg

logger = get_logger("main_hp", log_dir="logs", log_file="main_hp.log")

def main():
    logger.info("=== INICIO DEL FLUJO DE TASACIÓN ===")

    # ------------------------------------------------------------------
    # PASO 1: Procesar PDFs -> Generar JSON Estandarizado
    # ------------------------------------------------------------------
    logger.info(">>> EJECUTANDO PASO 1: Extracción masiva de PDFs...")
    
    # Esta función ahora devuelve la LISTA COMPLETA de propiedades (JSON)
    json_propiedades = paso1_hp.procesar_lote_pdfs(CARPETA_PDFS)    

    if not json_propiedades:
        logger.error("No se generó ningún JSON válido en el Paso 1. Abortando.")
        return

    logger.info(f"Paso 1 completado. {len(json_propiedades)} propiedades extraídas.")
    
    # (Opcional) Guardar snapshot del Paso 1
    with open(ARCHIVO_INTERMEDIO, "w", encoding="utf-8") as f:
        json.dump(json_propiedades, f, indent=4, ensure_ascii=False)

    # ------------------------------------------------------------------
    # PASO 2: Recorrer JSON -> Buscar Comparables y Anexar
    # ------------------------------------------------------------------
    logger.info(">>> EJECUTANDO PASO 2: Búsqueda de mercado (Selenium)...")
    
    # Aquí pasamos la LISTA COMPLETA al Paso 2, tal como pediste.
    # El Paso 2 es responsable de iterar, buscar y devolver la lista actualizada.
    json_enriquecido = paso2_hp.procesar_lista_propiedades(json_propiedades)

    logger.info(f"Paso 2 completado. Datos enriquecidos con comparables.")

    # ------------------------------------------------------------------
    # PASO 3 (Futuro): Generar Excel
    # ------------------------------------------------------------------
    # log.info(">>> EJECUTANDO PASO 3: Generación de Excel...")
    # paso3_hp.generar_excel(json_enriquecido)
    
    # Por ahora guardamos el JSON final
    with open(ARCHIVO_FINAL, "w", encoding="utf-8") as f:
        json.dump(json_enriquecido, f, indent=4, ensure_ascii=False)
    
    logger.info(f"=== PROCESO FINALIZADO. Resultados en {ARCHIVO_FINAL} ===")

if __name__ == "__main__":
    # Crear carpeta de inputs si no existe
    if not os.path.exists(CARPETA_PDFS):
        os.makedirs(CARPETA_PDFS)
        logger.warning(f"Carpeta '{CARPETA_PDFS}' creada. Coloca tus PDFs ahí.")
    else:
        main()