import os
import cv2
import pytesseract
import numpy as np
# Se eliminó matplotlib para evitar errores de hilo al cerrar
from scipy.signal import savgol_filter, find_peaks
from logger import get_logger
import sys

def resource_path(relative_path):
    """ Obtiene la ruta absoluta al recurso, funciona para dev y para PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# --- CONFIGURACIÓN DE TESSERACT PORTABLE ---
if getattr(sys, 'frozen', False):
    tesseract_cmd_path = resource_path(os.path.join("Tesseract-OCR", "tesseract.exe"))
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd_path
else:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Configuración de parámetros
custom_config = r'--oem 3 --psm 6 -l spa'


def procesar_remates_valpo(cancel_event, entrada_datos, region):
    """
    Función principal llamada por main.py.
    """
    logger = get_logger("paso2_valpo", log_dir="logs", log_file="paso2_valpo.log")
    logger.info(f"✂️ Iniciando Paso 2 ({region.upper()}) - SEPARACIÓN DE COLUMNAS")

    imagenes = []
    if isinstance(entrada_datos, list):
        imagenes = entrada_datos
    elif isinstance(entrada_datos, str) and os.path.exists(entrada_datos):
        with open(entrada_datos, 'r', encoding='utf-8') as f:
            imagenes = [line.strip() for line in f if line.strip()]

    if not imagenes:
        logger.warning("⚠️ No hay imágenes para procesar.")
        return {}

    output_folder = "temp_cortes_valpo"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # DICCIONARIO DE RESULTADOS
    diccionario_resultados = {}

    for idx, ruta_img in enumerate(imagenes):
        if cancel_event.is_set():
            logger.info("🛑 Proceso cancelado por usuario.")
            break
        
        logger.info(f"👉 Procesando página {idx + 1}/{len(imagenes)}: {os.path.basename(ruta_img)}")
        diccionario_resultados[ruta_img] = [] 
        
        try:
            # Llamamos al pipeline LIMPIO
            recortes_generados = pipeline_total_batch_adaptado(ruta_img, output_folder, logger)
            
            if recortes_generados:
                diccionario_resultados[ruta_img].extend(recortes_generados)
                logger.info(f"   ✅ Se extrajeron {len(recortes_generados)} columnas.")
            else:
                logger.warning(f"   ⚠️ No se detectaron bloques válidos en: {ruta_img}")

        except Exception as e:
            logger.error(f"   ❌ Error procesando {ruta_img}: {e}")

    return diccionario_resultados


# ==========================================
# FUNCIONES DE APOYO (VISIÓN COMPUTACIONAL)
# ==========================================

def reforzar_divisorias_tenues(binary_img, proyeccion, umbral_alto, r_sensibilidad):
    img_reforzada = binary_img.copy()
    ancho = len(proyeccion)
    proy_suave = savgol_filter(proyeccion, window_length=11, polyorder=2)
    umbral_pico_min = umbral_alto * r_sensibilidad
    umbral_valle_cero = umbral_alto * 0.08
    picos_indices, _ = find_peaks(proy_suave, height=umbral_pico_min, distance=15)
    radio = 15
    for x in picos_indices:
        val_pico = proy_suave[x]
        if val_pico >= umbral_alto or x < 20 or x >= ancho - 20:
            continue
        zona_izq = proy_suave[max(0, x - radio) : x]
        zona_der = proy_suave[x + 1 : min(ancho, x + radio + 1)]
        valle_izq = np.min(zona_izq) if len(zona_izq) > 0 else val_pico
        valle_der = np.min(zona_der) if len(zona_der) > 0 else val_pico
        
        tiene_valle_bajo = valle_izq < umbral_valle_cero or valle_der < umbral_valle_cero
        contraste_izq = val_pico / valle_izq if valle_izq > 0 else np.inf
        contraste_der = val_pico / valle_der if valle_der > 0 else np.inf
        contraste_min = min(contraste_izq, contraste_der)
        tiene_contraste = contraste_min >= 3.0
        es_maximo = val_pico > proy_suave[x-1] and val_pico > proy_suave[x+1]
        
        if tiene_valle_bajo and tiene_contraste and es_maximo:
            cv2.line(img_reforzada, (x, 0), (x, img_reforzada.shape[0]), 255, 2)
    return img_reforzada

def fase2_limpieza_previa(recorte_img, padding_borrado):
    img_limpia = recorte_img.copy()
    gray = cv2.cvtColor(recorte_img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=4)
    ancho_b, alto_b = recorte_img.shape[1], recorte_img.shape[0]
    for i in range(1, num_labels):
        x, y, w, h = stats[i, :4]
        if (w > ancho_b * 0.25 and h > 70) or stats[i, 4] > 5000:
            x_p, y_p = max(0, x - padding_borrado), max(0, y - padding_borrado)
            w_p, h_p = min(ancho_b - x_p, w + (padding_borrado * 2)), min(alto_b - y_p, h + (padding_borrado * 2))
            cv2.rectangle(img_limpia, (x_p, y_p), (x_p + w_p, y_p + h_p), (255, 255, 255), -1)
    return img_limpia

def fase1_segmentar_columnas_completo(img_limpia, p_ocr, h_factor, h_gap, r_activar, r_sens):
    gray = cv2.cvtColor(img_limpia, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)
    proy_original = np.sum(binary, axis=0)
    umbral = np.max(proy_original) * h_factor
    if r_activar and np.max(proy_original) > 0:
        binary = reforzar_divisorias_tenues(binary, proy_original, umbral, r_sens)
    proy_final = np.sum(binary, axis=0)
    indices = np.where(proy_final > umbral)[0]
    lineas = []
    if len(indices) > 0:
        lineas.append(indices[0])
        for i in range(1, len(indices)):
            if indices[i] - indices[i-1] > h_gap:
                lineas.append(indices[i])
    puntos_corte = [0] + lineas + [img_limpia.shape[1]]
    columnas = []
    for i in range(len(puntos_corte) - 1):
        x_s, x_e = max(0, puntos_corte[i] - p_ocr), min(img_limpia.shape[1], puntos_corte[i+1] + p_ocr)
        if (puntos_corte[i+1] - puntos_corte[i]) > 60:
            columnas.append(img_limpia[:, x_s:x_e])
    return columnas


# ==========================================
# PIPELINE ADAPTADO (SIN PLOT)
# ==========================================

def pipeline_total_batch_adaptado(ruta_img, output_folder, logger):
    """
    Ejecuta el pipeline:
    1. Detectar bloque (Filtro Tesseract 'REMATE'...)
    2. Limpiar
    3. Segmentar Columnas
    4. Guardar columnas
    """
    p_borrado = 10
    p_ocr = 10
    h_factor = 0.65
    h_gap = 30
    r_activar = True
    r_sens = 0.10

    img = cv2.imread(ruta_img)
    if img is None:
        logger.error(f"No se pudo cargar: {ruta_img}")
        return []

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 15))
    dilated = cv2.dilate(binary, kernel, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    rutas_columnas_guardadas = []
    base_name = os.path.splitext(os.path.basename(ruta_img))[0]
    contours = sorted(contours, key=lambda c: cv2.boundingRect(c)[1])
    bloques_encontrados = 0

    for idx_c, c in enumerate(contours):
        x, y, w, h = cv2.boundingRect(c)
        if w < 250 or h < 250: 
            continue
        
        roi = gray[y:y+h, x:x+w]
        try:
            texto_val = pytesseract.image_to_string(roi, config='--psm 3').upper()
        except Exception as e:
            logger.warning(f"Error Tesseract: {e}")
            texto_val = ""

        # FILTRO DE PALABRAS CLAVE
        if any(k in texto_val for k in ["REMATE", "JUZGADO", "EXTRACTO", "JUDICIAL"]):
            bloques_encontrados += 1
            bloque = img[y:y+h, x:x+w]
            
            # FASE 1: Limpiar bloque
            limpio = fase2_limpieza_previa(bloque, p_borrado)
            
            # FASE 2: Segmentar columnas
            cols = fase1_segmentar_columnas_completo(
                limpio, p_ocr, h_factor, h_gap, r_activar, r_sens
            )

            if not cols: 
                logger.warning(f"No se encontraron columnas en el bloque {idx_c}")
                continue
            
            # Guardamos las columnas detectadas
            for i, col_img in enumerate(cols):
                col_filename = f"{base_name}_blk{idx_c}_col{i}.jpg"
                col_path = os.path.join(output_folder, col_filename)
                cv2.imwrite(col_path, col_img)
                rutas_columnas_guardadas.append(col_path)

    if bloques_encontrados == 0:
        logger.debug("No se encontraron bloques con palabras clave en esta imagen.")

    return rutas_columnas_guardadas