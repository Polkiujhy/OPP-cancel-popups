# OPP Cancel Popups — wydanie 1.3

Pakiet dla autora docelowego moda. Dodaje popupy anulowania budynków, produkcji
jednostek i badań ulepszeń wyłącznie obserwatorom/sędziom. Aktywny popup tego
samego właściciela, kategorii i ID katalogowego zwiększa licznik ×2, ×3 itd.
i odnawia 5 sekund czasu gry. Po wygaśnięciu licznik zaczyna od nowa.
Maksymalnie trzy aktywne wiersze; dalsze wpisy trafiają do kolejki.

Wygląd 1.3: kwadrat w kolorze właściciela z ikoną pośrodku, mały odstęp,
nazwa anulowanego elementu u góry i duże „CANCELLED” poniżej. Proporcje
odpowiadają powiadomieniu ukończonego ulepszenia w Pro 2020 / GameHeart.
Grupowanie jednostek, budynków i ulepszeń pozostaje bez zmian.
Popup obejmuje również oczekujące jednostki i ulepszenia usunięte z kolejki,
nie tylko aktualnie produkowaną/badaną pozycję. Aktywna pozycja jest liczona raz.

## Co zawiera paczka

- `files/`: własne pliki do integracji, z zachowaniem ścieżek komponentów SC2.
- `source/`: edytowalne źródła Galaxy.
- `tools/generate_mod.py`: regeneracja `files/Triggers` i dwóch plików biblioteki.
- `SHA256SUMS`: sumy kontrolne pozostałych plików paczki.

To nie jest samodzielny mod do otwarcia w grze ani zestaw do bezwarunkowego
nadpisania katalogu docelowego. Nie zawiera map testowych, kont, haseł,
cache, binarek diagnostycznych ani cudzych modów i tekstur.

## Wymagane środowisko

Integracja była rozwijana dla SC2 5.0.16.97563, a wygląd 1.3 sprawdzono
w edytorze i Test Document 5.0.17.98310. Zależności:
Observer PlusPlus EU 1.1 oraz WCS GameHeart EU 1.24, z Void Multi.
W dokumencie zależności to:

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
`TimerStatus` dostarczanych przez GameHeart. Własne wiersze są w osobnym
kontenerze `OPPCancelStack`, po lewej pod produkcją. Kotwice wskazują stały
`FullscreenUpperContainer` (Left=0, Top=245), bez zależności od alertów robotnic.
Kontener ma Width=400 i Height=288, a wiersze Width=0 przy obu kotwicach
poziomych. Wiersze nadal korzystają ze wspólnego przełącznika panelu;
kolejka anulowań pozostaje osobna. Wiersz ma wysokość 92, kwadrat 92×92,
ikonę 76×76 i odstęp 8 jednostek UI przed tekstem. Własne style nazwy i statusu
to `OPPCancelName` (22) i `OPPCancelStatus` (28, Bold/Uppercase).
Kolor właściciela jest ustawiany na `TimerWindow/ColorAccent`; kontrolka
`Owner` pozostaje ukryta i służy wyłącznie odczytom diagnostycznym.
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

Wydanie 1.3 zmienia prezentację własnych anulowań, zachowując stałą pozycję
z wersji 1.2. Test Document v54 w SC2 5.0.17.98310 oraz walidator banku
potwierdziły trzy wiersze, kolejkę czwartego wpisu, grupowanie ×3, timery,
naprzemienne odświeżanie alertów i brak widoczności kontrolek aktywnych graczy.
Rewind potwierdził pełne własne ikony, długą nazwę, duży status oraz kolor
czerwonego i niebieskiego właściciela. Podgląd używał Pro 2020 jako lokalnej
zależności; inne alerty GameHeart miały znane przycięcia, a Rewind zgłaszał
powtórnie dodawane layouty. Nie jest to pełny test całego UI w normalnym kliencie.
Nie powtarzano meczu trzech kont dla zmiany wyglądu. Poprzednia wersja 1.2
miała ręczną akceptację użytkownika; użytkownik zatwierdził również wydanie
wyglądu 1.3. Docelowa integracja do innego moda wymaga własnego odbioru.

Po wstrzymaniu publikacji dodano poprawkę kolejki. Test Document v56 potwierdził
pięć SCV → ×5, trzy różne ulepszenia, brak podwójnego liczenia aktywnej pozycji
i brak własnych anulowań po śmierci producenta lub ukończeniu. V57 potwierdził
regresję trzech Drone, grupowanie i rozdzielenie właścicieli. V60 używał prawdziwych
kliknięć panelu produkcji: oczekujące ulepszenie i SCV dały właściwe anulowania,
a aktualne badanie GameHeart pozostało zachowane. Są to lokalne testy SC2,
bez nowego meczu trzech klientów. Powtórny test v61 potwierdził te same wyniki;
użytkownik obejrzał Rewind i zaakceptował wydanie całej poprawki.

Publiczny mod w EU: **OPP Cancel Popups**, autor **Auddi**, Public / Unlocked.
W grze: Custom → Melee → wybierz mapę → Create with Mod → wyszukaj nazwę.
Numer 1.3 dotyczy publicznej linii wydań. Osobny mod testowy pozostaje
Private / Locked w wersji 1.4 i zawiera wcześniejszy wygląd.
