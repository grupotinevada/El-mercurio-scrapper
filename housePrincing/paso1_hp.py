import io
import re
import uuid
import os
import logging
from typing import Dict, Any, List, Optional
import pdfplumber

from logger import get_logger, log_section, dbg

logger = get_logger("paso1_hp", log_dir="logs", log_file="paso1_hp.log")

# --- Helpers de Limpieza (ORIGINALES) ---
def clean_money(text: str) -> int:
    if not text: return 0
    clean = re.sub(r'[^\d]', '', text)
    return int(clean) if clean else 0

def clean_float(text: str) -> float:
    if not text: return 0.0
    text = text.replace(',', '.')
    clean = re.sub(r'[^\d\.]', '', text)
    try:
        return float(clean)
    except:
        return 0.0

def clean_text(text: str) -> str:
    if not text: return ""
    return re.sub(r'\s+', ' ', text).strip()

# --- LÓGICA DE EXTRACCIÓN (CORE - INTACTA DE TU API) ---
def parse_house_pricing_text(full_text: str) -> Dict[str, Any]:
    data = {
        "ID_Propiedad": str(uuid.uuid4()), # ID Único generado aquí
        "informacion_general": {},
        "caracteristicas": {},
        "avaluo": { 
            "Avalúo Total": 0, "Avalúo Exento": 0, "Avalúo Afecto": 0, "Contribuciones Semestrales": 0
        },
        "roles_cbr": [],
        "deudas": [],
        "construcciones": [],
        "transaccion": {},
        "informacion_cbr": {},
        "raw_text_debug": "" 
    }

    lines = full_text.split('\n')
    
    for i, line in enumerate(lines):
        line_clean = line.strip()
        
        # Comuna y Rol
        if "Comuna" in line and "Rol" in line:
            if i + 1 < len(lines):
                next_line = lines[i+1].strip()
                parts = re.split(r'\s{2,}', next_line)
                for part in parts:
                    part = part.strip()
                    if re.match(r'^\d+-[\dKk]+$', part):
                        data["informacion_general"]["rol"] = part
                    elif len(part) > 2 and not re.match(r'^\d+$', part):
                        data["informacion_general"]["comuna"] = part

        # Propietario
        if line_clean == "Propietario":
            if i + 1 < len(lines):
                val = lines[i+1].strip()
                if val:
                    data["informacion_general"]["propietario"] = val
        
        # Dirección
        if "Informe de antecedentes" in line:
            if i + 1 < len(lines):
                 candidate = lines[i+1].strip()
                 if re.search(r'\d', candidate) and len(candidate) > 5:
                     data["informacion_general"]["direccion"] = candidate

        # Roles CBR
        if "Roles inscritos en CBR" in line:
            rol_line_index = -1
            for offset in range(1, 6): 
                if i + offset < len(lines):
                    if "ROL" in lines[i+offset].upper() and re.search(r'\d', lines[i+offset]):
                        rol_line_index = i + offset
                        break
            
            if rol_line_index != -1:
                rol_line = lines[rol_line_index]
                type_line = ""
                for offset_type in range(1, 5):
                    if rol_line_index + offset_type < len(lines):
                        candidate = lines[rol_line_index + offset_type]
                        if candidate.strip():
                            type_line = candidate
                            break
                
                roles_parts = re.split(r'\s{2,}', rol_line.strip())
                types_parts = re.split(r'\s{2,}', type_line.strip()) if type_line else []
                valid_roles = [r.strip() for r in roles_parts if "ROL" in r.upper()]
                valid_types = [t.strip() for t in types_parts if t.strip()]

                for idx, rol_val in enumerate(valid_roles):
                    t_val = valid_types[idx] if idx < len(valid_types) else "S/I"
                    data["roles_cbr"].append({"rol": rol_val, "tipo": t_val})

        # Construcciones
        match_cons = re.search(r'^(\d+)\s+(.+?)\s+(20\d{2})\s+([\d,.]+)\s+(.+)$', line.strip())
        if match_cons:
            try:
                nro = match_cons.group(1)
                mid_content = match_cons.group(2).strip()
                anio = match_cons.group(3)
                m2 = clean_float(match_cons.group(4))
                destino = match_cons.group(5).strip()

                mid_parts = re.split(r'\s{2,}', mid_content)
                material = mid_content
                calidad = ""
                
                if len(mid_parts) >= 2:
                    material = mid_parts[0]
                    calidad = " ".join(mid_parts[1:])
                else:
                    material = mid_content

                data["construcciones"].append({
                    "nro": nro,
                    "material": material,
                    "calidad": calidad,
                    "anio": anio,
                    "m2": m2,
                    "destino": destino
                })
            except:
                pass 

    # Regex Globales
    patterns_carac = {
        "Tipo": r'Tipo\s+([A-Za-z\s]+?)(?=\n|$)', 
        "Destino": r'Destino\s+([A-Za-z\s]+?)(?=\n|$)',
        "M2 Construcción": r'M² Construcción\s+([\d,]+)',
        "M2 Terreno": r'M² Terreno\s+([\d,]+)',
        "Estacionamientos": r'Estacionamientos\s+(.+?)(?=\n|$)',
        "Bodegas": r'Bodegas\s+(.+?)(?=\n|$)'
    }
    
    for key, pat in patterns_carac.items():
        match = re.search(pat, full_text)
        if match:
            val = match.group(1).strip()
            if "M2" in key:
                data["caracteristicas"][key] = clean_float(val)
            else:
                data["caracteristicas"][key] = clean_text(val)
    
    if data["caracteristicas"].get("M2 Terreno", 0.0) == 0.0:
        data["caracteristicas"]["M2 Terreno"] = data["caracteristicas"].get("M2 Construcción", 0.0)

    # Avalúo, Deudas, Transacción
    patterns_avaluo = {
        "Avalúo Total": r'Avalúo Total\s+(\$[\d\.]+)',
        "Avalúo Exento": r'Avalúo Exento\s+(\$[\d\.]+)',
        "Avalúo Afecto": r'Avalúo Afecto\s+(\$[\d\.]+)',
        "Contribuciones Semestrales": r'Contribuciones Semestrales\s+(\$[\d\.]+)'
    }
    for key, pattern in patterns_avaluo.items():
        match = re.search(pattern, full_text)
        if match:
            data["avaluo"][key] = clean_money(match.group(1))

    deuda_matches = re.findall(r'(Rol\s+\d+-[\dKk]+)\s+(\$[\d\.]+)', full_text, re.IGNORECASE)
    seen_deudas = set()
    for rol_str, monto_str in deuda_matches:
        if rol_str not in seen_deudas: 
            data["deudas"].append({"rol": rol_str, "monto": clean_money(monto_str)})
            seen_deudas.add(rol_str)

    match_monto = re.search(r'Monto\s+(UF\s+[\d\.]+)', full_text)
    match_fecha = re.search(r'Fecha SII\s+(\d{2}/\d{2}/\d{4})', full_text)
    if match_monto: data["transaccion"]["monto"] = match_monto.group(1)
    if match_fecha: data["transaccion"]["fecha"] = match_fecha.group(1)
    
    try:
        if "Compradores" in full_text and "Vendedores" in full_text:
            bloque = full_text.split("Compradores")[1].split("Información CBR")[0]
            partes = bloque.split("Vendedores")
            comps = partes[0].strip().split('\n')
            vends = partes[1].strip().split('\n') if len(partes) > 1 else []
            data["transaccion"]["compradores"] = [c.replace('•', '').strip() for c in comps if c.strip()]
            data["transaccion"]["vendedores"] = [v.replace('•', '').strip() for v in vends if v.strip()]
    except:
        pass

    patterns_cbr = {
        "Foja": r'Foja\s+(.+?)(?=\n|$)',
        "Número": r'Número\s+(.+?)(?=\n|$)',
        "Año": r'Año CBR\s+(.+?)(?=\n|$)',
        "Acto": r'Acto\s+(.+?)(?=\n|$)'
    }
    for key, pat in patterns_cbr.items():
        match = re.search(pat, full_text)
        if match: data["informacion_cbr"][key] = match.group(1).strip()

    return data

# --- NUEVA FUNCIÓN DE LOTE (REEMPLAZA AL ENDPOINT) ---
def procesar_lote_pdfs(carpeta_inputs: str) -> List[Dict[str, Any]]:
    """
    Recorre una carpeta de PDFs, extrae la info de CADA UNO usando la lógica original,
    y retorna una lista de JSONs estandarizados.
    """
    resultados_json = []
    
    if not os.path.exists(carpeta_inputs):
        logger.error(f"La carpeta {carpeta_inputs} no existe.")
        return []

    archivos = [f for f in os.listdir(carpeta_inputs) if f.lower().endswith('.pdf')]
    logger.info(f"Paso 1: Se encontraron {len(archivos)} PDFs para procesar.")

    for archivo in archivos:
        ruta_completa = os.path.join(carpeta_inputs, archivo)
        
        try:
            full_text = ""
            with pdfplumber.open(ruta_completa) as pdf:
                # Protección básica
                if len(pdf.pages) > 50: 
                     logger.warning(f"PDF extenso ({len(pdf.pages)} págs): {archivo}")
                
                for page in pdf.pages:
                    text = page.extract_text(layout=True)
                    if text: full_text += text + "\n"
            
            # --- INVOCACIÓN CORE ---
            datos_extraidos = parse_house_pricing_text(full_text)
            
            # Agregar metadatos del archivo para trazabilidad
            datos_extraidos["meta_archivo"] = {
                "nombre": archivo,
                "ruta": ruta_completa
            }
            
            # Validación mínima (Rol/Comuna necesarios para Paso 2)
            rol = datos_extraidos["informacion_general"].get("rol")
            comuna = datos_extraidos["informacion_general"].get("comuna")
            
            if rol and comuna:
                resultados_json.append(datos_extraidos)
                logger.info(f"✅ Procesado OK: {archivo} -> Rol: {rol}")
            else:
                logger.warning(f"⚠️ Datos insuficientes en {archivo} (Falta Rol o Comuna).")

        except Exception as e:
            logger.error(f"❌ Error leyendo {archivo}: {e}")
            
    return resultados_json