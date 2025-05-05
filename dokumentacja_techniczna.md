📚 MusicBot - Dokumentacja techniczna
English | Polski

<a name="polski"></a>

📋 Struktura projektu

MusicBot/
├── bot.py              # Główny plik bota
├── config.py           # Konfiguracja bota
├── .env                # Zmienne środowiskowe (token, prefiks)
├── requirements.txt    # Zależności projektu
├── requirements-dev.txt # Zależności deweloperskie
├── tests/              # Testy
└── cogs/
    └── music/          # Moduł muzyczny
        ├── __init__.py # Inicjalizacja coga
        ├── base.py     # Klasa bazowa Music
        ├── player.py   # Funkcje odtwarzania muzyki
        ├── queue_manager.py # Zarządzanie kolejką
        ├── ui.py       # Interfejs użytkownika
        └── utils.py    # Narzędzia pomocnicze
└── utils/
    └── helpers.py      # Klasy pomocnicze do obsługi YouTube

🔧 Komponenty systemu
1. Główny bot (bot.py)
Plik bot.py zawiera inicjalizację bota Discord, ładowanie rozszerzeń (cogów) i funkcję główną obsługującą cykl życia bota.

2. Konfiguracja (config.py)
Moduł config.py zawiera konfigurację bota, ładuje zmienne środowiskowe z pliku .env, takie jak token Discord, prefiks komend oraz ustawienia systemu DJ.

3. Cog muzyczny (cogs/music/)
3.1 Klasa bazowa (base.py)
Music to główna klasa coga, która:

Inicjalizuje stan bota muzycznego
Przechowuje kolejki, aktualnie odtwarzane utwory i ustawienia
Integruje komponenty gracza, zarządzania kolejką i interfejsu użytkownika
3.2 Odtwarzacz (player.py)
Moduł odpowiedzialny za:

Połączenie z kanałami głosowymi
Odtwarzanie muzyki z YouTube
Sterowanie odtwarzaniem (start, pauza, wznowienie, zatrzymanie)
Zarządzanie głośnością
3.3 Zarządzanie kolejką (queue_manager.py)
Moduł obsługujący:

Wyświetlanie aktualnej kolejki utworów
Dodawanie pojedynczych utworów i playlist
Usuwanie utworów z kolejki
Mieszanie i czyszczenie kolejki
Zarządzanie trybami powtarzania
3.4 Interfejs użytkownika (ui.py)
Moduł zawierający:

Wizualne wyświetlanie informacji o utworach
Przyciski interaktywne do sterowania odtwarzaczem
Komendy pomocnicze i informacyjne
System embedów
3.5 Narzędzia pomocnicze (utils.py)
Zawiera:

System uprawnień DJ
Sprawdzanie uprawnień użytkowników
Narzędzia pomocnicze dla innych modułów
4. Klasy pomocnicze (utils/helpers.py)
Moduł helpers.py zawiera:

Klasę YTDLSource do obsługi źródeł audio z YouTube
Konfigurację yt-dlp/youtube-dl
Przetwarzanie metadanych utworów
🔐 System DJ
Bot implementuje system uprawnień DJ, który kontroluje, kto może używać określonych komend muzycznych. Użytkownik ma uprawnienia DJ, gdy:

Jest administratorem serwera
Ma rolę "DJ" (jeśli funkcja jest włączona w konfiguracji)
Jest sam na kanale głosowym z botem
Komendy wymagające uprawnień DJ:

skip - Pomijanie utworów
pause - Wstrzymywanie odtwarzania
resume - Wznawianie odtwarzania
stop - Zatrzymywanie odtwarzania
volume - Zmiana głośności
shuffle - Mieszanie kolejki
i inne komendy wpływające na odsłuch innych użytkowników
🧪 Testowanie
System testów jest oparty na pytest i pytest-asyncio, pozwalając na testowanie asynchronicznych funkcji bota. Główne kategorie testów:

Testy jednostkowe dla klas i funkcji
Testy funkcjonalne dla komend
Testy integracyjne sprawdzające współpracę komponentów
📝 Rozszerzanie bota
Aby dodać nowe funkcje do bota:

Nowe komendy muzyczne: Rozszerz odpowiedni moduł w music
Nowe cogi: Utwórz nowy folder w cogs i zaimplementuj podobną strukturę
Modyfikacja istniejących komend: Edytuj odpowiednie pliki modułów
📊 Wydajność i ograniczenia
Bot jest zaprojektowany do obsługi wielu serwerów jednocześnie
Każdy serwer ma własną kolejkę i stan odtwarzania
Streaming wideo wymaga dobrego połączenia internetowego serwera
Duże playlisty mogą wymagać znacznych zasobów podczas ładowania