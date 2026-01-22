# El Mercurio Scraper & House Pricing Tool

Este proyecto es una aplicación de escritorio desarrollada con Python y `pywebview` que permite la extracción y procesamiento de avisos de remates de propiedades desde "El Mercurio" (Santiago y Regiones) y "Macal", así como una herramienta de tasación de propiedades (House Pricing) basada en análisis de PDFs y comparación de mercado.

## 📋 Descripción General

El sistema integra múltiples flujos de trabajo en una sola interfaz gráfica unificada:

1.  **Scraper El Mercurio:**
    *   **Santiago:** Extracción web mediante Selenium y procesamiento de texto con Regex.
    *   **Regiones (Valparaíso, Antofagasta, Concepción/El Sur):** Descarga de imágenes de la edición impresa, segmentación de columnas y extracción de texto mediante OCR en la nube (Google Cloud Vision).
    *   **Inteligencia Artificial:** Uso de OpenAI para limpiar, estructurar y enriquecer los datos extraídos.

2.  **Scraper Macal:**
    *   Extracción directa desde la API de Macal para obtener listados de propiedades.

3.  **House Pricing (Tasación):**
    *   Ingesta masiva de PDFs de propiedades.
    *   Búsqueda automática de comparables en portales inmobiliarios usando Selenium.
    *   Generación de reportes de valoración en Excel.

## 🏗 Arquitectura del Proyecto

El proyecto sigue una arquitectura modular donde la interfaz de usuario (Frontend) está desacoplada de la lógica de negocio (Backend), comunicándose a través de una API expuesta por `pywebview`.

### Estructura Principal

*   **Frontend:** `templates/index.html`. Interfaz web que se carga en la ventana de escritorio.
*   **Backend (Controlador):** `app.py`. Entry point de la aplicación. Define la clase `Api` que recibe las peticiones desde JS e invoca a los orquestadores.
*   **Orquestadores:**
    *   `main.py`: Maneja la lógica de "El Mercurio". Decide qué estrategia usar según la URL (Santiago o Regional).
    *   `housePrincing/main_hp.py`: Maneja el flujo completo de House Pricing.
    *   `macal.py`: Maneja la extracción de Macal.

### Módulos Clave

*   **`valpoOCR/`:** Contiene la lógica específica para diarios regionales (corte de imágenes, filtrado, preparación para OCR).
*   **`housePrincing/`:**
    *   `paso1_hp.py`: Extracción de datos desde PDFs.
    *   `paso2_hp.py`: Enriquecimiento y búsqueda de comparables (Web Scraping).
    *   `paso3_hp.py`: Generación de reportes Excel.
*   **`paso1_copy.py`, `paso2_copy.py`, `paso3_copy.py`:** Lógica legacy/específica para El Mercurio Santiago y procesamiento final con IA.

## 🛠 Requisitos Previos

*   **Python 3.x**
*   **Google Chrome** (para Selenium).
*   **Cuenta de Google Cloud** con Vision API habilitada (archivo de credenciales JSON requerido).
*   **OpenAI API Key** (para el procesamiento de texto avanzado).

## 🚀 Instalación

1.  Clonar el repositorio.
2.  Instalar las dependencias listadas en `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```
3.  Asegurarse de tener las credenciales necesarias:
    *   Archivo JSON de Google Cloud Vision en la raíz (ej. `cloud-vision-api-....json`).
    *   Configuración de credenciales de OpenAI (verificar `paso3_copy.py` o variables de entorno).

## ▶️ Uso

Para iniciar la aplicación, ejecutar el script principal `app.py`:

```bash
python app.py
```

Esto abrirá una ventana de escritorio desde la cual se pueden controlar todos los procesos.

## 📂 Estructura de Carpetas

*   **`outputs/`**: Resultados finales del scraper de El Mercurio (JSON y Excel).
*   **`propiedades_macal/`**: Resultados del scraper de Macal.
*   **`house_pricing_outputs/`**: Reportes finales de la herramienta House Pricing.
*   **`input_pdfs/`**: Carpeta donde se cargan los PDFs para el proceso de House Pricing.
*   **`logs/`**: Archivos de registro (logs) de la ejecución.
*   **`templates/`**: Archivos HTML/CSS/JS de la interfaz gráfica.

## ⚠️ Notas Importantes

*   La carpeta `temp_...` y archivos temporales se limpian automáticamente finalizar el proceso, pero pueden persistir si hay errores críticos (configurable en `app.py`).
*   Modo Debug: `enable_cleanup = False` en `app.py` permite conservar archivos intermedios para depuración.

---
**Desarrollado para:** Automatización de extracción de remates y tasaciones.
