import sys
import os
import platform
import subprocess
import threading
import ctypes
import webview
import shutil
# Módulos propios
import main  # El Mercurio
import macal
from logger import get_logger
from housePrincing import main_hp

# --- Configuración Inicial ---
logger = get_logger("app", log_dir="logs", log_file="app.log")

# --- Utilidades del Sistema ---
def ocultar_consola_windows():
    """Oculta la ventana de consola si se ejecuta en Windows."""
    if sys.platform == "win32":
        hWnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hWnd:
            SW_MINIMIZE = 6
            ctypes.windll.user32.ShowWindow(hWnd, SW_MINIMIZE)

def abrir_ruta_sistema(ruta):
    """Abre una carpeta o archivo en el explorador del sistema operativo correspondiente."""
    try:
        if not os.path.exists(ruta):
            return False, f"La ruta '{ruta}' no existe."

        ruta_abs = os.path.abspath(ruta)
        sistema = platform.system()
        
        logger.info(f"Abriendo ruta en {sistema}: {ruta_abs}")

        if sistema == 'Windows':
            os.startfile(ruta_abs)
        elif sistema == 'Darwin': # macOS
            subprocess.Popen(['open', ruta_abs])
        elif sistema == 'Linux':
            subprocess.Popen(['xdg-open', ruta_abs])
        else:
            return False, f"Sistema operativo no soportado: {sistema}"
        
        return True, f"Carpeta abierta con éxito."
    except Exception as e:
        logger.error(f"Error al abrir ruta: {e}")
        return False, f"Error del sistema: {e}"

# --- Clase API ---
class Api:
    """
    Puente de comunicación entre el Frontend (JS) y el Backend (Python).
    """
    def __init__(self):
        self._window = None
        self.cancel_event = threading.Event()
        self.enable_cleanup = True
        
        # Rutas constantes
        self.DIR_OUTPUTS = "outputs"
        self.DIR_MACAL = "propiedades_macal"
        self.DIR_HP_OUTPUT = "reporte_final_housepricing.json"
        self.DIR_HP_INPUT = "./input_pdfs"

    def set_window(self, window):
        """Asigna la instancia de la ventana de pywebview a la API."""
        self._window = window

    # --- Métodos Auxiliares de UI ---
    def _enviar_js(self, script):
        """Ejecuta JS en la ventana de forma segura."""
        if self._window:
            self._window.evaluate_js(script)

    def _actualizar_progreso_ui(self, porcentaje, mensaje):
        """Callback estandarizado para actualizar barras de progreso."""
        mensaje_escapado = mensaje.replace("'", "\\'")
        self._enviar_js(f"actualizarProgreso({porcentaje}, '{mensaje_escapado}')")

    # --- Funcionalidades Expuestas ---

    def abrir_carpeta(self, ruta_carpeta="outputs"):
        """Abre la carpeta general de resultados."""
        # Asegurar creación de directorios base
        os.makedirs(self.DIR_OUTPUTS, exist_ok=True)
        os.makedirs(self.DIR_MACAL, exist_ok=True)

        print(f"Intentando abrir la carpeta: {ruta_carpeta}")
        
        # Si la ruta no existe, la creamos (comportamiento original)
        if not os.path.exists(ruta_carpeta):
            os.makedirs(ruta_carpeta)
            logger.info(f"Carpeta '{ruta_carpeta}' creada.")

        exito, mensaje = abrir_ruta_sistema(ruta_carpeta)
        return {'success': exito, 'message': mensaje}

    def abrir_carpeta_macal(self):
        """Abre la carpeta específica de Macal."""
        os.makedirs(self.DIR_MACAL, exist_ok=True)
        exito, mensaje = abrir_ruta_sistema(self.DIR_MACAL)
        return {'success': exito, 'message': mensaje}

    # NUEVO: Método para abrir carpeta HP
    def abrir_carpeta_hp(self):
        os.makedirs(self.DIR_HP, exist_ok=True)
        exito, mensaje = abrir_ruta_sistema(self.DIR_HP)
        return {'success': exito, 'message': mensaje}

    def cancelar_proceso(self):
        """Señaliza la cancelación del proceso actual."""
        if self.cancel_event.is_set():
            return {'success': False, 'message': 'No hay un proceso en ejecución para cancelar.'}
        
        self.cancel_event.set()
        self._enviar_js("actualizarMensajeUI('⛔ El proceso fue cancelado por el usuario.', 'warning')")
        return {'success': True, 'message': '⛔ Proceso cancelado.'}

    # --- Lógica de Negocio: El Mercurio ---

    def procesar_formulario(self, data):
        """Valida datos e inicia el scraper de El Mercurio."""
        self.cancel_event.clear()
        print("Datos recibidos:", data)

        try:
            url = data.get("url", "").strip()
            paginas = int(data.get("paginas", "0"))
            columnas = int(data.get("columnas", "7").strip())

            if not url:
                return {'success': False, 'message': 'Error: La URL es obligatoria.'}

            thread = threading.Thread(
                target=self._run_proceso_mercurio,
                args=(url, paginas, columnas),
                daemon=True
            )
            thread.start()
            return {'success': True, 'message': 'Proceso iniciado correctamente.'}

        except ValueError:
            return {'success': False, 'message': 'Error: Páginas y columnas deben ser números.'}
        except Exception as e:
            return {'success': False, 'message': f'Error inesperado: {e}'}

    def _run_proceso_mercurio(self, url, paginas, columnas):
        try:
            resultado = main.orquestador_con_datos(
                url, paginas, columnas, 
                self.cancel_event, 
                self.enable_cleanup, 
                self._actualizar_progreso_ui
            )

            if self.cancel_event.is_set():
                self._enviar_js("actualizarMensajeUI('⛔ Proceso cancelado por el usuario.', 'warning')")
            else:
                self._enviar_js("actualizarMensajeUI('✅ Proceso completado con éxito!', 'success')")

        except Exception as e:
            msg = f"Error inesperado: {e}"
            self._enviar_js(f"actualizarMensajeUI('{msg}', 'error')")
        
        finally:
            self._enviar_js("ocultarProgreso()")
            self._enviar_js("habilitarBoton()")

    # --- Lógica de Negocio: Macal ---

    def ejecutar_macal(self):
        """Inicia el extractor de Macal."""
        logger.info("Iniciando extractor Macal.")
        try:
            thread = threading.Thread(target=self._run_proceso_macal, daemon=True)
            thread.start()
            return {'success': True, 'message': 'Proceso de Macal iniciado.'}
        except Exception as e:
            logger.error(f"Error al iniciar Macal: {e}")
            return {'success': False, 'message': f'Error: {e}'}

    def _run_proceso_macal(self):
        logger.info("Ejecutando macal.run_extractor...")
        try:
            SEARCH_URL = "https://api-net.macal.cl/api/v1/properties/search"
            DETAILS_URL = "https://api-net.macal.cl/api/v1/properties/details"
            output_filename = os.path.join(self.DIR_MACAL, "propiedades_macal_final.xlsx")

            # Ejecución del script externo
            macal.run_extractor_macal(
                SEARCH_URL, DETAILS_URL, output_filename, 
                progress_callback=self._actualizar_progreso_ui
            )
            
            logger.info("Macal finalizado con éxito.")
            self._enviar_js("finalizarProcesoMacal('✅ Proceso Macal completado con éxito!', 'success')")

        except Exception as e:
            logger.error(f"Error crítico en Macal: {e}")
            mensaje_error = f"Error en Macal: {e}".replace("'", "\\'")
            self._enviar_js(f"finalizarProcesoMacal('{mensaje_error}', 'error')")

    # --- NUEVA LÓGICA: House Pricing ---
    def seleccionar_archivos_hp(self):
        """Abre diálogo nativo para elegir PDFs y los mueve a input_pdfs."""
        try:
            file_types = ('PDF Files (*.pdf)', 'All files (*.*)')
            # Abre diálogo de selección múltiple
            archivos = self._window.create_file_dialog(
                webview.OPEN_DIALOG, 
                allow_multiple=True, 
                file_types=file_types
            )

            if not archivos:
                return {'success': True, 'count': 0}

            # Preparar carpeta de inputs (Limpiar anterior)
            if os.path.exists(self.DIR_HP_INPUT):
                shutil.rmtree(self.DIR_HP_INPUT)
            os.makedirs(self.DIR_HP_INPUT)

            # Copiar archivos seleccionados
            for ruta_origen in archivos:
                if os.path.isfile(ruta_origen):
                    nombre = os.path.basename(ruta_origen)
                    ruta_destino = os.path.join(self.DIR_HP_INPUT, nombre)
                    shutil.copy2(ruta_origen, ruta_destino)

            logger.info(f"Se copiaron {len(archivos)} PDFs a {self.DIR_HP_INPUT}")
            return {'success': True, 'count': len(archivos)}

        except Exception as e:
            logger.error(f"Error seleccionando archivos: {e}")
            return {'success': False, 'message': str(e)}

    def ejecutar_house_pricing(self):
        """Dispara el main_hp.py en un hilo separado."""
        self.cancel_event.clear()
        
        # Verificar si hay archivos
        if not os.path.exists(self.DIR_HP_INPUT) or not os.listdir(self.DIR_HP_INPUT):
            return {'success': False, 'message': 'No hay archivos cargados. Selecciona PDFs primero.'}

        logger.info("Iniciando orquestador HP...")
        
        try:
            thread = threading.Thread(target=self._run_proceso_hp, daemon=True)
            thread.start()
            return {'success': True, 'message': 'Proceso iniciado.'}
        except Exception as e:
            return {'success': False, 'message': f'Error al iniciar hilo: {e}'}

    def _run_proceso_hp(self):
        try:
            # Aquí llamamos al main() de tu orquestador nuevo
            # Nota: main_hp.main() no recibe argumentos, lee de ./input_pdfs
            main_hp.main()

            if self.cancel_event.is_set():
                self._enviar_js("actualizarHPStatus('⛔ Proceso cancelado.', 'warning')")
            else:
                self._enviar_js("actualizarHPStatus('✅ Proceso masivo completado!', 'success')")

        except Exception as e:
            logger.error(f"Error fatal en HP: {e}")
            msg = f"Error: {e}".replace("'", "\\'")
            self._enviar_js(f"actualizarHPStatus('{msg}', 'error')")
        finally:
            self._enviar_js("finalizarProcesoHP()")


# --- Main Entry Point ---
if __name__ == "__main__":
    
    # 1. Configuración de entorno
    ocultar_consola_windows()
    
    # 2. Inicialización API
    api = Api()
    
    # 3. Creación de ventana
    window = webview.create_window(
        "Extractor de Remates",
        "templates/index.html",
        js_api=api,
        width=750,
        height=780,
        resizable=True
    )
    
    # 4. Vincular ventana a la API (Inyección de dependencia)
    api.set_window(window)
    
    # 5. Iniciar Loop
    webview.start(debug=False)