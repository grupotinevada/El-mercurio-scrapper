############################################################################################################################
#  El paso 2 por medio de SELENIUM abrimos la pagina de House Princing para poder extraer las propiedades comparables del rol y comuna ingresado
#  Viaja por la pagina , ingresa los datos y extrae la data de las propiedades comparables
#  Guarda la data en el JSON proveniente del paso 1
############################################################################################################################

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import math

from logger import get_logger, log_section, dbg
logger = get_logger("paso2_hp", log_dir="logs", log_file="paso2_hp.log")

from dotenv import load_dotenv
import os 


load_dotenv()

# --- CONFIGURACIÓN ---
EMAIL = os.getenv("USUARIO_HP")
PASSWORD = os.getenv("PASSWORD_HP")
LOGIN_URL = os.getenv("LOGIN_URL")
BUSQUEDA_URL = os.getenv("BUSQUEDA_URL")

# ## NUEVO: Función para generar el link
def generar_link_maps(lat, lng):
    """Genera link directo a Google Maps con pin en la coordenada"""
    if not lat or not lng:
        return None
    # Formato estándar: https://www.google.com/maps?q=LAT,LNG
    return f"https://www.google.com/maps?q={lat},{lng}"

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
def parse_propiedades(html, cancel_event,fuente_actual):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".hpid")
    
    resultados = []
    for card in cards:
        
        if cancel_event.is_set():
            return []
        try:

            raw_name = card.get("data-name")                # Puede ser Calle o Link
            raw_display = card.get("data-display-name")     # El "Plan B" para la dirección
            # --- LLAMADA A LA FUNCIÓN AUXILIAR ---
            direccion_final, link_final = extraer_direccion_y_link(raw_name, raw_display)
            # -------------------------------------

            # 1. Extracción de Atributos Crudos
            lat_str = card.get("data-lat")
            lng_str = card.get("data-lng")
            price_fmt = card.get("data-price-formatted")
            uf_m2_fmt = card.get("data-ufm2-formatted")
            
            # 2. Limpieza de datos numéricos
            m2_util = card.get("data-m2-formatted")
            m2_total = card.get("data-m2-total-formatted")
            
            # Conversión segura a float para cálculos
            lat_float = float(lat_str) if lat_str else None
            lng_float = float(lng_str) if lng_str else None

            # Construcción del objeto de datos con TODA LA INFO
            data = {
                "fuente": fuente_actual,  # <--- Guardamos si es Compraventa u Oferta
                "rol": card.get("data-rol"),
                "direccion": direccion_final,
                "comuna": card.get("data-comuna"),
                "lat": lat_float,
                "lng": lng_float,
                "link_maps": generar_link_maps(lat_str, lng_str),
                "precio_uf": card.get("data-price-formatted"),
                "uf_m2": card.get("data-ufm2-formatted"),
                "fecha_transaccion": card.get("data-date-trx"),
                "anio": int(card.get("data-year")) if card.get("data-year") else 0,
                "m2_util": card.get("data-m2-formatted") or "0",
                "m2_total": card.get("data-m2-total-formatted") or "0",
                "dormitorios": card.get("data-bed"),
                "banios": card.get("data-bath"),
                "distancia_metros": 999999, # Se calcula fuera
                "link_publicacion": link_final,
            }
            resultados.append(data)
        except:
            continue
    return resultados

def extraer_direccion_y_link(raw_name, raw_display_name):   #Funcion auxiliar de _buscar_propiedad_individual , se encarga de determinar la direccion y el link de la propiedad
    """
    Analiza el atributo 'data-name' para determinar si es una dirección física o una URL.
    Retorna una tupla: (direccion_limpia, link_detectado)
    """
    # Validación básica por si viene None
    if not raw_name:
        return "Sin dirección", None

    # CASO OFERTA CON LINK (Ej: Maule)
    # Si empieza con http o www, asumimos que usaron el campo para una URL
    if raw_name.startswith("http") or "www." in raw_name:
        link = raw_name
        
        # Intentamos usar el display-name como dirección
        direccion = raw_display_name
        
        # Si display-name también está vacío o es None, usamos el texto por defecto que pediste
        if not direccion:
            direccion = "No hay dato, Ver publicacion"
            
        return direccion, link

    # CASO NORMAL / COMPRAVENTA (Ej: Puchuncaví)
    # Si no es link, asumimos que el dato es la dirección real
    else:
        direccion = raw_name
        link = None # No hay link en este campo
        return direccion, link


# CORRECCIÓN: Agregar cancel_event
def _buscar_propiedad_individual(driver, wait, comuna_nombre, tipo_target, rol_target, cancel_event):
    datos_retorno = {
        "lat_centro": None, 
        "lng_centro": None, 
        "resultados": [], # Aquí guardaremos la suma de ambos (hasta 20 items)
        "mensaje": "OK" 
    }
    
    try:
        # --- [BLOQUE A, B, C: BÚSQUEDA INICIAL IGUAL QUE ANTES] ---
        driver.get(BUSQUEDA_URL)
        
        select_tipo = wait.until(EC.element_to_be_clickable((By.ID, "search-type")))
        Select(select_tipo).select_by_value("rol")
        wait.until(EC.visibility_of_element_located((By.ID, "rol-container")))
        time.sleep(1)

        select_comuna = driver.find_element(By.ID, "select-comuna")
        driver.execute_script("arguments[0].style.display = 'block';", select_comuna)
        Select(select_comuna).select_by_visible_text(comuna_nombre)
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", select_comuna)
        time.sleep(1)

        input_rol = driver.find_element(By.ID, "inputRol")
        input_rol.clear()
        input_rol.send_keys(rol_target)
        time.sleep(1)
        
        select_prop_type = wait.until(EC.element_to_be_clickable((By.ID, "tipo_propiedad")))
        Select(select_prop_type).select_by_visible_text(tipo_target)
        logger.debug("[TEST WAIT UNTIL PASO 1 RETURN DOCUMENT READY STATE === COMPLETE] Esperando a que la página se cargue TIPO DE PROPIEDAD...")
        wait.until(lambda d: d.execute_script("return document.readyState === 'complete'"))
        logger.debug("[TEST WAIT UNTIL PASO 1 RETURN DOCUMENT READY STATE === COMPLETE] TIPO DE PROPIEDAD Document ready state: " + driver.execute_script("return document.readyState"))

        driver.execute_script("arguments[0].click();", driver.find_element(By.ID, "btn-search-rol"))
        logger.info(f"Buscando Rol: {rol_target}...")



        #--------------------------------------------------------------------------------
        logger.debug("[TEST WAIT UNTIL PASO 2 RETURN DOCUMENT READY STATE === COMPLETE] Esperando a que la página se cargue...")
        wait.until(lambda d: d.execute_script("return document.readyState === 'complete'"))
        logger.debug("[TEST WAIT UNTIL PASO 2 RETURN DOCUMENT READY STATE === COMPLETE] Document ready state: " + driver.execute_script("return document.readyState"))
        #--------------------------------------------------------------------------------
        # --- [ESPERA INICIAL Y CENTROIDE] ---
        try:
            WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.CLASS_NAME, "hpid")))
            time.sleep(3)
            
            # Capturamos centroide una sola vez (es el mismo para ambas fuentes)
            ne_lat = driver.find_element(By.NAME, "ne_lat").get_attribute("value")
            ne_lng = driver.find_element(By.NAME, "ne_lng").get_attribute("value")
            sw_lat = driver.find_element(By.NAME, "sw_lat").get_attribute("value")
            sw_lng = driver.find_element(By.NAME, "sw_lng").get_attribute("value")

            if ne_lat and sw_lat:
                datos_retorno["lat_centro"] = (float(ne_lat) + float(sw_lat)) / 2
                datos_retorno["lng_centro"] = (float(ne_lng) + float(sw_lng)) / 2
        except Exception:
            logger.warning(f"⚠️ - Sin resultados iniciales o error de carga para {rol_target}")
            datos_retorno["mensaje"] = "Sin resultados iniciales"
            return datos_retorno

        # --- [BLOQUE NUEVO: ITERAR FUENTES] ---
        lista_total = []
        fuentes_a_extraer = ["Compraventas", "Ofertas"] # <--- CONFIGURA AQUÍ LAS FUENTES
        
        for fuente_val in fuentes_a_extraer:
            if cancel_event.is_set(): return datos_retorno
            
            logger.info(f"--- Procesando fuente: {fuente_val} ---")
            
            try:
                # 1. Seleccionar la fuente en el combobox
                select_elem = wait.until(EC.element_to_be_clickable((By.ID, "fuente")))
                Select(select_elem).select_by_value(fuente_val)
                
                # Esperamos a que la página reaccione (HTMX/AJAX refresh)
                # Si la página pone un overlay de carga, lo ideal sería esperar a que desaparezca
                time.sleep(3) 

                # 2. Re-aplicar orden por año (por si el refresh reseteó el filtro)
                try:
                    sort_select = driver.find_element(By.ID, "sort-selector")
                    Select(sort_select).select_by_value("year_desc")
                    time.sleep(2) # Esperar reordenamiento
                except:
                    pass # Quizás no hay resultados suficientes para ordenar
                
                # 3. Parsear
                propiedades_raw = parse_propiedades(driver.page_source, cancel_event, fuente_val)
                
                # 4. Calcular distancias y ordenar ESTE lote
                if datos_retorno["lat_centro"]:
                    for p in propiedades_raw:
                        p['distancia_metros'] = calcular_distancia(
                            datos_retorno["lat_centro"], datos_retorno["lng_centro"], 
                            p['lat'], p['lng']
                        )
                    # Ordenar por cercanía
                    propiedades_raw = sorted(propiedades_raw, key=lambda x: x.get('distancia_metros', 999999))
                
                # 5. Cortar las mejores 10 de ESTA fuente y agregar
                mejores_10 = propiedades_raw[:10]
                lista_total.extend(mejores_10)
                
                logger.info(f"Se agregaron {len(mejores_10)} propiedades de {fuente_val}")

            except Exception as e:
                logger.error(f"Error procesando fuente {fuente_val}: {e}")
                # No hacemos return para intentar con la siguiente fuente si esta falla
        
        datos_retorno["resultados"] = lista_total
        
        if not datos_retorno["resultados"]:
             datos_retorno["mensaje"] = "Sin resultados en ninguna fuente"

    except Exception as e:
        logger.error(f"Error crítico buscando {rol_target}: {e}")
        datos_retorno["mensaje"] = f"Error técnico: {str(e)}"
    
    return datos_retorno

# --- FUNCIÓN PRINCIPAL QUE PIDE EL MAIN ---
# CORRECCIÓN: Agregar cancel_event
def procesar_lista_propiedades(lista_propiedades, cancel_event):
    """
    Recibe la lista completa del Paso 1 (JSON), abre UNA sola sesión de navegador,
    itera todas las propiedades y devuelve la lista enriquecida.
    """
    logger.info(f"Iniciando sesión Selenium para procesar {len(lista_propiedades)} propiedades...")
    
    options = Options()
    # options.add_argument("--headless=new") 
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)
    
    lista_enriquecida = []

    try:
        # 1. LOGIN ÚNICO
        logger.info("Logueando en HousePricing...")
        if cancel_event.is_set(): 
            driver.quit(); return []

        driver.get(LOGIN_URL)
        wait.until(EC.presence_of_element_located((By.ID, "id_email"))).send_keys(EMAIL)
        driver.find_element(By.ID, "id_password").send_keys(PASSWORD)
        driver.execute_script("arguments[0].click();", driver.find_element(By.ID, "hp-login-btn"))
        wait.until(lambda d: "/login" not in d.current_url)
        logger.info("Login exitoso.")
        time.sleep(2)

        # 2. ITERACIÓN
        for i, item in enumerate(lista_propiedades):
            if cancel_event.is_set():
                logger.info("🛑 Proceso cancelado por usuario en Selenium.")
                return []
            id = item.get("ID_Propiedad")    
            rol = item.get("informacion_general", {}).get("rol")
            comuna = item.get("informacion_general", {}).get("comuna")
            tipo = item.get("caracteristicas",{}).get("Tipo")
            
            logger.info(f"[{i+1}/{len(lista_propiedades)}] Procesando: {id} - {comuna} - {rol} - {tipo}")

            if not rol or not comuna:
                logger.warning(f"Saltando item {i}: Falta Rol o Comuna")
                lista_enriquecida.append(item) 
                continue

            logger.info(f"[{i+1}/{len(lista_propiedades)}] Buscando: {comuna} - Rol {rol}")
            
            resultado_hp = _buscar_propiedad_individual(driver, wait, comuna, tipo, rol, cancel_event)
            
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
        logger.error(f"Error crítico en el bucle de Selenium: {e}")
    finally:
        driver.quit()
        logger.info("Sesión Selenium cerrada.")

    return lista_enriquecida