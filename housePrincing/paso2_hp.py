from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import math
from logger import get_logger
from dotenv import load_dotenv
import os 

log = get_logger("Paso2-Selenium")
load_dotenv()

# --- CONFIGURACIÓN ---
EMAIL = os.getenv("USUARIO_HP")
PASSWORD = os.getenv("PASSWORD_HP")
LOGIN_URL = os.getenv("LOGIN_URL")
BUSQUEDA_URL = os.getenv("BUSQUEDA_URL")

def calcular_distancia(lat1, lon1, lat2, lon2):
    """Calcula metros entre dos puntos (Fórmula de Haversine)"""
    if lat1 is None or lat2 is None: return 99999999
    
    R = 6371000 
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
    return int(R*c)

# CORRECCIÓN: Agregar cancel_event y LOGICA ROBUSTA DE PARSING
def parse_propiedades(html, cancel_event):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".hpid")
    
    resultados = []
    for card in cards:
        
        if cancel_event.is_set():
            return []
        try:
            # 1. Extracción de Atributos Crudos
            lat = card.get("data-lat")
            lng = card.get("data-lng")
            price_fmt = card.get("data-price-formatted")
            uf_m2_fmt = card.get("data-ufm2-formatted")
            
            # 2. Limpieza de datos numéricos
            m2_util = card.get("data-m2-formatted")
            m2_total = card.get("data-m2-total-formatted")
            
            # Construcción del objeto de datos con TODA LA INFO
            data = {
                # Identificadores
                "rol": card.get("data-rol"),
                "direccion": card.get("data-name"),
                "comuna": card.get("data-comuna"),
                "link": f"https://www.housepricing.cl/propiedad/{card.get('data-hash')}/",
                
                # Datos Geográficos
                "lat": float(lat) if lat else None,
                "lng": float(lng) if lng else None,
                
                # Datos Económicos
                "precio_uf": price_fmt,
                "uf_m2": uf_m2_fmt,
                "fecha_transaccion": card.get("data-date-trx"),
                
                # Características Físicas
                "anio": int(card.get("data-year")) if card.get("data-year") else 0,
                "m2_util": m2_util if m2_util else "0",
                "m2_total": m2_total if m2_total else "0",
                "dormitorios": card.get("data-bed"),
                "banios": card.get("data-bath"),
                
                # Placeholder para distancia (se calcula después)
                "distancia_metros": 999999
            }
            resultados.append(data)
        except:
            continue
    return resultados

# CORRECCIÓN: Agregar cancel_event
def _buscar_propiedad_individual(driver, wait, comuna_nombre, rol_target, cancel_event):
    """Lógica interna para buscar una sola propiedad en la sesión activa"""
    datos_retorno = {
        "lat_centro": None, 
        "lng_centro": None, 
        "resultados": [],
        "mensaje": "OK" 
    }
    
    try:
        # B. IR AL MAPA 
        driver.get(BUSQUEDA_URL)
        
        # C. CONFIGURAR BUSQUEDA
        select_tipo = wait.until(EC.element_to_be_clickable((By.ID, "search-type")))
        Select(select_tipo).select_by_value("rol")
        wait.until(EC.visibility_of_element_located((By.ID, "rol-container")))

        select_comuna = driver.find_element(By.ID, "select-comuna")
        driver.execute_script("arguments[0].style.display = 'block';", select_comuna)
        Select(select_comuna).select_by_visible_text(comuna_nombre)
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", select_comuna)
        time.sleep(2)

        input_rol = driver.find_element(By.ID, "inputRol")
        input_rol.clear()
        input_rol.send_keys(rol_target)
        
        driver.execute_script("arguments[0].click();", driver.find_element(By.ID, "btn-search-rol"))
        time.sleep(3)

        # D. ESPERAR RESULTADOS 
        if cancel_event.is_set(): return datos_retorno

        try:
            # Esperamos máximo 5 segundos para ver si aparece al menos un resultado
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "hpid")))
        except Exception:
            log.warning(f"⚠️ - No se encontraron resultados para Rol {rol_target} (0 registros).")
            datos_retorno["mensaje"] = "Sin resultados: Por favor revisar manualmente"
            return datos_retorno

        time.sleep(2) 

        # Extraer coordenadas del Centroide (Bounding Box)
        try:
            ne_lat = driver.find_element(By.NAME, "ne_lat").get_attribute("value")
            ne_lng = driver.find_element(By.NAME, "ne_lng").get_attribute("value")
            sw_lat = driver.find_element(By.NAME, "sw_lat").get_attribute("value")
            sw_lng = driver.find_element(By.NAME, "sw_lng").get_attribute("value")

            if ne_lat and sw_lat:
                datos_retorno["lat_centro"] = (float(ne_lat) + float(sw_lat)) / 2
                datos_retorno["lng_centro"] = (float(ne_lng) + float(sw_lng)) / 2
        except Exception:
            pass

        # E. FILTRAR POR AÑO (Más reciente primero)
        try:
            sort_select = wait.until(EC.element_to_be_clickable((By.ID, "sort-selector")))
            Select(sort_select).select_by_value("year_desc")
            time.sleep(2.5) # Esperar HTMX update
        except:
            log.warning("No se pudo aplicar el filtro de año (quizás solo hay 1 resultado).")

        if cancel_event.is_set(): return datos_retorno

        # F. PARSEAR Y ORDENAR POR DISTANCIA
        propiedades = parse_propiedades(driver.page_source, cancel_event)
        
        # Calcular distancias si tenemos el centro
        if datos_retorno["lat_centro"]:
            for p in propiedades:
                if cancel_event.is_set(): return datos_retorno
                p['distancia_metros'] = calcular_distancia(
                    datos_retorno["lat_centro"], datos_retorno["lng_centro"], 
                    p['lat'], p['lng']
                )
            # Ordenar por cercanía
            propiedades = sorted(propiedades, key=lambda x: x.get('distancia_metros', 999999))
        
        # Quedarse con los 10 mejores
        datos_retorno["resultados"] = propiedades[:10]
        
        if not datos_retorno["resultados"] and datos_retorno["mensaje"] == "OK":
             datos_retorno["mensaje"] = "Sin resultados: Por favor revisar manualmente"
        
    except Exception as e:
        log.error(f"Error crítico buscando {rol_target}: {e}")
        datos_retorno["mensaje"] = f"Error técnico: {str(e)}"
    
    return datos_retorno

# --- FUNCIÓN PRINCIPAL QUE PIDE EL MAIN ---
# CORRECCIÓN: Agregar cancel_event
def procesar_lista_propiedades(lista_propiedades, cancel_event):
    """
    Recibe la lista completa del Paso 1 (JSON), abre UNA sola sesión de navegador,
    itera todas las propiedades y devuelve la lista enriquecida.
    """
    log.info(f"Iniciando sesión Selenium para procesar {len(lista_propiedades)} propiedades...")
    
    options = Options()
    # options.add_argument("--headless=new") 
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)
    
    lista_enriquecida = []

    try:
        # 1. LOGIN ÚNICO
        log.info("Logueando en HousePricing...")
        if cancel_event.is_set(): 
            driver.quit(); return []

        driver.get(LOGIN_URL)
        wait.until(EC.presence_of_element_located((By.ID, "id_email"))).send_keys(EMAIL)
        driver.find_element(By.ID, "id_password").send_keys(PASSWORD)
        driver.execute_script("arguments[0].click();", driver.find_element(By.ID, "hp-login-btn"))
        wait.until(lambda d: "/login" not in d.current_url)
        log.info("Login exitoso.")
        time.sleep(2)

        # 2. ITERACIÓN
        for i, item in enumerate(lista_propiedades):
            if cancel_event.is_set():
                log.info("🛑 Proceso cancelado por usuario en Selenium.")
                return []
                
            rol = item.get("informacion_general", {}).get("rol")
            comuna = item.get("informacion_general", {}).get("comuna")
            
            if not rol or not comuna:
                log.warning(f"Saltando item {i}: Falta Rol o Comuna")
                lista_enriquecida.append(item) 
                continue

            log.info(f"[{i+1}/{len(lista_propiedades)}] Buscando: {comuna} - Rol {rol}")
            
            resultado_hp = _buscar_propiedad_individual(driver, wait, comuna, rol, cancel_event)
            
            valor_comparables = resultado_hp["resultados"]
            
            if not valor_comparables:
                valor_comparables = resultado_hp.get("mensaje", "Sin resultados")

            item["house_pricing"] = {
                "centro_mapa": {
                    "lat": resultado_hp["lat_centro"],
                    "lng": resultado_hp["lng_centro"]
                },
                "comparables": valor_comparables
            }
            
            lista_enriquecida.append(item)
            time.sleep(1) 

    except Exception as e:
        log.error(f"Error crítico en el bucle de Selenium: {e}")
    finally:
        driver.quit()
        log.info("Sesión Selenium cerrada.")

    return lista_enriquecida