# OPP Cancel Popups — wydanie 1.4

Popupy anulowania dla obserwatorów i sędziów StarCraft II. Wydanie obejmuje
budowy, aktywne i oczekujące jednostki/ulepszenia, addony, anulowalne przemiany
oraz warp-iny przerwane utratą zasilania Prisma lub Pylona.

## Użycie w grze

W SC2 wybierz **Custom → Melee → mapę → Create with Mod** i wyszukaj
**OPP Cancel Popups**. Gotowy mod jest dostępny na Battle.net:

| Region | Wersja nakładki | Autor |
| --- | --- | --- |
| EU | 1.4 | Auddi |
| US | 1.1 | Polkiujhy |
| KR / Azja | 1.1 | Auddi |

Numery są regionalne; wszystkie trzy publikacje zawierają ten sam kod.
Każda jest **Public / Unlocked** i korzysta z osobno opublikowanej zależności
**Observer PlusPlus - Popup Fix 1.0**, również dostępnej w EU/US/KR.
Przy uruchomieniu gotowego moda gra pobiera jego zależności.
Nie trzeba uruchamiać patchera ani instalować źródeł z GitHub, aby grać.

## Co poprawia 1.4

- Oczekujące popupy tego samego właściciela, kategorii i typu łączą się w całej
  kolejce: Oracle, Phoenix, Oracle daje Oracle ×2, potem Phoenix. Wiek
  oczekującej grupy nie rozdziela jej na kilka wpisów.
- Anulowania sześciu addonów działają zarówno przez budynek nadrzędny, jak
  i addon. Podpisy wskazują rodzica: **Tech Lab - Barracks/Factory/Starport**
  i **Reactor - Barracks/Factory/Starport**.
- Obsługiwane są anulowalne procesy Morph/MorphPlacement, w tym Lair, Hive,
  Greater Spire, Ravager, Lurker, Baneling, Brood Lord, Overseer, transportowy
  Overlord, Planetary Fortress, Orbital Command i oba kierunki Gateway/Warp Gate.
  Popup pokazuje cel przemiany.
- Zamknięcie Warp Prisma lub zniszczenie zasilającego Prisma/Pylona liczy
  rzeczywiście przerwane warp-iny według typu i właściciela jednostki.
  Każda jednostka jest liczona raz. Zachowane alternatywne zasilanie i ukończenie
  nie tworzą anulowania.
- Osobny fix Obs++ poprawia indeksy graczy w BattleReport, które powodowały
  błąd przy przerwanych warp-inach. Zachowuje raport i zwykłe statystyki walki.

Pozostają trzy wiersze w stałej pozycji pod produkcją, kolor właściciela,
ikona, nazwa i duże **CANCELLED**. Grupa jest widoczna przez pięć sekund czasu
gry; kolejne anulowanie aktywnej grupy zwiększa licznik i odnawia timer.
Po wygaśnięciu nowe anulowanie zaczyna nowy licznik. Dalsze grupy czekają
w osobnej kolejce. Trwające badanie i powiadomienia Denied GameHeart są zachowane.
Popupy są przeznaczone wyłącznie dla obserwatorów/sędziów; debug jest wyłączony.

## Obs++: zależność i źródła poprawki

**Sama nakładka nie naprawia starego Observer PlusPlus.** Gotowe wydanie
korzysta z **Observer PlusPlus - Popup Fix 1.0**. Przy własnej integracji wybierz
tę zależność z Battle.net w edytorze zamiast starego Observer PlusPlus.
Nie dodawaj obu kopii Obs++ jednocześnie. Zachowaj Void Multi i WCS GameHeart.

Oryginalny Observer PlusPlus: **nice__username / ESLMaps**.
Pełny Obs++, jego biblioteki i zasoby nie są zawarte w tym repozytorium ani ZIP-ie.
Publikujemy własny patcher, manifest zgodnego wejścia i krótkie fragmenty poprawki.
[Instrukcja patchera i szczegóły naprawy](OBSERVER-PLUSPLUS-PATCH.md) są dla
autorów pracujących na lokalnych komponentach. Patcher przyjmuje tylko dokładnie
określone, niezmienione wejście; nie służy do ponownego patchowania wersji Popup Fix.

## Zawartość paczki dla autorów modów

- `files/`: własna biblioteka, Triggers, rejestracja, layout, style i teksty.
- `source/`: siedem edytowalnych modułów Galaxy.
- `tools/generate_mod.py` i `tools/galaxy_sources.json`: generator i kolejność modułów.
- `tools/patch_observer_plus_plus.py` oraz `src/observer-plusplus-patches/`:
  własna poprawka zależności, bez pełnego Obs++.
- `SHA256SUMS`: sumy kontrolne wszystkich pozostałych plików paczki.

ZIP jest pakietem integracyjnym dla autora moda. Nie jest samodzielnym modem
do otwarcia w grze. Nie zawiera prywatnych map testowych, banków, replayów,
cache, kont ani narzędzi binarnych.

## Integracja do własnego moda

1. Pracuj na kopii docelowego moda. Wybierz w edytorze zgodne zależności:
   Void Multi, WCS GameHeart oraz **Observer PlusPlus - Popup Fix 1.0**.
   Przy integracji bezpośrednio do źródeł Obs++ zastosuj naprawę BattleReport
   w tej kopii, bez dodawania zależności moda od samego siebie.
2. Sprawdź, czy biblioteka `C0DEC0DE`, symbole `OPP_*`, style `OPPCancel*`
   i ramki `OPPCancelRow*` już nie istnieją. Nie instaluj nakładki jednocześnie
   przez zależność i bezpośrednie scalenie źródeł.
3. Skopiuj dwa własne pliki `LibC0DEC0DE*.galaxy` oraz
   `UI/Layout/OPPCancelPopups.SC2Layout`, zachowując ścieżki w `Base.SC2Data`.
4. **Scal Triggers:** przenieś `<Library Id="C0DEC0DE">` pod korzeń istniejącego
   `<TriggerData>`. Zachowaj pozostałe biblioteki. CustomScript i trigger
   inicjalizacji pozwalają edytorowi regenerować Galaxy.
5. Scal `<TriggerLibs Id="C0DEC0DE"/>` z istniejącym `CGame id="Dflt"`
   według dołączonego `GameData.xml`. Nie twórz drugiego elementu tego samego ID.
6. Dodaj pojedynczy Include własnego layoutu do istniejącego DescIndex.
   Scal własne style z FontStyles oraz **wszystkie** klucze `OPP/` z GameStrings,
   łącznie z sześcioma podpisami addonów. Zachowaj inne wpisy docelowego moda.
7. Przy pracy na komponentach scal brakujące wpisy z
   `files/ComponentList.entries.xml`. Pliki paczki nie zastępują DocumentInfo,
   DocumentHeader ani całego ComponentList docelowego moda.
8. Skompiluj dokument w edytorze i sprawdź bibliotekę po zapisaniu.
   `OPP_Init()` uruchamia się przez Map Initialization; nie dodawaj drugiego
   wywołania. GameHeart musi być zainicjalizowany przed adapterem badań.
9. Przeprowadź Test Document, replay oraz test ról w prywatnym lobby.
   Sprawdź anulowania, grupowanie, brak duplikatów GH, pięciosekundowe timery,
   przełączanie perspektywy i brak popupów u aktywnych graczy.

Integracja wymaga symboli `LibGHLo_h`, struktur `upgradeNotifications`
i interfejsu GameHeart. Inny UI lub zmodyfikowany GameHeart może wymagać
dostosowania. Własny kontener `OPPCancelStack` ma stałą pozycję i korzysta
ze wspólnego przełącznika panelu GameHeart.

Edytuj `source/*.galaxy`, następnie uruchom:

```bash
python3 tools/generate_mod.py
python3 tools/generate_mod.py --check
```

Generator aktualizuje własne pliki w `files/`. Po zmianie scal je ponownie
z dokumentem docelowym. Generator i kontrola XML nie kompilują Galaxy.

## Walidacja i ograniczenia

Kod sprawdzono w SC2 **5.0.17.98310**: 188 testów Python, 13 konfiguracji
natywnych, kompilacje bez błędów, Test Document, nowe replaye, Rewind/seek,
pauza/prędkości i perspektywy. Próby obejmowały 17 konfiguracji addonów,
macierz przemian, Oracle/Void Ray/Phoenix ×5, utratę zasilania warp-inów
oraz 11 rzeczywistych przypadków BattleReport. Przed publikacją potwierdzono
także kompilację z publiczną zależnością i zgodność kodu paczki.

Rzeczywisty wspólny mecz kilku klientów z rolami observer/referee/active player
oraz końcowy odbiór wizualny użytkownika pozostają otwarte dla tego pakietu.
W części scen Default występowały ostrzeżenia fontów/layoutów i aktora Zealot;
nie były to ScriptErrors. Własna integracja do innego moda wymaga własnego odbioru.
Stockowa możliwość ręcznego anulowania warp-inu pozostaje bez zmian.
