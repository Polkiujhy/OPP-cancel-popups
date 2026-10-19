# Unit tests — no external dependencies

**Language / Język:** [Polski](README.md) | **English**

Python 3.12+ is required; the standard library and a repository checkout suffice.
StarCraft II, mpqcli, Battle.net accounts and third-party files are not required.

```bash
python3 -m unittest discover -s tests/unit -v
python3 tools/generate_mod.py --check
```

The suite contains 159 tests in 13 modules:

- Preserving complete code when the editor removes XML indentation,
  library registration and the generator's module manifest.
- Generator independence after package extraction, checksums and refusal
  to overwrite an existing release.
- Reading bank values and rejecting duplicates, incomplete traces,
  unclosed fragments and invalid timing.
- Evidence contracts for add-ons, morphs, warp-in power loss,
  mixed regression and BattleReport.
- Detecting replaced sources, archives, receipts and dependency declarations.
- Bank naming, bridge declarations and the ESC/TAB protocol. UI input is mocked;
  these tests do not send real keystrokes.

Example banks are synthetic protocol data. Tests deliberately remove events,
change the owner, tag, icon or timer and require rejection of that evidence.
They do not recreate production Galaxy adapter logic in Python and do not
replace functional tests in the game.
