import json
import re
import time

# Cargar el archivo JSON con los remates
with open("remates_separados.json", "r", encoding="utf-8") as f:
    remates = json.load(f)

def funcion_limpieza_final(remates_json):
    
    remates_limpios = []
    print("[INFO]🧹 - Empezando limpieza")
    for remate in remates_json:
        texto = remate["remate"]

        # Normalizaciones y limpiezas básicas
        texto = texto.replace('\n', ' ')  # unir líneas
        texto = re.sub(r'\s+', ' ', texto)  # eliminar espacios repetidos
        texto = re.sub(r'[“”‘’]', "'", texto)  # normalizar comillas
        texto = texto.strip()

        remates_limpios.append({
            "id_remate": remate["id_remate"],
            "remate_limpio": texto
        })
    print("[INFO]🧹 - Terminando limpieza")
    return remates_limpios

# Ejecutar limpieza
remates_limpios = funcion_limpieza_final(remates)


#============================= INGENIERIA DE PROMPT =======================================


def generar_prompt_remate(texto_remate: str) -> str:
    prompt = f"""
    Extract all fields from the given auction text following the schema.  
    Rules:  
    - You may infer missing data (e.g., if comuna is "San Bernardo", region = "Región Metropolitana") only if inference is accurate using both your knowledge and the auction context. No false positives.  
    - If data is missing, set it to null.  
    - Currency: postura_minima_uf = UF value or 0 if in CLP; postura_minima_clp = CLP value or 0 if in UF.  
    - Do not invent data not present or reliably inferred.  
    - fecha_remate and comentario.fecha_hora_remate in ISO 8601 (YYYY-MM-DDTHH:MM:SS).  
    - causa = only case number/rol, no long descriptions.  
    - comentario.link_zoom = "Necesario contactar" if no link; if link present, also extract Zoom session ID.  
    - nombre_propiedad is a very short descriptive name, not from official titles.  
    - the response must be in spanish
    - The purchasing supplier is always the bank, financial institution or person who initiated the lawsuit to collect your debt.
    - Identify postura_minima_uf by the presence of "UF" (any case) and decimal separators (. and ,).
    - Identify postura_minima_clp by the $ sign and dots . (Chilean pesos).
    - tipo_propiedad can be any property type like "departamento", "patio", "sitio", "casa", "terreno", "condominio", etc.
    - the fecha_pago_saldo_remate is not a specifyc date, is a phrase like "quinto día hábil de efectuado el remate" or "quinto día hábil siguiente a la fecha  del  remate"
    Auction text:
    ---
    {texto_remate}
    ---
    """
    return prompt.strip()


#PARA SABER CUANTO SALEEEEEEEEE
def calcular_costo(usage, engine):
    precios_por_1M_tokens = {
        "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
        "gpt-4.1-nano": {"prompt": 0.10, "completion": 0.40},
        "gpt-4o": {"prompt": 2.50, "completion": 10.00},
        "gpt-4o-2024-05-13": {"prompt": 5.00, "completion": 15.00},
    }

    precios = precios_por_1M_tokens.get(engine)
    if not precios:
        raise ValueError(f"Modelo {engine} no reconocido para calcular precio")

    prompt_tokens = getattr(usage, "prompt_tokens", 0)
    completion_tokens = getattr(usage, "completion_tokens", 0)

    prompt_cost = (prompt_tokens / 1_000_000) * precios["prompt"]
    completion_cost = (completion_tokens / 1_000_000) * precios["completion"]
    return prompt_cost + completion_cost




from openai import APIError, OpenAI, RateLimitError

import json

from dotenv import load_dotenv
import os
API_KEY = os.getenv("OPENAI_API_KEY_EXTRACTOR") 
client = OpenAI(
    api_key=API_KEY
)
engine = "gpt-4o-mini"
import re
import json
from openai import APIError, RateLimitError

def extraer_datos_remate(texto_remate: str) -> dict:
    print("[INFO]🔩 - Generando Prompt")
    prompt = generar_prompt_remate(texto_remate)

    try:
        print("[INFO]🤖 - Llamando a la API de OpenAI con el modelo ", engine, " usando JSON Schema...")
        completion = client.chat.completions.create(
            #gpt-4o-mini  modelo un poco mas caro no mas
            #gpt-4.1-nano barato pero no tan vio
            model= engine,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1024,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "remate_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "nombre_propiedad": {"type": ["string", "null"]},
                            "proveedor_compra": {"type": ["string", "null"]},
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
                            "nombre_propiedad", "proveedor_compra", "region", "comuna",
                            "direccion", "tipo_propiedad", "villa_barrio_condominio",
                            "postura_minima_uf", "postura_minima_clp",
                            "forma_pago_garantia", "garantia_porcentaje",
                            "fecha_pago_saldo_remate", "diario", "corte", "tribunal",
                            "causa", "fecha_remate", "comentario"
                        ],
                        "additionalProperties": False
                    }
                }
            }
        )
        
        contenido_original = completion.choices[0].message.content
        datos = json.loads(contenido_original)
        usage = completion.usage  # Aquí está la info de tokens
        
        return {"datos": datos, "usage": usage}

    except RateLimitError as e:
        print(f"[ERROR] - ❌ Límite de API alcanzado: {e}")
        return {"error": "Rate limit alcanzado", "detalle": str(e)}
    except APIError as e:
        print(f"[ERROR] - ❌ Error en la API: {e}")
        return {"error": "Error de API", "detalle": str(e)}
    except Exception as e:
        print(f"[ERROR] - ❌ Error inesperado: {e}")
        return {"error": "Error inesperado", "detalle": str(e)}


    
    
# ==================== PIPELINE COMPLETO ====================

import pandas as pd

# resultados = []
# total_tokens_usados = 0
# total_costo_usd = 0

# print("[INFO]🏁 - Comienzo pipeline completo")

# for remate in remates_limpios:
#     print(f"Procesando remate ID {remate['id_remate']}...")
    
#     resultado = extraer_datos_remate(remate["remate_limpio"])
    
#     if "datos" in resultado and "usage" in resultado:
#         datos = resultado["datos"]
#         usage = resultado["usage"]

#         # Forzar diario
#         datos["diario"] = "El Mercurio"

#         # Guardar resultado
#         resultados.append({
#             "id_remate": remate["id_remate"],
#             **datos
#         })

#         # Acumular tokens y costo
#         total_tokens_usados += getattr(usage, "total_tokens", 0)
#         costo = calcular_costo(usage, engine)
#         total_costo_usd += costo

#     else:
#         print(f"[WARN] No se pudo extraer datos o usage para remate ID {remate['id_remate']}")

#     print("[INFO] ⏳ Esperando 5 segundos antes del siguiente remate...")
#     time.sleep(5)

# # Guardar a archivo JSON
# with open("remates_extraidos.json", "w", encoding="utf-8") as f:
#     json.dump(resultados, f, ensure_ascii=False, indent=2)

# # Convertir a DataFrame y aplanar campos anidados
# df = pd.json_normalize(resultados)

# # Guardar a Excel
# df.to_excel("remates_extraidos.xlsx", index=False)

# print(f"✅ Proceso completado.")
# print(f"Total tokens usados: {total_tokens_usados}")
# print(f"Costo estimado total USD: ${total_costo_usd:.4f}")
# print("Resultados guardados en 'remates_extraidos.json' y 'remates_extraidos.xlsx'")




# ==================== PIPELINE DE PRUEBA ====================

resultados_prueba = []
total_tokens_usados = 0
total_costo_usd = 0

# Tomar solo los primeros 2 remates limpios
for remate in remates_limpios[:5]:
    print(f"🔍 Procesando prueba con remate ID {remate['id_remate']}...")
    
    resultado = extraer_datos_remate(remate["remate_limpio"])
    
    # Aquí verificamos si la función devolvió datos y usage correctamente
    if "datos" in resultado and "usage" in resultado:
        datos = resultado["datos"]
        usage = resultado["usage"]

        # Calcular costo según tokens usados
        costo = calcular_costo(usage, engine)
        total_costo_usd += costo

        # Sumar tokens
        total_tokens_usados += getattr(usage, "total_tokens", 0)

        # Forzar diario
        datos["diario"] = "El Mercurio"

        # Guardar resultado con id_remate y datos desglosados
        resultados_prueba.append({
            "id_remate": remate["id_remate"],
            **datos
        })

    else:
        print("[WARN] No se pudo obtener datos o usage para este remate")

print(f"Motor usado: {engine}")
print(f"Total tokens usados: {total_tokens_usados}")
print(f"Costo estimado total USD: ${total_costo_usd:.4f}")

# Guardar resultados en JSON
with open("remates_prueba_extraidos.json", "w", encoding="utf-8") as f:
    json.dump(resultados_prueba, f, ensure_ascii=False, indent=2)

# Convertir a DataFrame y aplanar campos anidados
df_prueba = pd.json_normalize(resultados_prueba)

# Guardar en Excel
df_prueba.to_excel("remates_prueba_extraidos.xlsx", index=False)

print("✅ Prueba completada. Resultados guardados en 'remates_prueba_extraidos.json' y 'remates_prueba_extraidos.xlsx'")