import os
import json
import shutil
import uuid
from datetime import datetime

# Importamos los módulos de lógica
from housePrincing import paso1_hp, paso2_hp, paso3_hp
from logger import get_logger

# --- CONFIGURACIÓN ---
CARPETA_PDFS = "./input_pdfs"
OUTPUT_FOLDER = "house_pricing_outputs"

# Archivos temporales
TEMP_JSON_PASO1 = "temp_paso1.json"
TEMP_JSON_FINAL = "temp_final.json"
TEMP_EXCEL = "temp_reporte.xlsx"

ENABLE_CLEANUP = True 

logger = get_logger("main_hp", log_dir="logs", log_file="main_hp.log")

# CORRECCIÓN: Agregar cancel_event
def cleanup_temp_files(cancel_event):
    if not ENABLE_CLEANUP:
        logger.info("ℹ️ Limpieza de archivos desactivada (modo debug).")
        return

    archivos_a_eliminar = [TEMP_JSON_PASO1]
    
    logger.info("🧹 Ejecutando limpieza de archivos temporales...")
    for archivo in archivos_a_eliminar:
        
        if cancel_event.is_set():
            logger.info("🛑 Proceso cancelado por usuario.")
            return
        try:
            if os.path.exists(archivo):
                os.remove(archivo)
                logger.info(f"   -> Eliminado: {archivo}")
        except Exception as e:
            logger.warning(f"   ⚠️ No se pudo eliminar {archivo}: {e}")

# CORRECCIÓN: Agregar cancel_event
def main(cancel_event):
    logger.info("=== INICIO DEL FLUJO DE TASACIÓN ===")

    # ------------------------------------------------------------------
    # PASO 1: Procesar PDFs
    # ------------------------------------------------------------------
    if cancel_event.is_set(): return

    logger.info(">>> EJECUTANDO PASO 1: Extracción masiva de PDFs...")
    
    # Se pasa cancel_event (ya estaba en paso1_hp)
    json_propiedades = paso1_hp.procesar_lote_pdfs(CARPETA_PDFS, cancel_event)    

    if not json_propiedades:
        if cancel_event.is_set():
            logger.warning("Proceso cancelado en Paso 1.")
        else:
            logger.error("❌ No se generó ningún JSON válido en el Paso 1. Abortando.")
        return

    logger.info(f"✅ Paso 1 completado. {len(json_propiedades)} propiedades extraídas.")
    
    with open(TEMP_JSON_PASO1, "w", encoding="utf-8") as f:
        json.dump(json_propiedades, f, indent=4, ensure_ascii=False)

    # ------------------------------------------------------------------
    # PASO 2: Búsqueda Selenium
    # ------------------------------------------------------------------
    if cancel_event.is_set(): return

    logger.info(">>> EJECUTANDO PASO 2: Búsqueda de mercado (Selenium)...")
    
    # CORRECCIÓN: Pasar cancel_event a paso2_hp
    json_enriquecido = paso2_hp.procesar_lista_propiedades(json_propiedades, cancel_event)

    if cancel_event.is_set() or not json_enriquecido:
        logger.warning("Paso 2 cancelado o sin resultados.")
        return

    logger.info(f"✅ Paso 2 completado. Datos enriquecidos con comparables.")

    with open(TEMP_JSON_FINAL, "w", encoding="utf-8") as f:
        json.dump(json_enriquecido, f, indent=4, ensure_ascii=False)

    # ------------------------------------------------------------------
    # PASO 3: Generar Excel
    # ------------------------------------------------------------------
    if cancel_event.is_set(): return

    logger.info(">>> EJECUTANDO PASO 3: Generación de Excel...")
    
    # CORRECCIÓN: Pasar cancel_event a paso3_hp
    exito_excel = paso3_hp.generar_excel(json_enriquecido, cancel_event, TEMP_EXCEL)
    
    if exito_excel:
        logger.info(">>> FINALIZANDO: Moviendo archivos y limpieza...")
        
        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)

        fecha_str = datetime.now().strftime("%Y-%m-%d")
        uuid_str = uuid.uuid4().hex[:6]
        base_name = f"Reporte_HousePricing_{fecha_str}_{uuid_str}"

        ruta_final_json = os.path.join(OUTPUT_FOLDER, f"{base_name}.json")
        ruta_final_excel = os.path.join(OUTPUT_FOLDER, f"{base_name}.xlsx")

        try:
            if os.path.exists(TEMP_EXCEL):
                shutil.move(TEMP_EXCEL, ruta_final_excel)
                logger.info(f"📂 Excel guardado en: {ruta_final_excel}")
            
            if os.path.exists(TEMP_JSON_FINAL):
                shutil.move(TEMP_JSON_FINAL, ruta_final_json)
                logger.info(f"📂 JSON Raw guardado en: {ruta_final_json}")

            # CORRECCIÓN: Pasar cancel_event
            cleanup_temp_files(cancel_event)

            logger.info("🎉 === PROCESO FINALIZADO CON ÉXITO === 🎉")
            
            try:
                os.startfile(ruta_final_excel)
            except:
                pass

        except Exception as e:
            logger.error(f"❌ Error moviendo archivos finales: {e}")

    else:
        if cancel_event.is_set():
            logger.warning("Proceso cancelado en Paso 3.")
        else:
            logger.error("❌ El Paso 3 falló generando el Excel. Revisa los logs.")

if __name__ == "__main__":
    if not os.path.exists(CARPETA_PDFS):
        os.makedirs(CARPETA_PDFS)
    else:
        import threading
        main(threading.Event())