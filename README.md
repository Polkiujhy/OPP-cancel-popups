# OPP Cancel Popups — wydanie 1.1

Pakiet dla autora docelowego moda. Dodaje popupy anulowania budynków, produkcji
jednostek i badań ulepszeń wyłącznie obserwatorom/sędziom. Aktywny popup tego
samego właściciela, kategorii i ID katalogowego zwiększa licznik ×2, ×3 itd.
i odnawia 5 sekund czasu gry. Po wygaśnięciu licznik zaczyna od nowa.
Maksymalnie trzy aktywne wiersze; dalsze wpisy trafiają do kolejki.

## Co zawiera paczka

- `files/`: własne pliki do integracji, z zachowaniem ścieżek komponentów SC2.
- `source/`: edytowalne źródła Galaxy.
- `tools/generate_mod.py`: regeneracja `files/Triggers` i dwóch plików biblioteki.
- `SHA256SUMS`: sumy kontrolne pozostałych plików paczki.

To nie jest samodzielny mod do otwarcia w grze ani zestaw do bezwarunkowego
nadpisania katalogu docelowego. Nie zawiera map testowych, kont, haseł,
cache, binarek diagnostycznych ani cudzych modów i tekstur.

## Wymagane środowisko

Integracja była rozwijana dla SC2 5.0.16.97563, Observer PlusPlus EU 1.1
oraz WCS GameHeart EU 1.24, z Void Multi. W testowym dokumencie zależności to:

```
bnet:Void Multi (Mod)/0.0/999,file:Mods/VoidMulti.SC2Mod
bnet:WCS GameHeart/0.0/289917
bnet:Observer PlusPlus/0.0/309364
```

Wybierz i sprawdź zależności w edytorze docelowego moda; nie zastępuj jego
DocumentInfo/DocumentHeader. ID Battle.net powyżej dotyczą użytego regionu EU.
Jeśli integrujesz bezpośrednio do OPP, nie dodawaj zależności moda od samego siebie.

Kod wymaga biblioteki `LibGHLo_h` oraz jej struktur `upgradeNotifications`,
triggera `libGHLo_gt_UpgradeNotificationsResearchCancelled` i funkcji
`UpgradeNotificationsRemoveRunningUpgrade` / `UpgradeNotificationsSetStatusLabel`.
Dokładne używane symbole są w `source/opp_research.galaxy`.
Layout korzysta z istniejącego panelu
`GameUI/UIContainer/FullscreenUpperContainer/TimerNotificationPanel/ToggledContent`
oraz szablonu `UpgradeNotifications/TimerFrameTemplate` i stylów `TimerType` /
`TimerStatus` dostarczanych przez GameHeart. Wiersze tworzą wspólny stos
ze standardowymi powiadomieniami; kolejka anulowań pozostaje osobna.
Routing wymaga `GameUI/Dflt/DefaultObservedPlayerId` zgodnego z GameHeart.
Dla innego UI lub zmodyfikowanego GameHeart potrzebna jest adaptacja tych miejsc.

## Wdrożenie do kopii roboczej docelowego moda

1. Zrób kopię docelowego moda i zamknij jego dokument przed zmianami komponentów
   na dysku. Potwierdź zgodne zależności. Sprawdź, czy biblioteka `C0DEC0DE`,
   symbole `OPP_*`, style `OPPCancel*` i ramki `OPPCancelRow*` już nie istnieją.
   Nie instaluj modułu drugi raz przez zależność i bezpośrednio równocześnie.
2. Skopiuj nowe pliki `files/Base.SC2Data/LibC0DEC0DE.galaxy`,
   `LibC0DEC0DE_h.galaxy` oraz `UI/Layout/OPPCancelPopups.SC2Layout` do tych
   samych ścieżek w modzie.
3. **Scal Triggers, nie nadpisuj go.** Z `files/Triggers` przenieś całe
   `<Library Id="C0DEC0DE">...</Library>` jako element korzenia `<TriggerData>`
   istniejącego pliku Triggers. Pozostaw wszystkie biblioteki i triggery autora.
   Paczka zawiera Custom Script oraz trigger Map Initialization; dzięki temu
   edytor może bezpiecznie regenerować Galaxy. Samo skopiowanie Galaxy nie wystarcza.
4. Scal wpis `<TriggerLibs Id="C0DEC0DE"/>` z
   `files/Base.SC2Data/GameData/GameData.xml` z istniejącym `CGame id="Dflt"`.
   Zachowaj pozostałe biblioteki i ustawienia CGame. Nie dodawaj drugiego CGame
   o tym samym ID do tego samego pliku.
5. Do istniejącego `Base.SC2Data/UI/Layout/DescIndex.SC2Layout` dodaj pojedyncze
   `<Include path="UI/Layout/OPPCancelPopups.SC2Layout"/>` pod `<Desc>`.
   Zachowaj pozostałe Include i inne wpisy.
6. Do istniejącego `Base.SC2Data/UI/FontStyles.SC2Style` dodaj elementy Style
   z pliku paczki pod `<StyleFile>`. Nie usuwaj stylów docelowego moda.
7. Dopisz cztery klucze `OPP/*` z
   `files/enUS.SC2Data/LocalizedData/GameStrings.txt`. To wyłącznie teksty modułu;
   paczka nie zmienia nazwy/opisu moda. Dodaj tłumaczenia tych kluczy dla innych
   lokalizacji obsługiwanych przez docelowy mod.
8. Jeżeli pracujesz na komponentach, upewnij się, że ComponentList obejmuje
   istniejące komponenty Triggers, GameData, UI/Layout/DescIndex.SC2Layout,
   UI/FontStyles.SC2Style i GameText enUS. Wzór wpisów jest w
   `files/ComponentList.entries.xml`; scal tylko brakujące wpisy, nie kopiuj
   tego pliku pod nazwą ComponentList.SC2Components.
9. Otwórz dokument w edytorze i skompiluj triggery. Biblioteka rejestruje
   Map Initialization i wywołuje `OPP_Init()` — nie dodawaj drugiego wywołania.
   GameHeart musi być zainicjalizowany przed adapterem badań.
   Jeśli docelowy mod ma inną kolejność inicjalizacji, dostosuj jego bootstrap.
10. Zapisz dokument, sprawdź brak utraty biblioteki po regeneracji i przeprowadź
    Test Document oraz poniższy test w prywatnym lobby. Dopiero potem wydaj
    docelowy mod zgodnie z własnym procesem publikacji.

## Inicjalizacja i brak podwójnych alertów

`OPP_Init()` uruchamia UI, zdarzenia budynków, jednostek i adapter badań.
Jest zabezpieczony przed wielokrotną inicjalizacją. Adapter badań wyłącza
wyłącznie trigger anulowania GameHeart i przejmuje jego funkcję, usuwając
bieżący wpis badania przed pokazaniem własnego popupu. Nie wyłączaj pozostałych
triggerów GameHeart. Gdy własne UI nie zostanie zainicjalizowane, adapter
pozostawia oryginalny trigger badań włączony.

Punkty diagnostyczne DataTable: `OPPCancelPopups/InitializationCount` (1),
`OPPCancelPopups/UIReady` (true), `OPPCancelPopups/ResearchAdapter` (true).
Są to wskaźniki pomocnicze; nie zastępują sprawdzenia widoczności popupów.
Nie dodawaj fallbacku do aktywnych graczy. Debug pozostaje wyłączony.

## Minimalny odbiór integracji

- Dwóch graczy i obserwator: anuluj budynek, produkcję jednostki i badanie.
  Sprawdź nazwę, ikonę i właściciela; gracze nie mogą widzieć popupów.
- Dla każdej kategorii anuluj ten sam typ trzy razy przed wygaśnięciem:
  jeden popup ×3, wygasający 5 sekund czasu gry od ostatniego anulowania.
- Po wygaśnięciu kolejne anulowanie rozpoczyna nowy licznik.
- Inny właściciel lub typ daje oddzielny wpis; brak podwójnych alertów GameHeart.
- Ukończenie i zniszczenie nie są anulowaniem produkcji/budowy/badania.
- Sprawdź sędziego, przełączanie obserwowanego gracza, wspólny przełącznik
  panelu i replay, w tym przewijanie oraz zmianę szybkości.

## Zmiany kodu i status

Edytuj `source/*.galaxy`, następnie uruchom w katalogu paczki:

```
python3 tools/generate_mod.py
python3 tools/generate_mod.py --check
```

Generator aktualizuje wyłącznie pliki w paczce. Po zmianach ponownie scal
bibliotekę z docelowym Triggers. XML i pakowanie nie są kompilatorem Galaxy.

Wydanie 1.1 korzysta z oryginalnego szablonu powiadomień GameHeart.
Test Document v34 w SC2 5.0.16.97563 oraz testy grupowania budynków i jednostek,
timerów i widoczności kontrolek zakończyły się powodzeniem. Wygląd został
zaakceptowany przez użytkownika. Panel sterowania lokalnego Rewind edytora
może zasłaniać dolne wiersze. Nie przeprowadzono ponownego testu wielu klientów
dla tej zmiany wizualnej; docelowa integracja wymaga własnego odbioru.

Publiczny mod w EU: **OPP Cancel Popups**, autor **Auddi**, Public / Unlocked.
W grze: Custom → Melee → wybierz mapę → Create with Mod → wyszukaj nazwę.
Numer 1.1 dotyczy publicznej linii wydań; wcześniejsza paczka 1.2 odpowiadała
osobnej, prywatnej publikacji testowej.
