# paso1.py - Encapsulado para uso desde otros módulos
# EXTRACTOR DE REMATES JUDICIALES

def run_extractor():
    from logger import get_logger, log_section, dbg

    logger = get_logger("paso1", log_dir="logs", log_file="paso1.log")
    logger.info("Ejecutando Paso 1...")

    import os
    import sys
    import time
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

    # --------------------------------------------------------------------------
    # CONFIGURACIÓN DEL NAVEGADOR
    # --------------------------------------------------------------------------
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    service = Service(log_path="logs/chromedriver.log")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])  # Quita WARNINGs de absl
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])  # Opcional, quita banner "Chrome is being controlled...
    
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 25)

    URL = "https://digital.elmercurio.com/2025/08/10/F/S64IHN2V#zoom=page-width"
    EMAIL = "barbara@grupohouse.cl"
    PASSWORD = "Fliphouse"
    PAGINAS_A_PROCESAR = 5
    OUTPUT_FILE = "remates_extraidos.txt"
    DEBUG_SCREENSHOTS = True

    def modo_predeterminado():
        marco_horizontal = "═" * 50
        logger.info("\n╔%s╗", marco_horizontal)
        logger.info("║         🔨  Modo de extracción predeterminado         ║")
        logger.info("╠%s╣", marco_horizontal)
        logger.info("║   Se usará la opción:                                 ║")
        logger.info("║   2. Extraer texto directamente desde HTML           ║")
        logger.info("╚%s╝", marco_horizontal)
        input("Presione ENTER para comenzar...")

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

    def capture_text_from_textlayer(viewer_div):
        text_layer = viewer_div.find_element(By.CLASS_NAME, "textLayer")
        divs = text_layer.find_elements(By.TAG_NAME, "div")
        text = "\n".join(div.text for div in divs if div.text.strip())
        return text_layer, text

    # LOGIN
    log_section(logger, "LOGIN")
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
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#viewer .textLayer")))
                except Exception as e:
                    logger.error(f"❌ No se encontró viewer/textLayer: {e}")
                    if DEBUG_SCREENSHOTS:
                        guardar_screenshot(f"logs/error_page_{page_num}_viewer.png")
                    raise
                logger.info("   ✨ Extrayendo texto de la página...")
                f_out.write(f"--- Página {page_num} ---\n\n")
                try:
                    text_layer_elem, text = capture_text_from_textlayer(viewer_div)
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

    input(f"\n📄 Revisa el archivo '{OUTPUT_FILE}', haz cambios si es necesario.\nPresiona ENTER para continuar... ")
    return OUTPUT_FILE


if __name__ == "__main__":
    run_extractor()
