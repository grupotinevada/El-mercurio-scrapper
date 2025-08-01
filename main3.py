import re

def limpiar_encabezados_y_guardar(input_path: str, output_path: str = "remates_limpio.txt") -> None:
    with open(input_path, "r", encoding="utf-8") as f:
        texto = f.read()

    patrones = [
        r"1611\s+JUDICIALES",
        r"1612\s+REMATES",
        r"1616\s+REMATES\s+DE\s+PROPIEDADES",
        r"1635\s+PERSONAS\s+BUSCADAS\s+Y\s+COSAS\s+PERDIDAS",
        r"1640\s+CITAN\s+A\s+REUNIÓN\s+INSTITUCIONES",
        r"---\s+PÁGINA\s+\d+\s+---",
        r"\b(?:LUNES|MARTES|MIÉRCOLES|JUEVES|VIERNES|SÁBADO|DOMINGO)\s+\d{1,2}\s+DE\s+[A-ZÁÉÍÓÚÑ]+\s+DE\s+\d{4}",
        r"\bECONÓMICOS\s+CLASIFICADOS\b",
        r"\n{2,}\s*\d{1,}\s*\n{2,}"
    ]

    for patron in patrones:
        texto = re.sub(patron, '\n\n', texto, flags=re.IGNORECASE)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(texto)

    print(f"Texto limpio guardado en: {output_path}")


def es_encabezado(linea: str) -> bool:
    palabras = linea.strip().split()
    if len(palabras) < 3:
        return False
    mayusculas = sum(1 for c in linea if c.isupper())
    total = sum(1 for c in linea if c.isalpha())
    if total == 0:
        return False
    return mayusculas / total > 0.8


def extraer_parrafos_remates(texto: str) -> list[str]:
    lineas = texto.splitlines()
    parrafos = []
    parrafo_actual = []

    for linea in lineas:
        if es_encabezado(linea):
            if parrafo_actual:
                parrafos.append(" ".join(parrafo_actual).strip())
                parrafo_actual = []
            parrafo_actual.append(linea.strip())
        elif linea.strip() == "":
            if parrafo_actual:
                parrafos.append(" ".join(parrafo_actual).strip())
                parrafo_actual = []
        else:
            parrafo_actual.append(linea.strip())

    if parrafo_actual:
        parrafos.append(" ".join(parrafo_actual).strip())

    return parrafos


def procesar_remates(input_path: str, archivo_final: str = "remates_final.txt") -> None:
    # Paso 1: limpiar encabezados
    limpiar_encabezados_y_guardar(input_path)

    # Paso 2: leer el archivo limpio
    with open("remates_limpio.txt", "r", encoding="utf-8") as f:
        texto_limpio = f.read()

    # Paso 3: extraer párrafos
    parrafos = extraer_parrafos_remates(texto_limpio)

    # Paso 4: guardar resultados
    with open(archivo_final, "w", encoding="utf-8") as f:
        for i, p in enumerate(parrafos, 1):
            f.write(f"### REMATE {i} ###\n{p}\n\n")

    print(f"Archivo final con remates guardado en: {archivo_final}")

# Ejecutar el pipeline completo
procesar_remates("remates_extraidos.txt")
