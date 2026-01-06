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
    Evita falsos positivos como 'Casa 1615' o números largos.
    """
    linea = linea.strip()
    
    # 1. VALIDACIÓN BÁSICA
    # Si la línea es excesivamente larga, probablemente es cuerpo de texto, no un título.
    if len(linea) > 60: 
        return False

    # 2. DESCARTAR SÍMBOLOS DE CONTENIDO
    # Títulos de sección no suelen tener precios ($), UF, o @
    if any(x in linea for x in ["$", "UF", "UTM", "@", "www"]):
        return False

    # 3. VERIFICAR QUE NO SEA PARTE DE UN NÚMERO MÁS LARGO
    # El regex ya maneja \b, pero verificamos si después del código hay un punto decimal inmediato inválido
    # Ej: "1615.55" -> No es sección
    if re.match(rf"{codigo}\.\d", linea):
        return False

    # 4. PALABRAS CLAVE DE TÍTULO (Refuerzo Positivo)
    # Si contiene estas palabras, es casi seguro un título
    palabras_titulo = ["CITAN", "REUNION", "INSTITUCIONES", "PROPIEDADES", "VEHICULOS", "VARIOS", "JUDICIALES", "DEPORTES", "EMPLEOS","CITANAREUNION"]
    linea_upper = linea.upper()
    if any(w in linea_upper for w in palabras_titulo):
        return True

    # 5. PALABRAS PROHIBIDAS (Contexto de Dirección/Texto)
    # Si aparece esto, probablemente es una dirección que Tesseract cortó mal
    # Ej: "Calle 1615" (si 'Calle' quedó en la línea) o texto genérico.
    palabras_prohibidas = [
        "calle", "av", "avenida", "psje", "pasaje", "casa", "depto", 
        "block", "sitio", "lote", "rol", "fojas", "numero", "nro", "n°"
    ]
    
    palabras = linea.lower().split()
    
    # Si la línea es SOLO el número "1615", es sospechoso, pero podría ser.
    # Pero si tiene texto, analizamos.
    if len(palabras) > 1:
        # Si la palabra anterior al código es prohibida
        try:
            # Quitamos puntuación para buscar bien
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

def ejecutar_filtrado(diccionario_paginas, region):
    logger = get_logger("paso2_5_valpo", log_dir="logs", log_file="paso2_5_valpo.log")
    logger.info(f"🕵️ Iniciando Paso 2.5: Filtrado Inteligente (Regla Estricta {region.upper()})")
    
    reiniciar_estado()
    
    output_folder = "temp_filtrados_valpo"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    diccionario_filtrado = {}
    
    # --- REGEX AJUSTADOS ---
    # 1. Inicio: 1612 (con tolerancias OCR comunes)
    patron_inicio = re.compile(r'(1612|I612|l6l2|161Z)', re.IGNORECASE)
    
    # 2. Fin: Estrictamente comienza con 16 seguido de 2 dígitos (1600-1699)
    #    \b asegura que no sea 16150 (boundary)
    #    (?!1612) asegura que si por error vuelve a leer el titulo de inicio, no corte.
    patron_posible_fin = re.compile(r'^\s*(16(?!12)\d{2})\b', re.MULTILINE)

    total_cols_salida = 0

    for ruta_pagina, lista_columnas in diccionario_paginas.items():
        # Si ya encontramos el fin en una página anterior, ignoramos el resto de páginas
        if ESTADO["codigo_cierre_encontrado"]:
            logger.info(f"   ⏩ Saltando página {os.path.basename(ruta_pagina)} (Código de cierre ya encontrado).")
            continue 

        base_name = os.path.splitext(os.path.basename(ruta_pagina))[0]
        columnas_validas_pagina = []

        for i, ruta_col in enumerate(lista_columnas):
            img = cv2.imread(ruta_col)
            if img is None: continue
            
            try:
                # Obtenemos datos detallados para coordenadas y texto plano para regex
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config='--psm 6')
                lines_plain = pytesseract.image_to_string(img, config='--psm 6').split('\n')
                texto_completo_buscar = " ".join(lines_plain) # Usamos esto para buscar patrones
            except:
                continue

            # --- MÁQUINA DE ESTADOS ---
            
            # 1. BUSCANDO INICIO (1612)
            if not ESTADO["recolectando"]:
                match = patron_inicio.search(texto_completo_buscar)
                if match:
                    logger.info(f"   🟢 INICIO DETECTADO (1612) en: {os.path.basename(ruta_col)}")
                    ESTADO["recolectando"] = True
                    
                    # Buscar la coordenada Y donde empieza el 1612
                    y_corte = 0
                    for j in range(len(data['text'])):
                        if patron_inicio.search(data['text'][j]):
                            y_corte = data['top'][j]
                            break
                    
                    # Cortar desde el título hacia abajo
                    img_recortada = img[max(0, y_corte-5):, :]
                    
                    nombre_out = f"filtro_{base_name}_{i}_TAG1612.jpg"
                    ruta_out = os.path.join(output_folder, nombre_out)
                    cv2.imwrite(ruta_out, img_recortada)
                    columnas_validas_pagina.append(ruta_out)
                else:
                    # Si aún no empieza, ignoramos esta columna
                    pass

            # 2. BUSCANDO FIN (Cualquier código 16XX que no sea 1612)
            else:
                encontrado_fin = False
                texto_fin_detectado = ""
                y_fin = img.shape[0] # Por defecto, final de la imagen
                
                for linea in lines_plain:
                    match_fin = patron_posible_fin.match(linea)
                    if match_fin:
                        codigo = match_fin.group(1)
                        
                        # VALIDACIÓN ESTRUCTURAL MEJORADA
                        if es_titulo_real(linea, codigo):
                            encontrado_fin = True
                            texto_fin_detectado = linea
                            logger.info(f"   🔴 FIN DETECTADO ({linea.strip()}) en: {os.path.basename(ruta_col)}")
                            break
                        else:
                            # logger.debug(f"      ⚠️ Falso positivo ignorado: {linea.strip()}")
                            pass

                if encontrado_fin:
                    ESTADO["recolectando"] = False
                    ESTADO["codigo_cierre_encontrado"] = True
                    
                    # Buscar coordenada Y donde empieza el código de fin para cortar ANTES
                    # Buscamos la coincidencia más parecida en 'data'
                    codigo_clave = texto_fin_detectado.split()[0].replace(".", "").strip()
                    
                    for j in range(len(data['text'])):
                        # Comparamos si el texto OCR contiene el código (ej: "1615")
                        if codigo_clave in data['text'][j]:
                            y_fin = data['top'][j]
                            break
                    
                    # Cortamos HASTA donde empieza el nuevo código
                    img_recortada = img[:y_fin, :]
                    
                    # Solo guardamos si queda algo de imagen (evitar recortes vacíos)
                    if img_recortada.shape[0] > 10: 
                        nombre_out = f"filtro_{base_name}_{i}_end.jpg"
                        ruta_out = os.path.join(output_folder, nombre_out)
                        cv2.imwrite(ruta_out, img_recortada)
                        columnas_validas_pagina.append(ruta_out)
                    
                    diccionario_filtrado[ruta_pagina] = columnas_validas_pagina
                    break # Salimos del bucle de columnas de esta página

                else:
                    # Si estamos recolectando y NO hay fin, guardamos la columna entera
                    columnas_validas_pagina.append(ruta_col)

        if columnas_validas_pagina:
            diccionario_filtrado[ruta_pagina] = columnas_validas_pagina
            total_cols_salida += len(columnas_validas_pagina)

    logger.info(f"✅ Filtrado estructural terminado. Salida: {total_cols_salida} columnas recortadas.")
    return diccionario_filtrado