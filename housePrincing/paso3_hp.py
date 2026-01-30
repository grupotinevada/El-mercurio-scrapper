############################################################################################################################
#  El paso 3 es el que convierte el JSON con la data del informe y la data de los comparables en un archivo Excel estructurado con hojas
#  Extrae todos la data del JSON y la organiza en hojas separadas (Resumen, Construcciones, Roles, Deudas, Comparables).
############################################################################################################################

import pandas as pd
import os
from logger import get_logger

# Configurar logger
logger = get_logger("paso3_excel", log_dir="logs", log_file="paso3_excel.log")

def generar_excel(lista_datos, cancel_event, nombre_archivo="reporte_final.xlsx"):
    """
    Genera un Excel Relacional con 5 pestañas:
    1. 'Resumen General': Datos maestros.
    2. 'Detalle Construcciones': Desglose de construcción.
    3. 'Roles Asociados': Lista de roles inscritos en CBR + SU DEUDA ESPECÍFICA.
    4. 'Deudas TGR': Deudas detectadas SOLO DEL ROL PRINCIPAL.
    5. 'Comparables Mercado': Data completa de House Pricing.
    """
    logger.info(f"📊 Iniciando generación de Excel completo. Total propiedades a procesar: {len(lista_datos)}")

    # Listas para las hojas
    data_main = []
    data_constr = []
    data_roles = []   # Separado: Roles Asociados + Su Deuda
    data_deudas = []  # Separado: Solo Deuda Rol Principal
    data_comps = []

    for idx, item in enumerate(lista_datos):
        if cancel_event.is_set():
            logger.warning("🛑 Proceso cancelado por usuario durante la iteración de datos.")
            return False

        # --- EXTRACTORES ---
        uid = item.get("ID_Propiedad")
        info_gral = item.get("informacion_general", {})
        avaluo = item.get("avaluo", {})
        transaccion = item.get("transaccion", {})
        carac = item.get("caracteristicas", {})
        info_cbr = item.get("informacion_cbr", {})
        hp_data = item.get("house_pricing", {})
        
        rol_principal = info_gral.get("rol", "S/R")
        logger.debug(f"   [{idx+1}/{len(lista_datos)}] Procesando ID: {uid} | Rol: {rol_principal}")

        # --- 1. HOJA PRINCIPAL (RESUMEN) ---
        compradores_str = ", ".join(transaccion.get("compradores", []))
        vendedores_str = ", ".join(transaccion.get("vendedores", []))

        # Estado HP
        comps = hp_data.get("comparables", [])
        estado_hp = "Con Resultados"
        if isinstance(comps, str):
            estado_hp = comps 
            num_comps = 0
            logger.debug(f"     ⚠️ Estado HP para {rol_principal}: {estado_hp}")
        else:
            num_comps = len(comps)

        fila_main = {
            "ID Interno": uid,
            "Archivo Origen": item.get("meta_archivo", {}).get("nombre"),
            
            # Identificación
            "Rol SII": info_gral.get("rol"),
            "Comuna": info_gral.get("comuna"),
            "Dirección": info_gral.get("direccion"),
            "Propietario": info_gral.get("propietario"),
            
            # Características Globales
            "Tipo Propiedad": carac.get("Tipo"),
            "Destino": carac.get("Destino"),
            "M2 Util": carac.get("M2 Construcción"),
            "M2 Terreno": carac.get("M2 Terreno"),
            
            # Avalúo
            "Avalúo Total": avaluo.get("Avalúo Total"),
            "Avalúo Exento": avaluo.get("Avalúo Exento"),
            "Avalúo Afecto": avaluo.get("Avalúo Afecto"),
            "Contribuciones": avaluo.get("Contribuciones Semestrales"),
            
            # Datos CBR
            "CBR Foja": info_cbr.get("Foja"),
            "CBR Número": info_cbr.get("Número"),
            "CBR Año": info_cbr.get("Año"),
            
            # Transacción
            "Fecha Transacción": transaccion.get("fecha"),
            "Monto Transacción": transaccion.get("monto"),
            "Compradores": compradores_str,
            "Vendedores": vendedores_str,
            
            # Metadata HP
            "Estado Búsqueda HP": estado_hp,
            "Cant. Comparables": num_comps,
            "Latitud Origen": hp_data.get("centro_mapa", {}).get("lat"),
            "Longitud Origen": hp_data.get("centro_mapa", {}).get("lng")
        }
        data_main.append(fila_main)

        # --- 2. HOJA CONSTRUCCIONES ---
        construcciones = item.get("construcciones", [])
        if construcciones:
            logger.debug(f"     🏗️ Agregando {len(construcciones)} construcciones.")
        for c in construcciones:
            data_constr.append({
                "ID Interno (FK)": uid,
                "Rol Propiedad": info_gral.get("rol"),
                "Nro": c.get("nro"),
                "Material": c.get("material"),
                "Calidad": c.get("calidad"),
                "Año": c.get("anio"),
                "M2": c.get("m2"),
                "Destino": c.get("destino")
            })

        # --- PREPARACIÓN: MAPEO DE DEUDAS ---
        # Creamos un diccionario { "ROL NORMALIZADO": {objeto_deuda} } para cruzar fácil
        mapa_deudas = {}
        for d in item.get("deudas", []):
            # Normalizamos a mayúsculas y quitamos espacios (ej: "ROL 123" == "Rol 123")
            key_d = str(d.get("rol", "")).upper().strip()
            mapa_deudas[key_d] = d

        # --- 3. HOJA ROLES ASOCIADOS (MODIFICADO: AHORA INCLUYE DEUDA) ---
        roles_cbr = item.get("roles_cbr", [])
        if roles_cbr:
             logger.debug(f"     📚 Agregando {len(roles_cbr)} roles asociados CBR.")
        
        for r_cbr in roles_cbr:
            # Obtenemos el rol asociado (Ej: "ROL 9064-927")
            rol_asoc_raw = r_cbr.get("rol", "")
            rol_asoc_key = str(rol_asoc_raw).upper().strip()
            
            # Buscamos si tiene deuda en el mapa
            deuda_obj = mapa_deudas.get(rol_asoc_key, {})
            monto_asoc = deuda_obj.get("monto", 0)
            link_asoc = deuda_obj.get("link_tgr", "No detectado")
            if not link_asoc: link_asoc = "No detectado"

            data_roles.append({
                "ID Interno (FK)": uid,
                "Rol Propiedad": info_gral.get("rol"),
                "Rol Asociado": rol_asoc_raw,
                "Tipo / Ubicación": r_cbr.get("tipo"),
                "Monto Deuda": monto_asoc,  # <--- COLUMNA NUEVA
                "Link Deuda TGR": link_asoc # <--- COLUMNA NUEVA
            })
        
        # --- 4. HOJA DEUDAS TGR (MODIFICADO: FILTRO SOLO ROL PRINCIPAL) ---
        deudas_list = item.get("deudas", [])
        if deudas_list:
            logger.debug(f"     💰 Procesando deudas (Filtrando solo Rol Principal)...")
        
        for deuda in deudas_list:
            rol_deuda_str = str(deuda.get("rol", ""))
            
            # LOGICA DE FILTRO: Solo agregamos si el Rol Principal (ej: 9064-112)
            # está contenido en el texto del Rol Deuda (ej: Rol 9064-112).
            # Esto elimina los roles asociados de esta hoja.
            if str(rol_principal) in rol_deuda_str:
                
                link = deuda.get("link_tgr", "")
                if not link: link = "No detectado"
                
                data_deudas.append({
                    "ID Interno (FK)": uid,
                    "Rol Propiedad": info_gral.get("rol"),
                    "Rol Deuda": rol_deuda_str,
                    "Monto Deuda": deuda.get("monto"),
                    "Link informe de deuda TGR": link
                })

        # --- 5. HOJA COMPARABLES ---
        if isinstance(comps, list) and num_comps > 0:
            logger.debug(f"     🏘️ Agregando {num_comps} comparables de mercado.")
            for comp in comps:
                if cancel_event.is_set(): 
                    logger.warning("🛑 Cancelado dentro del loop de comparables.")
                    return False
                data_comps.append({
                    "ID Interno (FK)": uid,
                    "Fuente": comp.get("fuente"),
                    "Rol Origen": info_gral.get("rol"),
                    "Comuna": info_gral.get("comuna"),
                    "Rol Comparable": comp.get("rol"),
                    "Dirección": comp.get("direccion"),
                    "Precio UF": comp.get("precio_uf"),
                    "UF/M2": comp.get("uf_m2"),
                    "Fecha Transacción": comp.get("fecha_transaccion"),
                    "Año Const.": comp.get("anio"),
                    "M2 Útil": comp.get("m2_util"),
                    "M2 Total": comp.get("m2_total"),
                    "Dormitorios": comp.get("dormitorios"),
                    "Baños": comp.get("banios"),
                    "Distancia (mts)": comp.get("distancia_metros"),
                    "Link Mapa": comp.get("link_maps", ""),
                    "Link Publicacion": comp.get("link_publicacion", "")
                })

    # --- CREACIÓN DE DATAFRAMES ---
    logger.info("💾 Transformando listas a DataFrames...")
    df_main = pd.DataFrame(data_main)
    df_constr = pd.DataFrame(data_constr)
    df_roles = pd.DataFrame(data_roles)
    df_deudas = pd.DataFrame(data_deudas)
    df_comps = pd.DataFrame(data_comps)
    
    logger.debug(f"   📊 [Resumen] Dimensiones: {df_main.shape}")
    logger.debug(f"   📊 [Construcciones] Dimensiones: {df_constr.shape}")
    logger.debug(f"   📊 [Roles Asociados] Dimensiones: {df_roles.shape}")
    logger.debug(f"   📊 [Deudas TGR (Solo Princ.)] Dimensiones: {df_deudas.shape}")
    logger.debug(f"   📊 [Comparables] Dimensiones: {df_comps.shape}")

    try:
        logger.info(f"✍️ Escribiendo archivo físico: {nombre_archivo}")
        with pd.ExcelWriter(nombre_archivo, engine='openpyxl') as writer:
            
            # 1. Resumen
            if not df_main.empty:
                logger.debug("   -> Escribiendo hoja 'Resumen General'...")
                df_main.to_excel(writer, sheet_name="Resumen General", index=False)
                _ajustar_columnas(writer, "Resumen General", df_main, cancel_event)
            else:
                logger.warning("   ⚠️ Dataframe 'Resumen General' está vacío.")
            
            # 2. Comparables
            if not df_comps.empty:
                logger.debug("   -> Escribiendo hoja 'Comparables Mercado'...")
                df_comps.to_excel(writer, sheet_name="Comparables Mercado", index=False)
                _ajustar_columnas(writer, "Comparables Mercado", df_comps, cancel_event)
            else:
                logger.debug("   ℹ️ No hay comparables para escribir.")

            # 3. Construcciones
            if not df_constr.empty:
                logger.debug("   -> Escribiendo hoja 'Detalle Construcciones'...")
                df_constr.to_excel(writer, sheet_name="Detalle Construcciones", index=False)
                _ajustar_columnas(writer, "Detalle Construcciones", df_constr, cancel_event)
            
            # 4. Roles Asociados
            if not df_roles.empty:
                logger.debug("   -> Escribiendo hoja 'Roles Asociados'...")
                df_roles.to_excel(writer, sheet_name="Roles Asociados", index=False)
                _ajustar_columnas(writer, "Roles Asociados", df_roles, cancel_event)

            # 5. Deudas TGR
            if not df_deudas.empty:
                logger.debug("   -> Escribiendo hoja 'Deudas TGR'...")
                df_deudas.to_excel(writer, sheet_name="Deudas TGR", index=False)
                _ajustar_columnas(writer, "Deudas TGR", df_deudas, cancel_event)

        logger.success(f"✅ Excel completo generado exitosamente: {nombre_archivo}")
        return True

    except Exception as e:
        logger.error(f"❌ Error FATAL al guardar Excel completo: {e}", exc_info=True)
        return False

def _ajustar_columnas(writer, sheet_name, df, cancel_event):
    """Función auxiliar para auto-ajustar el ancho de columnas"""
    logger.debug(f"   🎨 Ajustando formato (Ancho/Links) en: {sheet_name}")
    worksheet = writer.sheets[sheet_name]
    
    for idx, col in enumerate(df.columns):
        if cancel_event.is_set(): return
        
        try:
            # Calculamos ancho basado en el contenido
            max_len_data = df[col].astype(str).map(len).max() if not df[col].empty else 0
            max_len = max(max_len_data, len(str(col))) + 2
            max_len = min(max_len, 60) # Tope máximo para no hacer columnas kilométricas
            
            worksheet.column_dimensions[chr(65 + idx)].width = max_len
        except Exception as e:
            logger.debug(f"      ⚠️ No se pudo ajustar ancho col {col}: {e}")
            pass
        
        # Detección de Links para formato azul y clickable
        if "Link" in str(col):
            col_letter = chr(65 + idx)
            # Iteramos sobre las celdas de esa columna (empezando desde fila 2 porque 1 es header)
            count_links = 0
            for row_idx in range(2, len(df) + 2):
                cell = worksheet[f"{col_letter}{row_idx}"]
                val = cell.value
                
                # Si el valor empieza con http, lo hacemos clickable y azul
                if val and str(val).startswith("http"):
                    cell.hyperlink = val
                    cell.style = "Hyperlink" # Estilo nativo de Excel (Azul + Subrayado)
                    count_links += 1
            
            if count_links > 0:
                logger.debug(f"      🔗 {count_links} hipervínculos formateados en columna {col}")