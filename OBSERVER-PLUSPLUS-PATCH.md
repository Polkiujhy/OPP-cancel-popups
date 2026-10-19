# Naprawa BattleReport Observer PlusPlus

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
Lokalne nazwy v2/Fix1 i identyfikatory prób poniżej opisują pochodzenie oraz
walidację poprawki, a nie dodatkowe pliki wymagane do uruchomienia gotowego moda.

Użytkownik zatwierdził fazę6 po zidentyfikowaniu blokady P144, a po testach
osobno zlecił publikację. Samo MPQ nakładki Cancel Popups **nie naprawia starej
zależności**. Zestaw wymaga nakładki oraz zgodnej kopii Obs++ po patchu.

## Potwierdzony błąd i rachunkowość

P144 ma 1082 rzeczywiste UnitDied: wszystkie203 anulowane warp-iny mają
KillingPlayer16, w tym dokładnie5 dzieci owner2 (TwoOwners×2,
TwoOwnersKilled×2, RetentionHeld×1). Nie ma KillingPlayer0. Historyczny przebieg
pozostaje FAIL przez logi, mimo poprawnego zachowania popupów i cleanup.

W zamrożonym `Lib7805B319.galaxy:1512–1517` neutralny killer16 daje slot15,
następnie kod przekazuje owner1/2 do `OppositePlayerSlot`, który przyjmuje slot0/1
(`:1155–1169`). Owner2 daje−1. Przedziały i jednostki numeracji muszą się zgadzać.

Naprawiony callback zachowuje zwykły kredyt walki `killer-1`. Przy killer16
stosuje `OppositePlayerSlot(owner-1)`. Oryginalny komentarz Triggers
„Banelings always belong to enemy player” określa także gałąź Baneling:
wszystkie jej liczniki trafiają do slotu przeciwnika właściciela, włącznie z
liczbą jednostek przed późniejszym liczeniem typów i zasobów. Nie zmieniamy
właścicieli, sprawców, KillOnCancel, natywnych ConstructCancel ani zasad walki.

Remove kończy callback przed jakąkolwiek zmianą statystyk. Końcowy guard
odrzuca sloty poza0/1 przed pierwszym odczytem/zapisem tablic. Zwykłe rzeczywiste
zgony nadal zwiększają właściwe liczniki; raport i jego trigger pozostają włączone.

## Źródło i powtarzalny patch

Obsługiwane wejście to zamrożona lokalna kopia EU PlusPlus v2. Pełne SHA256:

- Galaxy: `dc489e014c281deeaf1d326b4a7b042dc45e6650f4eabe2f11e186a2f341aa00`.
- Triggers: `9e1fd8806c80d1d5559755ed51e3810b03cda8c0a264cd6b86f9de461775f1af`.

Własny manifest jest w `src/observer-plusplus-patches/track-unit-kills-v1.json`.
Zawiera wyłącznie identyfikatory transformacji i krótkie własne wyrażenia/guardy.
Patcher odmawia nieznanych bajtów, ponownego zastosowania i istniejącego outputu,
archiwum, reportu lub pliku instalacji. Nie nadpisuje oryginału/v2/referencji.

Rzeczywisty graf Triggers: biblioteka7805B319, callback D3F37C35,
neutralny Param6C9458E6 oraz Baneling Param8A08DB2C. Pozostałe elementy i pliki
pozostają bajtowo niezmienione. Własne akcje CustomScript korzystają z istniejącego
FunctionDef Ntve00000123; parametry `CustomType=int/ScriptCode` mają wzorzec
w lokalnym `NativeLib.TriggerLib:43652`. Istniejący callback, jego event/warunki
i rzeczywiste akcje raportu pozostają. Galaxy ma tę samą transformację, aby
regeneracja w edytorze zachowała naprawę. Kompilacja i porównanie faktycznej
regeneracji są oddzielną bramką; sam XML nie jest kompilacją Galaxy.

Przykład z katalogu repo (w paczce te same własne ścieżki, dowolny cwd):

```bash
python3 /sciezka/do/paczki/tools/patch_observer_plus_plus.py \
  --source /sciezka/do/lokalnego/OPP_Dev_EU_PlusPlus_20260920_v2.SC2Mod \
  --output /sciezka/do/build/OPP_Dev_Popup_ObsPPBattleReportFix1.SC2Mod \
  --mpqcli /sciezka/do/lokalnego/mpqcli \
  --install-dir /sciezka/do/StarCraft-II/Mods
```

`mpqcli` jest lokalnym narzędziem wskazanym jawnie; binarki i cudze zasoby nie
są częścią paczki. Patcher tworzy nowy katalog, `<output>.mpq` oraz
`<output>.patch.json`; odczytuje każdy plik z MPQ i porównuje bajty, następnie
instaluje pod nową nazwą. Report zawiera hashe wejść, wszystkich plików wyjścia,
archiwum/instalacji, własnego patchera, manifestu i snippetów. Zmieniają się
wyłącznie Triggers i jedna biblioteka Galaxy.

## Tożsamość uruchomionego zestawu

Stager wymaga jawnego `--observer-patch-manifest <output>.patch.json` dla nowej
zależności. Zachowuje historyczny tryb bez manifestu. Report i map-only receipt
zawierają `observer_patch_manifest` i `observer_patch_manifest_sha256`, nazwę
zależności oraz jej pliki/hashe. Lokalny stage report wskazuje dodatkowo
oryginalny `observer_patch_manifest_path`; nie jest to zastępstwo weryfikacji.

Zamrozić oryginalny report, katalog output oraz dokładny MPQ. Validator
`verify_runtime_provenance.py` przyjmuje komplet:

```text
--observer-patch-manifest <zamrozony-report>
--observer-dependency-directory <zamrozony-katalog-o-oryginalnej-nazwie>
--observer-dependency-archive <zamrozony-MPQ>
```

Sprawdza receipt/report, bieżące własne transformacje, faktyczną instalację,
wszystkie pliki zamrożonego katalogu oraz każdy odczyt z MPQ. Historyczne
v121/v144 pozostają powiązane ze starą zależnością i zachowują swój FAIL.

## Wymagany dowód runtime

`--fixture obspp-battle-report-acceptance` ma11 rzeczywistych przypadków:
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
Validator wymaga dokładnych delt, także dodatkowej śmierci Prisma w Warp2;
Remove/unsupported killer/ukończenie nie zmieniają liczników raportu.
Własne popupy rosną wyłącznie raz w obu rzeczywistych anulowaniach warp-inu;
pozostałe kontrole dają zero.

Pierwszy natywny break v174 potwierdził dodatkowo semantykę aranżacji: jawne
`UnitRemove` nie emituje UnitDied. Kontrole Remove1/2 korzystają dlatego z
rzeczywistego `TriggerAddEventUnitRemoved` (`natives.galaxy:4402`). Zapisują żywy,
ważny cel przed akcją, zgodność callbacku z tym samym uchwytem i zachowanym tagiem,
a po akcji niezależnie wymagają `UnitIsValid=false` i braku życia. Metadanych
nie odczytuje się z nieważnego obiektu. W czasie callbacku zapisuje się jego
ważność, a natywny tag tylko jeśli uchwyt nadal jest ważny. Wymagane są brak
UnitDied/ConstructCancel/ConstructComplete oraz zerowe wszystkie delty raportu
i własnych popupów. Nie dopisujemy syntetycznego UnitDied z flagą Remove; ta
kontrola API nie jest przedstawiana jako pokrycie innej śmierci silnika z
`c_deathTypeRemove`. Wczesny guard tej flagi pozostaje bez zmian w patchu.

Wyłączenie/pozorna podmiana callbacku nie może zaliczyć tego dowodu: rzeczywiste
zgony muszą zwiększać oba sloty i konkretne liczniki typów/zasobów. Koordynator
wykonuje osobny negatywny break-check i przywraca właściwe źródła. Nowa pełna
akceptacja P/X oraz pozostałych fixture wymaga identycznej poprawionej zależności,
kompilacji Errors0 i zera nowych ScriptErrors. Do wykonania tych bramek dokument
opisuje implementację i kontrakt, nie zaliczenie runtime ani publikację.

## Bieżące dowody fazy6

Implementacja patchera: commit `154f572`. Odrębny Fix1 ma38plików MPQ
zweryfikowanych bajtowo; jego SHA to
`a8609c8b93e6d032af320d0976b82596aa6f202f271b2256d8954ac039ff998a`.
Prawdziwe zapisanie Triggers w edytorze na oddzielnej kopii zachowało każdą
niepustą linię wynikowego Galaxy (`obspp-regeneration1-proof.json`). Wszystkie
świeże fixture zawierały rzeczywisty kod zależności podczas kompilacji Errors0.

BR180 ma11/11PASS, dokładne delty obu slotów i rzeczywiste zdarzenia.
P152 przeszedł pełną macierz203/200,56fragmentów/129cykli. Obie próby mają
zero nowych ScriptErrors. Focused natywny break z wyłączonym callbackiem dał
RED dokładnie na Combat1 Units0; dobry asset przywrócono przed dalszymi próbami.
Historyczny P144 zachowuje FAIL. X186 przeszedł pełny strict native/provenance/logs
29źródeł/23grupy oraz obraz własnych popupów. Wszystkie13wymaganych konfiguracji
mają PASS na tej samej zależności; aktualne artefakty i ograniczenia wyznacza `docs/validation-cancel-popup-completeness-2026-10-19.md`.
