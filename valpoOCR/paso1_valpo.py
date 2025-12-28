import os
import time
import shutil
import tempfile
import requests
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Importamos el logger
from logger import get_logger, log_section, dbg


# --- CONTROLADOR PRINCIPAL ---
def run_extractor_ocr(url: str, paginas: int):
    logger = get_logger("paso1_valpo", log_dir="logs", log_file="paso1_valpo.log")
    logger.info("🌊 Iniciando Extractor Valparaíso (Modo OCR)...")

    load_dotenv()
    USUARIO = os.getenv("USUARIO")
    PASSWORD = os.getenv("PASSWORD")

    output_dir = "temp_img_valpo"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    chrome_options = Options()
    clean_profile_path = os.path.join(tempfile.gettempdir(), "chrome_profile_valpo_clean")
    if os.path.exists(clean_profile_path):
        try: shutil.rmtree(clean_profile_path)
        except: pass 
            
    chrome_options.add_argument(f"--user-data-dir={clean_profile_path}")
    chrome_options.add_argument("--incognito")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--log-level=3")
    
    service = Service(log_path="logs/chromedriver_valpo.log")
    driver = None
    lista_imagenes_descargadas = []

    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        wait = WebDriverWait(driver, 20)

        log_section(logger, "LOGIN")
        driver.get(url)
        try:
            modal_selector = "div.modal-dialog"
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, modal_selector)))
            logger.info("🔐 Logueando...")
            driver.find_element(By.CSS_SELECTOR, f"{modal_selector} input[placeholder*='correo']").send_keys(USUARIO)
            driver.find_element(By.CSS_SELECTOR, f"{modal_selector} input[type='password']").send_keys(PASSWORD)
            btn = driver.find_element(By.CSS_SELECTOR, f"{modal_selector} button[type='submit']")
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(2)
        except TimeoutException:
            logger.warning("⚠️ Modal login no apareció (continuando...)")
        
        log_section(logger, "DESCARGA")
        for page_num in range(1, paginas + 1):
            logger.info(f"📄 Procesando página {page_num} de {paginas}")
            ruta_img = busquedaImagen(driver, page_num, output_dir, logger)
            if ruta_img:
                lista_imagenes_descargadas.append(ruta_img)
            if page_num < paginas:
                navegar_siguiente_pagina(driver, logger)



        logger.info(f"✅ Proceso Paso 1 finalizado. {len(lista_imagenes_descargadas)} imágenes en memoria.")
        
        # RETORNAMOS LA LISTA (Memoria) Y LA RUTA DEL TXT (Debug/Cleanup)
        return lista_imagenes_descargadas, None

    except Exception as e:
        logger.error(f"❌ Error crítico: {e}")
        raise e
    finally:
        if driver:
            driver.quit()

# --- FUNCIÓN DE DESCARGA (Opción 1: Headers Referer) ---
def busquedaImagen(driver, page_num, output_dir, logger):
    """
    Busca la imagen y la guarda renombrándola con el número de secuencia (1.jpg, 2.jpg...).
    """
    try:
        logger.info(f"   🔎 Buscando imagen de la página {page_num}...")
        
        # Esperar a que la imagen 'img-page' sea visible
        img_element = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "img.img-page"))
        )
        img_url = img_element.get_attribute("src")
        current_page_url = driver.current_url
        
        if not img_url:
            raise ValueError("Src vacío.")

        # Preparar sesión (Cookies + Headers)
        session = requests.Session()
        selenium_cookies = driver.get_cookies()
        for cookie in selenium_cookies:
            session.cookies.set(cookie['name'], cookie['value'])
        
        headers = {
            "User-Agent": driver.execute_script("return navigator.userAgent;"),
            "Referer": current_page_url,
            "Origin": "https://www.mercuriovalpo.cl",
            "Accept": "image/*"
        }

        # Descargar
        response = session.get(img_url, headers=headers, stream=True)
        
        if response.status_code == 200:
            filename = f"{page_num}.jpg" # Nombre simple: 1.jpg, 2.jpg...
            file_path = os.path.join(output_dir, filename)
            
            with open(file_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)
            
            logger.info(f"   💾 Guardada: {filename}")
            return file_path
        else:
            logger.error(f"   ❌ Fallo descarga (Status {response.status_code})")
            return None

    except Exception as e:
        logger.error(f"   ❌ Error en página {page_num}: {e}")
        return None




def navegar_siguiente_pagina(driver, logger):
    """
    Avanza a la siguiente página usando el botón 'icon-next'.
    """
    try:
        logger.info("   ➡️ Buscando botón 'Siguiente'...")
        
        # Selector basado en tu captura: <a class="icon icon-next">
        selector_next = "a.icon-next"
        
        # Esperar a que sea clickeable
        btn_next = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector_next))
        )
        
        # Usamos JavaScript para el click (más robusto en visores con capas)
        driver.execute_script("arguments[0].click();", btn_next)
        
        logger.info("   ⏳ Cambiando página...")
        
        # Espera técnica para dar tiempo a que el DOM cambie y la nueva imagen inicie carga
        time.sleep(2) 

    except Exception as e:
        logger.warning(f"⚠️ No se pudo avanzar a la siguiente página (¿Fin del diario?): {e}")
        raise e