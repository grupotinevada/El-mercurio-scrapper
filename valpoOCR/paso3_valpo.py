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

# Google Cloud busca automáticamente la variable 'GOOGLE_APPLICATION_CREDENTIALS'
# No necesitamos hacer nada más si está en el .env.
# Pero por seguridad, verificamos que exista.

if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
    print("⚠️ ADVERTENCIA: No se detectó 'GOOGLE_APPLICATION_CREDENTIALS' en el .env")

# Google Vision soporta hasta 10MB por request.
# Subimos el límite para evitar compresiones que degraden la calidad.
LIMITE_MB = 9 * 1024 * 1024 


# ==========================================
# 🧹 FUNCIÓN DE LIMPIEZA (NUEVA)
# ==========================================
def limpiar_basura_ocr(texto_crudo, logger):
    """
    Elimina encabezados y pies de página específicos de El Mercurio de Valparaíso.
    Protege las fechas reales de los remates.
    """
    if not texto_crudo:
        return ""

    lineas = texto_crudo.split('\n')
    lineas_limpias = []

    # Regex compilados para velocidad
    
    # 1. Detectar "EL MERCURIO DE VALPARAÍSO" solo o con espacios
    re_diario = re.compile(r'^\s*EL\s+MERCURIO\s+DE\s+VALPARA[ÍI]SO\s*$', re.IGNORECASE)
    
    # 2. Detectar "Página X" o números sueltos de paginación
    # Ej: "Página 14", "Pag. 5", "30" (si está solo en la línea y parece paginación)
    re_pagina = re.compile(r'^\s*(P[áa]gina|P[áa]g\.?)\s*\d+\s*$', re.IGNORECASE)
    
    # 3. Detectar Fecha de Encabezado (CON CUIDADO)
    # Patrón: "EL MERCURIO... | Martes..." o "SO | Martes..."
    # La clave es la BARRA VERTICAL "|" cerca de una fecha. Los avisos no usan eso.
    # Expresión: (Algo opcional) + "|" + (Día semana) + (número) + "de" + (mes)
    re_fecha_header = re.compile(
        r'.*\|\s*(lunes|martes|mi[ée]rcoles|jueves|viernes|s[áa]bado|domingo)\s+\d{1,2}\s+de\s+[a-z]+\s+de\s+\d{4}', 
        re.IGNORECASE
    )

    for linea in lineas:
        linea_strip = linea.strip()
        
        # Filtro 1: Nombre del diario exacto
        if re_diario.match(linea_strip):
            # logger.debug(f"   🗑️ Eliminado Header Diario: '{linea_strip}'")
            continue

        # Filtro 2: Paginación
        if re_pagina.match(linea_strip):
            # logger.debug(f"   🗑️ Eliminado Paginación: '{linea_strip}'")
            continue

        # Filtro 3: Fecha de Encabezado (con pipe |)
        if re_fecha_header.match(linea_strip):
            # logger.debug(f"   🗑️ Eliminado Header Fecha: '{linea_strip}'")
            continue
        
        # Filtro 4: El texto "EL MERCURIO DE VALPARAÍSO" metido en medio de una línea de fecha (caso raro OCR)
        if "EL MERCURIO DE VALPARAÍSO |" in linea_strip.upper():
             continue

        # Si pasa los filtros, se guarda
        lineas_limpias.append(linea)

    return "\n".join(lineas_limpias)

def comprimir_imagen_si_es_necesario(path_imagen, logger):
    """
    Verifica si la imagen pesa más de 9MB. Si es mayor, comprime en memoria.
    Retorna: (nombre_archivo, objeto_archivo_binario)
    """
    try:
        peso_actual = os.path.getsize(path_imagen)
        nombre_archivo = os.path.basename(path_imagen)

        # Si está bajo el límite, enviamos la original (mejor calidad)
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
                img_buffer.seek(0)
                img_buffer.truncate(0)
                img.save(img_buffer, format='JPEG', optimize=True, quality=calidad)
                
                size_bytes = img_buffer.tell()
                
                if size_bytes < LIMITE_MB:
                    logger.info(f"     -> Optimizado a: {size_bytes/1024/1024:.2f} MB (Q:{calidad})")
                    break
                
                if calidad > 10:
                    calidad -= 5
                else:
                    logger.warning("     ⚠️ Límite de compresión alcanzado, enviando mejor esfuerzo.")
                    break
            
            img_buffer.seek(0)
            return nombre_archivo.replace(".png", ".jpg"), img_buffer
    except Exception as e:
        logger.error(f"     ❌ Error preparando imagen: {e}")
        return None, None

def detectar_texto_google_vision(archivo_tuple, logger):
    """
    Envía la imagen a Google Cloud Vision API.
    """
    filename, file_obj = archivo_tuple
    if not file_obj:
        return None

    try:
        # Instanciamos el cliente
        client = vision.ImageAnnotatorClient()

        # Leemos el contenido del buffer o archivo
        content = file_obj.read()
        image = vision.Image(content=content)

        # Llamada a la API (TEXT_DETECTION es ideal para documentos)
        # DOCUMENT_TEXT_DETECTION es otra opción si el layout es muy complejo
        response = client.text_detection(image=image)
        
        if response.error.message:
            logger.error(f"     ❌ Google API Error: {response.error.message}")
            return None

        texts = response.text_annotations
        
        # texts[0] contiene el texto completo concatenado
        if texts:
            return texts[0].description.strip()
        else:
            return ""

    except Exception as e:
        logger.error(f"     ❌ Excepción en Google Vision: {e}")
        return None
    finally:
        if file_obj and not file_obj.closed:
            file_obj.close()

def procesar_pagina_por_lotes(base_name, lista_columnas, output_folder, logger):
    """
    Función core: Une imágenes por lotes, detecta TAGS de código e inyecta marcadores.
    """
    texto_pagina = ""
    
    # 1. Cargar imágenes y metadatos
    imgs_obj = []
    metadata_tags = [] 

    for ruta in lista_columnas:
        img = cv2.imread(ruta)
        if img is not None:
            imgs_obj.append(img)
            # Detectamos TAGs en el nombre del archivo
            if "TAG1612" in ruta:
                metadata_tags.append("[CODE:1612]")
            else:
                metadata_tags.append(None)

    if not imgs_obj: 
        return texto_pagina + "(No se pudieron cargar columnas)\n\n"

    # 2. Dividir en lotes de 2 columnas (Chunks)
    chunk_size = 2
    chunks_img = [imgs_obj[x:x+chunk_size] for x in range(0, len(imgs_obj), chunk_size)]
    chunks_tags = [metadata_tags[x:x+chunk_size] for x in range(0, len(metadata_tags), chunk_size)]
    
    logger.info(f"   🧩 Dividido en {len(chunks_img)} tiras.")

    for idx_chunk, chunk_imgs in enumerate(chunks_img):
        current_tags = chunks_tags[idx_chunk]
        
        try:
            # Unificación de imágenes (Manteniendo alta calidad para GCV)
            ancho_max = max(img.shape[1] for img in chunk_imgs)
            processed_chunk = []
            separador = np.ones((20, ancho_max, 3), dtype=np.uint8) * 255 # Separador un poco más grande

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
            
            # Guardamos temporalmente como PNG para no perder calidad antes de enviar
            nombre_tira = f"{base_name}_parte_{idx_chunk+1}.png"
            ruta_tira = os.path.join(output_folder, nombre_tira)
            cv2.imwrite(ruta_tira, tira_lote)

            # --- ENVIAR LOTE A GOOGLE CLOUD VISION ---
            logger.info(f"   📡 Enviando parte {idx_chunk+1} a Google Cloud Vision...")
            nombre_archivo, archivo_listo = comprimir_imagen_si_es_necesario(ruta_tira, logger)
            
            if archivo_listo:
                texto_chunk = detectar_texto_google_vision((nombre_archivo, archivo_listo), logger)
                
                if texto_chunk:
                    # --- APLICAR LIMPIEZA AQUÍ ---
                    texto_limpio = limpiar_basura_ocr(texto_chunk, logger)
                    # --- INYECCIÓN DE CÓDIGO ---
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

    texto_pagina += ""
    return texto_pagina

def orquestador_ocr_valpo(diccionario_paginas, output_folder="temp_tiras_valpo"):
    logger = get_logger("paso3_valpo", log_dir="logs", log_file="paso3_valpo.log")
    logger.info("🏗️ Iniciando Paso 3: Unificación + Google Cloud Vision")

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    texto_completo_final = ""
    ruta_txt_salida = os.path.abspath("remates_valpo_ocr.txt")
    total_paginas = len(diccionario_paginas)

    for i, (ruta_pagina, lista_columnas) in enumerate(diccionario_paginas.items()):
        if not lista_columnas:
            continue
        base_name = os.path.splitext(os.path.basename(ruta_pagina))[0]
        logger.info(f"⚡ Procesando página {i+1}/{total_paginas}: {base_name}")
        texto_extraido_pagina = procesar_pagina_por_lotes(base_name, lista_columnas, output_folder, logger)
        texto_completo_final += texto_extraido_pagina

    with open(ruta_txt_salida, "w", encoding="utf-8") as f:
        f.write(texto_completo_final)
    
    logger.info(f"💾 Texto guardado en: {ruta_txt_salida}")
    return ruta_txt_salida