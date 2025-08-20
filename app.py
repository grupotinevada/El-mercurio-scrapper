import webview
import threading
import main  # Asegúrate de que main.py exista con la función orquestador_con_datos

cancel_event = threading.Event()
enable_cleanup = True
window = None

class Api:
    """
    Clase que expone la funcionalidad del backend (Python) al frontend (JavaScript).
    """
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
        width=650,
        height=680,
        resizable=True
    )
    
    webview.start(debug=False)
