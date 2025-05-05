import os
from dotenv import load_dotenv

# Załaduj zmienne środowiskowe z pliku .env
load_dotenv()

# Podstawowe ustawienia bota
TOKEN = os.getenv("TOKEN")
PREFIX = os.getenv("PREFIX", "%")

# Konfiguracja muzyki
INACTIVITY_TIMEOUT = int(os.getenv("INACTIVITY_TIMEOUT", "300"))
DJ_ROLE_ENABLED = os.getenv("DJ_ROLE_ENABLED", "False").lower() == "true"
DJ_ROLE_NAME = os.getenv("DJ_ROLE_NAME", "DJ")

# Opcje debugowania
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

# Sprawdź, czy token jest dostępny
if not TOKEN:
    print("ERROR: Nie znaleziono tokena bota! Upewnij się, że zmienna TOKEN jest ustawiona w pliku .env")