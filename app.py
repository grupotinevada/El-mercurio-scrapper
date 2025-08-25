import webview
import threading
import main  # Asegúrate de que main.py exista con la función orquestador_con_datos
from logger import get_logger, log_section, dbg

logger = get_logger("app", log_dir="logs", log_file="app.log")

cancel_event = threading.Event()
enable_cleanup = True
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
        import os
        import platform
        import subprocess
        """
        Abre una carpeta en el explorador de archivos del sistema operativo.
        Por defecto, intenta abrir la carpeta 'resultados'.
        """
        try:
            if not os.path.exists(ruta_carpeta):
                print(f"La carpeta '{ruta_carpeta}' no existe. Creándola...")
                os.makedirs(ruta_carpeta)
                logger.info(f"Carpeta '{ruta_carpeta}' creada.")
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

    def procesar_formulario(self, data):
        global cancel_event
        cancel_event.clear()  # Reinicia el evento por si se ejecutó antes

        print("Datos recibidos desde la UI:", data)

        try:
            # Extraer y validar los datos
            url = data.get("url", "").strip()
            paginas_str = data.get("paginas", "0")
            usuario = data.get("usuario", "")
            password = data.get("password", "")

            if not url:
                return {'success': False, 'message': 'Error: La URL no puede estar vacía.'}

            num_paginas = int(paginas_str)

            # Lanzar el hilo para procesar sin bloquear la UI
            thread = threading.Thread(
                target=self._run_proceso,
                args=(url, num_paginas, usuario, password),
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

    def _run_proceso(self, url, paginas, usuario, password):
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
            resultado = main.orquestador_con_datos(url, paginas, usuario, password, cancel_event, enable_cleanup, progress_callback)
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
