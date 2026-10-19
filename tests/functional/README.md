# Functional — z zależnościami

Są tu dwa osobne rodzaje sprawdzenia: wykonanie patchera na rzeczywistych
komponentach zależności oraz scenariusze uruchamiane w StarCraft II.
Wynik jednego nie zalicza drugiego.

## Patcher Obs++

Wskaż zgodne, **nienaprawione** komponenty o SHA256 z manifestu
`src/observer-plusplus-patches/track-unit-kills-v1.json` oraz lokalne mpqcli:

```bash
export OPP_OBSERVER_SOURCE=/sciezka/do/zgodnego-Observer.SC2Mod
export OPP_MPQCLI=/sciezka/do/mpqcli
python3 -m unittest discover -s tests/functional -v
```

Trzy testy sprawdzają rzeczywistą transformację Triggers/Galaxy, niezmienność
pozostałego grafu i plików, odczyt każdego pliku MPQ, odmowę powtórnego patcha
i wykrywanie podmiany. Wyjścia powstają wyłącznie w katalogu tymczasowym;
testy nie instalują niczego do działającej gry. Bez wejścia/narzędzia zestaw
kończy się błędem przygotowania. Nie używaj już naprawionego Popup Fix jako wejścia.

Pełne komponenty Obs++, mpqcli i instalacja SC2 nie są częścią repozytorium.
Gotowy publiczny mod w grze używa **Observer PlusPlus - Popup Fix 1.0** z Battle.net.

## Scenariusze SC2

`scenarios/` zawiera własne scenariusze Galaxy, bridge diagnostyczne,
macierz oczekiwań i dane używane wyłącznie w testach. `baseline/` zawiera
zamrożony własny raport zakresu morfów i jeden bank izolowanej kontroli
negatywnej. Są to historyczne dane wejściowe walidatora, nie wynik nowego uruchomienia.

| Scenariusz | Bridge w prywatnej kopii nakładki | Walidator w tools/ |
| --- | --- | --- |
| queue-aggregation-acceptance | queue-aggregation-bridge | verify_queue_aggregation.py |
| addon-acceptance | addon-acceptance-bridge | verify_addon_acceptance.py |
| morph-acceptance | morph-acceptance-bridge | verify_morph_acceptance.py |
| prism-acceptance | prism-acceptance-bridge | verify_prism_acceptance.py |
| obspp-battle-report-acceptance | obspp-battle-report-bridge | verify_obspp_battle_report.py |
| mixed-regression | queue-aggregation-bridge + mixed-regression-bridge | verify_mixed_regression.py |

Dodatkowe pliki obejmują zwykłą budowę/ukończenie, aktywną i oczekującą kolejkę,
rzeczywiste kliknięcia slotów, pozycję popupów, sondy stockowego Warpable
oraz historyczne badanie zakresu. Samo istnienie pliku nie oznacza zaliczenia testu.

### Przygotowanie źródeł prywatnej próby

```bash
python3 tools/prepare_functional_source.py queue-aggregation-acceptance \
  --revision qa1 --output build/qa1-source
```

Narzędzie nie uruchamia edytora ani gry. Tworzy nowy katalog z kodem scenariusza,
bridge i opisem hashy; nie nadpisuje wcześniejszych wyjść. Nadaje bankom unikalny
prefiks i przygotowuje oczekiwania morfów z dołączonej macierzy. Nie jest stagerem
gotowej mapy ani dowodem kompilacji.

1. W edytorze utwórz własną prywatną mapę testową i osobno nazwaną kopię
   nakładki ze zgodnymi zależnościami Void Multi, GameHeart i Popup Fix 1.0.
   Mapa musi mieć dwóch aktywnych graczy 1/2, właściwy teren i miejsce dla
   współrzędnych użytych przez scenariusz. Usuń przeszkadzające triggery melee.
2. Do CustomScript biblioteki C0DEC0DE **prywatnej** kopii dopisz wygenerowany
   `private-mod-bridge.galaxy`; zachowaj odpowiadający mu Galaxy po regeneracji.
   Nie zmieniaj źródeł produkcyjnych. Gdy bridge jest ładowany jako zależność,
   przygotowany kod mapy usuwa wyłącznie pokryte nim deklaracje prototypów.
3. Dodaj `map-custom-script.galaxy` jako CustomScript mapy i wywołaj
   `OPP_Test_Run(false, true);` raz z Map Initialization. Zachowaj poprawną
   inicjalizację nakładki/GameHeart. Skompiluj pełny kontekst bibliotek;
   podgląd samego Built-In lub brak definicji zależności nie zalicza kompilacji.
4. Prywatny `prism-acceptance` wymaga także wygenerowanego
   `PRIVATE-TEST-ONLY-data.xml`: `Warpable.Cancelable=1`. To wyłącznie kontrola
   dodatnia adaptera. Zapisz loaded value i odrębnie wykonaj stockowy
   `prism-direct-order-probe` bez override. Override nigdy nie trafia do wydania.
5. Uruchom Test Document, wykonaj wymagane rzeczywiste ESC/TAB/kliknięcia
   i zachowaj wszystkie banki/fragments, mapę, MPQ, logi oraz replay.
   Dla addonów sterownik `drive_addon_acceptance.py` wymaga własnego jawnie
   wskazanego helpera, który przy każdym wejściu sprawdza cel PID/okna.
   Helper zależny od pulpitu nie jest dołączony do repozytorium.
6. Uruchom właściwy walidator na **nowych, kompletnych** bankach. Skompletuj
   powtarzalne argumenty `--matrix-bank`, `--retention-bank` lub `--fragment-bank`.
   Dokładne argumenty pokazuje `--help` danego walidatora.
7. Obejrzyj właściwe UI w replayu, sprawdź Rewind/seek, pauzę, prędkości,
   perspektywy i normalny klient. Role observer/referee/active player wymagają
   rzeczywistego meczu wielu klientów; odczyt kontrolek w fixture go nie zastępuje.

Przykłady walidacji prostych, zamkniętych prób:

```bash
python3 tools/verify_queue_aggregation.py /sciezka/nowa-proba.SC2Bank
python3 tools/verify_obspp_battle_report.py /sciezka/nowy-battlereport.SC2Bank
python3 tools/verify_mixed_regression.py /sciezka/nowy-mixed.SC2Bank
```

`--first-lair-only` i `--single-close-only` potwierdzają pojedynczą scenę,
nie cały zestaw. Jawne `--allow-late-manual` pozostawia brakujący wynik jako
MANUAL_PENDING; nie zamienia go na PASS. `Done=1`, przyjęcie rozkazu ani same
liczniki nie wystarczają. Sprawdź również brak nowych ScriptErrors,
tożsamość uruchomionych plików i kompletne ślady rzeczywistych zdarzeń.
