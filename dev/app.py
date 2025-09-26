import webview
import threading
import main  # Asegúrate de que main.py exista con la función orquestador_con_datos

cancel_event = threading.Event()

class Api:
    """
    Clase que expone la funcionalidad del backend (Python) al frontend (JavaScript).
    """
    def procesar_formulario(self, data):
        global cancel_event
        # Reinicia el evento por si se ejecutó antes
        cancel_event.clear()
        """
        Recibe los datos del formulario HTML, los valida y comienza el proceso
        en un hilo separado para no bloquear la interfaz de usuario.
        """
        print("Datos recibidos desde la UI:", data)

        try:
            # Extraer y validar los datos
            url = data.get("url", "").strip()
            paginas_str = data.get("paginas", "0")
            
            if not url:
                # Devolvemos un diccionario para que JS pueda interpretarlo
                return {'success': False, 'message': 'Error: La URL no puede estar vacía.'}

            num_paginas = int(paginas_str)

            # Iniciar el proceso pesado en un hilo secundario para no congelar la app
            # daemon=True asegura que el hilo se cerrará si la aplicación principal se cierra
            thread = threading.Thread(
                target=main.orquestador_con_datos,
                args=(url, num_paginas, cancel_event),
                daemon=True
            )
            thread.start()

            return {'success': True, 'message': '¡Proceso iniciado correctamente! Revisa la consola para ver el progreso.'}

        except ValueError:
            return {'success': False, 'message': 'Error: El número de páginas debe ser un valor numérico válido.'}
        except Exception as e:
            # Captura cualquier otro error inesperado
            print(f"Ocurrió un error inesperado: {e}")
            return {'success': False, 'message': f'Ocurrió un error inesperado: {e}'}


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