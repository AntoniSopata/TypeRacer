# TypeRacer - SK2 Projekt

## Grupa:
- 155937
- 155953

Komendy by uruchomić:

make all

./serwer

python3 klient.py


Opis:
TypeRacer - wieloosobowa gra polegająca na szybkim pisaniu na klawiaturze

### Zasady gry:
- Gracz łączy się do serwera i wysyła swój nick (jeśli nick jest już zajęty, serwer prosi o podanie innego nicku).

- W grze istnieje wiele pokoi, które mogą pomieścić maksymalnie 4 graczy. Pierwszy gracz, który dołączy do pokoju, zostaje administratorem gry i ma możliwość jej rozpoczęcia.

- Gracze widzą listę wszystkich pozostałych uczestników. Administrator widzi dodatkowo przycisk umożliwiający rozpoczęcie gry.

- Po rozpoczęciu gry przez administratora, serwer losuje tekst z bazy. Gracze widzą:
- tekst do przepisania
- pole do wpisywania tekstu
- postęp wszystkich graczy (pozycja samochodów)
- czas od rozpoczęcia wyścigu

### Podczas pisania:
- gracze wpisują znaki do pola. Po kliknięciu spacji/ostatniej kropki wyraz znika
- każdy błąd jest oznaczany i musi zostać poprawiony
- postęp gracza jest na bieżąco aktualizowany u wszystkich uczestników
- gracze widzą swoją aktualną prędkość pisania WPM

### Wyścig kończy się, gdy:
- ostatni gracz bezbłędnie przepisze cały tekst
- lub gdy upłynie maksymalny czas

### Po zakończeniu wyścigu gracze widzą:
- ranking z wynikami (nick, WPM, czas ukończenia, średnią prędkość, poprawność)
- przycisk umożliwiający rozpoczęcie gry jeśli osoba jest administratorem gry
- gracz może w dowolnym momencie opuścić pokój. Jeśli administrator opuści grę, jego rolę przejmuje kolejny gracz.
