```markdown
Work In Progress
```



# 🎵 MusicBot - Discord Music Bot 🎧

**Wielojęzyczny bot muzyczny dla Discorda z zaawansowanymi funkcjami!**

[![GitHub Stars](https://img.shields.io/github/stars/PeterPage2115/Discord-Music-Bot?style=social)](https://github.com/PeterPage2115/Discord-Music-Bot)
[![GitHub Issues](https://img.shields.io/github/issues/PeterPage2115/Discord-Music-Bot)](https://github.com/PeterPage2115/Discord-Music-Bot/issues)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Dostępne języki:** [English](#english) | [Polski](#polski)

---

<a name="english"></a>

## 📖 About 

MusicBot is a feature-rich Discord music bot that brings your favorite tunes from YouTube directly to your voice channels. Enjoy seamless music playback with powerful features like queue management, a DJ role system, volume control, and much more!

### ✨ Key Features

-   **Effortless Playback:** Play music from YouTube links or search for tracks directly within Discord.
-   **Playlist Support:** Add entire YouTube playlists to the queue and let the music play on.
-   **Queue Mastery:** Manage your queue like a pro! View, clear, shuffle, and remove specific tracks with ease.
-   **DJ Role System:** Control who gets to control the music with the flexible DJ role permission system.
-   **Playback Control:** Pause, resume, skip, and stop playback with intuitive commands.
-   **Volume Control:** Adjust the volume to the perfect level for everyone to enjoy.
-   **Loop Modes:** Repeat your favorite song or keep the queue going on a loop.
-   **Interactive UI:** Enjoy a responsive user interface with embedded messages and interactive buttons.

### 🚀 Get Started

#### 1. Prerequisites

-   Python 3.10 or higher
-   FFmpeg (installed and added to your system's PATH)
-   Discord Bot Token (get yours from the [Discord Developer Portal](https://discord.com/developers/applications))

#### 2. Installation Steps


# Clone the repository
```bash
git clone [https://github.com/PeterPage2115/Discord-Music-Bot.git](https://github.com/PeterPage2115/Discord-Music-Bot.git)
cd MusicBot
```
# Install dependencies
```bash
pip install -r requirements.txt
```
# Create .env file with your bot's configuration
```bash
echo "DISCORD_TOKEN=your_token_here" > .env  # Replace 'your_token_here' with your actual token
echo "PREFIX=%" >> .env             # Set your desired command prefix
echo "DJ_ROLE_ENABLED=True" >> .env  # Enable/disable the DJ role system
```
# Run the bot!
```bash
python bot.py
```
3. Discord Bot Setup

Create a Bot: Go to the Discord Developer Portal and create a new application, then convert it to a bot.
Enable Message Content Intent: In your bot's settings, under "Privileged Gateway Intents", make sure "Message Content Intent" is enabled. This is crucial for the bot to function correctly.
Invite the Bot: Invite your bot to your server using the generated OAuth2 URL. Ensure it has the necessary permissions (e.g., View Channel, Send Messages, Connect, Speak).

🎶 Commands
Use %musichelp or %mh to display a comprehensive list of all available commands within Discord.

Here are a few essential commands to get you started:

```markdown
%play <link/search term>: Play music from a YouTube link or search for a song.
%skip: Skip the currently playing track.
%pause: Pause the current playback.
%resume: Resume paused playback.
%queue: View the current music queue.
%shuffle: Shuffle the order of tracks in the queue.
%loop: Toggle loop mode for the current track or the entire queue.
%volume <0-100>: Adjust the bot's volume.
```

🧪 Running Tests
Ensure everything is working correctly by running the tests:

```bash
pip install -r requirements-dev.txt
pytest tests
```
📄 License
This project is licensed under the MIT License. See the LICENSE file for more details.

--------------------------------------------------------------------------------------------------------------------------------------------------------------------

📖 O projekcie

MusicBot to w pełni funkcjonalny bot muzyczny dla Discorda, który umożliwia odtwarzanie muzyki z YouTube na kanałach głosowych. Bot zawiera funkcje takie jak zarządzanie kolejką, system ról DJ, kontrolę głośności i wiele więcej.

🌟 Funkcje

Odtwarzanie muzyki z linków YouTube lub fraz wyszukiwania
Dodawanie całych playlist YouTube do kolejki
Zarządzanie kolejką (przeglądanie, czyszczenie, mieszanie, usuwanie konkretnych utworów)
System ról DJ do zarządzania uprawnieniami
Kontrola odtwarzania (pauza, wznowienie, pomijanie, zatrzymanie)
Regulacja głośności
Tryby powtarzania (pojedynczy utwór lub cała kolejka)
Responsywny interfejs użytkownika z osadzonymi wiadomościami i przyciskami
🛠️ Instalacja
1. Wymagania wstępne:
```markdown
Python 3.10 lub nowszy
FFmpeg zainstalowany w systemie
Token bota Discord
```
2. Konfiguracja:
```bash
# Klonowanie repozytorium
git clone [https://github.com/PeterPage2115/Discord-Music-Bot.git](https://github.com/PeterPage2115/Discord-Music-Bot.git)
cd MusicBot
```
```bash
# Instalacja zależności
pip install -r requirements.txt
```
```bash
# Utwórz plik .env z tokenem Discord
echo "DISCORD_TOKEN=twoj_token_tutaj" > .env
echo "PREFIX=%" >> .env
echo "DJ_ROLE_ENABLED=True" >> .env
```
```bash
# Uruchom bota
python bot.py
```
Konfiguracja bota Discord:

Utwórz bota na Discord Developer Portal
Włącz "Message Content Intent" w ustawieniach bota
Zaproś bota na swój serwer z odpowiednimi uprawnieniami


 Komendy
Użyj %musichelp lub %mh, aby zobaczyć wszystkie dostępne komendy w Discordzie.
```markdown
%play <link/fraza> - Odtwarzaj muzykę z YouTube
%skip - Pomiń aktualny utwór
%pause - Wstrzymaj odtwarzanie
%resume - Wznów odtwarzanie
%queue - Zobacz aktualną kolejkę
%shuffle - Wymieszaj kolejkę
I wiele innych!
```
🧪 Uruchamianie testów
```bash
pip install -r requirements-dev.txt
pytest tests
```
📄 Licencja
Ten projekt jest licencjonowany na warunkach licencji MIT - szczegóły znajdują się w pliku LICENSE.
