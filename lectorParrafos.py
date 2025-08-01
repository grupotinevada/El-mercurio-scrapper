import re
import pandas as pd

def normalizar_espacios(texto):
    return re.sub(r"\s+", " ", texto.replace("\n", " ")).strip()

def extraer_info_remate(texto):
    texto = normalizar_espacios(texto)
    data = {
        "Nombre Propiedad Remates": "",
        "Proveedor Compra": "",
        "Tipo Propiedad": "",
        "Direccion": "",
        "Forma Pago Garantia": "",
        "Comuna": "",
        "Region": "",
        "Villa": "",
        "Postura Minima (UF)": "",
        "Postura Minima ($)": "",
        "Banco": "",
        "Corte": "",
        "Tribunal": "",
        "Fecha Remate": "",
        "URL Zoom": "",
        "Rol de la Causa": "",
        "Comentarios": texto
    }

    # Tribunal
    m = re.search(r"REMATE[:\-]?\s*(.+?),\s*Hu[ée]rfanos.*?,", texto, re.IGNORECASE)
    if m:
        data["Tribunal"] = m.group(1).strip()

    # Dirección del tribunal
    m = re.search(r"Hu[ée]rfanos\s+(\d+)", texto, re.IGNORECASE)
    if m:
        data["Direccion"] = f"Huérfanos {m.group(1)}"

    # Fecha de remate
    m = re.search(r"(?:el\s+)?(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})", texto, re.IGNORECASE)
    if m:
        data["Fecha Remate"] = m.group(1).strip()

    # Tipo y nombre de propiedad
    m = re.search(r"(departamento|casa|parcela)\s+(n[uú]mero\s+)?([^\s,]+).*?edificio\s+[‘\"']?(.+?)[,\.]", texto, re.IGNORECASE)
    if m:
        tipo = m.group(1).capitalize()
        numero = m.group(3)
        edificio = m.group(4).strip("‘'\" ")
        data["Tipo Propiedad"] = tipo
        data["Nombre Propiedad Remates"] = f"{tipo} {numero}, Edificio {edificio}"

    # Comuna y región
    m = re.search(r"comuna\s+y\s+regi[oó]n\s+de\s+([a-zA-ZÁÉÍÓÚÑáéíóúñ\s]+)", texto, re.IGNORECASE)
    if m:
        region = m.group(1).strip().title()
        data["Region"] = region
        if not data["Comuna"]:
            data["Comuna"] = region

    m = re.search(r"comuna\s+de\s+([a-zA-ZÁÉÍÓÚÑáéíóúñ\s]+)", texto, re.IGNORECASE)
    if m:
        data["Comuna"] = m.group(1).strip().title()

    m = re.search(r"Conservador De Bienes Ra[ií]ces De\s+([a-zA-Z\s]+?)\.", texto, re.IGNORECASE)
    if m:
        data["Comuna"] = m.group(1).strip()

    # Monto en UF
    m = re.search(r"mínimo.*?([\d.,]+)\s*uf", texto, re.IGNORECASE)
    if m:
        data["Postura Minima (UF)"] = m.group(1).replace(",", ".")

    # Monto en pesos si no hay UF
    if not data["Postura Minima (UF)"]:
        m = re.search(r"mínimo\s*(subasta\s*será\s*la\s*cantidad\s*de)?\s*\$?\s*([\d\.]+)", texto, re.IGNORECASE)
        if m:
            data["Postura Minima ($)"] = m.group(2).replace(".", "")

    # Garantía
    if "10%" in texto and "vale vista" in texto:
        data["Forma Pago Garantia"] = "10% del precio mínimo con vale vista"

    # Banco / Proveedor Compra
    m = re.search(r"Caratulados\s+(.*?)\s*/", texto, re.IGNORECASE)
    if m:
        banco = m.group(1).strip()
        data["Banco"] = banco
        data["Proveedor Compra"] = banco
    else:
        m = re.search(r"expediente\s+[‘\"]?(.+?)\s+Con", texto, re.IGNORECASE)
        if m:
            banco = m.group(1).strip()
            data["Banco"] = banco
            data["Proveedor Compra"] = banco

    # Rol de la causa
    m = re.search(r"rol\s*[n°º:]?\s*(C-\d{3,6}-\d{4})", texto, re.IGNORECASE)
    if m:
        data["Rol de la Causa"] = m.group(1).strip()

    # URL de Zoom
    m = re.search(r"https?://[^\s]+zoom[^\s]*", texto)
    if m:
        data["URL Zoom"] = m.group(0).strip()
    elif "plataforma zoom" in texto.lower():
        data["URL Zoom"] = "Zoom implícito (requiere solicitud por correo)"

    return data

def procesar_txt_multiples_remates(path_entrada: str, path_salida: str = "remates.xlsx"):
    with open(path_entrada, "r", encoding="utf-8") as f:
        contenido = f.read()

    bloques = re.split(r"##REMATE\s+\d+##", contenido, flags=re.IGNORECASE)
    registros = []

    for bloque in bloques:
        bloque = bloque.strip()
        if not bloque:
            continue
        datos = extraer_info_remate(bloque)
        registros.append(datos)

    df = pd.DataFrame(registros)
    df.to_excel(path_salida, index=False)
    print(f"✅ {len(registros)} remates extraídos y guardados en '{path_salida}'")

# Ejecutar si se usa como script principal
if __name__ == "__main__":
    procesar_txt_multiples_remates("remates_extraidos.txt")
