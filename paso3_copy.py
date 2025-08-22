import json
import re
import time
import pandas as pd
from openai import APIError, OpenAI, RateLimitError

# --- Configuración de logger ---
from logger import get_logger, log_section, dbg

logger = get_logger("paso3", log_dir="logs", log_file="paso3.log")

# ==================== FUNCIONES AUXILIARES ====================

def funcion_limpieza_final(remates_json):
    """
    Realiza una limpieza básica en el texto de cada remate.
    """
    remates_limpios = []
    logger.info("🧹 - Empezando limpieza final de textos...")
    for remate in remates_json:
        texto = remate["remate"]
        texto = texto.replace('\n', ' ')
        texto = re.sub(r'\s+', ' ', texto)
        texto = re.sub(r'[“”‘’]', "'", texto)
        texto = texto.strip()
        remates_limpios.append({
            "id_remate": remate["id_remate"],
            "remate_limpio": texto
        })
    logger.info("🧹 - Limpieza final terminada.")
    return remates_limpios

def generar_prompt_remate(texto_remate: str) -> str:
    """
    Crea el prompt estructurado para la API de OpenAI.
    """ 
    prompt = f"""Extract all fields from the auction text per schema. Rules: - Infer missing data only if accurate (e.g., comuna "San Bernardo" → region "Región Metropolitana"). No false positives; use null if missing. - Currency: postura_minima_uf = UF or 0 if CLP; postura_minima_clp = CLP or 0 if UF. - Do not invent data. - fecha_remate and comentario.fecha_hora_remate in ISO 8601. - causa = case/rol number only. - comentario.link_zoom = "Necesario contactar" if no link; else extract Zoom ID. - nombre_propiedad and direccion: short, no special characters ("°", "N°"). - Caratulado = bank, financial institution, creditor, or person initiating the lawsuit. - Detect postura_minima_uf by "UF" and decimals; postura_minima_clp by "$" and dots. - tipo_propiedad: departamento, parcela, patio, sitio, casa, terreno, condominio, bodega, galpón, loteo, estacionamiento, oficina. - Auction balance payment date: relative phrase, e.g., "quinto día hábil del remate"(it can be any day, not necessarily the fifth day), do not calculate the date, this field may or may not be present, do not invent, if it does not exist, leave the field empty. - Standardize corte/tribunal names: convert "DÉCIMO SEXTO JUZGADO de santiago" → "16° Juzgado de Santiago"; may appear as "{{Number° (optional)}} Juzgado Civil {{city}}" or "{{Number° (optional)}} Juzgado de Letras {{city}}"; if no number, use "Juzgado de {{city}}". - forma_pago_garantia: Vale Vista Endosable, Vale Vista Nominativo, Transferencia, or Cupón de Pago. could be Precio Contado you must put a * to Precio Contado e.g: Precio Contado*. Auction text:  --- {texto_remate} --- Answer in Spanish."""

    return prompt.strip()

def calcular_costo(usage, engine):
    """
    Calcula el costo de la llamada a la API basado en los tokens usados.
    """
    precios_por_1M_tokens = {
        "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
        "gpt-4.1-nano": {"prompt": 0.10, "completion": 0.40},
        "gpt-5-nano":{"prompt": 0.05, "completion": 0.40}
    }
    precios = precios_por_1M_tokens.get(engine)
    if not precios:
        raise ValueError(f"Modelo {engine} no reconocido para calcular precio")
    
    prompt_tokens = getattr(usage, "prompt_tokens", 0)
    completion_tokens = getattr(usage, "completion_tokens", 0)
    
    prompt_cost = (prompt_tokens / 1_000_000) * precios["prompt"]
    completion_cost = (completion_tokens / 1_000_000) * precios["completion"]
    return prompt_cost + completion_cost

def extraer_datos_remate(client, engine, texto_remate: str) -> dict:
    """
    Llama a la API de OpenAI para extraer los datos estructurados.
    """
    logger.info("🔩 - Generando Prompt")
    prompt = generar_prompt_remate(texto_remate)
    
    try:
        logger.info(f"🤖 - Llamando a la API de OpenAI con el modelo {engine}...")
        completion = client.chat.completions.create(
            model=engine,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,# NO SE PERMITE CAMBIAR LA TEMPERATURA EN LOS MODELOS 5
            max_tokens=2048,   #FORMA DE LIMITAR TOKENS ANTES DE GPT 5
            # max_completion_tokens=8192, #para gtp5
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "remate_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "nombre_propiedad": {"type": ["string", "null"]},
                            "Caratulado": {"type": ["string", "null"]},
                            "region": {"type": ["string", "null"]},
                            "comuna": {"type": ["string", "null"]},
                            "direccion": {"type": ["string", "null"]},
                            "tipo_propiedad": {"type": ["string", "null"]},
                            "villa_barrio_condominio": {"type": ["string", "null"]},
                            "postura_minima_uf": {"type": "string"},
                            "postura_minima_clp": {"type": "string"},
                            "forma_pago_garantia": {"type": ["string", "null"]},
                            "garantia_porcentaje": {"type": "number"},
                            "fecha_pago_saldo_remate": {"type": ["string", "null"]},
                            "diario": {"type": ["string", "null"]},
                            "corte": {"type": ["string", "null"]},
                            "tribunal": {"type": ["string", "null"]},
                            "causa": {"type": ["string", "null"]},
                            "fecha_remate": {"type": ["string", "null"]},
                            "comentario": {
                                "type": "object",
                                "properties": {
                                    "link_zoom": {"type": ["string", "null"]},
                                    "fecha_hora_remate": {"type": ["string", "null"]}
                                },
                                "required": ["link_zoom", "fecha_hora_remate"]
                            }
                        },
                        "required": [
                            "nombre_propiedad", "Caratulado", "region", "comuna",
                            "direccion", "tipo_propiedad", "villa_barrio_condominio",
                            "postura_minima_uf", "postura_minima_clp",
                            "forma_pago_garantia", "garantia_porcentaje",
                            "fecha_pago_saldo_remate", "diario", "corte", "tribunal",
                            "causa", "fecha_remate", "comentario"
                        ],
                        "additionalProperties": False
                    }
                }
            },
        )
        
        contenido_original = completion.choices[0].message.content
        logger.debug(f"Contenido recibido de la API: '{contenido_original}'")
        logger.debug(f"Razón de finalización: {completion.choices[0].finish_reason}")
        
        datos = json.loads(contenido_original)
        usage = completion.usage
        
        return {"datos": datos, "usage": usage}

    except RateLimitError as e:
        logger.error(f"❌ Límite de API alcanzado: {e}")
        return {"error": "Rate limit alcanzado", "detalle": str(e)}
    except APIError as e:
        logger.error(f"❌ Error en la API: {e}")
        return {"error": "Error de API", "detalle": str(e)}
    except Exception as e:
        logger.error(f"❌ Error inesperado: {e}")
        return {"error": "Error inesperado", "detalle": str(e)}

# ==================== FUNCIÓN PRINCIPAL ENCAPSULADA ====================
from dotenv import load_dotenv
import os

def run_processor(cancel_event, input_json_path: str, progress_callback, output_prefix: str = "remates_final"):
    load_dotenv()
    """
    Orquesta el proceso completo de limpieza, extracción con IA y guardado.
    
    Args:
        input_json_path (str): Ruta al archivo JSON generado por el paso 2.
        output_prefix (str): Prefijo para los archivos de salida (JSON y Excel).
        
    Returns:
        tuple: Una tupla con las rutas de los archivos generados (json_path, excel_path).
    """
    API_KEY = os.getenv("OPENAI_API_KEY_EXTRACTOR") 
    MODEL_ENGINE = os.getenv("MODEL_ENGINE")
    
    client = OpenAI(api_key=API_KEY)

    # --- CARGA DE DATOS ---
    try:
        with open(input_json_path, "r", encoding="utf-8") as f:
            remates_iniciales = json.load(f)
    except FileNotFoundError:
        logger.error(f"No se encontró el archivo de entrada: {input_json_path}")
        return None, None
    except json.JSONDecodeError:
        logger.error(f"El archivo {input_json_path} no es un JSON válido.")
        return None, None

    # --- PROCESAMIENTO ---
    remates_limpios = funcion_limpieza_final(remates_iniciales)
    
    resultados = []
    #calculo % etapa 3
    total_remates = len(remates_limpios)
    progreso_base_etapa3 = 66.6
    peso_total_etapa3 = 33.3 # (99.9 - 66.6)
    
    total_tokens_usados = 0
    total_costo_usd = 0

    logger.info("🏁 - Comienzo del pipeline de extracción con IA")

    for i, remate in enumerate(remates_limpios):  #5 PARA PRUEBAS
        logger.info("-" * 50)
        logger.info(f"Procesando remate ID {remate['id_remate']}...")
        
        #calculo %
        progreso_en_etapa = ((i + 1) / total_remates) * peso_total_etapa3
        progreso_total_actual = progreso_base_etapa3 + progreso_en_etapa
        mensaje_progreso = f"Etapa 3: Analizando remate {i + 1} de {total_remates}"
        progress_callback(progreso_total_actual, mensaje_progreso)
        
        resultado_ia = extraer_datos_remate(client, MODEL_ENGINE, remate["remate_limpio"])
        
        if "datos" in resultado_ia and "usage" in resultado_ia:
            datos = resultado_ia["datos"]
            usage = resultado_ia["usage"]

            datos["diario"] = "El Mercurio"
            print("[DEBUG] - DATOS: ", datos)
            remate_texto = remate["remate_limpio"] if "remate_limpio" in remate else "Sin remate"

            resultados.append({
                "id_remate": remate["id_remate"],
                **datos,
                "remate_texto": remate_texto
            })
            

            total_tokens_usados += getattr(usage, "total_tokens", 0)
            costo = calcular_costo(usage, MODEL_ENGINE)
            total_costo_usd += costo

        else:
            logger.warning(f"No se pudo extraer datos para remate ID {remate['id_remate']}")

        logger.info("⏳ Esperando 0.8 segundos antes del siguiente remate... (evita saturar api)")
        time.sleep(0.8)

    # --- GUARDADO DE RESULTADOS ---
    json_output_path = f"{output_prefix}.json"
    excel_output_path = f"{output_prefix}.xlsx"

    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    if resultados:
        df = pd.json_normalize(resultados)

        # Paso 1: Obtenemos la lista de todas las columnas
        columnas = df.columns.tolist()
        
        # Paso 2: Eliminamos 'remate_texto' de su posición actual
        columnas.remove('remate_texto')
        
        # Paso 3: Agregamos 'remate_texto' al final de la lista
        columnas.append('remate_texto')
        
        # Paso 4: Reindexamos el DataFrame con el nuevo orden de columnas
        df = df[columnas]
        
        # Guardamos el Excel
        df.to_excel(excel_output_path, index=False)
    else:
        logger.warning("No se generaron resultados, el archivo Excel estará vacío.")
        pd.DataFrame().to_excel(excel_output_path, index=False)

    logger.info("="*50)
    logger.info("✅ Proceso completado.")
    logger.info(f"Total tokens usados: {total_tokens_usados}")
    logger.info(f"Costo estimado total USD: ${total_costo_usd:.4f}")
    logger.info(f"Resultados guardados en '{json_output_path}' y '{excel_output_path}'")
    logger.info("="*50)
    
    return json_output_path, excel_output_path

# ==================== BLOQUE DE EJECUCIÓN DIRECTA ====================

if __name__ == "__main__":
    # Esta parte se ejecuta solo si corres 'python paso3.py' directamente
    # Sirve para probar el módulo de forma aislada
    archivo_entrada_paso2 = "remates_separados.json"
    logger.info(f"Ejecutando el Paso 3 en modo de prueba con el archivo: {archivo_entrada_paso2}")
    run_processor(archivo_entrada_paso2)
