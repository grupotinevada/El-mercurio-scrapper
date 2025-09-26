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
    prompt = f"""
        EXTRACTOR DE DATOS DE REMATES JUDICIALES
            Eres un especialista en extracción de datos de remates judiciales chilenos. Tu tarea es extraer información precisa y estructurada del texto proporcionado.
        REGLAS FUNDAMENTALES
            NUNCA INVENTAR DATOS - Solo extraer información explícitamente presente
            PRECISIÓN ABSOLUTA - Mejor campo vacío que dato incorrecto
            UN OBJETO JSON POR INMUEBLE - Si hay múltiples propiedades, crear array con objetos separados
            SI EL DATO NO EXISTE EN EL TEXTO, DEJARLO COMO "No se menciona", si el campo es numerico dejarlo como 0
        
        ESQUEMA DE EXTRACCIÓN
        
        1.- IDENTIFICACIÓN DEL REMATE
            -causa: Solo el número de rol (formato: "C-1234-2020", "O-567-2023", etc.)
            -Caratulado: Nombre completo del demandante (banco, institución financiera, acreedor)
            -corte: Nombre de la corte (ej: "Corte de Apelaciones de Santiago")
            -tribunal: Tribunal específico formato estandarizado:
            -Con número: "16° Juzgado Civil de Santiago", "3° Juzgado de Letras de Valparaíso"
            -Sin número: "Juzgado de Letras de Rancagua"
            -Convertir ordinales: "DÉCIMO SEXTO" → "16°", "SEGUNDO" → "2°"
            -si no se menciona, no inferir, dejar el campo "No se menciona"
        2.- DATOS DE LA PROPIEDAD
            -tipo_propiedad: SOLO valores permitidos:
            -departamento | casa | parcela | sitio | terreno | patio | condominio | bodega | galpón | loteo | estacionamiento | oficina
            -nombre_propiedad: Descripción corta, sin "°" ni "N°"
            -direccion: Dirección limpia, sin caracteres especiales
            -villa_barrio_condominio: Nombre de villa, barrio o condominio si se menciona
            -comuna: Extraer literal del texto
            -region: Solo inferir si comuna es inequívocamente identificable
        3.- VALORES MONETARIOS
            -Reglas de detección:
            -UF: Presencia de "UF" + números decimales (ej: "2.500,50 UF")
            -CLP: Símbolo "$" + números con puntos (ej: "$150.000.000")
            -postura_minima_uf: Valor en UF si existe, "0" si solo hay CLP
            -postura_minima_clp: Valor en CLP si existe, "0" si solo hay UF
        4.- FECHAS Y HORARIOS
            -fecha_remate: Formato ISO 8601 (YYYY-MM-DD)
            -comentario.fecha_hora_remate: Con hora si disponible (YYYY-MM-DDTHH:MM)
            -Si no hay fecha/hora específica: null
        5.- MODALIDADES DE PAGO
            -forma_pago_garantia: Valores exactos permitidos:
            -"Vale Vista Endosable" = Sin endoso, no trasferible,
            -"Vale Vista Nominativo" = Beneficiario final, a nombre del tribunal, trasferible, persona, etc,
            -"Transferencia",
            -"Cupón de Pago",
            -"Precio Contado*" (con asterisco obligatorio),
            -null si no se especifica.
            -garantia_porcentaje: Porcentaje numérico de garantía requerida (sin símbolo %)
            -fecha_pago_saldo_remate:
            -Copiar frase RELATIVA o LITERAL del texto (ej: "quinto día hábil siguiente al remate", "5to dia hábil siguiente al remate", etc)
            -NO calcular fechas específicas
            -null si no aparece
        6.- INFORMACIÓN COMPLEMENTARIA
            -diario: Nombre del diario oficial donde se publicó el remate
            -comentario.link_zoom:
            -URL completa o ID de Zoom si existe
            -"Necesario contactar" si no hay enlace
            -comentario.fecha_hora_remate: Fecha y hora específica del remate si disponible
        7.- CASOS ESPECIALES
            7.1 .-Múltiples Inmuebles
                Si un remate incluye varios inmuebles (ej: departamento + estacionamiento):
                Crear objeto separado para cada propiedad
                Mantener datos comunes (causa, tribunal, fecha, etc.)
                Diferenciar en tipo_propiedad y descripción.
                Estar atento a la direccion, revisar si entre propiedades cambian si no, se mantiene la general.
            7.2 .- Datos Faltantes
                String fields: null
                Campos numéricos: usar 0 para garantia_porcentaje si no se especifica
                Campos requeridos siempre deben tener valor o null
                Inferencias Permitidas (ÚNICAMENTE)
                Comuna → Región (solo si es inequívoca)
                Abreviaciones conocidas de tribunales
                Conversión de números ordinales a formato estándar
        8.- INSTRUCCIÓN FINAL
            -haz una pequeña validacion de los datos, contrasta con el remate solo para verificar.
            -Respeta el esquema JSON.
            -Procesa el siguiente texto de remate y devuelve ÚNICAMENTE el JSON resultante, en español, siguiendo todas las reglas establecidas:
        {texto_remate}
    """

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
            max_tokens=8192,   #FORMA DE LIMITAR TOKENS ANTES DE GPT 5
            # max_completion_tokens=8192, #para gtp5
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "remate_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "remates": {
                                "type": "array",
                                "items": {
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
                        "required": ["remates"]
                    }
                }
            }

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

    for i, remate in enumerate(remates_limpios):
        logger.info("-" * 50)
        logger.info(f"Procesando remate ID {remate['id_remate']}...")

        # cálculo % progreso
        progreso_en_etapa = ((i + 1) / total_remates) * peso_total_etapa3
        progreso_total_actual = progreso_base_etapa3 + progreso_en_etapa
        mensaje_progreso = f"Etapa 3: Analizando remate {i + 1} de {total_remates}"
        progress_callback(progreso_total_actual, mensaje_progreso)

        resultado_ia = extraer_datos_remate(client, MODEL_ENGINE, remate["remate_limpio"])

        if "datos" in resultado_ia and isinstance(resultado_ia["datos"], dict):
            lista_propiedades = resultado_ia["datos"].get("remates", [])
            usage = resultado_ia.get("usage", {})

            remate_texto = remate.get("remate_limpio", "Sin remate")

            if len(lista_propiedades) == 1:
                propiedad = lista_propiedades[0]
                propiedad["diario"] = "El Mercurio"
                registro_final = {
                    "id_remate": remate["id_remate"],
                    **propiedad,
                    "remate_texto": remate_texto
                    }
                resultados.append(registro_final)
                logger.info(f"  -> Propiedad '{propiedad.get('nombre_propiedad')}' agregada con ID {remate['id_remate']}.")
            else:
                for j, propiedad in enumerate(lista_propiedades, 1):
                    propiedad["diario"] = "El Mercurio"
                    id_remate_compuesto = f"{remate['id_remate']}.{j}"
                    registro_final = {
                        "id_remate": id_remate_compuesto,
                        **propiedad,
                        "remate_texto": remate_texto
                    }
                    resultados.append(registro_final)
                    logger.info(f"  -> Propiedad '{propiedad.get('nombre_propiedad')}' agregada con ID {id_remate_compuesto}.")

            total_tokens_usados += getattr(usage, "total_tokens", 0)
            total_costo_usd += calcular_costo(usage, MODEL_ENGINE)

        else:
            logger.warning(f"No se pudo extraer datos para remate ID {remate['id_remate']}")

        time.sleep(0.8)


    # --- GUARDADO DE RESULTADOS ---
    json_output_path = f"{output_prefix}.json"
    excel_output_path = f"{output_prefix}.xlsx"

    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    if resultados:
        df = pd.json_normalize(resultados)
        columnas = df.columns.tolist()
        columnas.remove('remate_texto')
        columnas.append('remate_texto')
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
    # Esta parte se ejecuta solo si corres el script directamente
    archivo_entrada_paso2 = "remates_separados.json" # Asegúrate que este archivo exista
    
    # Crear un archivo de entrada de ejemplo si no existe
    if not os.path.exists(archivo_entrada_paso2):
        logger.info(f"Creando archivo de prueba '{archivo_entrada_paso2}'...")
        mock_data = [
            {"id_remate": 1, "remate": "Texto de un remate simple para una casa."},
            {"id_remate": 2, "remate": "Texto de un remate para dos propiedades: un depto y una bodega."}
        ]
        with open(archivo_entrada_paso2, "w", encoding="utf-8") as f:
            json.dump(mock_data, f)
            
    logger.info(f"Ejecutando el Paso 3 en modo de prueba con el archivo: {archivo_entrada_paso2}")
    
    ### CORRECCIÓN 3: Se añaden argumentos dummy para que la función se pueda llamar.
    mock_cancel_event = None
    def mock_progress_callback(progress, message):
        print(f"  [Callback] {progress:.1f}% - {message}")

    run_processor(
        cancel_event=mock_cancel_event,
        input_json_path=archivo_entrada_paso2,
        progress_callback=mock_progress_callback
    )
