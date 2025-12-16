import paso1_copy
import paso2_copy
import paso3_copy
# import paso1_valpo  # <-- Descomenta esto cuando crees el archivo para Valparaíso
# import paso2_valpo  # <-- Descomenta esto cuando crees el archivo para Valparaíso

import os
import uuid
from datetime import datetime
from logger import get_logger

# --- Bloque para limpieza de archivos finales ---
def cleanup_temp_files(logger, enable_cleanup: bool = True):
    """
    Elimina archivos temporales generados durante el proceso.
    Se puede desactivar con enable_cleanup=False (para desarrollo).
    """
    if not enable_cleanup:
        logger.info("Limpieza de archivos desactivada (modo desarrollo).")
        return

    archivos_a_eliminar = [
        "remates_cortados.txt",
        "remates_extraidos.txt",
        "remates_limpio.txt",
        "remates_separados.json",
    ]

    for archivo in archivos_a_eliminar:
        try:
            if os.path.exists(archivo):
                os.remove(archivo)
                logger.info(f"Archivo eliminado en cleanup: {archivo}")
            else:
                logger.debug(f"Archivo no encontrado (ya eliminado): {archivo}")
        except Exception as e:
            logger.warning(f"No se pudo eliminar {archivo}: {e}")

# --- FLUJO 1: EL MERCURIO SANTIAGO (Tu flujo actual) ---
def flujo_el_mercurio_santiago(url, paginas, columnas, cancel_event, progress_callback, logger):
    """
    Lógica específica para digital.elmercurio.com (Santiago)
    Usa paso1_copy (Selenium + Capa Texto) y paso2_copy (Regex Santiago).
    """
    logger.info("🔵 Iniciando flujo específico: El Mercurio (Santiago)")
    
    # --- PASO 1: Extracción Web ---
    logger.info("=" * 20 + " INICIANDO PASO 1: EXTRACCIÓN WEB (SANTIAGO) " + "=" * 20)
    progress_callback(5, 'Etapa 1: Extrayendo datos web (Santiago)...')
    
    # Llama a tu extractor original
    ruta_txt_bruto = paso1_copy.run_extractor(url, paginas, columnas)
    
    if not ruta_txt_bruto:
        logger.error("PASO 1 (Santiago) FALLÓ - No se generó archivo TXT.")
        raise Exception("La extracción web de Santiago falló.")
    
    logger.info(f"PASO 1 completado. Archivo generado: {ruta_txt_bruto}")

    # --- PASO 2: Limpieza y Separación ---
    logger.info("=" * 20 + " INICIANDO PASO 2: LIMPIEZA DE TEXTO (SANTIAGO) " + "=" * 20)
    progress_callback(33.3, 'Etapa 2: Limpiando y separando texto...')
    
    ruta_json_separado = paso2_copy.procesar_remates(cancel_event, ruta_txt_bruto)
    
    return ruta_json_separado, ruta_txt_bruto

# --- FLUJO 2: EL MERCURIO VALPARAÍSO (Nuevo flujo) ---
def flujo_el_mercurio_valpo(url, paginas, cancel_event, progress_callback, logger):
    """
    Lógica específica para mercuriovalpo.cl / mercurioantofagasta.cl
    Debe usar un extractor con OCR (paso1_valpo) y una limpieza adaptada (paso2_valpo).
    """
    logger.info("🟢 Iniciando flujo específico: El Mercurio de Valparaíso/Regional")
    
    # --- PASO 1: Extracción con OCR ---
    logger.info("=" * 20 + " INICIANDO PASO 1: EXTRACCIÓN CON OCR (VALPO) " + "=" * 20)
    progress_callback(5, 'Etapa 1: Extrayendo imágenes y OCR (Valpo)...')
    

    # TODO: Aquí llamarás a tu nuevo módulo:
    # ruta_txt_bruto = paso1_valpo.run_extractor_ocr(url, paginas)
    
    # Como aún no existe, lanzamos un error controlado para aviso:
    logger.warning("⚠️ El módulo paso1_valpo aún no está implementado.")
    raise NotImplementedError("El soporte para Valparaíso (OCR) está en construcción.")

    # --- PASO 2: Limpieza Específica ---
    # logger.info("=" * 20 + " INICIANDO PASO 2: LIMPIEZA (VALPO) " + "=" * 20)
    # progress_callback(33.3, 'Etapa 2: Limpiando texto OCR...')
    # ruta_json_separado = paso2_valpo.procesar_remates_valpo(cancel_event, ruta_txt_bruto)
    
    # return ruta_json_separado, ruta_txt_bruto


# --- ORQUESTADOR PRINCIPAL (Dispatcher) ---
def orquestador_con_datos(url, paginas, columnas, cancel_event, enable_cleanup, progress_callback):
    logger = get_logger("main", log_dir="logs", log_file="orquestador.log")

    logger.info("===== INICIO DEL PROCESO CENTRALIZADO =====")
    logger.info(f"Datos recibidos -> URL: {url} | Páginas: {paginas} | Columnas: {columnas}")

    ruta_json_separado = None
    ruta_txt_bruto = None

    try:
        # 1. ENRUTAMIENTO INTELIGENTE
        if "digital.elmercurio.com" in url:
            # ---> Flujo Santiago
            ruta_json_separado, ruta_txt_bruto = flujo_el_mercurio_santiago(
                url, paginas, columnas, cancel_event, progress_callback, logger
            )
            
        elif "mercuriovalpo.cl" in url :
            # ---> Flujo Valparaíso
            ruta_json_separado, ruta_txt_bruto = flujo_el_mercurio_valpo(
                url, paginas, cancel_event, progress_callback, logger
            )
            
        else:
            logger.error(f"URL no reconocida: {url}")
            raise Exception("La URL no corresponde a un diario soportado (Santiago o Valparaíso).")

        # 2. VERIFICACIÓN DE ESTADO
        if cancel_event.is_set():
            logger.warning("Proceso cancelado por el usuario antes del paso 3.")
            return

        if not ruta_json_separado:
            raise Exception("El flujo seleccionado no generó el archivo JSON intermedio.")

        # 3. PASO 3: IA (ESTO ES REUTILIZABLE PARA AMBOS)
        # La IA recibe el JSON limpio, sin importar de qué diario vino.
        logger.info("=" * 20 + " INICIANDO PASO 3: EXTRACCIÓN CON IA (COMÚN) " + "=" * 20)
        progress_callback(66.6, 'Etapa 3: Analizando con IA...')
        
        ruta_json_final, ruta_excel_final = paso3_copy.run_processor(cancel_event, ruta_json_separado, progress_callback)
        
        if cancel_event.is_set():
            logger.warning("Proceso cancelado por el usuario durante el paso 3.")
            return
        
        # 4. FINALIZACIÓN Y GUARDADO
        if ruta_json_final and ruta_excel_final:
            progress_callback(99, 'Finalizando y guardando archivos...')
            os.makedirs("outputs", exist_ok=True)

            # Prefijo para diferenciar en el nombre del archivo
            prefix = "VALPO" if "mercuriovalpo" in url else "SANTIAGO"
            fecha_str = datetime.now().strftime("%d-%m-%Y")
            uuid_str = uuid.uuid4().hex[:6]
            base_name = f"remates_{prefix}_{fecha_str}-{uuid_str}"

            nuevo_json = os.path.join("outputs", f"{base_name}.json")
            nuevo_excel = os.path.join("outputs", f"{base_name}.xlsx")

            os.rename(ruta_json_final, nuevo_json)
            os.rename(ruta_excel_final, nuevo_excel)

            # Eliminar temporales (si aplica)
            for tmp_file in [ruta_txt_bruto, ruta_json_separado]:
                if tmp_file:
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
            raise Exception("El procesamiento con IA (Paso 3) falló.")

    except Exception as e:
        logger.exception(f"Error inesperado en el orquestador: {e}")
        # Re-lanzamos la excepción para que app.py pueda mostrar el mensaje de error en la UI
        raise e
    finally:
        cleanup_temp_files(logger, enable_cleanup)
        logger.info("===== FIN DEL PROCESO =====\n")

# --- Bloque para mantener funcionalidad CLI ---
if __name__ == "__main__":
    # Dummy cancel event para pruebas CLI
    import threading
    dummy_event = threading.Event()
    def dummy_callback(p, m): print(f"[{p}%] {m}")
    
    orquestador_con_datos(
        url="https://digital.elmercurio.com/...", # Pon una URL de prueba aquí
        paginas=1,
        columnas=7,
        cancel_event=dummy_event,
        enable_cleanup=True,
        progress_callback=dummy_callback
    )