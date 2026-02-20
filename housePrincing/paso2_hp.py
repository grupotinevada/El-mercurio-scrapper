############################################################################################################################
#  El paso 2 por medio de SELENIUM abrimos la pagina de House Princing para poder extraer las propiedades comparables del rol y comuna ingresado
#  Viaja por la pagina , ingresa los datos y extrae la data de las propiedades comparables
#  Guarda la data en el JSON proveniente del paso 1
############################################################################################################################
############################################################################################################################
#   ACUERDATE DE EJECUTAR EL PROCESO Y MANDAR EL LOG AL CHAT DE GEMINIS PARA QUE TE EVALUE LOS ERRORES Y SI ESTA FUNCIONANDO LA LOGICA QUE CREAMOS
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
from concurrent.futures import ThreadPoolExecutor # Para paralelismo

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
WORKERS = 2  # Estandarizado con Paso 0

logger.info(f"⚙️ Configuración cargada. Usuario: {EMAIL} | Workers: {WORKERS}")

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
    dist = int(R*c)
    # logger.debug(f"📏 Distancia calculada: {dist} mts") # Muy verborrágico, descomentar si es necesario
    return dist

# CORRECCIÓN: Agregar cancel_event y LOGICA ROBUSTA DE PARSING
def parse_propiedades(html, cancel_event,fuente_actual):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".hpid")
    
    logger.debug(f"   🧩 [BS4] Iniciando parsing HTML para '{fuente_actual}'. Cards detectadas: {len(cards)}")
    
    resultados = []
    for idx, card in enumerate(cards):
        
        if cancel_event.is_set():
            logger.warning("🛑 Parsing interrumpido por evento de cancelación.")
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
            rol = card.get("data-rol")
            comuna = card.get("data-comuna")
            fecha_transaccion = card.get("data-date-trx")
            # 2. Limpieza de datos numéricos
            m2_util = card.get("data-m2-formatted")
            m2_total = card.get("data-m2-total-formatted")
            dormitorios = card.get("data-bed")
            banios = card.get("data-bath")
            anio = int(card.get("data-year")) if card.get("data-year") else 0
            # Conversión segura a float para cálculos
            lat_float = float(lat_str) if lat_str else None
            lng_float = float(lng_str) if lng_str else None

            # Construcción del objeto de datos con TODA LA INFO
            data = {
                "fuente": fuente_actual,  # <--- Guardamos si es Compraventa u Oferta
                "rol": rol,
                "direccion": direccion_final,
                "comuna": comuna,
                "lat": lat_float,
                "lng": lng_float,
                "link_maps": generar_link_maps(lat_str, lng_str),
                "precio_uf": price_fmt,
                "uf_m2": uf_m2_fmt,
                "fecha_transaccion": fecha_transaccion,
                "anio": anio,
                "m2_util": m2_util or "0",
                "m2_total": m2_total or "0",
                "dormitorios": dormitorios,
                "banios": banios,
                "distancia_metros": 999999, 
                "link_publicacion": link_final,
            }
            resultados.append(data)
            # logger.debug(f"     ✅ Card parseada: Rol {rol} - {price_fmt}") 
        except Exception as e:
            logger.warning(f"     ⚠️ Error parseando card #{idx}: {e}")
            continue
            
    logger.debug(f"   ✨ [BS4] Parsing finalizado. {len(resultados)} propiedades extraídas correctamente.")
    return resultados

def extraer_direccion_y_link(raw_name, raw_display_name):   #Funcion auxiliar de _buscar_propiedad_individual , se encarga de determinar la direccion y el link de la propiedad
    """
    Analiza el atributo 'data-name' para determinar si es una dirección física o una URL.
    Retorna una tupla: (direccion_limpia, link_detectado)
    """
    # Validación básica por si viene None
    if not raw_name:
        return "Sin dirección", None

    if raw_name.startswith("http") or "www." in raw_name:
        link = raw_name
        direccion = raw_display_name
        if not direccion:
            direccion = "No hay dato, Ver publicacion"
        # logger.debug(f"       🔗 Link detectado en data-name: {link[:30]}...")
        return direccion, link
    else:
        direccion = raw_name
        link = None # No hay link en este campo
        return direccion, link


# CORRECCIÓN: Agregar cancel_event
def _buscar_propiedad_individual(driver, wait, comuna_nombre, tipo_target, rol_target, cancel_event):
    from selenium.common.exceptions import TimeoutException
    
    logger.info(f"🔎 Buscando: {comuna_nombre} | Rol: {rol_target} | Tipo: {tipo_target}")
    
    datos_retorno = {
        "lat_centro": None, 
        "lng_centro": None, 
        "resultados": [], 
        "mensaje": "OK" 
    }
    
    try:
        # --- [BLOQUE A, B, C: BÚSQUEDA INICIAL] ---
        driver.get(BUSQUEDA_URL)
        logger.debug(f"   ➡️ Navegando a URL de búsqueda...")
        
        select_tipo = wait.until(EC.element_to_be_clickable((By.ID, "search-type")))
        Select(select_tipo).select_by_value("rol")
        try:
            wait.until(EC.visibility_of_element_located((By.ID, "rol-container")))
        except TimeoutException:
            logger.warning(f"   ⚠️ Timeout esperando formulario para {rol_target}. Solicitando reintento...")
            raise
        # time.sleep(1) # Pequeña pausa eliminada, Selenium maneja el ritmo

        logger.debug("   🖱️ Seleccionando comuna...")
        select_comuna = driver.find_element(By.ID, "select-comuna")
        driver.execute_script("arguments[0].style.display = 'block';", select_comuna)
        Select(select_comuna).select_by_visible_text(comuna_nombre)
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", select_comuna)
        # time.sleep(1)

        logger.debug(f"   ⌨️ Ingresando Rol {rol_target}...")
        input_rol = driver.find_element(By.ID, "inputRol")
        input_rol.clear()
        input_rol.send_keys(rol_target)
        # time.sleep(1)
        
        select_prop_type = wait.until(EC.element_to_be_clickable((By.ID, "tipo_propiedad")))
        Select(select_prop_type).select_by_visible_text(tipo_target)
        
        # Esperamos a que la página esté "tranquila" antes de buscar
        wait.until(lambda d: d.execute_script("return document.readyState === 'complete'"))

        
        # 1. Capturar contenedor viejo
        lista_vieja = None
        try:
            # Usamos ID 'property_list' que vimos en tu imagen 2
            lista_vieja = driver.find_element(By.ID, "property_list")
            logger.debug(f"   👀 Contenedor viejo detectado (ID: {lista_vieja.id}).")
        except Exception:
            # Si por alguna razón no existe al inicio, esperamos que aparezca el nuevo directamente
            logger.debug("   👀 No se detectó contenedor viejo (limpio).")
            pass 

        # 2. Click en Buscar (Dispara el evento HTMX)
        logger.debug("   🖱️ Click en botón Buscar...")
        driver.execute_script("arguments[0].click();", driver.find_element(By.ID, "btn-search-rol"))
        logger.info(f"   🚀 Request enviado para Rol: {rol_target}...")

        # 3. Sincronización: Esperar el "Parpadeo" del contenedor
        try:
            # A) Si existía la lista vieja, esperar a que MUERA (se desvincule del DOM)
            if lista_vieja:
                wait.until(EC.staleness_of(lista_vieja))
                logger.debug("   🔄 Contenedor antiguo destruido (DOM Refresh iniciado).")
            
            # B) Esperar a que NAZCA la nueva lista (el servidor respondió)
            # Esto ocurrirá haya 0 o 100 resultados.
            nueva_lista = wait.until(EC.presence_of_element_located((By.ID, "property_list")))
            logger.debug("   🆕 Nuevo contenedor 'property_list' cargado exitosamente.")

            # 4. VERIFICACIÓN RÁPIDA DE RESULTADOS (Evitar Timeout si es 0)
            # En tu imagen se ve el atributo data-total-count="300"
            try:
                total_count = nueva_lista.get_attribute("data-total-count")
                if total_count and int(total_count) == 0:
                    logger.warning(f"   ⚠️ La búsqueda terminó correctamente pero hay 0 resultados (Data del sitio).")
                    datos_retorno["mensaje"] = "Sin resultados (Fuente oficial)"
                    # Intentamos sacar el centroide igual por si acaso el mapa se movió
                    # pero no entramos a buscar cards
                else:
                    logger.info(f"   🔢 Resultados encontrados según atributo: {total_count}")
            except:
                pass # Si no tiene el atributo, seguimos al método clásico

        except TimeoutException:
            logger.error("   ❌ Timeout esperando que se refresque #property_list.")
            datos_retorno["mensaje"] = "Error de carga (Timeout)"
            raise   

        # --- [EXTRACCIÓN DE CENTROIDE Y DATOS] ---
        # Solo intentamos buscar .hpid si sabemos que hay algo o si falló la lectura del count
        if datos_retorno["mensaje"] == "OK":
            try:
                # Damos un respiro mínimo para que el renderizado interno termine
                # (A veces el div padre está, pero los hijos tardan milisegundos en pintar)
                time.sleep(2) 
                
                ne_lat = driver.find_element(By.NAME, "ne_lat").get_attribute("value")
                ne_lng = driver.find_element(By.NAME, "ne_lng").get_attribute("value")
                sw_lat = driver.find_element(By.NAME, "sw_lat").get_attribute("value")
                sw_lng = driver.find_element(By.NAME, "sw_lng").get_attribute("value")

                if ne_lat and sw_lat:
                    datos_retorno["lat_centro"] = (float(ne_lat) + float(sw_lat)) / 2
                    datos_retorno["lng_centro"] = (float(ne_lng) + float(sw_lng)) / 2
                    logger.debug(f"   📍 Centroide calculado: {datos_retorno['lat_centro']:.5f}, {datos_retorno['lng_centro']:.5f}")
            except Exception:
                logger.warning(f"   ⚠️ No se pudieron extraer coordenadas del mapa para {rol_target}")

            # --- [BLOQUE ITERAR FUENTES] ---
            # Solo entramos aquí si NO detectamos 0 resultados arriba
            lista_total = []
            fuentes_a_extraer = ["Compraventas", "Ofertas"] 
            
            for fuente_val in fuentes_a_extraer:
                if cancel_event.is_set(): return datos_retorno
                
                logger.info(f"   --- 🔄 Cambiando a fuente: {fuente_val} ---")
                
                try:
                    # 1. Seleccionar la fuente (Esto TAMBIÉN refresca la lista, ojo)
                    
                    select_elem = wait.until(EC.element_to_be_clickable((By.ID, "fuente")))
                    Select(select_elem).select_by_value(fuente_val)
                    
                    # Esperamos recarga (Idealmente usar staleness aquí también, 
                    # pero un sleep de 3s suele bastar para el cambio de filtro secundario)
                    logger.debug(f"     ⏳ Esperando recarga de filtro {fuente_val}...")
                    time.sleep(3) 

                    # 2. Re-aplicar orden
                    try:
                        sort_select = driver.find_element(By.ID, "sort-selector")
                        Select(sort_select).select_by_value("year_desc")
                        time.sleep(2)
                        logger.debug("     🔽 Orden aplicado: Año descendente")
                    except:
                        logger.debug("     ℹ️ No se encontró selector de orden.")
                        pass 
                    
                    # 3. Parsear
                    propiedades_raw = parse_propiedades(driver.page_source, cancel_event, fuente_val)
                    
                    # 4. Calcular distancias
                    if datos_retorno["lat_centro"]:
                        logger.debug(f"     📐 Calculando distancias para {len(propiedades_raw)} propiedades...")
                        for p in propiedades_raw:
                            p['distancia_metros'] = calcular_distancia(
                                datos_retorno["lat_centro"], datos_retorno["lng_centro"], 
                                p['lat'], p['lng']
                            )
                        propiedades_raw = sorted(propiedades_raw, key=lambda x: x.get('distancia_metros', 999999))
                    
                    # 5. Cortar mejores 10
                    mejores_10 = propiedades_raw[:10]
                    lista_total.extend(mejores_10)
                    
                    logger.success(f"     📥 Se agregaron {len(mejores_10)} propiedades (Top 10 más cercanas) de {fuente_val}")

                except Exception as e:
                    logger.error(f"     ❌ Error procesando fuente {fuente_val}: {e}", exc_info=True)
            
            datos_retorno["resultados"] = lista_total
            
            if not datos_retorno["resultados"] and datos_retorno["mensaje"] == "OK":
                datos_retorno["mensaje"] = "Sin resultados en ninguna fuente"
                logger.warning("   ⚠️ Finalizado sin resultados en Compraventas ni Ofertas.")
    except Exception as e:
        raise e
    except Exception as e:
        logger.error(f"❌ Error crítico buscando {rol_target}: {e}", exc_info=True)
        datos_retorno["mensaje"] = f"Error técnico: {str(e)}"
    
    return datos_retorno

# ==============================================================================
# WORKER ESTANDARIZADO (CADA WORKER TIENE SU NAVEGADOR)
# ==============================================================================
def procesar_lote_worker(id_worker, sublista_propiedades, cancel_event):
    """
    Función Worker que se ejecuta en su propio hilo.
    Abre su navegador independiente, se loguea y procesa su sublista.
    """
    logger.info(f"👷 [Worker-{id_worker}] Iniciando sesión Selenium...")
    
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    
    prefs = {
        "profile.managed_default_content_settings.images": 2, # 2 = Bloquear
        "profile.default_content_setting_values.notifications": 2, # Bloquear notificaciones
        "profile.managed_default_content_settings.stylesheets": 2, # A veces rompe sitios, probar con cuidado (opcional)
    }
    options.add_experimental_option("prefs", prefs)
    options.page_load_strategy = 'eager'
    
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)
    
    lista_worker_enriquecida = []

    try:
        # 1. LOGIN
        logger.info(f"🔐 [Worker-{id_worker}] Logueando en HousePricing...")
        if cancel_event.is_set(): 
            driver.quit(); return []

        driver.get(LOGIN_URL)
        logger.debug(f"   ➡️ Navegando a URL de login...")
        wait.until(EC.presence_of_element_located((By.ID, "id_email"))).send_keys(EMAIL)
        logger.debug(f"   ➡️ Ingresando correo...")
        driver.find_element(By.ID, "id_password").send_keys(PASSWORD)
        logger.debug(f"   ➡️ Ingresando contraseña...")

        driver.execute_script("arguments[0].click();", driver.find_element(By.ID, "hp-login-btn"))
        logger.debug(f"   ➡️ Clickando botón de login...")
        wait.until(lambda d: "/login" not in d.current_url)
        logger.success(f"✅ [Worker-{id_worker}] Login exitoso.")
        logger.debug(f"   ➡️ Esperando que se refrezque la página...")
        time.sleep(2)

        # 2. ITERACIÓN
        for i, item in enumerate(sublista_propiedades):
            if cancel_event.is_set():
                logger.info(f"🛑 [Worker-{id_worker}] Proceso cancelado.")
                break
            
            id_prop = item.get("ID_Propiedad")    
            rol = item.get("informacion_general", {}).get("rol")
            comuna = item.get("informacion_general", {}).get("comuna")
            tipo = item.get("caracteristicas",{}).get("Tipo")
            
            logger.info(f"🏁 [Worker-{id_worker}] Procesando: {comuna} | Rol: {rol}")

            if not rol or not comuna:
                logger.warning(f"⏩ [Worker-{id_worker}] Saltando item sin datos.")
                lista_worker_enriquecida.append(item) 
                continue
            
            resultado_hp = None
            MAX_INTENTOS = 3

            for intento in range(MAX_INTENTOS):
                if cancel_event.is_set(): break
                try:
                    # Intento de búsqueda
                    resultado_hp = _buscar_propiedad_individual(driver, wait, comuna, tipo, rol, cancel_event)
                    break # Si llega aquí, fue éxito (o error controlado no crítico)
                
                except Exception as e:
                    # Capturamos TimeoutException y otros errores de red
                    if intento < MAX_INTENTOS - 1:
                        logger.warning(f"🔄 [Worker-{id_worker}] Fallo intento {intento+1}/{MAX_INTENTOS} para {rol}. Reintentando en 5s... (Error: {e})")
                        time.sleep(3) # Espera de enfriamiento
                        try: driver.refresh() # Refrescar por si acaso
                        except: pass
                    else:
                        logger.error(f"💀 [Worker-{id_worker}] Fallo definitivo para {rol} tras {MAX_INTENTOS} intentos.")
                        resultado_hp = {
                            "lat_centro": None, "lng_centro": None, 
                            "resultados": [], 
                            "mensaje": f"Error Técnico Persistente: {str(e)}"
                        }

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
            
            lista_worker_enriquecida.append(item)
            time.sleep(1) 

    except Exception as e:
        logger.error(f"💀 [Worker-{id_worker}] Error crítico: {e}", exc_info=True)
    finally:
        driver.quit()
        logger.info(f"👋 [Worker-{id_worker}] Sesión cerrada.")

    return lista_worker_enriquecida

# ==============================================================================
# ORQUESTADOR PRINCIPAL (ESTANDARIZADO CON PASO 0)
# ==============================================================================
def procesar_lista_propiedades(lista_propiedades, cancel_event):
    """
    Orquestador que divide la lista y lanza workers en paralelo.
    """
    total = len(lista_propiedades)
    if total == 0: return []
    
    logger.info(f"🚀 Iniciando orquestador Selenium PARALELO para {total} propiedades. WORKERS={WORKERS}")
    
    # División en chunks (igual que Paso 0)
    chunk_size = math.ceil(total / WORKERS)
    chunks = [lista_propiedades[i:i + chunk_size] for i in range(0, total, chunk_size)]
    
    lista_final_consolidada = []

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = []
        for i, chunk in enumerate(chunks):
            futures.append(executor.submit(procesar_lote_worker, i+1, chunk, cancel_event))
        
        # Recolección de resultados
        for future in futures:
            try:
                res_worker = future.result()
                lista_final_consolidada.extend(res_worker)
            except Exception as e:
                logger.error(f"❌ Error en worker: {e}")
            
    logger.success(f"🏁 Proceso finalizado. Propiedades procesadas: {len(lista_final_consolidada)}/{total}")     
    return lista_final_consolidada