import os
import cv2
import pytesseract
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter, find_peaks
from logger import get_logger
import sys

def resource_path(relative_path):
    """ Obtiene la ruta absoluta al recurso, funciona para dev y para PyInstaller """
    try:
        # PyInstaller crea una carpeta temporal en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# --- CONFIGURACIÓN DE TESSERACT PORTABLE ---
if getattr(sys, 'frozen', False):
    # Si estamos corriendo como .EXE (PyInstaller)
    # Asumimos que la carpeta 'Tesseract-OCR' está empaquetada en la raíz temporal
    tesseract_cmd_path = resource_path(os.path.join("Tesseract-OCR", "tesseract.exe"))
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd_path
else:
    # Si estamos en MODO DESARROLLO (Pycharm, VSCode, Colab local)
    # Ajusta esta ruta a donde TÚ lo tengas instalado
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Configuración de parámetros
custom_config = r'--oem 3 --psm 6 -l spa'

def procesar_remates_valpo(cancel_event, entrada_datos):
    """
    Función principal llamada por main.py.
    Adapta la entrada (lista de imágenes) a la lógica de procesamiento visual.
    """
    logger = get_logger("paso2_valpo", log_dir="logs", log_file="paso2_valpo.log")
    logger.info("🧪 Iniciando Paso 2 (Valparaíso) - MODO DIAGNÓSTICO VISUAL COMPLETO")

    imagenes = []
    if isinstance(entrada_datos, list):
        imagenes = entrada_datos
    elif isinstance(entrada_datos, str) and os.path.exists(entrada_datos):
        with open(entrada_datos, 'r', encoding='utf-8') as f:
            imagenes = [line.strip() for line in f if line.strip()]

    if not imagenes:
        logger.warning("⚠️ No hay imágenes para procesar.")
        return []

    output_folder = "temp_cortes_valpo"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    lista_total_recortes = []

    # Iteramos sobre las imágenes que entregó el paso 1
    for idx, ruta_img in enumerate(imagenes):
        if cancel_event.is_set():
            logger.info("🛑 Proceso cancelado por usuario.")
            break
        
        logger.info(f"👉 Procesando imagen {idx + 1}/{len(imagenes)}: {ruta_img}")
        
        try:
            # Ejecutamos TU lógica de pipeline visual
            recortes_generados = pipeline_total_batch_adaptado(ruta_img, output_folder, logger)
            
            if recortes_generados:
                lista_total_recortes.extend(recortes_generados)
            else:
                logger.warning(f"   ⚠️ No se detectaron bloques válidos (Remate/Juzgado) en: {ruta_img}")

        except Exception as e:
            logger.error(f"   ❌ Error procesando {ruta_img}: {e}")
            # No detenemos el loop, intentamos con la siguiente

    logger.info(f"✅ Diagnóstico finalizado. Columnas guardadas: {len(lista_total_recortes)}")
    return None   #para no seguir al proceso 3


# ==========================================
# LÓGICA ORIGINAL ADAPTADA (FUNCIONES DE APOYO)
# ==========================================

def mostrar_diagnostico_completo(original, limpio, columnas, proy_orig, proy_ref, puntos_corte, umbral, p_borrado, p_ocr):
    """
    Muestra el flujo completo con validación.
    """
    total_cols = len(columnas)
    if total_cols == 0:
        print("  [!] Aviso: No se detectaron columnas en este bloque. Revisar umbrales.")
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7))
        ax1.imshow(cv2.cvtColor(original, cv2.COLOR_BGR2RGB))
        ax1.set_title("BLOQUE ORIGINAL (Sin columnas detectadas)")
        ax2.imshow(cv2.cvtColor(limpio, cv2.COLOR_BGR2RGB))
        ax2.set_title("BLOQUE LIMPIO")
        plt.show()
        return

    colspan_val = max(1, total_cols // 2)
    fig = plt.figure(figsize=(22, 22))
    
    # FILA 1: Procesamiento de Imagen
    ax1 = plt.subplot2grid((4, total_cols), (0, 0), colspan=colspan_val)
    ax1.imshow(cv2.cvtColor(original, cv2.COLOR_BGR2RGB))
    ax1.set_title("1. BLOQUE ORIGINAL")
    ax1.axis('off')
    
    ax2 = plt.subplot2grid((4, total_cols), (0, colspan_val), colspan=total_cols - colspan_val)
    ax2.imshow(cv2.cvtColor(limpio, cv2.COLOR_BGR2RGB))
    ax2.set_title(f"2. BLOQUE LIMPIO (Borrado Pad: {p_borrado}px)")
    ax2.axis('off')

    # FILA 2: Histograma Original
    ax3 = plt.subplot2grid((4, total_cols), (1, 0), colspan=total_cols)
    ax3.plot(proy_orig, color='gray', lw=1, alpha=0.6)
    ax3.fill_between(range(len(proy_orig)), proy_orig, color='gray', alpha=0.2)
    ax3.axhline(y=umbral, color='green', linestyle='-', linewidth=2, label=f'Umbral Crítico ({int(umbral)})')
    ax3.set_title("HISTOGRAMA ORIGINAL")
    ax3.set_xticks(np.arange(0, len(proy_orig) + 1, 50)) # Ajustado paso ticks para legibilidad
    ax3.legend(loc='upper right')

    # FILA 3: Histograma Reforzado
    ax4 = plt.subplot2grid((4, total_cols), (2, 0), colspan=total_cols)
    ax4.plot(proy_ref, color='blue', lw=1)
    ax4.fill_between(range(len(proy_ref)), proy_ref, color='blue', alpha=0.3)
    ax4.axhline(y=umbral, color='green', linestyle='-', linewidth=2)

    for p in puntos_corte:
        ax4.axvline(x=p, color='red', linestyle='--', alpha=0.8)

    ax4.set_title("HISTOGRAMA REFORZADO (Detección Blanco-Pico-Blanco)")
    ax4.set_xticks(np.arange(0, len(proy_orig) + 1, 50))

    # FILA 4: Recortes de Columnas
    for i, col in enumerate(columnas):
        # Manejo seguro de grid si hay muchas columnas
        if i < total_cols:
            ax = plt.subplot2grid((4, total_cols), (3, i))
            ax.imshow(cv2.cvtColor(col, cv2.COLOR_BGR2RGB))
            ax.set_title(f"Col {i+1}")
            ax.axis('off')
            
    plt.tight_layout()
    # Bloqueante para ver el debug visual antes de seguir
    print(">>> Cierra la ventana del gráfico para continuar con la siguiente imagen...")
    plt.show()

def reforzar_divisorias_tenues(binary_img, proyeccion, umbral_alto, r_sensibilidad):
    """
    Versión para producción (usada dentro del flujo).
    """
    img_reforzada = binary_img.copy()
    ancho = len(proyeccion)
    
    proy_suave = savgol_filter(proyeccion, window_length=11, polyorder=2)
    umbral_pico_min = umbral_alto * r_sensibilidad
    umbral_valle_cero = umbral_alto * 0.08
    
    picos_indices, _ = find_peaks(proy_suave, height=umbral_pico_min, distance=15)
    
    radio = 15
    
    for x in picos_indices:
        val_pico = proy_suave[x]
        
        if val_pico >= umbral_alto or x < 20 or x >= ancho - 20:
            continue
        
        # Buscar valles mínimos
        zona_izq = proy_suave[max(0, x - radio) : x]
        zona_der = proy_suave[x + 1 : min(ancho, x + radio + 1)]
        
        valle_izq = np.min(zona_izq) if len(zona_izq) > 0 else val_pico
        valle_der = np.min(zona_der) if len(zona_der) > 0 else val_pico
        
        # Validaciones
        tiene_valle_bajo = valle_izq < umbral_valle_cero or valle_der < umbral_valle_cero
        
        contraste_izq = val_pico / valle_izq if valle_izq > 0 else np.inf
        contraste_der = val_pico / valle_der if valle_der > 0 else np.inf
        contraste_min = min(contraste_izq, contraste_der)
        
        tiene_contraste = contraste_min >= 3.0
        es_maximo = val_pico > proy_suave[x-1] and val_pico > proy_suave[x+1]
        
        if tiene_valle_bajo and tiene_contraste and es_maximo:
            cv2.line(img_reforzada, (x, 0), (x, img_reforzada.shape[0]), 255, 2)
    
    return img_reforzada

def fase2_limpieza_previa(recorte_img, padding_borrado):
    img_limpia = recorte_img.copy()
    gray = cv2.cvtColor(recorte_img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=4)
    ancho_b, alto_b = recorte_img.shape[1], recorte_img.shape[0]
    for i in range(1, num_labels):
        x, y, w, h = stats[i, :4]
        if (w > ancho_b * 0.25 and h > 70) or stats[i, 4] > 5000:
            x_p, y_p = max(0, x - padding_borrado), max(0, y - padding_borrado)
            w_p, h_p = min(ancho_b - x_p, w + (padding_borrado * 2)), min(alto_b - y_p, h + (padding_borrado * 2))
            cv2.rectangle(img_limpia, (x_p, y_p), (x_p + w_p, y_p + h_p), (255, 255, 255), -1)
    return img_limpia

def fase1_segmentar_columnas_completo(img_limpia, p_ocr, h_factor, h_gap, r_activar, r_sens):
    gray = cv2.cvtColor(img_limpia, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)
    proy_original = np.sum(binary, axis=0)
    umbral = np.max(proy_original) * h_factor
    if r_activar and np.max(proy_original) > 0:
        binary = reforzar_divisorias_tenues(binary, proy_original, umbral, r_sens)
    proy_final = np.sum(binary, axis=0)
    indices = np.where(proy_final > umbral)[0]
    lineas = []
    if len(indices) > 0:
        lineas.append(indices[0])
        for i in range(1, len(indices)):
            if indices[i] - indices[i-1] > h_gap:
                lineas.append(indices[i])
    puntos_corte = [0] + lineas + [img_limpia.shape[1]]
    columnas = []
    for i in range(len(puntos_corte) - 1):
        x_s, x_e = max(0, puntos_corte[i] - p_ocr), min(img_limpia.shape[1], puntos_corte[i+1] + p_ocr)
        if (puntos_corte[i+1] - puntos_corte[i]) > 60:
            columnas.append(img_limpia[:, x_s:x_e])
    return columnas, proy_original, proy_final, puntos_corte, umbral

def segmentar_avisos_mejorado(columna_img, visualizar=True):
    """
    Versión mejorada que detecta espacios en blanco (gaps) para separar avisos.
    """
    if len(columna_img.shape) == 3:
        gray = cv2.cvtColor(columna_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = columna_img.copy()
    
    _, binary = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)
    proyeccion = np.sum(binary, axis=1)
    
    proy_suave = savgol_filter(proyeccion, window_length=9, polyorder=2)
    altura = len(proy_suave)
    
    umbral_separador = np.max(proy_suave) * 0.10
    bajo_umbral = proy_suave < umbral_separador
    
    puntos_corte = []
    en_gap = False
    inicio_gap = 0
    min_gap_altura = 8 
    
    for y in range(altura):
        if bajo_umbral[y] and not en_gap:
            en_gap = True
            inicio_gap = y
        elif (not bajo_umbral[y] or y == altura - 1) and en_gap:
            en_gap = False
            altura_gap = y - inicio_gap
            if altura_gap >= min_gap_altura:
                medio = (inicio_gap + y) // 2
                puntos_corte.append(medio)
    
    puntos_corte = [0] + puntos_corte + [altura]
    
    avisos = []
    for i in range(len(puntos_corte) - 1):
        y_inicio = puntos_corte[i]
        y_fin = puntos_corte[i+1]
        if (y_fin - y_inicio) > 40:
            aviso = columna_img[y_inicio:y_fin, :]
            avisos.append(aviso)
    
    if visualizar:
        fig, axes = plt.subplots(1, 2, figsize=(16, 10))
        img_cajas = columna_img.copy()
        for i in range(len(puntos_corte) - 1):
            y_start = puntos_corte[i]
            y_end = puntos_corte[i+1]
            if (y_end - y_start) > 40:
                cv2.rectangle(img_cajas, (2, y_start), (img_cajas.shape[1]-2, y_end), (0, 255, 0), 2)
        
        axes[0].imshow(cv2.cvtColor(img_cajas, cv2.COLOR_BGR2RGB))
        axes[0].set_title(f"Avisos Detectados: {len(avisos)}")
        axes[0].axis('off')
        
        axes[1].plot(proy_suave, range(altura), 'b-', lw=1.5)
        axes[1].fill_betweenx(range(altura), proy_suave, color='blue', alpha=0.2)
        axes[1].axvline(umbral_separador, color='red', ls='--', lw=2, label=f'Umbral ({umbral_separador:.0f})')
        for y in puntos_corte[1:-1]:
            axes[1].axhline(y, color='green', ls='-', lw=2.5, alpha=0.8)
        axes[1].set_ylim([altura, 0])
        axes[1].set_title("Proyección Horizontal (Corte de filas)")
        axes[1].legend()
        plt.tight_layout()
        print(">>> Cierra la ventana de avisos para continuar...")
        plt.show()
    
    return avisos


# ==========================================
# PIPELINE ADAPTADO AL FLUJO PRINCIPAL
# ==========================================

def pipeline_total_batch_adaptado(ruta_img, output_folder, logger):
    """
    Ejecuta el pipeline:
    1. Detectar bloque (Filtro Tesseract 'REMATE'...)
    2. Limpiar
    3. Segmentar Columnas (Genera Gráfico 1)
    4. Segmentar Avisos dentro de columnas (Genera Gráfico 2)
    5. Retorna rutas de COLUMNAS guardadas (para el siguiente paso del sistema)
    """
    # --- Parámetros ajustados (Tus valores originales) ---
    p_borrado = 10
    p_ocr = 10
    h_factor = 0.65
    h_gap = 30
    r_activar = True
    r_sens = 0.10
    # ----------------------------

    img = cv2.imread(ruta_img)
    if img is None:
        logger.error(f"No se pudo cargar: {ruta_img}")
        return []

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 15))
    dilated = cv2.dilate(binary, kernel, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    rutas_columnas_guardadas = []
    base_name = os.path.splitext(os.path.basename(ruta_img))[0]
    bloques_encontrados = 0

    for idx_c, c in enumerate(contours):
        x, y, w, h = cv2.boundingRect(c)
        if w < 250 or h < 250: 
            continue
        
        roi = gray[y:y+h, x:x+w]
        try:
            texto_val = pytesseract.image_to_string(roi, config='--psm 3').upper()
        except Exception as e:
            logger.warning(f"Error Tesseract (¿Instalado?): {e}")
            texto_val = ""

        # FILTRO DE PALABRAS CLAVE
        if any(k in texto_val for k in ["REMATE", "JUZGADO", "EXTRACTO", "JUDICIAL"]):
            bloques_encontrados += 1
            bloque = img[y:y+h, x:x+w]
            
            # FASE 1: Limpiar bloque
            limpio = fase2_limpieza_previa(bloque, p_borrado)
            
            # FASE 2: Segmentar columnas
            cols, p_orig, p_ref, cortes, umb = fase1_segmentar_columnas_completo(
                limpio, p_ocr, h_factor, h_gap, r_activar, r_sens
            )

            if len(cols) == 0:
                continue
            
            # --- DEBUG VISUAL 1: DIAGNÓSTICO DE COLUMNAS ---
            print(f"\n--- MOSTRANDO DIAGNÓSTICO DE COLUMNAS (Bloque {idx_c}) ---")
            mostrar_diagnostico_completo(bloque, limpio, cols, p_orig, p_ref, cortes, umb, p_borrado, p_ocr)
            
            # Guardamos las columnas detectadas (Artifacts para el Paso 3)
            for i, col_img in enumerate(cols):
                col_filename = f"{base_name}_blk{idx_c}_col{i}.jpg"
                col_path = os.path.join(output_folder, col_filename)
                cv2.imwrite(col_path, col_img)
                rutas_columnas_guardadas.append(col_path)
                
                # --- DEBUG VISUAL 2: AVISOS DENTRO DE LA COLUMNA ---
                print(f"   --- Analizando filas internas de Columna {i+1} ---")
                segmentar_avisos_mejorado(col_img, visualizar=True)

    if bloques_encontrados == 0:
        logger.debug("No se encontraron bloques con palabras clave en esta imagen.")

    return rutas_columnas_guardadas