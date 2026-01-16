import os
import cv2
import pytesseract
import re
import sys
from logger import get_logger
logger = get_logger("[paso2_5 REGIONAL]", log_dir="logs", log_file="paso2_5_regional.log")

# --- CONFIGURACIÓN TESSERACT ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if getattr(sys, 'frozen', False):
    tesseract_cmd_path = resource_path(os.path.join("Tesseract-OCR", "tesseract.exe"))
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd_path
else:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- VARIABLES DE ESTADO ---
ESTADO = {
    "recolectando": False,
    "codigo_cierre_encontrado": False,
    "inicio_detectado_en_pagina": False # NUEVO: Bandera para activar el fallback
}

def reiniciar_estado():
    global ESTADO
    ESTADO = {
        "recolectando": False,
        "codigo_cierre_encontrado": False,
        "inicio_detectado_en_pagina": False
    }

def es_titulo_real(linea, codigo):
    """
    Valida si una línea es un título de sección real (ej: '1615 CITAN A REUNION').
    """
    linea = linea.strip()
    # DEBUG: Inspeccionar la validación de títulos potenciales
    # print(f"DEBUG: Validando título: '{linea}' para código {codigo}")
    
    if len(linea) > 60: return False
    if any(x in linea for x in ["$", "UF", "UTM", "@", "www"]): return False
    if re.match(rf"{codigo}\.\d", linea): return False

    palabras_titulo = ["CITAN", "REUNION", "INSTITUCIONES", "PROPIEDADES", "VEHICULOS", "VARIOS", "JUDICIALES", "DEPORTES", "EMPLEOS","CITANAREUNION"]
    linea_upper = linea.upper()
    if any(w in linea_upper for w in palabras_titulo): return True

    palabras_prohibidas = [
        "calle", "av", "avenida", "psje", "pasaje", "casa", "depto", 
        "block", "sitio", "lote", "rol", "fojas", "numero", "nro", "n°"
    ]
    palabras = linea.lower().split()
    if len(palabras) > 1:
        try:
            clean_words = [w.strip(".,:;") for w in palabras]
            if codigo in clean_words:
                idx = clean_words.index(codigo)
                if idx > 0:
                    prev = clean_words[idx-1]
                    if prev in palabras_prohibidas:
                        return False
        except:
            pass
    return True

def detectar_1612_valparaiso(img, patron_inicio, logger):
    """
    Mantiene el flujo original probado para Valparaíso y Antofagasta.
    Usa PSM 6 para bloques de texto uniforme.
    """
    config = '--psm 6'
    try:
        logger.debug(f"🔍 [OCR VALPO] Iniciando detección con patrón: {patron_inicio.pattern}")
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config=config)
        texto_completo = pytesseract.image_to_string(img, config=config)
        
        # DEBUG: Ver los primeros 100 caracteres del OCR
        logger.debug(f"📄 [OCR VALPO] Texto bruto: {texto_completo.strip()[:100].replace('\n', ' ')}...")
        
        match = patron_inicio.search(texto_completo)
        
        if match:
            logger.debug(f"🎯 [OCR VALPO] Match encontrado: '{match.group()}'")
            y_corte = 0
            for j in range(len(data['text'])):
                if patron_inicio.search(data['text'][j]):
                    y_corte = data['top'][j]
                    logger.debug(f"📍 [OCR VALPO] Coordenada Y de corte: {y_corte}")
                    break
            # Retornamos la imagen original sin cambios
            return True, y_corte, img
    except Exception as e:
        logger.error(f"Error en detector Valparaíso: {e}")
    # Retornamos la imagen original en caso de fallo
    return False, 0, img

def detectar_1612_concepcion(img, patron_inicio, logger): #VOLVEMOS AL INICIO POR EL MOMENTO EL TEXTO PASA SIN FILTRAR
    """
    Detección robusta para diario El Sur (Concepción).
    """
    config = '--psm 6'
    try:
        logger.debug(f"🔍 [OCR CONCE] Iniciando detección con patrón: {patron_inicio.pattern}")
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config=config)
        texto_completo = pytesseract.image_to_string(img, config=config)
        
        # DEBUG: Ver los primeros 100 caracteres del OCR
        logger.debug(f"📄 [OCR CONCE] Texto bruto: {texto_completo.strip()[:100].replace('\n', ' ')}...")
        
        match = patron_inicio.search(texto_completo)
        
        if match:
            logger.debug(f"🎯 [OCR CONCE] Match encontrado: '{match.group()}'")
            y_corte = 0
            for j in range(len(data['text'])):
                if patron_inicio.search(data['text'][j]):
                    y_corte = data['top'][j]
                    logger.debug(f"📍 [OCR CONCE] Coordenada Y de corte: {y_corte}")
                    break
            # Retornamos la imagen original sin cambios
            return True, y_corte, img
    except Exception as e:
        logger.error(f"Error en detector Concepción: {e}")
    # Retornamos la imagen original en caso de fallo
    return False, 0, img

def detectar_1312_antofagasta(img, patron_inicio, logger):
    """
    Mantiene el flujo original probado para Valparaíso y Antofagasta.
    Usa PSM 6 para bloques de texto uniforme.
    """
    config = '--psm 6'
    try:
        logger.debug(f"🔍 [OCR VALPO] Iniciando detección con patrón: {patron_inicio.pattern}")
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config=config)
        texto_completo = pytesseract.image_to_string(img, config=config)
        
        # DEBUG: Ver los primeros 100 caracteres del OCR
        logger.debug(f"📄 [OCR VALPO] Texto bruto: {texto_completo.strip()[:100].replace('\n', ' ')}...")
        
        match = patron_inicio.search(texto_completo)
        
        if match:
            logger.debug(f"🎯 [OCR VALPO] Match encontrado: '{match.group()}'")
            y_corte = 0
            for j in range(len(data['text'])):
                if patron_inicio.search(data['text'][j]):
                    y_corte = data['top'][j]
                    logger.debug(f"📍 [OCR VALPO] Coordenada Y de corte: {y_corte}")
                    break
            # Retornamos la imagen original sin cambios
            return True, y_corte, img
    except Exception as e:
        logger.error(f"Error en detector Valparaíso: {e}")
    # Retornamos la imagen original en caso de fallo
    return False, 0, img


# CORRECCIÓN: Agregar cancel_event
# CORRECCIÓN: Agregar cancel_event
def ejecutar_filtrado(diccionario_paginas, region, cancel_event):

    logger.info(f"🕵️ Iniciando Paso 2.5: Filtrado Regional ({region.upper()})")
    
    reiniciar_estado() # Limpia variables de control
    
    output_folder = "temp_filtrados_valpo"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    diccionario_filtrado = {}
    
    # CORRECCIÓN 1: Regex arreglado (sin el pipe '|' al final)
    CODIGOS_INICIO = {
        "valparaiso": r'(1612|I612|l6l2)',
        "antofagasta": r'(1312|I312|l3l2)',
        "concepcion": r'(1612|I612|l6l2|1512)' 
    }
    
    codigo_reg_busqueda = CODIGOS_INICIO.get(region, r'1612')
    patron_inicio = re.compile(codigo_reg_busqueda, re.IGNORECASE)
    logger.debug(f"⚙️ Patrón de inicio configurado: {patron_inicio.pattern}")

    # Patrón para detectar el fin de sección (códigos 16XX que no sean 1612)
    patron_posible_fin = re.compile(r'^\s*(16(?!12)\d{2})\b', re.MULTILINE)
    logger.debug(f"⚙️ Patrón de fin configurado: {patron_posible_fin.pattern}")

    total_cols_salida = 0

    for ruta_pagina, lista_columnas in diccionario_paginas.items():
        if cancel_event.is_set():
            logger.info("🛑 Proceso cancelado por usuario.")
            return None 

        if ESTADO["codigo_cierre_encontrado"]:
            logger.debug(f"⏭️ Página omitida: Cierre ya detectado anteriormente.")
            continue 

        base_name = os.path.splitext(os.path.basename(ruta_pagina))[0]
        columnas_validas_pagina = []
        
        # Reseteamos bandera de inicio por página nueva
        ESTADO["inicio_detectado_en_pagina"] = False

        logger.debug(f"📄 Procesando página: {base_name} ({len(lista_columnas)} columnas)")

        for i, ruta_col in enumerate(lista_columnas):
            if cancel_event.is_set(): return None

            img = cv2.imread(ruta_col)
            if img is None: 
                logger.warning(f"❌ No se pudo leer la imagen: {ruta_col}")
                continue
            
            # --- FASE DE DETECCIÓN DE INICIO ---
            if not ESTADO["recolectando"]:
                logger.debug(f"🔍 Analizando columna {i} para INICIO: {os.path.basename(ruta_col)}")
                detectado = False
                y_corte = 0
                img_procesada = img 

                # BIFURCACIÓN REGIONAL
                if region == "concepcion":
                    detectado, y_corte, img_procesada = detectar_1612_concepcion(img, patron_inicio, logger)
                elif region == "antofagasta":
                    detectado, y_corte, img_procesada = detectar_1312_antofagasta(img, patron_inicio, logger)
                else:
                    detectado, y_corte, img_procesada = detectar_1612_valparaiso(img, patron_inicio, logger)

                if detectado:
                    logger.info(f"   🟢 INICIO DETECTADO en {region.upper()}: {os.path.basename(ruta_col)}")
                    ESTADO["recolectando"] = True
                    ESTADO["inicio_detectado_en_pagina"] = True
                    
                    # Usamos img_procesada
                    img_recortada = img_procesada[max(0, y_corte-5):, :]
                    nombre_out = f"filtro_{base_name}_{i}_TAG1612.jpg"
                    ruta_out = os.path.join(output_folder, nombre_out)
                    cv2.imwrite(ruta_out, img_recortada)
                    columnas_validas_pagina.append(ruta_out)
                    logger.debug(f"💾 Columna de inicio guardada en: {ruta_out}")
            
            # --- FASE DE RECOLECCIÓN Y CIERRE ---
            else:
                logger.debug(f"📥 Recolectando columna {i}: {os.path.basename(ruta_col)}")
                
                # CORRECCIÓN 2: Eliminado el aumento forzado en recolección normal
                img_trabajo = img
                
                encontrado_fin = False
                y_fin = img_trabajo.shape[0] 
                
                # Para el cierre seguimos usando el OCR estándar
                texto_cierre_ocr = pytesseract.image_to_string(img_trabajo, config='--psm 6')
                lines_plain = texto_cierre_ocr.split('\n')
                
                for linea in lines_plain:
                    linea_strip = linea.strip()
                    if not linea_strip: continue
                    
                    if "16" in linea_strip:
                        logger.debug(f"🕵️ Evaluando línea sospechosa: '{linea_strip}'")
                    
                    match_fin = patron_posible_fin.match(linea_strip)
                    if match_fin:
                        codigo = match_fin.group(1)
                        if es_titulo_real(linea_strip, codigo):
                            encontrado_fin = True
                            logger.info(f"   🔴 FIN DETECTADO ({linea_strip}) en: {os.path.basename(ruta_col)}")
                            break

                if encontrado_fin:
                    ESTADO["recolectando"] = False
                    ESTADO["codigo_cierre_encontrado"] = True
                    
                    img_recortada = img_trabajo[:y_fin, :]
                    if img_recortada.shape[0] > 10: 
                        nombre_out = f"filtro_{base_name}_{i}_end.jpg"
                        ruta_out = os.path.join(output_folder, nombre_out)
                        cv2.imwrite(ruta_out, img_recortada)
                        columnas_validas_pagina.append(ruta_out)
                        logger.debug(f"💾 Columna de fin guardada en: {ruta_out}")
                    break 

                else:
                    # Guardamos la columna intermedia (original)
                    nombre_out = f"filtro_{base_name}_{i}_cont.jpg"
                    ruta_out = os.path.join(output_folder, nombre_out)
                    cv2.imwrite(ruta_out, img_trabajo)
                    columnas_validas_pagina.append(ruta_out)

        # --- FALLBACK PARA CONCEPCIÓN: SI NO ENCONTRÓ NADA EN LA PÁGINA ---
        if region == "concepcion" and not ESTADO["inicio_detectado_en_pagina"]:
            logger.warning(f"⚠️ [FALLBACK CONCEPCION] No se detectó inicio en toda la página.")
            logger.warning(f"🚀 Enviando TODAS las columnas (SIN PROCESAR) al siguiente paso.")
            
            columnas_validas_pagina = [] # Reiniciamos para llenar con todo
            
            for i, ruta_col in enumerate(lista_columnas):
                if cancel_event.is_set(): return None
                img = cv2.imread(ruta_col)
                if img is None: continue
                
                # CORRECCIÓN 3: Eliminado el resize X4. Se guarda la imagen tal cual.
                nombre_out = f"filtro_{base_name}_{i}_FALLBACK_RAW.jpg"
                ruta_out = os.path.join(output_folder, nombre_out)
                cv2.imwrite(ruta_out, img) # Guarda original
                
                columnas_validas_pagina.append(ruta_out)
                logger.debug(f"💾 Fallback guardado: {nombre_out}")

        if columnas_validas_pagina:
            diccionario_filtrado[ruta_pagina] = columnas_validas_pagina
            total_cols_salida += len(columnas_validas_pagina)

    logger.info(f"✅ Filtrado estructural terminado. Salida: {total_cols_salida} columnas.")
    return diccionario_filtrado