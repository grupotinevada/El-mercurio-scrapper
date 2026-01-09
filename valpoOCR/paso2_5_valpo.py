import os
import cv2
import pytesseract
import re
import sys
from logger import get_logger

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
    "codigo_cierre_encontrado": False
}

def reiniciar_estado():
    global ESTADO
    ESTADO = {
        "recolectando": False,
        "codigo_cierre_encontrado": False
    }

def es_titulo_real(linea, codigo):
    """
    Valida si una línea es un título de sección real (ej: '1615 CITAN A REUNION').
    """
    linea = linea.strip()
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

# CORRECCIÓN: Agregar cancel_event
def ejecutar_filtrado(diccionario_paginas, region, cancel_event):
    logger = get_logger("paso2_5_valpo", log_dir="logs", log_file="paso2_5_valpo.log")
    logger.info(f"🕵️ Iniciando Paso 2.5: Filtrado Inteligente (Regla Estricta {region.upper()})")
    
    reiniciar_estado()
    
    output_folder = "temp_filtrados_valpo"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    diccionario_filtrado = {}
    patron_inicio = re.compile(r'(1612|I612|l6l2|161Z)', re.IGNORECASE)
    patron_posible_fin = re.compile(r'^\s*(16(?!12)\d{2})\b', re.MULTILINE)

    total_cols_salida = 0

    for ruta_pagina, lista_columnas in diccionario_paginas.items():
        if cancel_event.is_set():
            logger.info("🛑 Proceso cancelado por usuario.")
            return None # Cancelar

        if ESTADO["codigo_cierre_encontrado"]:
            logger.info(f"   ⏩ Saltando página {os.path.basename(ruta_pagina)} (Código de cierre ya encontrado).")
            continue 

        base_name = os.path.splitext(os.path.basename(ruta_pagina))[0]
        columnas_validas_pagina = []

        for i, ruta_col in enumerate(lista_columnas):
            if cancel_event.is_set(): return None

            img = cv2.imread(ruta_col)
            if img is None: continue
            
            try:
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config='--psm 6')
                lines_plain = pytesseract.image_to_string(img, config='--psm 6').split('\n')
                texto_completo_buscar = " ".join(lines_plain)
            except:
                continue

            if not ESTADO["recolectando"]:
                match = patron_inicio.search(texto_completo_buscar)
                if match:
                    logger.info(f"   🟢 INICIO DETECTADO (1612) en: {os.path.basename(ruta_col)}")
                    ESTADO["recolectando"] = True
                    y_corte = 0
                    for j in range(len(data['text'])):
                        if patron_inicio.search(data['text'][j]):
                            y_corte = data['top'][j]
                            break
                    img_recortada = img[max(0, y_corte-5):, :]
                    nombre_out = f"filtro_{base_name}_{i}_TAG1612.jpg"
                    ruta_out = os.path.join(output_folder, nombre_out)
                    cv2.imwrite(ruta_out, img_recortada)
                    columnas_validas_pagina.append(ruta_out)
            else:
                encontrado_fin = False
                texto_fin_detectado = ""
                y_fin = img.shape[0] 
                
                for linea in lines_plain:
                    match_fin = patron_posible_fin.match(linea)
                    if match_fin:
                        codigo = match_fin.group(1)
                        if es_titulo_real(linea, codigo):
                            encontrado_fin = True
                            texto_fin_detectado = linea
                            logger.info(f"   🔴 FIN DETECTADO ({linea.strip()}) en: {os.path.basename(ruta_col)}")
                            break

                if encontrado_fin:
                    ESTADO["recolectando"] = False
                    ESTADO["codigo_cierre_encontrado"] = True
                    codigo_clave = texto_fin_detectado.split()[0].replace(".", "").strip()
                    for j in range(len(data['text'])):
                        if codigo_clave in data['text'][j]:
                            y_fin = data['top'][j]
                            break
                    img_recortada = img[:y_fin, :]
                    if img_recortada.shape[0] > 10: 
                        nombre_out = f"filtro_{base_name}_{i}_end.jpg"
                        ruta_out = os.path.join(output_folder, nombre_out)
                        cv2.imwrite(ruta_out, img_recortada)
                        columnas_validas_pagina.append(ruta_out)
                    
                    diccionario_filtrado[ruta_pagina] = columnas_validas_pagina
                    break 

                else:
                    columnas_validas_pagina.append(ruta_col)

        if columnas_validas_pagina:
            diccionario_filtrado[ruta_pagina] = columnas_validas_pagina
            total_cols_salida += len(columnas_validas_pagina)

    logger.info(f"✅ Filtrado estructural terminado. Salida: {total_cols_salida} columnas recortadas.")
    return diccionario_filtrado