import cv2
import os
import io
import numpy as np
from google.cloud import vision
from PIL import Image
from logger import get_logger
from dotenv import load_dotenv
import re

# --- CONFIGURACIÓN GOOGLE CLOUD VISION ---
load_dotenv()
if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
    print("⚠️ ADVERTENCIA: No se detectó 'GOOGLE_APPLICATION_CREDENTIALS' en el .env")

LIMITE_MB = 9 * 1024 * 1024 

# CORRECCIÓN: Agregar cancel_event
def limpiar_basura_ocr(texto_crudo, logger, cancel_event):
    if not texto_crudo:
        return ""

    lineas = texto_crudo.split('\n')

    re_diario = re.compile(r'^\s*(EL\s+MERCURIO\s+DE\s+VALPARA[ÍI]SO|EL\s+SUR|EL\s+MERCURIO\s+DE\s+ANTOFAGASTA)\s*$', re.IGNORECASE)
    re_pagina = re.compile(r'^\s*(P[áa]gina|P[áa]g\.?)\s*\d+\s*$', re.IGNORECASE)
    re_fecha_header = re.compile(
        r'.*\|\s*(lunes|martes|mi[ée]rcoles|jueves|viernes|s[áa]bado|domingo).*\d{4}', 
        re.IGNORECASE
    )

    EXCLUSIONES_EXACTAS = {
        "EL MERCURIO DE VALPARAÍSO",
        "EL SUR",
        "EL MERCURIO DE ANTOFAGASTA",
    }

    EXCLUSIONES_PARCIALES = (
        "EL MERCURIO DE VALPARAÍSO |",
        "EL SUR |",
        "EL MERCURIO DE ANTOFAGASTA |",
        "CLASIFICADOS",
        "CLASIFICADOS |",
    )

    lineas_limpias = []

    for linea in lineas:
        if cancel_event.is_set():
            return None

        linea_strip = linea.strip()
        linea_upper = linea_strip.upper()

        if (
            re_diario.match(linea_strip)
            or re_pagina.match(linea_strip)
            or re_fecha_header.match(linea_strip)
        ):
            continue

        if linea_upper in EXCLUSIONES_EXACTAS:
            continue

        if any(excl in linea_upper for excl in EXCLUSIONES_PARCIALES):
            continue

        lineas_limpias.append(linea)

    return "\n".join(lineas_limpias)

def comprimir_imagen_si_es_necesario(path_imagen, logger):
    try:
        peso_actual = os.path.getsize(path_imagen)
        nombre_archivo = os.path.basename(path_imagen)

        if peso_actual <= LIMITE_MB:
            logger.info(f"     ✅ Imagen lista para GCV ({peso_actual/1024/1024:.2f} MB). Se usa original.")
            return nombre_archivo, open(path_imagen, 'rb')

        logger.info(f"     ⚠️ Imagen excede 9MB ({peso_actual/1024/1024:.2f} MB). Optimizando...")
        
        with Image.open(path_imagen) as img:
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img_buffer = io.BytesIO()
            calidad = 95
            while True:
                img_buffer.seek(0); img_buffer.truncate(0)
                img.save(img_buffer, format='JPEG', optimize=True, quality=calidad)
                size_bytes = img_buffer.tell()
                if size_bytes < LIMITE_MB: break
                if calidad > 10: calidad -= 5
                else: break
            img_buffer.seek(0)
            return nombre_archivo.replace(".png", ".jpg"), img_buffer
    except Exception as e:
        logger.error(f"     ❌ Error preparando imagen: {e}")
        return None, None

def detectar_texto_google_vision(archivo_tuple, logger):
    filename, file_obj = archivo_tuple
    if not file_obj: return None
    try:
        client = vision.ImageAnnotatorClient()
        content = file_obj.read()
        image = vision.Image(content=content)
        response = client.text_detection(image=image)
        if response.error.message:
            logger.error(f"     ❌ Google API Error: {response.error.message}")
            return None
        texts = response.text_annotations
        if texts: return texts[0].description.strip()
        else: return ""
    except Exception as e:
        logger.error(f"     ❌ Excepción en Google Vision: {e}")
        return None
    finally:
        if file_obj and not file_obj.closed:
            file_obj.close()

# CORRECCIÓN: Agregar cancel_event
def procesar_pagina_por_lotes(base_name, lista_columnas, output_folder, logger, cancel_event):
    texto_pagina = ""
    imgs_obj = []
    metadata_tags = [] 

    for ruta in lista_columnas:
        if cancel_event.is_set(): return None
        img = cv2.imread(ruta)
        if img is not None:
            imgs_obj.append(img)
            if "TAG1612" in ruta: metadata_tags.append("[CODE:1612]")
            else: metadata_tags.append(None)

    if not imgs_obj: return texto_pagina + "(No se pudieron cargar columnas)\n\n"

    chunk_size = 2
    chunks_img = [imgs_obj[x:x+chunk_size] for x in range(0, len(imgs_obj), chunk_size)]
    chunks_tags = [metadata_tags[x:x+chunk_size] for x in range(0, len(metadata_tags), chunk_size)]
    
    logger.info(f"   🧩 Dividido en {len(chunks_img)} tiras.")

    for idx_chunk, chunk_imgs in enumerate(chunks_img):
        if cancel_event.is_set(): return None
        current_tags = chunks_tags[idx_chunk]
        
        try:
            ancho_max = max(img.shape[1] for img in chunk_imgs)
            processed_chunk = []
            separador = np.ones((20, ancho_max, 3), dtype=np.uint8) * 255 

            for img in chunk_imgs:
                h, w = img.shape[:2]
                if w < ancho_max:
                    borde = np.ones((h, ancho_max - w, 3), dtype=np.uint8) * 255
                    img_ajustada = np.hstack((img, borde))
                else:
                    img_ajustada = img
                processed_chunk.append(img_ajustada)
                processed_chunk.append(separador)

            tira_lote = cv2.vconcat(processed_chunk[:-1])
            nombre_tira = f"{base_name}_parte_{idx_chunk+1}.png"
            ruta_tira = os.path.join(output_folder, nombre_tira)
            cv2.imwrite(ruta_tira, tira_lote)

            logger.info(f"   📡 Enviando parte {idx_chunk+1} a Google Cloud Vision...")
            nombre_archivo, archivo_listo = comprimir_imagen_si_es_necesario(ruta_tira, logger)
            
            if archivo_listo:
                texto_chunk = detectar_texto_google_vision((nombre_archivo, archivo_listo), logger)
                
                if texto_chunk:
                    # CORRECCIÓN: Pasar cancel_event
                    texto_limpio = limpiar_basura_ocr(texto_chunk, logger, cancel_event)
                    if texto_limpio is None: return None
                    
                    for tag in current_tags:
                        if tag:
                            logger.info(f"      🏷️ Inyectando marcador: {tag}")
                            texto_chunk = f"{tag}\n{texto_chunk}"
                            break 
                    
                    texto_pagina += texto_chunk + "\n"
                    logger.info("      ✅ Texto detectado con éxito.")
                else:
                    logger.warning("      ⚠️ No se detectó texto (Google devolvió vacío).")
            else:
                logger.error("      ❌ Falló preparación de imagen.")

        except Exception as e:
            logger.error(f"   ❌ Error en parte {idx_chunk+1}: {e}")

    return texto_pagina

# CORRECCIÓN: Agregar cancel_event
def orquestador_ocr_valpo(diccionario_paginas, cancel_event,region, output_folder="temp_tiras_valpo"):
    logger = get_logger(f"paso3_{region}", log_dir="logs", log_file=f"paso3_{region}.log")
    logger.info(f"🏗️ Iniciando Paso 3: Unificación + Google Cloud Vision {region}")

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    texto_completo_final = ""
    ruta_txt_salida = os.path.abspath(f"remates_{region}_ocr.txt")
    total_paginas = len(diccionario_paginas)

    for i, (ruta_pagina, lista_columnas) in enumerate(diccionario_paginas.items()):
        if cancel_event.is_set():
            logger.info("🛑 Proceso cancelado por usuario.")
            return None

        if not lista_columnas: continue
        base_name = os.path.splitext(os.path.basename(ruta_pagina))[0]
        logger.info(f"⚡ Procesando página {i+1}/{total_paginas}: {base_name}")
        
        # CORRECCIÓN: Pasar cancel_event
        texto_extraido_pagina = procesar_pagina_por_lotes(base_name, lista_columnas, output_folder, logger, cancel_event)
        
        if texto_extraido_pagina is None: return None # Cancelado

        texto_completo_final += texto_extraido_pagina

    with open(ruta_txt_salida, "w", encoding="utf-8") as f:
        f.write(texto_completo_final)
    
    logger.info(f"💾 Texto guardado en: {ruta_txt_salida}")
    return ruta_txt_salida