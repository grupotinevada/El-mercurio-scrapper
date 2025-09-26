import pandas as pd
import sys

def analizar_columnas(nombre_archivo='debug_data.csv'):
    """
    Analiza el archivo de datos crudos para encontrar el tamaño de fuente principal
    y las coordenadas que dividen las columnas.
    """
    try:
        # Cargar el archivo CSV usando el delimitador correcto
        df = pd.read_csv(nombre_archivo, delimiter='|')
    except FileNotFoundError:
        print(f"--- ERROR ---")
        print(f"No se encontró el archivo '{nombre_archivo}'.")
        print("Asegúrate de que este script esté en la misma carpeta que tu archivo CSV.")
        sys.exit(1)
    except Exception as e:
        print(f"--- ERROR ---")
        print(f"No se pudo leer el archivo. Causa: {e}")
        sys.exit(1)

    print("--- 1. Análisis de Tamaño de Fuente ---")
    if 'font_size' not in df.columns:
        print("El archivo CSV no contiene la columna 'font_size'. No se puede continuar.")
        sys.exit(1)

    # Encontrar el tamaño de fuente más común (el del texto principal)
    font_size_counts = df['font_size'].value_counts()
    main_font_size = font_size_counts.idxmax()
    print(f"El tamaño de fuente más común (texto principal) es: {main_font_size}px")

    # Filtrar los datos para quedarnos solo con el texto principal
    df_filtered = df[df['font_size'] == main_font_size].copy()
    print(f"Se conservaron {len(df_filtered)} fragmentos de texto para el análisis de columnas.\n")

    print("--- 2. Análisis de Posición de Columnas ---")
    if 'left' not in df_filtered.columns:
        print("El archivo CSV no contiene la columna 'left'. No se puede continuar.")
        sys.exit(1)

    # Obtener todas las coordenadas 'left' únicas y ordenarlas
    sorted_left_coords = sorted(df_filtered['left'].unique())

    # Calcular las brechas (gaps) entre cada coordenada consecutiva
    gaps = [sorted_left_coords[i+1] - sorted_left_coords[i] for i in range(len(sorted_left_coords) - 1)]

    # Una forma robusta de encontrar las columnas es buscar las brechas más grandes.
    # Si esperamos 7 columnas, debe haber 6 brechas grandes (gutters).
    NUM_COLUMNAS_ESPERADAS = 7

    # Ordenamos las brechas de mayor a menor para encontrar las más grandes
    sorted_gaps = sorted(gaps, reverse=True)

    # Tomamos las N-1 brechas más grandes como los gutters principales
    main_gutters = sorted_gaps[:NUM_COLUMNAS_ESPERADAS - 1]

    # El umbral para ser un gutter es el tamaño de la brecha más pequeña de este grupo
    if not main_gutters:
         print("No se encontraron suficientes brechas para determinar las columnas.")
         sys.exit(1)

    min_gutter_size = min(main_gutters)

    print(f"Se detectaron {NUM_COLUMNAS_ESPERADAS} columnas.")
    print(f"Cualquier brecha mayor a {min_gutter_size:.2f}px se considerará un separador.\n")

    # Calcular los puntos medios de estas brechas para obtener los divisores
    dividers = []
    for i in range(len(sorted_left_coords) - 1):
        gap = sorted_left_coords[i+1] - sorted_left_coords[i]
        if gap >= min_gutter_size:
            dividers.append(sorted_left_coords[i] + gap / 2)

    print("--- 3. RESULTADO FINAL ---")
    print("Copia y pega todo este bloque en el chat:\n")
    print("---------------------------------------------")
    print(f"main_font_size = {main_font_size}")
    print("dividers = [")
    for d in sorted(dividers):
        print(f"    {d},")
    print("]")
    print("---------------------------------------------")

if __name__ == '__main__':
    # Asegúrate de tener pandas instalado. Si no, abre tu terminal y ejecuta:
    # pip install pandas
    analizar_columnas()