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

log = get_logger("Paso2-Selenium")

# --- CONFIGURACIÓN ---
EMAIL = "barbara@grupohouse.cl"
PASSWORD = "Fliphouse"
LOGIN_URL = "https://www.housepricing.cl/login/"
BUSQUEDA_URL = "https://www.housepricing.cl/buscar-propiedades/mapa-rol/"

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

def parse_propiedades(html):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".hpid")
    
    resultados = []
    for card in cards:
        try:
            lat = card.get("data-lat")
            lng = card.get("data-lng")
            
            data = {
                "rol": card.get("data-rol"),
                "direccion": card.get("data-name"),
                "precio_uf": card.get("data-price-formatted"),
                "anio": int(card.get("data-year")) if card.get("data-year") else 0,
                "lat": float(lat) if lat else None,
                "lng": float(lng) if lng else None,
                "link": f"https://www.housepricing.cl/propiedad/{card.get('data-hash')}/"
            }
            resultados.append(data)
        except:
            continue
    return resultados

def _buscar_propiedad_individual(driver, wait, comuna_nombre, rol_target):
    """Lógica interna para buscar una sola propiedad en la sesión activa"""
    datos_retorno = {
        "lat_centro": None, 
        "lng_centro": None, 
        "resultados": [],
        "mensaje": "OK"
    }
    
    try:
        # B. IR AL MAPA (Refresh para limpiar estado anterior)
        driver.get(BUSQUEDA_URL)
        
        # C. CONFIGURAR BUSQUEDA
        select_tipo = wait.until(EC.element_to_be_clickable((By.ID, "search-type")))
        Select(select_tipo).select_by_value("rol")
        wait.until(EC.visibility_of_element_located((By.ID, "rol-container")))

        select_comuna = driver.find_element(By.ID, "select-comuna")
        driver.execute_script("arguments[0].style.display = 'block';", select_comuna)
        Select(select_comuna).select_by_visible_text(comuna_nombre)
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", select_comuna)
        time.sleep(2.5)

        input_rol = driver.find_element(By.ID, "inputRol")
        input_rol.clear()
        input_rol.send_keys(rol_target)
        
        driver.execute_script("arguments[0].click();", driver.find_element(By.ID, "btn-search-rol"))
        time.sleep(2.5)

        # D. ESPERAR RESULTADOS (Manejo de 0 resultados)
        try:
            # Esperamos máximo 5 segundos para ver si aparece al menos un resultado
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "hpid")))
        except Exception:
            # Si falla el wait, significa que no aparecieron resultados
            log.warning(f"⚠️ No se encontraron resultados para Rol {rol_target} (0 registros).")
            datos_retorno["mensaje"] = "Sin resultados: Por favor revisar manualmente"
            return datos_retorno

        time.sleep(2) # Estabilizar mapa si encontró algo

        # Extraer coordenadas
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

        # E. FILTRAR POR AÑO
        try:
            sort_select = wait.until(EC.element_to_be_clickable((By.ID, "sort-selector")))
            Select(sort_select).select_by_value("year_desc")
            time.sleep(3.5)
        except:
            log.warning("No se pudo aplicar el filtro de año (quizás solo hay 1 resultado).")

        # F. PARSEAR Y ORDENAR POR DISTANCIA
        propiedades = parse_propiedades(driver.page_source)
        
        if datos_retorno["lat_centro"]:
            for p in propiedades:
                p['distancia_metros'] = calcular_distancia(
                    datos_retorno["lat_centro"], datos_retorno["lng_centro"], 
                    p['lat'], p['lng']
                )
            propiedades = sorted(propiedades, key=lambda x: x.get('distancia_metros', 999999))
        
        datos_retorno["resultados"] = propiedades[:10]
        
    except Exception as e:
        log.error(f"Error crítico buscando {rol_target}: {e}")
        datos_retorno["mensaje"] = f"Error técnico: {str(e)}"
    
    return datos_retorno

# --- FUNCIÓN PRINCIPAL QUE PIDE EL MAIN ---
def procesar_lista_propiedades(lista_propiedades):
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
        driver.get(LOGIN_URL)
        wait.until(EC.presence_of_element_located((By.ID, "id_email"))).send_keys(EMAIL)
        driver.find_element(By.ID, "id_password").send_keys(PASSWORD)
        driver.execute_script("arguments[0].click();", driver.find_element(By.ID, "hp-login-btn"))
        wait.until(lambda d: "/login" not in d.current_url)
        log.info("Login exitoso.")
        time.sleep(2.5)
        # 2. ITERACIÓN
        for i, item in enumerate(lista_propiedades):
            # Extraer datos del JSON plano generado en Paso 1
            rol = item.get("informacion_general", {}).get("rol")
            comuna = item.get("informacion_general", {}).get("comuna")
            
            if not rol or not comuna:
                log.warning(f"Saltando item {i}: Falta Rol o Comuna")
                lista_enriquecida.append(item) # Se agrega sin cambios
                continue

            log.info(f"[{i+1}/{len(lista_propiedades)}] Buscando: {comuna} - Rol {rol}")
            
            # Llamar a la lógica de búsqueda reutilizando el driver
            resultado_hp = _buscar_propiedad_individual(driver, wait, comuna, rol)
            
            # ANEXAR AL JSON ORIGINAL
            item["house_pricing"] = {
                "centro_mapa": {
                    "lat": resultado_hp["lat_centro"],
                    "lng": resultado_hp["lng_centro"]
                },
                "comparables": resultado_hp["resultados"]
            }
            
            lista_enriquecida.append(item)
            time.sleep(1) # Pausa entre consultas

    except Exception as e:
        log.error(f"Error crítico en el bucle de Selenium: {e}")
        # Devolvemos lo que hayamos logrado procesar hasta el error
    finally:
        driver.quit()
        log.info("Sesión Selenium cerrada.")

    return lista_enriquecida