import paso1_copy
import paso2_copy
import paso3_copy
import sys
import os
from valpoOCR import paso1_regional, paso2_5_regional, paso2_regional, paso3_regional
import uuid
from datetime import datetime
from logger import get_logger

# --- Bloque para limpieza de archivos finales ---
import shutil

# CORRECCION: Se agrega cancel_event como argumento
def cleanup_temp_files(logger, cancel_event, enable_cleanup: bool = True):
    """
    Elimina archivos y carpetas temporales generados durante el proceso.
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
        
        "remates_separados_descartados.json",
        "remates_valparaiso_temp_descartados.json",


        "remates_valpo_ocr.txt",
        "remates_valpo_temp_descartados.json"
    ]
    
    carpetas_a_eliminar = [
        "temp_cortes_valpo",
        "temp_filtrados_valpo",
        "temp_img_valpo",
        "temp_tiras_valpo"
    ]

    for archivo in archivos_a_eliminar:
        
        if cancel_event.is_set():
            logger.info("🛑 Proceso cancelado por usuario.")
            return
        try:
            if os.path.isfile(archivo):
                os.remove(archivo)
                logger.info(f"Archivo eliminado: {archivo}")
        except Exception as e:
            logger.warning(f"No se pudo eliminar archivo {archivo}: {e}")

    for carpeta in carpetas_a_eliminar:
        
        if cancel_event.is_set():
            logger.info("🛑 Proceso cancelado por usuario.")
            return
        try:
            if os.path.isdir(carpeta):
                shutil.rmtree(carpeta)
                logger.info(f"Carpeta eliminada: {carpeta}")
        except Exception as e:
            logger.warning(f"No se pudo eliminar carpeta {carpeta}: {e}")

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
    # CORRECCION: Se pasa cancel_event a la funcion
    ruta_txt_bruto = paso1_copy.run_extractor(url, paginas, columnas, cancel_event)
    
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
# --- FLUJO 2: EL MERCURIO VALPARAÍSO ---
def flujo_el_mercurio_regional(url, paginas, cancel_event, progress_callback, logger, region):
    """
    Lógica compartida para diarios regionales (Valparaíso y Antofagasta).
    Recibe el parámetro 'region' para diferenciar configuraciones.
    """
    logger.info(f"🟢 Iniciando flujo regional: El Mercurio de {region.capitalize()}")
    
    # --- PASO 1: Extracción Web ---
    logger.info("=" * 20 + f" PASO 1: DESCARGA IMÁGENES ({region.upper()}) " + "=" * 20)
    progress_callback(5, f'Etapa 1: Descargando páginas ({region})...')
    
    # CORRECCIÓN: Pasar cancel_event
    lista_imagenes, ruta_txt_debug = paso1_regional.run_extractor_ocr(url, paginas, region, cancel_event)
    
    if cancel_event.is_set(): return None, None
    if not lista_imagenes:
        raise Exception(f"El extractor de {region} no obtuvo imágenes.")

    # --- PASO 2: Procesamiento (Corte de Columnas) ---
    logger.info("=" * 20 + " PASO 2: SEPARACIÓN DE COLUMNAS " + "=" * 20)
    progress_callback(20, f'Etapa 2: Separando columnas ({region})...')
    
    # CORRECCIÓN: procesar_remates_valpo ya recibía cancel_event, pero aseguramos que lo use bien internamente
    diccionario_cols = paso2_regional.procesar_remates_valpo(cancel_event, lista_imagenes, region)
    
    if cancel_event.is_set(): return None, None
    if not diccionario_cols:
         raise Exception("El Paso 2 no generó columnas válidas.")

    # --- PASO 2.5: Filtrado Inteligente (Códigos Específicos) ---
    logger.info("=" * 20 + " PASO 2.5: FILTRADO INTELIGENTE " + "=" * 20)
    progress_callback(30, 'Etapa 2.5: Filtrando sección Remates...')
    
    # CORRECCIÓN: Pasar cancel_event
    diccionario_cols_limpio = paso2_5_regional.ejecutar_filtrado(diccionario_cols, region, cancel_event)
    
    if cancel_event.is_set(): return None, None
    if not diccionario_cols_limpio:
        logger.warning(f"⚠️ El filtro 2.5 eliminó todas las columnas (No se encontraron códigos de {region}).")

    # --- PASO 3: Unificación + OCR (Nube) ---
    logger.info("=" * 20 + " PASO 3: UNIFICACIÓN Y OCR " + "=" * 20)
    progress_callback(50, 'Etapa 3: OCR en la nube... ')
    
    # CORRECCIÓN: Pasar cancel_event
    logger.info(f"OCR REGION: {region}")
    ruta_txt_ocr = paso3_regional.orquestador_ocr_valpo(diccionario_cols_limpio, cancel_event, region)
    
    if cancel_event.is_set(): return None, None
    
    logger.info(f"✅ Se generó el archivo OCR bruto: {ruta_txt_ocr}")

    # --- PASO 4: Limpieza y JSON ---
    logger.info("=" * 20 + " PASO 4: LIMPIEZA Y ESTRUCTURACIÓN " + "=" * 20)
    progress_callback(75, 'Etapa 4: Limpiando texto y revisión humana...')

    ruta_json_final = paso2_copy.procesar_remates(
        cancel_event, 
        ruta_txt_ocr, 
        archivo_final=f"remates_{region}_temp.json" 
    )

    if not ruta_json_final:
        logger.warning("⚠️ El usuario canceló o no se generó el JSON final.")
        return None, None

    return ruta_json_final, ruta_txt_debug


# --- ORQUESTADOR PRINCIPAL (Dispatcher) ---
def orquestador_con_datos(url, paginas, columnas, cancel_event, enable_cleanup, progress_callback):
    logger = get_logger("main", log_dir="logs", log_file="orquestador.log")

    logger.info("===== INICIO DEL PROCESO CENTRALIZADO =====")
    logger.info(f"Datos recibidos -> URL: {url} | Páginas: {paginas} | Columnas: {columnas}")

    ruta_json_separado = None
    ruta_txt_bruto = None
    region = "santiago"
    try:
        # 1. ENRUTAMIENTO INTELIGENTE
        if "digital.elmercurio.com" in url:
            # ---> Flujo Santiago
            ruta_json_separado, ruta_txt_bruto = flujo_el_mercurio_santiago(
                url, paginas, columnas, cancel_event, progress_callback, logger
            )
        
        elif any(domain in url for domain in ["mercuriovalpo.cl", "mercurioantofagasta.cl", "elsur.cl"]):
            # ---> Flujo Regional (Valpo / Antofa / El Sur)
            
            # Determinamos la región
            if "mercuriovalpo.cl" in url:
                region = "valparaiso"
            elif "mercurioantofagasta.cl" in url:
                region = "antofagasta"
            else:
                region = "concepcion" # Identificador para El Sur
            
            ruta_json_separado, ruta_txt_bruto = flujo_el_mercurio_regional(
                url, paginas, cancel_event, progress_callback, logger, region
            )
            
            if not ruta_json_separado:
                logger.info(f"⏹️ Proceso detenido en flujo {region}.")
                return
            
        else:
            logger.error(f"URL no reconocida: {url}")
            raise Exception("La URL no corresponde a un diario soportado (Santiago o Valparaíso).")

        # 2. VERIFICACIÓN DE ESTADO
        if cancel_event.is_set():
            logger.warning("Proceso cancelado por el usuario antes del paso 3.")
            return

        if not ruta_json_separado or not os.path.exists(ruta_json_separado):
            logger.error("No se generó el archivo JSON intermedio. Abortando.")
            raise Exception("Fallo en la generación del JSON intermedio.")

        # 3. PASO 3: IA (ESTO ES REUTILIZABLE PARA AMBOS)
        # La IA recibe el JSON limpio, sin importar de qué diario vino.
        logger.info("=" * 20 + " INICIANDO PASO 3: EXTRACCIÓN CON IA (COMÚN) " + "=" * 20)
        progress_callback(66.6, 'Etapa 3: Analizando con IA...')
        
        # paso3_copy es el procesador de IA
        ruta_json_final, ruta_excel_final = paso3_copy.run_processor(
            cancel_event, 
            ruta_json_separado, 
            progress_callback
        )
        
        if cancel_event.is_set():
            logger.warning("Proceso cancelado por el usuario durante el paso 3.")
            return
        
        # 4. FINALIZACIÓN Y GUARDADO
        if ruta_json_final and ruta_excel_final:
            progress_callback(99, 'Finalizando y guardando archivos...')
            os.makedirs("outputs", exist_ok=True)

            # Prefijo para diferenciar en el nombre del archivo
            prefix = region.upper()
            fecha_str = datetime.now().strftime("%d-%m-%Y")
            uuid_str = uuid.uuid4().hex[:6]
            base_name = f"remates_{prefix}_{fecha_str}-{uuid_str}"

            nuevo_json = os.path.join("outputs", f"{base_name}.json")
            nuevo_excel = os.path.join("outputs", f"{base_name}.xlsx")

            # Mover y renombrar archivos finales
            if os.path.exists(ruta_json_final):
                os.rename(ruta_json_final, nuevo_json)
            if os.path.exists(ruta_excel_final):
                os.rename(ruta_excel_final, nuevo_excel)

            # Eliminar temporales (si aplica)
            for tmp_file in [ruta_txt_bruto, ruta_json_separado]:
                if cancel_event.is_set():
                    return
                if tmp_file:
                    try:
                        if os.path.exists(tmp_file):
                            # Para Valpo no borramos el TXT del OCR si quisieras guardarlo como debug,
                            # pero normalmente ya no es necesario. Lo borramos para limpieza.
                            os.remove(tmp_file)
                            logger.info(f"Archivo temporal eliminado: {tmp_file}")
                    except Exception as e:
                        logger.warning(f"No se pudo eliminar {tmp_file}: {e}")

            logger.info(f"PASO 3 completado.")
            logger.info(f"Archivos finales guardados en 'outputs':\n  - {nuevo_json}\n  - {nuevo_excel}")
            
            # Intentar abrir el Excel automáticamente al finalizar
            try:
                os.startfile(nuevo_excel)
            except:
                pass

            logger.info("🎉 ¡PROCESO FINALIZADO CON ÉXITO! 🎉")
        else:
            logger.error("PASO 3 FALLÓ - No se generaron archivos finales")
            raise Exception("El procesamiento con IA (Paso 3) falló.")

    except Exception as e:
        logger.exception(f"Error inesperado en el orquestador: {e}")
        # Re-lanzamos la excepción para que app.py pueda mostrar el mensaje de error en la UI
        raise e
    finally:
        # CORRECCION: Se pasa cancel_event a cleanup_temp_files
        cleanup_temp_files(logger, cancel_event, enable_cleanup)
        logger.info("===== FIN DEL PROCESO =====\n")
# --- Bloque para mantener funcionalidad CLI ---
if __name__ == "__main__":
    # Dummy cancel event para pruebas CLI
    import threading
    dummy_event = threading.Event()
    def dummy_callback(p, m): print(f"[{p}%] {m}")
    
    # URL de prueba para verificar que entra al flujo de Valpo
    test_url_valpo = "https://www.mercuriovalpo.cl/impresa/2023/12/01/papel/"
    
    orquestador_con_datos(
        url=test_url_valpo, 
        paginas=1,
        columnas=7,
        cancel_event=dummy_event,
        enable_cleanup=True,
        progress_callback=dummy_callback
    )