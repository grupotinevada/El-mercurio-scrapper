import webview
import threading
import html

def mostrar_preview_html(file_path: str, cancel_event: threading.Event):
    """
    Crea una ventana de pywebview para mostrar y editar el contenido de un archivo.
    La ejecución del script que llama a esta función se bloquea hasta que la 
    ventana de previsualización se cierra.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        content = f"Error: No se pudo encontrar el archivo {file_path}"
    except Exception as e:
        content = f"Error al leer el archivo: {e}"

    # Evento para sincronizar el hilo de trabajo con el hilo de la GUI
    is_window_closed = threading.Event()
    window_ref = []  # Usamos una lista para pasar la referencia de la ventana

    # Clase API para comunicar la ventana HTML con Python
    class Api:
        def get_initial_data(self):
            """
            Función que JavaScript llamará para obtener el contenido inicial.
            """
            return {
                "filePath": file_path,
                "content": content
            }

        def guardar_y_cerrar(self, new_content):
            """
            Guarda el contenido modificado en el archivo y cierra la ventana.
            """
            print("📝 Guardando cambios y continuando...")
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                if window_ref:
                    window_ref[0].destroy()
            except Exception as e:
                print(f"Error al guardar el archivo: {e}")

        def cerrar_sin_guardar(self):
            """
            Cierra la ventana sin guardar cambios.
            """
            print("❌ Cambios descartados. Continuando...")
            if window_ref:
                window_ref[0].destroy()
        
        def cancelar_proceso_entero(self):
            """
            Activa el evento de cancelación global y cierra la ventana.
            """
            print("🛑 Proceso completo cancelado por el usuario.")
            cancel_event.set() # <-- ¡Importante! Señala al hilo de trabajo que debe detenerse.
            if window_ref:
                window_ref[0].destroy()


    api = Api()

    # Función que se ejecutará cuando la ventana se cierre
    def on_closed():
        is_window_closed.set() # Señala al evento que la ventana se ha cerrado

    # Crear la ventana (esto es seguro desde un hilo secundario)
    window = webview.create_window(
        f"Previsualización - {file_path}",
        "templates/preview.html", # Carga el archivo HTML
        js_api=api,
        width=800,
        height=600,
        resizable=True
    )
    window_ref.append(window)
    
    # Suscribirse al evento 'closed' de la ventana
    window.events.closed += on_closed
    
    # Bloquea el hilo de trabajo (background) hasta que el evento se active
    is_window_closed.wait()
