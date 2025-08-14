# EXTRACTOR DE REMATES JUDICIALES

import os
import sys
import time
import logging
from io import BytesIO
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    WebDriverException,
)

import pytesseract
from PIL import Image

# --------------------------------------------------------------------------
# CONFIGURACIÓN INICIAL
# --------------------------------------------------------------------------

# Directorios de logs y salida
os.makedirs("logs", exist_ok=True)

# Redirigir stderr a log
sys.stderr = open("logs/selenium_stderr.log", "w", encoding="utf-8")

# Logging (consola + archivo)
logger = logging.getLogger("remates")
logger.setLevel(logging.DEBUG)

fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

fh = logging.FileHandler("logs/run.log", encoding="utf-8")
fh.setLevel(logging.DEBUG)
fh.setFormatter(fmt)
logger.addHandler(fh)

sh = logging.StreamHandler(sys.stdout)
sh.setLevel(logging.INFO)
sh.setFormatter(fmt)
logger.addHandler(sh)

def log_section(name: str):
    logger.info("")
    logger.info("="*12 + f" [{name}] " + "="*12)

def dbg(msg: str):
    logger.debug(msg)

# Mostrar idiomas disponibles para Tesseract (debug)
try:
    dbg(f"Idiomas disponibles Tesseract: {pytesseract.get_languages(config='')}")
except Exception as e:
    logger.warning(f"No fue posible listar idiomas de Tesseract: {e}")

# Configuración de navegador
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
# chrome_options.add_argument("--disable-gpu")
# chrome_options.add_argument("--headless=new")  # Actívalo si quieres modo headless

service = Service(log_path="logs/chromedriver.log")
driver = webdriver.Chrome(service=service, options=chrome_options)
wait = WebDriverWait(driver, 25)

# Parámetros configurables
URL = "https://digital.elmercurio.com/2025/08/10/F/S64IHN2V#zoom=page-width"
EMAIL = "barbara@grupohouse.cl"
PASSWORD = "Fliphouse"
PAGINAS_A_PROCESAR = 6
OUTPUT_FILE = "remates_extraidos.txt"
DEBUG_SCREENSHOTS = True  # guarda screenshots en errores

# --------------------------------------------------------------------------
# ELECCIÓN DE MODO
# --------------------------------------------------------------------------
print("\nSeleccione el modo de extracción:")
print("1. OCR (captura de imagen y reconocimiento visual)")
print("2. Extraer texto directamente desde HTML (más rápido y preciso)")
modo_ocr = input("Ingrese 1 o 2: ").strip() == "1"

# --------------------------------------------------------------------------
# HELPERS
# --------------------------------------------------------------------------

def is_headless() -> bool:
    # heurística simple: en headless no hay tamaño de ventana real
    try:
        w = driver.get_window_size().get("width", 0)
        return w == 0
    except Exception:
        return True

def guardar_screenshot(path: str):
    try:
        driver.save_screenshot(path)
        logger.info(f"Screenshot guardado: {path}")
    except Exception as e:
        logger.warning(f"No se pudo guardar screenshot ({path}): {e}")

def click_siguiente_pagina(driver, wait):
    """
    Hace click en el botón 'siguiente' cuya estructura es:
    <a ...>
      <div class="next_arrow">
        <i class="fa fa-angle-right"></i>
      </div>
    </a>
    Usa varios métodos de click (normal y JS) y espera a que el textLayer cambie.
    """
    xpath_next = ("//a[.//div[contains(concat(' ', normalize-space(@class), ' '), ' next_arrow ') "
                  "and .//i[contains(@class,'fa-angle-right')]]]")
    # TextLayer actual para detectar cambio de página
    current_text_layer = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#viewer .textLayer")))
    dbg("textLayer actual referenciado para staleness_of.")

    # localizar el anchor clickeable
    next_anchor = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_next)))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", next_anchor)
    dbg("Siguiente anchor localizado y llevado a viewport.")

    # Intentos de click
    last_err = None
    for attempt in range(3):
        try:
            next_anchor.click()
            dbg(f"Click normal en 'siguiente' (intento {attempt+1}).")
            break
        except (ElementClickInterceptedException, StaleElementReferenceException, WebDriverException) as e:
            last_err = e
            dbg(f"Click normal falló (intento {attempt+1}): {e}. Reintentando...")
            time.sleep(0.4)
            # Re-localizar por si quedó stale
            try:
                next_anchor = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_next)))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", next_anchor)
            except Exception:
                pass
    else:
        # Fallback JS
        try:
            driver.execute_script("arguments[0].click();", next_anchor)
            dbg("Fallback: click por JavaScript ejecutado.")
        except Exception as e:
            raise TimeoutException(f"No se pudo hacer click en siguiente: {last_err or e}")

    # Esperar que el textLayer cambie (stale) y aparezca el nuevo
    wait.until(EC.staleness_of(current_text_layer))
    dbg("textLayer anterior quedó stale (cambio de página detectado).")
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#viewer .textLayer")))
    dbg("textLayer nuevo presente.")

def try_keyboard_next(driver):
    """Fallback de avance por teclado (flecha derecha) si el visor lo soporta."""
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.ARROW_RIGHT)
        dbg("Enviado Keys.ARROW_RIGHT como fallback.")
    except Exception as e:
        dbg(f"Fallback teclado no disponible: {e}")

def capture_text_from_textlayer(viewer_div):
    """Extrae texto concatenando los <div> dentro de .textLayer."""
    text_layer = viewer_div.find_element(By.CLASS_NAME, "textLayer")
    divs = text_layer.find_elements(By.TAG_NAME, "div")
    text = "\n".join(div.text for div in divs if div.text.strip())
    return text_layer, text

def capture_text_by_ocr(text_layer):
    """Hace screenshot del textLayer y ejecuta OCR spa."""
    # Ajuste de ventana al contenido
    scroll_width = driver.execute_script("return arguments[0].scrollWidth", text_layer)
    scroll_height = driver.execute_script("return arguments[0].scrollHeight", text_layer)
    try:
        driver.set_window_size(max(scroll_width + 100, 1280), max(scroll_height + 100, 800))
    except Exception:
        pass
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", text_layer)
    time.sleep(0.3)

    png = text_layer.screenshot_as_png
    image = Image.open(BytesIO(png))

    # Mostrar imagen solo si no es headless
    if not is_headless():
        try:
            image.show()
            input("Presiona Enter para continuar...")
        except Exception:
            pass

    dbg("Ejecutando OCR (lang='spa').")
    text = pytesseract.image_to_string(image, lang='spa')
    return text

# --------------------------------------------------------------------------
# LOGIN AUTOMÁTICO
# --------------------------------------------------------------------------

log_section("LOGIN")
try:
    logger.info(f"🌍 Navegando a: {URL}")
    driver.get(URL)

    logger.info("🔐 Esperando el formulario de login...")
    username_field = wait.until(EC.element_to_be_clickable((By.ID, "txtUsername")))
    password_field = driver.find_element(By.ID, "txtPassword")

    logger.info("🔑 Ingresando credenciales...")
    username_field.send_keys(EMAIL)
    password_field.send_keys(PASSWORD)

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
    sys.exit(1)
except Exception as e:
    logger.error(f"❌ Error inesperado durante el login: {e}")
    if DEBUG_SCREENSHOTS:
        guardar_screenshot("logs/error_login.png")
    driver.quit()
    sys.exit(1)

# --------------------------------------------------------------------------
# EXTRACCIÓN DE TEXTO
# --------------------------------------------------------------------------

log_section("EXTRACT")
logger.info("--- Iniciando proceso de extracción de texto ---")

try:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f_out:
        try:
            logger.info("   🖼 Activando modo HD (si existe botón)...")
            hd_button = wait.until(EC.element_to_be_clickable((By.ID, "active_pdf")))
            driver.execute_script("arguments[0].click();", hd_button)
            time.sleep(1)
            dbg("Botón HD clickeado.")
        except Exception as e:
            logger.info(f"   ⚠️ No se pudo activar modo HD (continuo): {e}")
        
        for page_num in range(1, PAGINAS_A_PROCESAR + 1):


            # PAGE_PREP: activar modo HD si está disponible
            log_section("PAGE_PREP")
            logger.info(f"📄 Procesando página {page_num}...")
            time.sleep(1) #cargar pagina 1
            # Obtener textLayer / viewer
            try:
                logger.info("   🔍 Buscando el contenedor #viewer y .textLayer...")
                viewer_div = wait.until(EC.presence_of_element_located((By.ID, "viewer")))
                # Espera explícita de textLayer presente
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#viewer .textLayer")))
            except Exception as e:
                logger.error(f"❌ No se encontró viewer/textLayer: {e}")
                if DEBUG_SCREENSHOTS:
                    guardar_screenshot(f"logs/error_page_{page_num}_viewer.png")
                raise

            # EXTRACT: escribir cabecera y extraer
            logger.info("   ✨ Extrayendo texto de la página...")
            f_out.write(f"--- Página {page_num} ---\n\n")

            try:
                if modo_ocr:
                    text_layer_elem = viewer_div.find_element(By.CLASS_NAME, "textLayer")
                    text = capture_text_by_ocr(text_layer_elem)
                else:
                    text_layer_elem, text = capture_text_from_textlayer(viewer_div)

                f_out.write(text + "\n\n")
                logger.info(f"   💾 Texto de la página {page_num} guardado ({len(text)} chars).")
            except Exception as e:
                logger.error(f"❌ Error al capturar o procesar la página {page_num}: {e}")
                if DEBUG_SCREENSHOTS:
                    guardar_screenshot(f"logs/error_page_{page_num}.png")
                # Continuar con intento de siguiente página aunque haya fallado extracción
                # para no frenar el batch completo
            finally:
                f_out.flush()

            # NEXT_PAGE: avanzar si faltan páginas
            if page_num < PAGINAS_A_PROCESAR:
                log_section("NEXT_PAGE")
                try:
                    logger.info("   ➡️ Avanzando a la siguiente página (click en next_arrow)...")
                    click_siguiente_pagina(driver, wait)
                    logger.info("   ✅ Página avanzada correctamente.")
                except TimeoutException as te:
                    logger.warning(f"⚠️ Click 'siguiente' no funcionó a tiempo: {te}. Intento fallback con teclado...")
                    try_keyboard_next(driver)
                    # Validar si cambió página con una espera corta (staleness o al menos nuevo textLayer)
                    try:
                        # sleep corto para permitir refresco del layer
                        time.sleep(0.8)
                        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#viewer .textLayer")))
                        logger.info("   ✅ Fallback teclado parece haber avanzado (textLayer presente).")
                    except Exception:
                        logger.error("   ❌ No se pudo avanzar de página tras fallback. Abortando.")
                        if DEBUG_SCREENSHOTS:
                            guardar_screenshot(f"logs/error_next_page_from_{page_num}.png")
                        break
                except Exception as e:
                    logger.error(f"⚠️ Error al avanzar de página: {e}")
                    if DEBUG_SCREENSHOTS:
                        guardar_screenshot(f"logs/error_next_page_from_{page_num}.png")
                    break

except Exception as e:
    log_section("EXTRACT_ERROR")
    logger.error(f"❌ Error general durante la extracción: {e}")
finally:
    log_section("CLEANUP")
    try:
        driver.quit()
    except Exception:
        pass
    logger.info(f"✅ Proceso completado. Texto guardado en: {OUTPUT_FILE}")
