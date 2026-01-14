import pandas as pd
import os
from logger import get_logger

# Configurar logger
logger = get_logger("paso3_excel", log_dir="logs", log_file="paso3_excel.log")

def generar_excel(lista_datos, cancel_event, nombre_archivo="reporte_final.xlsx"):
    """
    Genera un Excel Relacional con 4 pestañas para representar la totalidad de los datos:
    1. 'Resumen General': Datos maestros de la propiedad (1 fila por propiedad).
    2. 'Detalle Construcciones': Desglose de cada línea de construcción.
    3. 'Roles y Deudas': Roles inscritos en CBR y Deudas TGR.
    4. 'Comparables Mercado': Data completa de House Pricing + Links Maps.
    """
    logger.info(f"Iniciando generación de Excel completo para {len(lista_datos)} propiedades...")

    # Listas para las 4 hojas
    data_main = []
    data_constr = []
    data_legal = [] # Roles CBR y Deudas
    data_comps = []

    for item in lista_datos:
        if cancel_event.is_set():
            logger.info("🛑 Proceso cancelado por usuario.")
            return False

        # --- EXTRACTORES ---
        uid = item.get("ID_Propiedad")
        info_gral = item.get("informacion_general", {})
        avaluo = item.get("avaluo", {})
        transaccion = item.get("transaccion", {})
        carac = item.get("caracteristicas", {})
        info_cbr = item.get("informacion_cbr", {})
        hp_data = item.get("house_pricing", {})
        
        # --- 1. HOJA PRINCIPAL (RESUMEN) ---
        # Aplanamos listas simples como compradores/vendedores
        compradores_str = ", ".join(transaccion.get("compradores", []))
        vendedores_str = ", ".join(transaccion.get("vendedores", []))

        # Estado HP
        comps = hp_data.get("comparables", [])
        estado_hp = "Con Resultados"
        if isinstance(comps, str):
            estado_hp = comps # Mensaje de error
            num_comps = 0
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
            "M2 Construcción Total": carac.get("M2 Construcción"),
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

        # --- 3. HOJA LEGAL (Roles Asociados y Deudas) ---
        # Roles CBR
        for r_cbr in item.get("roles_cbr", []):
            data_legal.append({
                "ID Interno (FK)": uid,
                "Rol Propiedad": info_gral.get("rol"),
                "Categoría": "Inscripción CBR",
                "Rol Referencia": r_cbr.get("rol"),
                "Detalle / Monto": r_cbr.get("tipo")
            })
        
        # Deudas
        for deuda in item.get("deudas", []):
            data_legal.append({
                "ID Interno (FK)": uid,
                "Rol Propiedad": info_gral.get("rol"),
                "Categoría": "Deuda TGR",
                "Rol Referencia": deuda.get("rol"),
                "Detalle / Monto": deuda.get("monto") # Aquí va el dinero
            })

        # --- 4. HOJA COMPARABLES (House Pricing Completo) ---
        if isinstance(comps, list) and num_comps > 0:
            for comp in comps:
                if cancel_event.is_set(): return False
                
                data_comps.append({
                    "ID Interno (FK)": uid,
                    "Rol Origen": info_gral.get("rol"),
                    "Comuna": info_gral.get("comuna"),
                    
                    # Datos del Comparable
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
                    
                    # ## NUEVO: Columna con el link de Google Maps
                    "Link Mapa": comp.get("link_maps", "")
                })

    # --- CREACIÓN DE DATAFRAMES ---
    df_main = pd.DataFrame(data_main)
    df_constr = pd.DataFrame(data_constr)
    df_legal = pd.DataFrame(data_legal)
    df_comps = pd.DataFrame(data_comps)

    try:
        with pd.ExcelWriter(nombre_archivo, engine='openpyxl') as writer:
            
            # Hoja 1: Resumen
            if not df_main.empty:
                df_main.to_excel(writer, sheet_name="Resumen General", index=False)
                _ajustar_columnas(writer, "Resumen General", df_main, cancel_event)
            
            # Hoja 2: Comparables (La más importante después del resumen)
            if not df_comps.empty:
                df_comps.to_excel(writer, sheet_name="Comparables Mercado", index=False)
                _ajustar_columnas(writer, "Comparables Mercado", df_comps, cancel_event)
            else:
                logger.warning("No hay comparables para la hoja 'Comparables Mercado'.")

            # Hoja 3: Construcciones
            if not df_constr.empty:
                df_constr.to_excel(writer, sheet_name="Detalle Construcciones", index=False)
                _ajustar_columnas(writer, "Detalle Construcciones", df_constr, cancel_event)

            # Hoja 4: Legal
            if not df_legal.empty:
                df_legal.to_excel(writer, sheet_name="Roles y Deudas", index=False)
                _ajustar_columnas(writer, "Roles y Deudas", df_legal, cancel_event)

        logger.info(f"✅ Excel completo generado exitosamente: {nombre_archivo}")
        return True

    except Exception as e:
        logger.error(f"❌ Error al guardar Excel completo: {e}")
        return False

def _ajustar_columnas(writer, sheet_name, df, cancel_event):
    """Función auxiliar para auto-ajustar el ancho de columnas"""
    worksheet = writer.sheets[sheet_name]
    for idx, col in enumerate(df.columns):
        if cancel_event.is_set(): return
        
        # Calcular ancho basado en el encabezado y datos
        try:
            max_len_data = df[col].astype(str).map(len).max() if not df[col].empty else 0
            max_len = max(max_len_data, len(str(col))) + 2
            max_len = min(max_len, 60) # Tope máximo visual
            
            worksheet.column_dimensions[chr(65 + idx)].width = max_len
        except:
            pass # Si falla el cálculo de ancho, no romper el proceso