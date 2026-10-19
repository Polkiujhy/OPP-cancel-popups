# Testy

| Zestaw | Zależności | Co potwierdza |
| --- | --- | --- |
| [unit](unit/README.md) | Python 3.12+ i pliki tego repozytorium | Generator, pakowanie, protokoły banków, walidatory, korelację dowodów i przygotowanie scenariuszy. |
| [functional](functional/README.md) — patcher | Zgodne lokalne komponenty Obs++ i mpqcli | Rzeczywistą transformację zależności, zgodność XML/Galaxy i odczyt MPQ. |
| [functional](functional/README.md) — SC2 | Gra, Galaxy Editor, GameHeart, Popup Fix, prywatny dokument testowy | Faktyczne zdarzenia silnika, popupy, replay i role. |

```bash
python3 -m unittest discover -s tests/unit -v
```

Unit nie uruchamia gry, edytora, logowania ani wejścia klawiatury/myszy.
Syntetyczny bank w unit sprawdza walidator; nie dowodzi działania Galaxy.
Functional uruchamiaj osobno. Brak wymaganych zależności patchera daje błąd
przygotowania, zamiast zielonego wyniku z pominiętymi testami.

W CI działa wyłącznie unit. Testy funkcjonalne w SC2 wymagają rzeczywistego
uruchomienia, kompletu dowodów i osobnej oceny. Zielony CI, poprawny XML,
spakowany MPQ lub sam PID gry nie oznaczają ich zaliczenia.

Do repozytorium trafiły testy dotyczące publicznych źródeł i protokołów moda.
Testy prywatnego launchera, lokalnych kont i konfiguracji pulpitu pozostają
w środowisku deweloperskim. Opublikowane scenariusze są kodem testowym;
nie należy dołączać ich do wydawanego moda.
