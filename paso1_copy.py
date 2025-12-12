# paso1.py - Encapsulado para uso desde otros módulos
# EXTRACTOR DE REMATES JUDICIALES

# pégalo en paso1.py
import os
import sys
import time
from datetime import datetime
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    WebDriverException,
)
import tempfile
from dotenv import load_dotenv
from collections import Counter

def run_extractor( url: str, paginas: int, columnas: int):
    from logger import get_logger, log_section, dbg

    logger = get_logger("paso1", log_dir="logs", log_file="paso1.log")
    logger.info("Ejecutando Paso 1...")



# --------------------------------------------------------------------------
# CONFIGURACIÓN DEL NAVEGADOR
# --------------------------------------------------------------------------
    chrome_options = Options()

    # 1. Creas la ruta única para el perfil (esto está perfecto)
    user_data_dir = os.path.join(tempfile.gettempdir(), f"chrome_profile_{os.getpid()}")

    # 2. Le dices a Chrome que USE esa ruta 
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

    # El resto de tu configuración está bien
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])

    service = Service(log_path="logs/chromedriver.log")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 25)
    
    load_dotenv()
    URL = url
    EMAIL = os.getenv("USUARIO") 
    PASSWORD = os.getenv("PASSWORD") 
    PAGINAS_A_PROCESAR = paginas
    COLUMNAS = columnas
    OUTPUT_FILE = "remates_extraidos.txt"
    DEBUG_SCREENSHOTS = True

    def modo_predeterminado():
        marco_horizontal = "═" * 50
        logger.info(f"\n{marco_horizontal}\n")
        logger.info("Empezando el proceso de extracción de remates judiciales...")
        logger.info(f"Datos de entrada:\n URL: {URL}, \n Usuario: {EMAIL}, \n Páginas a procesar: {PAGINAS_A_PROCESAR} \n Columnas: {COLUMNAS}")
        

    modo_predeterminado()

    def guardar_screenshot(path: str):
        try:
            driver.save_screenshot(path)
            logger.info(f"Screenshot guardado: {path}")
        except Exception as e:
            logger.warning(f"No se pudo guardar screenshot ({path}): {e}")

    def click_siguiente_pagina(driver, wait):
        xpath_next = ("//a[.//div[contains(concat(' ', normalize-space(@class), ' '), ' next_arrow ') "
                      "and .//i[contains(@class,'fa-angle-right')]]]")
        current_text_layer = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#viewer .textLayer")))
        dbg(logger, "textLayer actual referenciado para staleness_of.")
        next_anchor = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_next)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", next_anchor)
        dbg(logger, "Siguiente anchor localizado y llevado a viewport.")
        last_err = None
        for attempt in range(3):
            try:
                next_anchor.click()
                dbg(logger, f"Click normal en 'siguiente' (intento {attempt+1}).")
                break
            except (ElementClickInterceptedException, StaleElementReferenceException, WebDriverException) as e:
                last_err = e
                dbg(logger, f"Click normal falló (intento {attempt+1}): {e}. Reintentando...")
                time.sleep(0.4)
                try:
                    next_anchor = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_next)))
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", next_anchor)
                except Exception:
                    pass
        else:
            try:
                driver.execute_script("arguments[0].click();", next_anchor)
                dbg(logger, "Fallback: click por JavaScript ejecutado.")
            except Exception as e:
                raise TimeoutException(f"No se pudo hacer click en siguiente: {last_err or e}")
        wait.until(EC.staleness_of(current_text_layer))
        dbg(logger, "textLayer anterior quedó stale (cambio de página detectado).")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#viewer .textLayer")))
        dbg(logger, "textLayer nuevo presente.")

    def try_keyboard_next(driver):
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ARROW_RIGHT)
            dbg(logger, "Enviado Keys.ARROW_RIGHT como fallback.")
        except Exception as e:
            dbg(logger, f"Fallback teclado no disponible: {e}")

    from collections import Counter
    # Importamos el algoritmo de clustering
    from sklearn.cluster import KMeans
    import numpy as np
    
    
    def capture_text_from_textlayer(viewer_div):
        """
        Versión con LOGS DE PROCESO para depuración detallada.
        """
        # Si 'logger' no es global, descomentar la siguiente línea o pasarlo como argumento
        # from logger import get_logger; logger = get_logger("paso1_debug")

        logger.info(f"📊 [DEBUG] Iniciando captura de texto. Columnas esperadas: {COLUMNAS}")
        NUM_COLUMNAS_ESPERADAS = COLUMNAS  

        # 1. Extraer TODOS los fragmentos
        all_fragments = []
        try:
            text_layer = viewer_div.find_element(By.CLASS_NAME, "textLayer")
            divs = text_layer.find_elements(By.TAG_NAME, "div")
            logger.info(f"   🔍 [RAW] Elementos 'div' encontrados en textLayer: {len(divs)}")
        except Exception as e:
            logger.error(f"   ❌ Error accediendo a textLayer: {e}")
            return ""

        for i, div in enumerate(divs):
            style = div.get_attribute('style')
            text = div.text.strip()
            if not text:
                continue
            try:
                top = float(re.search(r'top:\s*([\d\.]+)px', style).group(1))
                left = float(re.search(r'left:\s*([\d\.]+)px', style).group(1))
                font_size_match = re.search(r'font-size:\s*([\d\.]+)px', style)
                font_size = float(font_size_match.group(1)) if font_size_match else 0.0
                
                # Loguear solo los primeros 3 para verificar que el regex funciona
                if i < 3: 
                    logger.debug(f"      🔹 Muestra div[{i}]: '{text[:20]}...' | T:{top} L:{left} FS:{font_size}")
                
                all_fragments.append({'text': text, 'top': top, 'left': left, 'font_size': font_size})

            except (AttributeError, ValueError) as e:
                logger.warning(f"      ⚠️ Error parseando estilo de div[{i}]: {e}")
                continue

        if not all_fragments:
            logger.warning("   ⚠️ No se extrajeron fragmentos válidos (all_fragments vacío).")
            return ""

        # 2. Filtrar por font-size más común Y títulos numéricos
        logger.info("   ⚙️ [FILTRO] Analizando tamaños de fuente...")
        if not any(f['font_size'] > 0 for f in all_fragments):
            logger.warning("      ⚠️ No se detectaron font-sizes > 0. Usando todos los fragmentos.")
            filtered_fragments = all_fragments
        else:
            font_size_counts = Counter(f['font_size'] for f in all_fragments if f['font_size'] > 0)
            main_font_size = font_size_counts.most_common(1)[0][0]
            logger.info(f"      🎯 Font-size principal detectado: {main_font_size}px")

            filtered_fragments = []
            for frag in all_fragments:
                is_main_font = abs(frag['font_size'] - main_font_size) < 0.1
                is_numeric_title = frag['text'].isdigit() # A veces los títulos de remate son números con otra font
                if is_main_font or is_numeric_title:
                    filtered_fragments.append(frag)
            
            logger.info(f"      📉 Fragmentos tras filtro: {len(filtered_fragments)} (de {len(all_fragments)} originales)")

        if len(filtered_fragments) < 2:
            logger.warning("      ⚠️ Menos de 2 fragmentos tras filtrado. Retornando texto plano sin columnas.")
            return "\n".join(f['text'] for f in filtered_fragments)

        # 3. Clustering por columnas
        logger.info("   🧮 [KMEANS] Calculando columnas...")
        try:
            left_coords = np.array([f['left'] for f in filtered_fragments]).reshape(-1, 1)
            kmeans = KMeans(n_clusters=NUM_COLUMNAS_ESPERADAS, n_init='auto', random_state=0)
            kmeans.fit(left_coords)
            column_centers = sorted(kmeans.cluster_centers_.flatten())
            dividers = [(column_centers[i] + column_centers[i+1]) / 2 for i in range(len(column_centers)-1)]
            
            logger.info(f"      📍 Centros de columna detectados (X): {[round(c,1) for c in column_centers]}")
            logger.info(f"      ✂️ Divisores calculados: {[round(d,1) for d in dividers]}")
        except Exception as e:
            logger.error(f"      ❌ Error en KMeans: {e}. Retornando texto plano.")
            return "\n".join(f['text'] for f in filtered_fragments)

        # 4. Asignar fragmentos a columnas
        num_columns = len(column_centers)
        columns = [[] for _ in range(num_columns)]
        for frag in filtered_fragments:
            col_index = 0
            for divider in dividers:
                if frag['left'] > divider:
                    col_index += 1
                else:
                    break
            if col_index < num_columns:
                columns[col_index].append(frag)
        
        # Log de distribución
        distribucion = [len(c) for c in columns]
        logger.info(f"      📦 Distribución de items por columna: {distribucion}")


        # 5. Armar texto columna por columna y limpiar con lógica por códigos especiales
        full_page_text = []
        numeros_especiales = {"1300", "1640", "1309", "1312", "1315", "1320", "1321", "1316", "1612", "1616", "1630", "1635"}
        remate_re = re.compile(r'^16\d{2}$')  # regla: 16xx se considera remate

        logger.info("   📝 [ENSAMBLAJE] Procesando texto columna por columna...")

        for i, column in enumerate(columns):
            if not column:
                continue
            
            # Ordenar de arriba a abajo
            column.sort(key=lambda f: f['top'])
            
            output_lines = []
            capture = False          # True = estamos acumulando texto de remate
            seen_remate = False      # si vimos al menos un remate en esta columna
            last_special_code = None
            
            logger.debug(f"      Processing Col {i+1} ({len(column)} items)...")

            for frag in column:
                s = frag['text'].strip()
                # Ajuste ligero: a veces el font size de titulos varia un poco, cuidado con el filtro estricto aqui
                # Usamos el font_size del fragmento
                
                UMBRAL_FONT_SIZE_TITULO = 10.0 # Baje un poco el umbral por seguridad, ajustalo si es necesario
                is_special_code = s in numeros_especiales
                
                if is_special_code and frag['font_size'] > UMBRAL_FONT_SIZE_TITULO:
                    last_special_code = s
                    s_marcado = f"[CODE:{s}]"
                    
                    if remate_re.match(s):   # es remate (16xx)
                        logger.info(f"         🟢 [START] Código de inicio detectado: {s} (Col {i+1})")
                        output_lines.append(s_marcado)
                        capture = True
                        seen_remate = True
                    else:
                        logger.info(f"         🔴 [STOP] Código de fin/ruido detectado: {s} (Col {i+1})")
                        capture = False
                    continue

                # línea NO es código especial
                if capture:
                    output_lines.append(s)

            # Si no se detectó ningún remate en la columna, conservar sólo el último código especial
            if not seen_remate and last_special_code:
                logger.debug(f"      ⚠️ Columna {i+1} sin remates. Conservando solo código: {last_special_code}")
                output_lines = [last_special_code]

            # Normalizar
            normalized = []
            prev = None
            for L in output_lines:
                if prev is not None and prev.strip() == L.strip():
                    continue
                normalized.append(L)
                prev = L

            texto_columna = "\n".join(normalized)
            full_page_text.append(texto_columna)
            logger.debug(f"      ✅ Columna {i+1} procesada: {len(normalized)} líneas útiles.")

        final_text = "".join(full_page_text)
        logger.info(f"   🏁 [FIN] Texto capturado total: {len(final_text)} caracteres.")
        return final_text
    
    
    # def limpiar_por_codigos(texto):
    #     lineas = texto.split("\n")
    #     resultado = []
    #     for linea in lineas:
    #         codigo_match = re.match(r"^(\d{3,4})\b", linea.strip())
    #         if codigo_match:
    #             codigo = int(codigo_match.group(1))
    #             # Guardar solo remates (16xx)
    #             if 1600 <= codigo < 1700:
    #                 resultado.append(linea)
    #                 # marcar que estamos dentro de un remate
    #                 continue
    #             else:
    #                 # ignorar bloques 13xx, no se agregan
    #                 continue
    #         else:
    #             # Si no es encabezado de anuncio y estamos en modo "remate", lo guardamos
    #             if resultado:
    #                 resultado.append(linea)
    #     return "\n".join(resultado)



    # LOGIN
    log_section(logger, "LOGIN")
    try:
        logger.info(f"🌍 Navegando a: {URL}")
        driver.delete_all_cookies()
        driver.get(URL)
        logger.info("🔐 Esperando el formulario de login...")
        username_field = wait.until(EC.element_to_be_clickable((By.ID, "txtUsername")))
        password_field = driver.find_element(By.ID, "txtPassword")
        logger.info("🔑 Ingresando credenciales...")
        time.sleep(0.5)
        username_field.send_keys(EMAIL)
        time.sleep(0.5)
        password_field.send_keys(PASSWORD)
        time.sleep(0.5)
        login_button = driver.find_element(By.ID, "gopram")
        driver.execute_script("arguments[0].click();", login_button)
        logger.info("✅ Login enviado. Esperando a que desaparezca el modal...")
        wait.until(EC.invisibility_of_element_located((By.ID, "modal_limit_articulos")))
        time.sleep(1.0)
        logger.info("👍 Modal cerrado. Vista del diario habilitada.")
    except TimeoutException:
        logger.error("❌ Error: El modal de login no desapareció a tiempo.")
        if DEBUG_SCREENSHOTS:
            guardar_screenshot("logs/error_login.png")
        driver.quit()
        return None
    except Exception as e:
        logger.error(f"❌ Error inesperado durante el login: {e}")
        if DEBUG_SCREENSHOTS:
            guardar_screenshot("logs/error_login.png")
        driver.quit()
        return None

    # EXTRACCIÓN
    log_section(logger, "EXTRACT")
    logger.info("--- Iniciando proceso de extracción de texto ---")
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f_out:
            try:
                #input("\n⏸️  Presiona Enter para continuar con la extracción...")
                logger.info("   🖼 Activando modo HD (si existe botón)...")
                hd_button = wait.until(EC.element_to_be_clickable((By.ID, "active_pdf")))
                driver.execute_script("arguments[0].click();", hd_button)
                time.sleep(1)
                dbg(logger, "Botón HD clickeado.")
            except Exception as e:
                logger.info(f"   ⚠️ No se pudo activar modo HD (continuo): {e}")
            for page_num in range(1, PAGINAS_A_PROCESAR + 1):
                log_section(logger, "PAGE_PREP")
                logger.info(f"📄 Procesando página {page_num}...")
                time.sleep(1)
                try:
                    logger.info("   🔍 Buscando el contenedor #viewer y .textLayer...")
                    viewer_div = wait.until(EC.presence_of_element_located((By.ID, "viewer")))
                    
                    # 1. Esperamos a que la capa exista
                    text_layer = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#viewer .textLayer")))
                    
                    # 2. VALIDACIÓN CRÍTICA: Esperar a que la capa tenga hijos (texto real)
                    # Reintentamos hasta 10 veces (5 segundos aprox)
                    texto_cargado = False
                    for i in range(10):
                        divs_texto = text_layer.find_elements(By.TAG_NAME, "div")
                        if len(divs_texto) > 10: # Asumimos que una página válida tiene al menos 10 líneas
                            texto_cargado = True
                            logger.info(f"   ✅ Texto detectado: {len(divs_texto)} líneas encontradas.")
                            break
                        else:
                            logger.warning(f"   ⏳ Esperando renderizado de texto (Intento {i+1}/10)...")
                            time.sleep(0.5)
                    
                    if not texto_cargado:
                        logger.error("   ❌ La capa de texto existe pero está vacía después de esperar.")
                        # Opcional: guardar screenshot aquí para debug visual
                        if DEBUG_SCREENSHOTS:
                            guardar_screenshot(f"logs/debug_vacio_pag_{page_num}.png")

                except Exception as e:
                    logger.error(f"❌ No se encontró viewer/textLayer: {e}")
                    if DEBUG_SCREENSHOTS:
                        guardar_screenshot(f"logs/error_page_{page_num}_viewer.png")
                    raise
                logger.info("   ✨ Extrayendo texto de la página...")
                f_out.write(f"--- Página {page_num} ---\n\n")
                try:
                    text = capture_text_from_textlayer(viewer_div)
                    # text = limpiar_por_codigos(text1)
                    f_out.write(text + "\n\n")
                    logger.info(f"   💾 Texto de la página {page_num} guardado ({len(text)} chars).")
                except Exception as e:
                    logger.error(f"❌ Error al capturar o procesar la página {page_num}: {e}")
                    if DEBUG_SCREENSHOTS:
                        guardar_screenshot(f"logs/error_page_{page_num}.png")
                finally:
                    f_out.flush()
                if page_num < PAGINAS_A_PROCESAR:
                    log_section(logger, "NEXT_PAGE")
                    try:
                        logger.info("   ➡️ Avanzando a la siguiente página (click en next_arrow)...")
                        click_siguiente_pagina(driver, wait)
                        logger.info("   ✅ Página avanzada correctamente.")
                    except TimeoutException as te:
                        logger.warning(f"⚠️ Click 'siguiente' no funcionó: {te}. Fallback con teclado...")
                        try_keyboard_next(driver)
                        time.sleep(0.8)
                        try:
                            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#viewer .textLayer")))
                            logger.info("   ✅ Fallback teclado avanzó de página.")
                        except Exception:
                            logger.error("   ❌ No se pudo avanzar de página.")
                            break
                    except Exception as e:
                        logger.error(f"⚠️ Error al avanzar de página: {e}")
                        break
    except Exception as e:
        log_section(logger, "EXTRACT_ERROR")
        logger.error(f"❌ Error general durante la extracción: {e}")
        
    finally:
        log_section(logger, "CLEANUP")

        try:
            driver.quit()
        except Exception:
            pass
        
        logger.info(f"✅ Proceso completado. Texto guardado en: {OUTPUT_FILE}")


    logger.info(f"✅ Previsualización finalizada. Continuando con el siguiente paso.")
    return OUTPUT_FILE


if __name__ == "__main__":
    run_extractor()
