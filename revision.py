import webview
import threading
import os

def mostrar_revision(lista_validos: list, lista_descartados: list, cancel_event: threading.Event):
    """
    Abre una ventana para que el usuario revise y mueva ítems entre 
    la lista de Válidos y Descartados.
    
    Retorna: (lista_validos_final, lista_descartados_final)
    """
    
    # Contenedores para almacenar la respuesta del usuario
    resultado = {
        "validos": lista_validos,
        "descartados": lista_descartados,
        "confirmado": False
    }
    
    is_window_closed = threading.Event()
    window_ref = []

    class Api:
        def get_data(self):
            return {
                "validos": lista_validos,
                "descartados": lista_descartados
            }

        def confirmar_revision(self, nuevos_validos, nuevos_descartados):
            print(f"✅ Revisión confirmada. A procesar: {len(nuevos_validos)} | Descartados: {len(nuevos_descartados)}")
            resultado["validos"] = nuevos_validos
            resultado["descartados"] = nuevos_descartados
            resultado["confirmado"] = True
            
            if window_ref:
                window_ref[0].destroy()

        def cancelar(self):
            print("🛑 Revisión cancelada por el usuario.")
            cancel_event.set()
            if window_ref:
                window_ref[0].destroy()

    def on_closed():
        is_window_closed.set()

    api = Api()
    
    window = webview.create_window(
        "Revisión de Remates Detectados",
        "templates/revision.html",
        js_api=api,
        width=1280,
        height=850,
        resizable=True,
        on_top=True
    )
    window_ref.append(window)
    window.events.closed += on_closed

    # Bloqueamos el hilo hasta que se cierre la ventana
    is_window_closed.wait()

    # Si el usuario cerró la ventana con la X sin confirmar, asumimos cancelación o mantener original
    # Para seguridad, si no confirmó, retornamos lo que entró pero verificamos cancel_event
    if not resultado["confirmado"] and not cancel_event.is_set():
        # Si cerró con la X, podemos preguntar o asumir cancelación. 
        # Aquí asumiremos que si cierra sin confirmar, quiere cancelar el proceso.
        print("⚠️ Ventana cerrada sin confirmar. Cancelando proceso.")
        cancel_event.set()

    return resultado["validos"], resultado["descartados"]