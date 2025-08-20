# logger.py
import logging
import os
import sys
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)  # Inicializa colorama para colores en consola

class ColoredFormatter(logging.Formatter):
    """Formatter que agrega colores según nivel de log en consola"""
    LEVEL_COLORS = {
        logging.DEBUG: Fore.WHITE,
        logging.INFO: Fore.CYAN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA
    }

    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelno, Fore.WHITE)
        msg = super().format(record)
        return f"{color}{msg}{Style.RESET_ALL}"

def get_logger(name: str, log_dir: str = "logs", log_file: str = None,
               level_console=logging.INFO, level_file=logging.DEBUG) -> logging.Logger:
    """
    Devuelve un logger configurado para archivo y consola con colores en consola.
    - name: nombre del logger (usualmente __name__ del módulo que lo llama)
    - log_dir: carpeta donde guardar el log
    - log_file: nombre de archivo, si no se da se crea con timestamp
    - level_console: nivel mínimo para consola
    - level_file: nivel mínimo para archivo
    """
    os.makedirs(log_dir, exist_ok=True)

    if log_file is None:
        log_file = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    log_path = os.path.join(log_dir, log_file)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Siempre capturamos todo en el logger

    # Evitar handlers duplicados
    if logger.handlers:
        return logger

    # Formato base
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter_file = logging.Formatter(fmt)
    formatter_console = ColoredFormatter(fmt)

    # Handler archivo
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(level_file)
    fh.setFormatter(formatter_file)
    logger.addHandler(fh)

    # Handler consola
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level_console)
    ch.setFormatter(formatter_console)
    logger.addHandler(ch)

    return logger

def log_section(logger: logging.Logger, name: str):
    """Marca una sección destacada en los logs"""
    logger.info("")
    logger.info("="*12 + f" [{name}] " + "="*12)

def dbg(logger: logging.Logger, msg: str):
    """Función rápida para debug"""
    logger.debug(msg)
