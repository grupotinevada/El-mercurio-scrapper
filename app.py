import webview
import threading
import os
import platform
import subprocess
import main  # Asegúrate de que main.py exista con la función orquestador_con_datos
import macal
from logger import get_logger, log_section, dbg

logger = get_logger("app", log_dir="logs", log_file="app.log")

cancel_event = threading.Event()
enable_cleanup = False
window = None

import sys
import ctypes

if sys.platform == "win32":
    # Obtiene el handle de la ventana de la consola
    hWnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hWnd:
        SW_MINIMIZE = 6
        ctypes.windll.user32.ShowWindow(hWnd, SW_MINIMIZE)

class Api:

    """
    Clase que expone la funcionalidad del backend (Python) al frontend (JavaScript).
    """
    def abrir_carpeta(self, ruta_carpeta="outputs"):
        print(f"Intentando abrir la carpeta: {ruta_carpeta}")
        

        """
        Abre una carpeta en el explorador de archivos del sistema operativo.
        Por defecto, intenta abrir la carpeta 'resultados'.
        """
        try:
            if not os.path.exists(ruta_carpeta):
                print(f"La carpeta '{ruta_carpeta}' no existe. Creándola...")
                os.makedirs(ruta_carpeta)
                logger.info(f"Carpeta '{ruta_carpeta}' creada.")
                
            ruta_macal = "propiedades_macal"
            if not os.path.exists(ruta_macal):
                os.makedirs(ruta_macal)
                
            sistema = platform.system()
            print("aaaaaaaaaaaa")
            
            if sistema == 'Windows':
                print(f"Abriendo carpeta: {os.path.abspath(ruta_carpeta)}")
                os.startfile(os.path.abspath(ruta_carpeta))
            elif sistema == 'Darwin':
                print(f"Abriendo carpeta: {os.path.abspath(ruta_carpeta)}")
                subprocess.Popen(['open', os.path.abspath(ruta_carpeta)])
            elif sistema == 'Linux':
                print(f"Abriendo carpeta: {os.path.abspath(ruta_carpeta)}")
                subprocess.Popen(['xdg-open', os.path.abspath(ruta_carpeta)])
            else:
                return {'success': False, 'message': f'Error: Sistema operativo no soportado para esta función: {sistema}'}
            
            return {'success': True, 'message': f'Carpeta "{ruta_carpeta}" abierta con éxito.'}

        except Exception as e:
            logger.info(f"Error al intentar abrir la carpeta: {e}")
            return {'success': False, 'message': f'Ocurrió un error al abrir la carpeta: {e}'}
        
    def abrir_carpeta_macal(self):
        """
        Abre la carpeta de resultados específica para el extractor de Macal.
        """
        ruta_macal = "propiedades_macal"
        logger.info(f"Intentando abrir la carpeta de Macal: {ruta_macal}")
        try:
            # Asegura que la carpeta exista antes de intentar abrirla
            os.makedirs(ruta_macal, exist_ok=True)
            sistema = platform.system()
            if sistema == 'Windows':
                os.startfile(os.path.abspath(ruta_macal))
            elif sistema == 'Darwin':
                subprocess.Popen(['open', os.path.abspath(ruta_macal)])
            elif sistema == 'Linux':
                subprocess.Popen(['xdg-open', os.path.abspath(ruta_macal)])
            else:
                return {'success': False, 'message': f'Sistema operativo no soportado: {sistema}'}
            return {'success': True, 'message': f'Carpeta "{ruta_macal}" abierta.'}
        except Exception as e:
            logger.error(f"Error al abrir la carpeta de Macal: {e}")
            return {'success': False, 'message': f'Ocurrió un error al abrir la carpeta: {e}'}


    def procesar_formulario(self, data):
        global cancel_event
        cancel_event.clear()  # Reinicia el evento por si se ejecutó antes

        print("Datos recibidos desde la UI:", data)

        try:
            # Extraer y validar los datos
            url = data.get("url", "").strip()
            paginas_str = data.get("paginas", "0")

            if not url:
                return {'success': False, 'message': 'Error: La URL no puede estar vacía.'}

            num_paginas = int(paginas_str)

            # Lanzar el hilo para procesar sin bloquear la UI
            thread = threading.Thread(
                target=self._run_proceso_mercurio,
                args=(url, num_paginas),
                daemon=True
            )
            thread.start()

            # Mensaje inicial
            return {'success': True, 'message': '¡Proceso iniciado correctamente! Revisa la consola para ver el progreso.'}

        except ValueError:
            return {'success': False, 'message': 'Error: El número de páginas debe ser un valor numérico válido.'}
        except Exception as e:
            print(f"Ocurrió un error inesperado: {e}")
            return {'success': False, 'message': f'Ocurrió un error inesperado: {e}'}
        
        
    def ejecutar_macal(self):
        """
        Lanza la ejecución del extractor de Macal en un hilo separado.
        """
        logger.info("Solicitud recibida para ejecutar el extractor de Macal.")
        try:
            thread = threading.Thread(target=self._run_proceso_macal, daemon=True)
            thread.start()
            return {'success': True, 'message': 'Proceso de Macal iniciado.'}
        except Exception as e:
            logger.error(f"Error al iniciar el hilo de Macal: {e}")
            return {'success': False, 'message': f'Error al iniciar el proceso: {e}'}

    def _run_proceso_macal(self):
            """
            Contiene la lógica para ejecutar el script de Macal y notificar a la UI.
            """
            global window
            logger.info("Iniciando la ejecución de macal.run_extractor...")
            
            def progress_callback(porcentaje, mensaje):
                """Esta función se encargará de enviar el progreso a la interfaz."""
                if window:
                    # Escapamos comillas para no romper el string de JavaScript
                    mensaje_escapado = mensaje.replace("'", "\\'")
                    window.evaluate_js(f"actualizarProgreso({porcentaje}, '{mensaje_escapado}')")
                
            try:
                # Define las URLs y el nombre de archivo aquí
                SEARCH_URL = "https://api-net.macal.cl/api/v1/properties/search"
                DETAILS_URL = "https://api-net.macal.cl/api/v1/properties/details"
                OUTPUT_FILENAME = "propiedades_macal" # Carpeta de salida
                os.makedirs(OUTPUT_FILENAME, exist_ok=True) # Asegura que la carpeta exista
                output_filename = os.path.join(OUTPUT_FILENAME, "propiedades_macal_final.xlsx")

                # Ejecuta la función principal de tu script
                macal.run_extractor_macal(SEARCH_URL, DETAILS_URL, output_filename, progress_callback=progress_callback)
                
                # Si todo sale bien, notifica a la UI
                if window:
                    logger.info("Proceso de Macal finalizado con éxito.")
                    window.evaluate_js("finalizarProcesoMacal('✅ Proceso Macal completado con éxito!', 'success')")

            except Exception as e:
                logger.error(f"Error crítico durante la ejecución de Macal: {e}")
                # Si hay un error, notifica a la UI
                if window:
                    mensaje_error = f"Error en el proceso Macal: {e}".replace("'", "\\'")
                    window.evaluate_js(f"finalizarProcesoMacal('{mensaje_error}', 'error')")

    def _run_proceso_mercurio(self, url, paginas):
        """
        Ejecuta el orquestador y notifica a la UI si hubo cancelación o finalización.
        """
        global window
        
        def progress_callback(porcentaje, mensaje):
            if window:
                # Escapamos comillas simples en el mensaje para no romper el JS
                mensaje_escapado = mensaje.replace("'", "\\'")
                window.evaluate_js(f"actualizarProgreso({porcentaje}, '{mensaje_escapado}')")
                
        try:
            resultado = main.orquestador_con_datos(url, paginas, cancel_event, enable_cleanup, progress_callback)
            # Al final, actualizar mensaje en la UI
            if cancel_event.is_set():
                if window: # ✅ 3. Usa la variable window para llamar al método
                    window.evaluate_js("actualizarMensajeUI('⛔ Proceso cancelado por el usuario.', 'warning')")
            else:
                if window:
                    window.evaluate_js("actualizarMensajeUI('✅ Proceso completado con éxito!', 'success')")

        except Exception as e:
            # Notificar error en UI
            msg = f"Ocurrió un error inesperado durante la ejecución: {e}"
            if window:
                window.evaluate_js(f"actualizarMensajeUI('{msg}', 'error')")
        
        finally:
            if window:
                window.evaluate_js("ocultarProgreso()")
                window.evaluate_js("habilitarBoton()")

    def cancelar_proceso(self):
        """
        Permite al usuario cancelar el proceso en curso desde la UI.
        """
        global cancel_event
        if cancel_event.is_set():
            return {'success': False, 'message': 'No hay un proceso en ejecución para cancelar.'}
        
        cancel_event.set()
        # Notifica inmediatamente a la UI
        webview.evaluate_js("actualizarMensajeUI('⛔ El proceso fue cancelado por el usuario.', 'warning')")
        return {'success': True, 'message': '⛔ El proceso fue cancelado por el usuario.'}


if __name__ == "__main__":
    
    api = Api()
    window = webview.create_window(
        "Extractor de Remates",
        "templates/index.html",
        js_api=api,
        width=750,
        height=780,
        resizable=True
    )
    
    webview.start(debug=False)
