import paso1_copy
import paso2_copy
import paso3_copy
import os
import uuid
from datetime import datetime

# --- Configuración del logger centralizado ---
from logger import get_logger
def orquestador_con_datos(url, paginas, usuario, password,cancel_event):
    logger = get_logger("orquestador", log_dir="logs", log_file="orquestador.log")

    logger.info("===== INICIO DEL PROCESO =====")
    print("Datos recibidos:")
    print(f"URL: {url}")
    print(f"Número de páginas: {paginas}")
    print(f"Usuario: {usuario}")
    print(f"Password: {password}")
    logger.info("===== FIN DEL PROCESO =====\n")


    try:
        # --- PASO 1: Extracción Web ---
        logger.info("=" * 20 + " INICIANDO PASO 1: EXTRACCIÓN WEB " + "=" * 20)
        ruta_txt_bruto = paso1_copy.run_extractor(url, paginas, usuario, password)
                
        if not ruta_txt_bruto:
            logger.error("PASO 1 FALLÓ - No se generó archivo TXT. Abortando.")
            return
        else:
            logger.info(f"PASO 1 completado. Archivo generado: {ruta_txt_bruto}")

            # --- PASO 2: Limpieza y Separación ---
            logger.info("=" * 20 + " INICIANDO PASO 2: LIMPIEZA DE TEXTO " + "=" * 20)
            ruta_json_separado = paso2_copy.procesar_remates(cancel_event, ruta_txt_bruto)
            
            if cancel_event.is_set():
                logger.warning("Proceso cancelado por el usuario durante el paso 2.")
                return # Termina la ejecución
            
            if not ruta_json_separado:
                logger.error("PASO 2 FALLÓ - No se generó archivo JSON separado. Abortando.")
                return
            else:
                logger.info(f"PASO 2 completado. Archivo generado: {ruta_json_separado}")

                # --- PASO 3: Procesamiento con IA ---
                logger.info("=" * 20 + " INICIANDO PASO 3: EXTRACCIÓN CON IA " + "=" * 20)
                ruta_json_final, ruta_excel_final = paso3_copy.run_processor(cancel_event, ruta_json_separado)
                
                if cancel_event.is_set():
                    logger.warning("Proceso cancelado por el usuario durante el paso 3.")
                    return # Termina la ejecución
                
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
                    for tmp_file in [ruta_txt_bruto, ruta_json_separado]:
                        try:
                            if os.path.exists(tmp_file):
                                os.remove(tmp_file)
                                logger.info(f"Archivo temporal eliminado: {tmp_file}")
                        except Exception as e:
                            logger.warning(f"No se pudo eliminar {tmp_file}: {e}")

                    logger.info(f"PASO 3 completado.")
                    logger.info(f"Archivos finales guardados en 'outputs':\n  - {nuevo_json}\n  - {nuevo_excel}")
                    logger.info("🎉 ¡PROCESO FINALIZADO CON ÉXITO! 🎉")
                else:
                    logger.error("PASO 3 FALLÓ - No se generaron archivos finales")
                    return

    except Exception as e:
        logger.exception(f"Error inesperado en el orquestador: {e}")

    logger.info("===== FIN DEL PROCESO =====\n")
# --- Bloque para mantener funcionalidad CLI ---
if __name__ == "__main__":
    # Esto permite ejecutar main.py directamente como antes
    orquestador_con_datos(
        url="http://ejemplo.com",
        paginas=2,
        usuario="usuario_prueba",
        password="pass123"
    )