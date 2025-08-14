import re
from typing import List, Optional
import json

def limpiar_encabezados_y_guardar(
    input_path: str,
    output_path: str = "remates_limpio.txt"
) -> str:
    """
    Limpia un archivo de texto de remates, eliminando encabezados y
    separando cada aviso al identificar su título (líneas en mayúsculas).
    Devuelve el texto limpio y guarda una copia si se indica output_path.
    """
    with open(input_path, "r", encoding="utf-8") as f:
        texto = f.read()

    texto_limpio = limpiar_encabezados(texto)
    # Se reemplaza la función de spaCy por la de RegEx, que es más precisa para esta tarea.
    texto_limpio = insertar_separadores(texto_limpio)
    texto_limpio = limpiar_lineas_vacias(texto_limpio)

    # Guardar el resultado si se proporciona un path
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(texto_limpio)
        print(f"✅ Texto limpio y separado correctamente guardado en: {output_path}")

    return texto_limpio


def limpiar_encabezados(texto: str) -> str:
    """
    Elimina encabezados no relevantes y une líneas mal separadas usando una lista de patrones.
    """
    # Patrones para eliminar encabezados y paginación (sin cambios)
    patrones_eliminar = [
        r"---\s+PÁGINA\s+\d+\s+---\s*\n\d+\s*\n",
        r"^(?:LUNES|MARTES|MIÉRCOLES|JUEVES|VIERNES|SÁBADO|DOMINGO)\s+\d{1,2}\s+DE\s+[A-ZÁÉÍÓÚÑ]+\s+DE\s+\d{4}$",
        r"1611\s+JUDICIALES",
        r"1612\s+REMATES",
        r"1616\s+REMATES\s+DE\s+PROPIEDADES",
        r"1635\s+PERSONAS\s+BUSCADAS\s+Y\s+COSAS\s+PERDIDAS",
        r"1640\s+CITAN\s+A\s+REUNIÓN\s+INSTITUCIONES",
        r"\bECONÓMICOS\s+CLASIFICADOS\b",
        r"---\s+Página\s+\d+\s+---",
        r"^\s*\d+\s*$"
    ]
    for patron in patrones_eliminar:
        texto = re.sub(patron, "", texto, flags=re.IGNORECASE | re.MULTILINE)

    # Lista de patrones para unir líneas que son continuaciones de un párrafo
    patrones_union = [
        # Une palabras cortadas por guión (ej: "propieda-\ndes")
        (r"(\w+)-\s*\n\s*(\w+)", r"\1\2"),
        # Une líneas en medio de un correo electrónico (ej: "correo\n@pjud.cl")
        (r"([a-zA-Z0-9_.-])\s*\n\s*(@)", r"\1\2"),
        # Une líneas después de dos puntos (ej: "correo:\najurzua@uc.cl")
        (r"(:)\s*\n\s*([a-zA-Z0-9])", r"\1 \2"),
        # Une una descripción con su número (ej: "Piso\n3")
        (r'\b(N|N°|Nº|Departamento|Depto|Oficina|Of|Bodega|Estacionamiento|Rol|Piso)\s*\n\s*(\d+)', r'\1 \2'),
        # Une una línea que termina en número con la siguiente que empieza en minúscula (ej: "inciso 5\ndel artículo")
        (r"(\d)\s*\n\s*([a-z])", r"\1 \2"),
        # Une una línea que termina en minúscula/coma con la siguiente que empieza en mayúscula (nuestra regla anterior)
        (r"([a-z0-9,])\s*\n\s*([A-Z][a-z])", r"\1 \2")
    ]

    for patron, reemplazo in patrones_union:
        texto = re.sub(patron, reemplazo, texto, flags=re.IGNORECASE)

    return texto


def insertar_separadores(texto: str) -> str:
    """
    Inserta un doble salto de línea antes de posibles encabezados de remate.
    El patrón es flexible con espacios, acentos y mayúsculas/minúsculas.
    """
    # Lista de frases clave que suelen iniciar remates
    claves = [
        r"REMATE",
        r"EXTRACTO",
        r"JUZGADO\s+DE\s+POLIC[ÍI]A\s+LOCAL",
        r"JUZGADO\s+DE\s+LETRAS",
        r"JUEZ\s+ARBITRO",
        r"LICITACI[ÓO]N\s+REMATE",
        r"EN\s+JUICIO\s+PARTICI[ÓO]N",
        r"OFERTA\s+REMATE",
        r"VENTA\s+EN\s+REMATE",
        r"ANTE\s+EL\s+\d{1,2}°?\s+JUZGADO\s+CIVIL",
        r"\d{1,2}°?\s+JUZGADO\s+CIVIL",  # Detecta "1° JUZGADO CIVIL", "15° JUZGADO CIVIL"
        r"VIG[ÉE]SIMO",  # Vigésimo, Vigésimo segundo...
        r"D[ÉE]CIMO",    # Décimo, Décimo cuarto...
    ]

    # Unir todas las frases clave en un solo patrón con espacios flexibles (\s+)
    patron_frases = "|".join(claves)

    # Patrón para detectar saltos de línea antes de cualquier encabezado
    patron_separador = rf"""
        \n                                  # Salto de línea antes
        (?=                                 # Lookahead: debe cumplirse pero no se consume
            \s*                             # Espacios iniciales
            (?:{patron_frases})             # Cualquiera de las frases clave
            (?:\s+[A-ZÁÉÍÓÚÑ\d]+)*           # Palabras extra en mayúsculas o números
        )
    """

    return re.sub(patron_separador, "\n\n", texto, flags=re.MULTILINE | re.VERBOSE )


def limpiar_lineas_vacias(texto: str) -> str:
    """
    Estandariza los saltos de línea múltiples a doble salto.
    """
    return re.sub(r"\n\s*\n+", "\n\n", texto).strip()



def es_encabezado(linea: str) -> bool:
    """
    Determina si una línea es un encabezado en mayúsculas reales (tolerando acentos y Ñ).
    """
    palabras = linea.strip().split()
    if len(palabras) < 3:
        return False
    mayusculas = sum(1 for c in linea if c.isupper() or c in "ÁÉÍÓÚÑÜ")
    total = sum(1 for c in linea if c.isalpha())
    return total > 0 and (mayusculas / total) > 0.8


def extraer_parrafos_remates(texto: str) -> List[str]:
    """
    Extrae párrafos de remates desde un texto limpio, considerando los encabezados.
    """

    parrafos_brutos = texto.split('\n\n')
    parrafos_limpios = []
    for p in parrafos_brutos:
        parrafo_procesado = " ".join(p.strip().splitlines())
        if parrafo_procesado:
            parrafos_limpios.append(parrafo_procesado)
    
    return parrafos_limpios


def procesar_remates(input_path: str, archivo_final: str = "remates_separados.json") -> None:
    """
    Ejecuta el pipeline completo: limpieza, separación, extracción y escritura de remates.
    """
    texto_limpio = limpiar_encabezados_y_guardar(input_path, output_path="remates_limpio.txt")

    parrafos = extraer_parrafos_remates(texto_limpio)

    lista_remates = []
    for i, p in enumerate(parrafos, 1):
        remate_obj = {
            "id_remate": i,
            "remate": p.strip()  
        }
        lista_remates.append(remate_obj)
           
    with open(archivo_final, "w", encoding="utf-8") as f:
        json.dump(lista_remates, f, indent=4, ensure_ascii=False)

    print(f"✅ Archivo final con remates en formato JSON guardado en: {archivo_final}")


# Punto de entrada
if __name__ == "__main__":
    procesar_remates("remates_extraidos.txt")