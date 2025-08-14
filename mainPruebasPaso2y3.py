import paso2_copy
import paso3_copy
import os
import uuid
from datetime import datetime
import time

# --- Configuración del logger centralizado ---
from logger import get_logger
logger = get_logger("orquestador_test", log_dir="logs", log_file="orquestador_test.log")

logger.info("===== INICIO DEL PROCESO (PRUEBA PASO 2 → PASO 3) =====")
start_time = time.time()  # <-- Inicio del timer
try:
    # --- PASO 2: Limpieza y Separación ---
    # Cambia esta ruta al TXT que quieres usar para pruebas
    ruta_txt_bruto = "tests/remates_prueba.txt"
    
    if not os.path.exists(ruta_txt_bruto):
        logger.error(f"No se encontró el archivo de prueba: {ruta_txt_bruto}")
    else:
        logger.info(f"Usando archivo de prueba: {ruta_txt_bruto}")
        ruta_json_separado = paso2_copy.procesar_remates(ruta_txt_bruto)

        if not ruta_json_separado:
            logger.error("PASO 2 FALLÓ - No se generó archivo JSON separado. Abortando.")
        else:
            logger.info(f"PASO 2 completado. Archivo generado: {ruta_json_separado}")

            # --- PASO 3: Procesamiento con IA ---
            ruta_json_final, ruta_excel_final = paso3_copy.run_processor(ruta_json_separado)

            if ruta_json_final and ruta_excel_final:
                os.makedirs("outputs", exist_ok=True)

                # Generar nombre único
                fecha_str = datetime.now().strftime("%d-%m-%Y")
                uuid_str = uuid.uuid4().hex[:6]
                base_name = f"remates_dia_{fecha_str}-{uuid_str}"

                nuevo_json = os.path.join("outputs", f"{base_name}.json")
                nuevo_excel = os.path.join("outputs", f"{base_name}.xlsx")

                os.rename(ruta_json_final, nuevo_json)
                os.rename(ruta_excel_final, nuevo_excel)

                # Eliminar temporales
                try:
                    if os.path.exists(ruta_json_separado):
                        os.remove(ruta_json_separado)
                        logger.info(f"Archivo temporal eliminado: {ruta_json_separado}")
                except Exception as e:
                    logger.warning(f"No se pudo eliminar {ruta_json_separado}: {e}")
                elapsed_time = time.time() - start_time  # <-- Tiempo total
                logger.info(f"PASO 3 completado.")
                logger.info(f"Archivos finales guardados en 'outputs':\n  - {nuevo_json}\n  - {nuevo_excel}")
                logger.info(f"🎉 ¡PROCESO FINALIZADO CON ÉXITO! Tiempo total: {elapsed_time:.2f} segundos 🎉")
            else:
                logger.error("PASO 3 FALLÓ - No se generaron archivos finales")

except Exception as e:
    logger.exception(f"Error inesperado en el orquestador de prueba: {e}")

logger.info("===== FIN DEL PROCESO DE PRUEBA =====\n")
