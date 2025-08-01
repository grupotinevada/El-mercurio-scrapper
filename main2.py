import re
def unir_palabras_cortadas(texto):
    # Une líneas con guión al final: línea- \n siguiente → línea + siguiente
    # Importante: no añade espacio entre líneas unidas
    texto_unido = re.sub(r'-\n(\s*)', '', texto)
    return texto_unido

def normalizar_espacios(texto):
    texto = '\n'.join(line.strip() for line in texto.splitlines())
    texto = re.sub(r'\n{2,}', '\n', texto)
    texto = re.sub(r'[ \t]{2,}', ' ', texto)
    return texto.strip()

def unir_lineas_normales(texto):
    """
    Une líneas separadas por saltos de línea normales,
    manteniendo separación entre párrafos si aplica más adelante.
    """
    # Paso 1: quitar guiones con salto de línea (ya lo habías hecho antes)
    texto = re.sub(r'-\n\s*', '', texto)

    # Paso 2: reemplazar saltos de línea simples con espacio
    texto = re.sub(r'(?<!\n)\n(?!\n)', ' ', texto)  # solo si no es doble salto

    # Paso 3: reemplazar múltiples espacios por uno solo
    texto = re.sub(r'[ \t]{2,}', ' ', texto)

    # Paso 4: normalizar dobles saltos a uno solo
    texto = re.sub(r'\n{2,}', '\n', texto)

    return texto.strip()


def limpiar_texto_bruto(texto):
    # 1. Remover encabezados de página
    texto = re.sub(r'--- Página \d+ ---', '', texto)

    # 2. Eliminar líneas que contengan solo fechas o palabras tipo "DOMINGO", "ECONÓMICOS CLASIFICADOS", etc.
    lineas = texto.splitlines()
    texto_limpio = []

    for linea in lineas:
        linea_strip = linea.strip()
        if (
            not linea_strip or  # línea vacía
            re.match(r'^(DOMINGO|LUNES|MARTES|MIÉRCOLES|JUEVES|VIERNES|SÁBADO)', linea_strip) or
            re.match(r'^\d+$', linea_strip) or  # solo número
            re.match(r'^ECONÓMICOS CLASIFICADOS$', linea_strip, re.IGNORECASE) or
            re.match(r'^Remates de$', linea_strip, re.IGNORECASE) or
            re.match(r'^propiedades$', linea_strip, re.IGNORECASE) or
            re.match(r'^\d{4}$', linea_strip)  # como "1616"
        ):
            continue  # saltamos esta línea
        texto_limpio.append(linea)

    return '\n'.join(texto_limpio).strip()


def extraer_bloques_remates(texto):
    # Normalizamos saltos de línea
    texto = texto.replace('\r\n', '\n').replace('\r', '\n')

    # Regex para detectar inicio de bloques de remate
    patron = re.compile(
        r'(?=(REMATE(?:S)?(?:\s+\w+)*))',  # grupo de lookahead que captura REMATE, REMATES JUDICIAL, etc.
        re.MULTILINE
    )

    # Encuentra los índices de inicio de cada remate
    indices = [m.start() for m in patron.finditer(texto)]
    bloques = []

    # Cortamos desde cada inicio hasta el próximo (o hasta el final)
    for i in range(len(indices)):
        inicio = indices[i]
        fin = indices[i + 1] if i + 1 < len(indices) else len(texto)
        bloque = texto[inicio:fin].strip()
        bloques.append(bloque)

    return bloques

# Paso 1: Leer archivo
with open("remates_extraidos.txt", "r", encoding="utf-8") as f:
    texto = f.read()

# Paso 2: Limpiar encabezados y secciones
texto_limpio = limpiar_texto_bruto(texto)

# Paso 3: Unir palabras partidas por guión
texto_unido = unir_palabras_cortadas(texto_limpio)

texto_final = normalizar_espacios(texto_unido)

texto_final2 = unir_lineas_normales(texto_final)

# Paso 4: Guardar resultado si se desea
with open("remates_procesado.txt", "w", encoding="utf-8") as f:
    f.write(texto_final2)

remates = extraer_bloques_remates(texto_final2)

# Listas clave para filtrar remates
PALABRAS_INMUEBLE = [
    "inmueble", "departamento", "casa", "propiedad", "terreno", "parcela",
    "condominio", "estacionamiento", "bodega", "sitio", "local comercial", "predio"
]

PALABRAS_EXCLUIR = [
    "vehículo", "automóvil", "camioneta", "motocicleta", "auto",
    "station wagon", "furgón", "camión", "maquinaria", "computador",
    "notebook", "instrumental", "equipos médicos", "muebles", "joyas"
]

def es_remate_de_propiedad(remate):
    texto = remate.lower()
    tiene_inmueble = any(p in texto for p in PALABRAS_INMUEBLE)

    return tiene_inmueble 

# 🔎 Aplicar filtro
remates_propiedades = [r for r in remates if es_remate_de_propiedad(r)]

# 📦 Guardar y mostrar
with open("remates_propiedades.txt", "w", encoding="utf-8") as f:
    for i, remate in enumerate(remates_propiedades, 1):
        f.write(f"\n--- REMATE {i} ---\n{remate}\n")

print(f"Se encontraron {len(remates_propiedades)} remates de propiedades.")

