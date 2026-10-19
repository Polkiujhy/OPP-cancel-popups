# Naprawa BattleReport Observer PlusPlus

**Język / Language:** **Polski** | [English](https://github.com/Polkiujhy/OPP-cancel-popups/blob/main/OBSERVER-PLUSPLUS-PATCH.en.md)

## Gotowa zależność na Battle.net — 2026-10-19

**Observer PlusPlus - Popup Fix 1.0** jest dostępny w **EU, US i KR**, wszędzie
**Public / Unlocked** (EU/KR: Auddi, US: Polkiujhy). Gotowy **OPP Cancel Popups**
EU 1.4 / US 1.1 / KR 1.1 już korzysta z tej zależności; gra pobiera ją przy
uruchomieniu moda. Do zwykłego użycia nie trzeba uruchamiać patchera.

Przy własnej integracji wybierz Popup Fix 1.0 w zależnościach edytora zamiast
starego Observer PlusPlus. Nie dołączaj obu kopii Obs++ jednocześnie.
Oryginalny Observer PlusPlus jest autorstwa **nice__username / ESLMaps**.
GitHub/ZIP zawiera tylko własny patcher, manifest i krótkie fragmenty poprawki.
Pełna zależność, jej biblioteki i zasoby nie są częścią publikacji GitHub.

Patcher opisany niżej jest narzędziem dla autorów lokalnych komponentów.
Przyjmuje tylko bajtowo zgodne wejście o podanych SHA256; odmowa dla innej
wersji jest zamierzona. Nie stosuj go do już naprawionego Popup Fix 1.0.
Samo MPQ nakładki Cancel Popups **nie naprawia starej zależności**. Naprawa
dotyczy statystyk BattleReport wewnątrz Observer PlusPlus, dlatego zestaw
wymaga nakładki oraz zgodnej kopii Obs++ po patchu.

## Potwierdzony błąd i rachunkowość

W próbie sprzed naprawy zarejestrowano 1082 rzeczywiste zdarzenia `UnitDied`.
Wszystkie 203 anulowane warp-iny miały neutralnego sprawcę `KillingPlayer=16`,
w tym pięć jednostek gracza 2. Popupy anulowań działały, ale zależność Obs++
zgłaszała błędy indeksowania statystyk. Ta historyczna próba pozostaje niezaliczona.

W zamrożonym `Lib7805B319.galaxy:1512–1517` neutralny killer16 daje slot 15,
następnie kod przekazuje owner1/2 do `OppositePlayerSlot`, który przyjmuje slot 0/1
(`:1155–1169`). Owner2 daje −1. Przedziały i jednostki numeracji muszą się zgadzać.

Naprawiony callback zachowuje zwykły kredyt walki `killer-1`. Przy killer16
stosuje `OppositePlayerSlot(owner-1)`. Oryginalny komentarz Triggers
„Banelings always belong to enemy player” określa także gałąź Baneling:
wszystkie jej liczniki trafiają do slotu przeciwnika właściciela, włącznie z
liczbą jednostek przed późniejszym liczeniem typów i zasobów. Nie zmieniamy
właścicieli, sprawców, KillOnCancel, natywnych ConstructCancel ani zasad walki.

Remove kończy callback przed jakąkolwiek zmianą statystyk. Końcowy guard
odrzuca sloty poza 0/1 przed pierwszym odczytem/zapisem tablic. Zwykłe rzeczywiste
zgony nadal zwiększają właściwe liczniki; raport i jego trigger pozostają włączone.

## Źródło i powtarzalny patch

Obsługiwane wejście to konkretna, niezmieniona kopia komponentów Observer
PlusPlus z regionu EU, rozpoznawana po pełnych SHA256:

- Galaxy: `dc489e014c281deeaf1d326b4a7b042dc45e6650f4eabe2f11e186a2f341aa00`.
- Triggers: `9e1fd8806c80d1d5559755ed51e3810b03cda8c0a264cd6b86f9de461775f1af`.

Własny manifest jest w `src/observer-plusplus-patches/track-unit-kills-v1.json`.
Zawiera wyłącznie identyfikatory transformacji i krótkie własne wyrażenia/guardy.
Patcher odmawia nieznanych bajtów, ponownego zastosowania i istniejącego outputu,
archiwum, raportu lub pliku instalacji. Nie nadpisuje oryginalnej zależności.

Rzeczywisty graf Triggers: biblioteka 7805B319, callback D3F37C35,
neutralny Param 6C9458E6 oraz Baneling Param 8A08DB2C. Pozostałe elementy i pliki
pozostają bajtowo niezmienione. Własne akcje CustomScript korzystają z istniejącego
FunctionDef Ntve 00000123; parametry `CustomType=int/ScriptCode` mają wzorzec
w lokalnym `NativeLib.TriggerLib:43652`. Istniejący callback, jego event/warunki
i rzeczywiste akcje raportu pozostają. Galaxy ma tę samą transformację, aby
regeneracja w edytorze zachowała naprawę. Kompilacja i porównanie faktycznej
regeneracji są oddzielną bramką; sam XML nie jest kompilacją Galaxy.

Przykład z katalogu repo (w paczce te same własne ścieżki, dowolny cwd):

```bash
python3 /sciezka/do/paczki/tools/patch_observer_plus_plus.py \
  --source /sciezka/do/lokalnego/ObserverPlusPlus.SC2Mod \
  --output /sciezka/do/build/ObserverPlusPlus_Patched.SC2Mod \
  --mpqcli /sciezka/do/lokalnego/mpqcli \
  --install-dir /sciezka/do/StarCraft-II/Mods
```

`mpqcli` jest lokalnym narzędziem wskazanym jawnie; binarki i cudze zasoby nie
są częścią paczki. Patcher tworzy nowy katalog, `<output>.mpq` oraz
`<output>.patch.json`; odczytuje każdy plik z MPQ i porównuje bajty, następnie
instaluje pod nową nazwą. Raport zawiera hashe wejść, wszystkich plików wyjścia,
archiwum/instalacji, własnego patchera, manifestu i snippetów. Zmieniają się
wyłącznie Triggers i jedna biblioteka Galaxy.

## Tożsamość uruchomionego zestawu

W lokalnym procesie testowym zapisujemy raport przygotowania próby oraz receipt,
czyli bank potwierdzający tożsamość zestawu załadowanego przez grę. Oba zawierają
`observer_patch_manifest` i `observer_patch_manifest_sha256`, nazwę zależności
oraz jej pliki/hashe. Sama ścieżka do raportu nie jest dowodem zgodności plików.

Zamrozić oryginalny raport, katalog wyjściowy oraz dokładny MPQ. Walidator
`verify_runtime_provenance.py` przyjmuje komplet:

```text
--observer-patch-manifest <zamrozony-report>
--observer-dependency-directory <zamrozony-katalog-o-oryginalnej-nazwie>
--observer-dependency-archive <zamrozony-MPQ>
```

Sprawdza receipt/report, bieżące własne transformacje, faktyczną instalację,
wszystkie pliki zamrożonego katalogu oraz każdy odczyt z MPQ. Wyników prób
ze starą zależnością nie przepisujemy jako wyników poprawionej wersji.

## Wymagany dowód runtime

Scenariusz `obspp-battle-report-acceptance` ma 11 rzeczywistych przypadków:
normalny kredytowany combat obu stron, native killer16 po przerwanym warp-inie
owner1/2, Baneling owner1/2, Remove owner1/2, nieobsługiwany killer3 dla ofiar
owner1/2 oraz naturalne ukończenie warp-inu. Warp1 zamyka Prisma, Warp2 niszczy
go rzeczywistym wrogim Marine. Nie ma syntetycznych sygnałów anulowania.
Stałe Pylony zasilają producentów z dala od punktów warp-inu; kontrola ukończenia
ma nową bramkę poza poprzednią żywą bramką. Dwa rzeczywiste niezabijające trafienia
Marine w Nexus utrzymują naturalny timer bitwy podczas tej kontroli, z osobnym
śladem dodatniego Absorbed i poprawnego sprawcy; fixture nie zapisuje timerów.

Niezależny ślad rejestruje actual Created/Order/ConstructCancel/ConstructComplete
i UnitDied z tagiem, owner/type, czasem, killerem oraz Remove. Read-only bridge
odczytuje oba rzeczywiste sloty: liczbę jednostek, typy/ilości, minerały, gaz
i supply, stan bitwy i włączony trigger. Supply jest mierzone także w samym
UnitDied, zgodnie z dostępną natywną właściwością w tej fazie życia obiektu.
Walidator wymaga dokładnych delt, także dodatkowej śmierci Prisma w Warp2;
Remove/unsupported killer/ukończenie nie zmieniają liczników raportu.
Własne popupy rosną wyłącznie raz w obu rzeczywistych anulowaniach warp-inu;
pozostałe kontrole dają zero.

Osobna próba w silniku potwierdziła, że jawne `UnitRemove` nie emituje
`UnitDied`. Kontrole usuwania jednostek obu graczy korzystają dlatego z
rzeczywistego `TriggerAddEventUnitRemoved` (`natives.galaxy:4402`). Zapisują żywy,
ważny cel przed akcją, zgodność callbacku z tym samym uchwytem i zachowanym tagiem,
a po akcji niezależnie wymagają `UnitIsValid=false` i braku życia. Metadanych
nie odczytuje się z nieważnego obiektu. W czasie callbacku zapisuje się jego
ważność, a natywny tag tylko jeśli uchwyt nadal jest ważny. Wymagane są brak
UnitDied/ConstructCancel/ConstructComplete oraz zerowe wszystkie delty raportu
i własnych popupów. Nie dopisujemy syntetycznego UnitDied z flagą Remove; ta
kontrola API nie jest przedstawiana jako pokrycie innej śmierci silnika z
`c_deathTypeRemove`. Wczesny guard tej flagi pozostaje bez zmian w patchu.

Wyłączenie lub pozorna podmiana callbacku nie może zaliczyć tego testu:
rzeczywiste zgony muszą zwiększać właściwe sloty i konkretne liczniki
typów/zasobów. Próba kontrolna z celowo wyłączonym callbackiem musi zostać
odrzucona przez walidator; przed dalszymi testami przywracamy właściwy kod.
Pełny odbiór wymaga tej samej poprawionej zależności w scenariuszach warp-inów
i regresji, kompilacji bez błędów oraz braku nowych `ScriptErrors`.

## Wyniki testów naprawy BattleReport

Poniższe wyniki dotyczą lokalnych prób deweloperskich z 2026-10-19:

| Sprawdzenie | Wynik |
| --- | --- |
| Patcher i archiwum zależności | Wszystkie 38 plików MPQ odczytane i porównane bajt po bajcie. |
| Zapis i regeneracja w edytorze | Zachowana każda niepusta linia naprawionego Galaxy; kompilacje bez błędów. |
| Statystyki BattleReport | 11/11 przypadków zaliczonych, dokładne zmiany obu slotów, brak nowych ScriptErrors. |
| Anulowania warp-inów | 203 anulowania, 200 powiązań ze źródłami zasilania, 56 fragmentów i 129 cykli retencji — zaliczone. |
| Regresja mieszana | 29 źródeł anulowań i 23 grupy popupów; zgodność uruchomionych plików, logi i obraz popupów sprawdzone. |
| Celowo wyłączony callback | Walidator odrzucił brak wzrostu statystyk po rzeczywistej śmierci jednostki. |

Łącznie 13 konfiguracji testowych przeszło na tej samej poprawionej zależności.
Testy ról w rzeczywistym meczu wielu klientów i końcowy odbiór wizualny
pozostają osobnymi, otwartymi punktami; powyższa tabela ich nie zalicza.

Kod scenariuszy i walidatorów oraz wymagania uruchomienia są opisane
w [instrukcji testów funkcjonalnych](https://github.com/Polkiujhy/OPP-cancel-popups/blob/main/tests/functional/README.md). Samodzielne
testy walidatorów w Pythonie nie zastępują prób w SC2.
