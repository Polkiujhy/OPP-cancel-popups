# Testy jednostkowe — bez zależności zewnętrznych

**Język / Language:** **Polski** | [English](README.en.md)

Wymagany jest Python 3.12+; wystarczą biblioteka standardowa i lokalna kopia repozytorium.
Nie potrzeba StarCraft II, mpqcli, kont Battle.net ani cudzych plików.

```bash
python3 -m unittest discover -s tests/unit -v
python3 tools/generate_mod.py --check
```

Zestaw obejmuje 159 testów w 13 modułach:

- Zachowanie pełnego kodu przy usuwaniu marginesu XML przez edytor,
  rejestrację biblioteki i manifest modułów generatora.
- Niezależność generatora po wypakowaniu paczki, sumy kontrolne i odmowę
  nadpisania istniejącego wydania.
- Odczyt wartości banków, odrzucanie duplikatów, niepełnych śladów,
  niedomkniętych fragmentów i nieprawidłowego czasu.
- Kontrakty dowodów addonów, morfów, utraty zasilania warp-inów,
  mieszanej regresji i BattleReport.
- Wykrywanie podmiany źródeł, archiwum, receiptu i deklaracji zależności.
- Dobór nazw banków, deklaracje bridge i protokół ESC/TAB. Wejście UI jest
  symulowane; te testy nie wysyłają naciśnięć klawiszy.

Przykłady banków są syntetycznymi danymi protokołu. Testy celowo usuwają
zdarzenia, zmieniają właściciela, tag, ikonę lub timer i wymagają odrzucenia
takiego materiału. Nie odtwarzają w Pythonie logiki produkcyjnych adapterów
Galaxy i nie zastępują testów funkcjonalnych w grze.
