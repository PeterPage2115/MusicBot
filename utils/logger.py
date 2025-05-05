import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Upewnij się, że katalog logs istnieje
if not os.path.exists('logs'):
    os.makedirs('logs')

# Data do nazwy pliku logu
current_date = datetime.now().strftime("%Y-%m-%d")
log_file = f"logs/musicbot_{current_date}.log"

# Konfiguracja formatowania logów
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def get_logger(name='MusicBot'):
    """
    Tworzy i zwraca logger z określoną konfiguracją.
    
    Args:
        name: Nazwa loggera
        
    Returns:
        Skonfigurowany logger
    """
    logger = logging.getLogger(name)
    
    # Jeśli logger już jest skonfigurowany, zwróć go
    if logger.handlers:
        return logger
    
    # Ustaw poziom logowania
    logger.setLevel(logging.DEBUG)
    
    # Utwórz i skonfiguruj handler dla pliku z rotacją
    # 5 MB maksymalny rozmiar pliku, maksymalnie 5 plików backupowych
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Utwórz i skonfiguruj handler dla konsoli
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)  # Konsola pokazuje tylko INFO i wyżej
    
    # Dodaj handlery do loggera
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger