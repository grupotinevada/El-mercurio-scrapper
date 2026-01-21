import requests
import pandas as pd
import math
import time
import random
import unicodedata
from datetime import datetime, timedelta 
import re 
import backoff
from logger import get_logger
import os

logger = get_logger("macal", log_dir="logs", log_file="macal.log")

TEST_MODE = False 
TEST_LIMIT = 3
MIN_DELAY = 2
MAX_DELAY = 5

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/115.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; rv:102.0) Gecko/20100101 Firefox/102.0",
]

BASE_HEADERS = {
    'Accept-Language': 'es-CL,es;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.macal.cl/',
    'Connection': 'keep-alive'
}

# --- Wrapper robusto ---
@backoff.on_exception(
    backoff.expo,
    (requests.exceptions.RequestException),
    max_tries=5,
    jitter=None
)

def robust_get(session, url, **kwargs):
    headers = BASE_HEADERS.copy()
    headers["User-Agent"] = random.choice(USER_AGENTS)
    kwargs["headers"] = {**session.headers, **headers}

    response = session.get(url, timeout=(5, 15), **kwargs)

    if response.status_code == 429:
        wait = int(response.headers.get("Retry-After", 60))
        logger.warning(f"⚠️ Rate limit alcanzado, esperando {wait}s...")
        time.sleep(wait)
        return robust_get(session, url, **kwargs)


    if 500 <= response.status_code < 600:
        logger.warning(f"⚠️ Error {response.status_code} en {url}, reintentando...")
        raise requests.exceptions.RequestException(f"Server error {response.status_code}")

    response.raise_for_status()
    return response

# --- Helpers ---
def _normalize_key(text):
    if not text:
        return ""
    
    s = text.lower().strip().replace(' ', '_')
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

    if 'rol' in s and 'avaluo' in s:
        return 'rol_de_avaluo'
    
    if 'superficie_total' in s or 'superficie_terreno' in s:
        return 'superficie_terreno'
    if 'superficie_util' in s or 'superficie_construida' in s:
        return 'superficie_util'
    
    s = s.replace('/', '_').replace(':', '').replace('-', '_')
    
    return s

def _flatten_features(feature_list):
    """
    Aplana la lista de características. 
    NOTA: Se eliminó el check de cancel_event aquí por ser una operación atómica muy rápida.
    """
    flat_dict = {}
    if not feature_list or not isinstance(feature_list, list):
        return flat_dict
    for item in feature_list:
        if item and 'label' in item and 'value' in item:
            key = _normalize_key(item.get('label', ''))
            value = item.get('value', '').strip()
            if key:
                flat_dict[key] = value
    return flat_dict

def _calculate_estimated_payment_date(property_info: dict) -> str:
    """
    Calcula la fecha de pago estimada basándose en la fecha de remate y el plazo.
    """
    default_message = "No se pudo calcular"
    try:
        fecha_remate_str = property_info.get('fecha_remate')
        plazo_pago_str = property_info.get('plazo_de_pago')

        if not fecha_remate_str or not plazo_pago_str or \
           fecha_remate_str == "No se encontró" or plazo_pago_str == "No se encontró":
            return default_message

        base_date = datetime.strptime(fecha_remate_str, "%d/%m/%Y")

        match = re.search(r'\d+', plazo_pago_str)
        if not match:
            return plazo_pago_str 
        
        days_to_add = int(match.group(0))
        estimated_date = base_date + timedelta(days=days_to_add)
        return estimated_date.strftime("%d/%m/%Y")

    except Exception as e:
        logger.warning(f"No se pudo calcular la fecha de pago estimada. Error: {e}")
        return default_message

def update_excel_with_new_properties(output_filename: str, new_data: list, id_field: str = "url_propiedad"):
    if not new_data:
        logger.info("No hay nuevas propiedades para agregar.")
        return None

    # --- CORRECCIÓN: Crear directorio si no existe ---
    directory = os.path.dirname(output_filename)
    if directory and not os.path.exists(directory):
        try:
            os.makedirs(directory)
            logger.info(f"Directorio creado: {directory}")
        except OSError as e:
            logger.error(f"Error al crear el directorio {directory}: {e}")
            return None
    # -------------------------------------------------

    df_new = pd.DataFrame(new_data)

    if not os.path.exists(output_filename):
        df_new.to_excel(output_filename, index=False, engine='openpyxl')
        logger.info(f"Archivo creado con {len(df_new)} propiedades nuevas.")
        return df_new

    try:
        df_existing = pd.read_excel(output_filename)

        if id_field in df_existing.columns:
            existing_ids = set(df_existing[id_field].astype(str))
        else:
            existing_ids = set()
        
        df_new_unique = df_new[~df_new[id_field].astype(str).isin(existing_ids)]

        if df_new_unique.empty:
            logger.info("Todas las propiedades nuevas ya estaban en el archivo.")
            return df_existing
        
        all_cols = pd.Index(df_existing.columns).union(df_new_unique.columns)
        
        df_existing_aligned = df_existing.reindex(columns=all_cols)
        df_new_unique_aligned = df_new_unique.reindex(columns=all_cols)

        df_final = pd.concat([df_existing_aligned, df_new_unique_aligned], ignore_index=True)
        df_final.to_excel(output_filename, index=False, engine='openpyxl')

        logger.info(f"Archivo actualizado con {len(df_new_unique)} propiedades nuevas (total: {len(df_final)}).")
        return df_final

    except Exception as e:
        logger.error(f"Error al actualizar el archivo Excel: {e}")
        return None

# --- Función principal ---
# CORRECCIÓN: Se agrega cancel_event como argumento
def run_extractor_macal(search_url: str, details_url: str, output_folder: str, cancel_event, progress_callback=None):
    start_time = time.perf_counter()
    session = requests.Session()
    all_property_ids = []
    
    failed_ids = []

    if progress_callback:
        progress_callback(0, "Obteniendo lista de propiedades...")
    
    logger.info("Iniciando la obtención de IDs de propiedades...")
    try:
        params_initial = {'page': 1, 'tipoOrden': 0, 'hasFilters': 'false'}
        response = robust_get(session, search_url, params=params_initial)
        data = response.json()
        total_entries = data.get("total_entries", 0)
        per_page = data.get("per_page", 18) or 18
        total_pages = math.ceil(total_entries / per_page)
        logger.info(f"Se encontraron {total_entries} propiedades en {total_pages} páginas.")

        for page in range(1, total_pages + 1):
            if cancel_event.is_set():
                logger.info("🛑 Proceso cancelado por usuario.")
                return

            if TEST_MODE and len(all_property_ids) >= TEST_LIMIT:
                break
            logger.info(f"Obteniendo IDs de la página {page}/{total_pages}...")
            params_page = {'page': page, 'tipoOrden': 0, 'hasFilters': 'false'}
            response = robust_get(session, search_url, params=params_page)
            page_data = response.json().get("entries", [])
            for prop in page_data:
                if cancel_event.is_set():
                    return
                if 'id' in prop:
                    all_property_ids.append(prop['id'])
            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
    except Exception as e:
        end_time = time.perf_counter()
        logger.error(f"Error crítico al obtener la lista de propiedades: {e}")
        logger.info(f"Tiempo total transcurrido: {(end_time - start_time)/60:.2f} minutos.")
        return None

    if TEST_MODE:
        logger.warning(f"MODO DE PRUEBA ACTIVO: Se procesarán solo las primeras {TEST_LIMIT} propiedades.")
        all_property_ids = all_property_ids[:TEST_LIMIT]

    extracted_data = []
    total_ids = len(all_property_ids)
    logger.info(f"Iniciando extracción de detalles para {total_ids} propiedades...")
    
    if total_ids == 0:
        if progress_callback:
            progress_callback(100, "No se encontraron propiedades para procesar.")
        end_time = time.perf_counter()
        logger.warning("No se encontraron propiedades para procesar.")
        logger.info(f"Tiempo total transcurrido: {(end_time - start_time)/60:.2f} minutos.")
        return pd.DataFrame()
    
    for i, prop_id in enumerate(all_property_ids):
        if cancel_event.is_set():
            logger.info("🛑 Proceso cancelado por usuario.")
            return

        if progress_callback:
            porcentaje = int(((i + 1) / total_ids) * 100)
            mensaje = f"Procesando propiedad {i + 1} de {total_ids}..."
            progress_callback(porcentaje, mensaje)
            
        logger.info(f"Procesando propiedad {i+1}/{total_ids} (ID: {prop_id})...")
        try:
            params_details = {'id': prop_id}
            response = robust_get(session, details_url, params=params_details)
            details = response.json()

            raw_auction_date = details.get("auction", {}).get("auction_date")
            formatted_date = "No se encontró"
            if raw_auction_date:
                try:
                    date_obj = datetime.strptime(raw_auction_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                    formatted_date = date_obj.strftime("%d/%m/%Y")
                except ValueError:
                    formatted_date = raw_auction_date.split('T')[0]
                    logger.warning(f"Formato de fecha inesperado para la propiedad ID {prop_id}: {raw_auction_date}.")

            price_info = details.get("property_price", {})
            property_info = {
                "direccion": details.get("property_name", "No se encontró"),
                "comuna": details.get('property_location', {}).get('commune', 'No se encontró'),
                "ciudad": details.get('property_location', {}).get('city', 'No se encontró'),
                "region": details.get('property_location', {}).get('region', 'No se encontró'),
                "tipo_propiedad": details.get("property_type", "No se encontró"),
                "precio_minimo": f"{price_info.get('price', 'N/A')} {price_info.get('price_type', '')}".strip(), 
                "garantia_clp": details.get("warranty_price", "No se encontró"),
                "fecha_remate": formatted_date,
                "descripcion": (details.get("property_description") or "No se encontró").strip(),
                "url_propiedad": f"https://www.macal.cl/propiedades/{prop_id}"
            }
            general_features_flat = _flatten_features(details.get("general_features") or [])
            other_features_flat = _flatten_features(details.get("other_features") or [])
            specific_features_flat = _flatten_features(details.get("specific_features") or [])

            all_features = {
                **general_features_flat, 
                **specific_features_flat, 
                **other_features_flat
            }
            property_info.update(all_features)
            property_info['fecha_pago_estimado(fecha_remate + plazo_de_pago)'] = _calculate_estimated_payment_date(property_info)

            extracted_data.append(property_info)
            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
            
        except Exception as e:
            logger.error(f"Error al obtener detalles para la propiedad ID {prop_id}: {e}")
            failed_ids.append(prop_id) 
            continue

    if not extracted_data:
        logger.warning("El proceso finalizó sin datos nuevos para procesar.")
        return None

    df = pd.DataFrame(extracted_data)
    try:       
        preferred_order = [
            'descripcion','direccion', 'comuna', 'ciudad', 'region', 'tipo_propiedad', 'precio_minimo', 
            'fecha_remate', 'plazo_de_pago', 'fecha_pago_estimado(fecha_remate + plazo_de_pago)', 
            'garantia_clp', 'superficie_terreno', 'superficie_util', 
            'dormitorios', 'banos', 'cocina', 'estacionamiento', 'bodega',
            'disponibilidad', 'mandante', 'liquidador', 'rol_de_avaluo','rol_causa', 'uso_de_suelo',
            'url_propiedad'
        ]
        final_columns_ordered = [col for col in preferred_order if col in df.columns]
        remaining_columns = sorted([col for col in df.columns if col not in final_columns_ordered])
        
        df = df[final_columns_ordered + remaining_columns]

        # --- CAMBIO: Generar nombre de archivo con fecha y hora ---
        # Si output_folder viene vacía, usa la carpeta actual
        if not output_folder:
            output_folder = "."
        
        # Crear carpeta si no existe
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"propiedades_macal_{timestamp}.xlsx"
        full_path = os.path.join(output_folder, filename)

        df.to_excel(full_path, index=False, engine='openpyxl')
        logger.info(f"Archivo guardado exitosamente: '{full_path}'")
        # ----------------------------------------------------------
        
    except Exception as e:
        logger.error(f"Error al guardar el archivo Excel: {e}")
    finally:
        end_time = time.perf_counter()
        logger.info(f"Tiempo total transcurrido: {(end_time - start_time)/60:.2f} minutos.")
        if failed_ids:
            logger.warning(f"Proceso completado con {len(failed_ids)} propiedades fallidas.")
        else:
            logger.info("Proceso completado exitosamente sin propiedades fallidas.")
    return df


if __name__ == "__main__":
    import threading
    SEARCH_URL = "https://api-net.macal.cl/api/v1/properties/search"
    DETAILS_URL = "https://api-net.macal.cl/api/v1/properties/details"
    OUTPUT_FILENAME = "propiedades_macal_final.xlsx"
    
    # Dummy event para prueba
    dummy_event = threading.Event()
    
    run_extractor_macal(SEARCH_URL, DETAILS_URL, OUTPUT_FILENAME, dummy_event)