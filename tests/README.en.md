# Tests

**Language / Język:** [Polski](README.md) | **English**

| Suite | Dependencies | What it verifies |
| --- | --- | --- |
| [Unit](unit/README.en.md) | Python 3.12+ and this repository's files | Generator, packaging, bank protocols, validators, evidence correlation and scenario preparation. |
| [Functional](functional/README.en.md) — patcher | Compatible local Obs++ components and mpqcli | Actual dependency transformation, XML/Galaxy consistency and MPQ readback. |
| [Functional](functional/README.en.md) — SC2 | Game, Galaxy Editor, GameHeart, Popup Fix and a private test document | Actual engine events, notifications, replays and roles. |

```bash
python3 -m unittest discover -s tests/unit -v
```

Unit tests do not launch the game, editor, login or keyboard/mouse input.
A synthetic bank in a unit test checks the validator; it does not prove Galaxy
behaviour. Run functional tests separately. Missing patcher dependencies produce
a preparation error instead of a passing result with skipped tests.

Only unit tests run in CI. SC2 functional tests require actual execution,
complete evidence and separate assessment. Passing CI, valid XML, a packed MPQ
or a running game PID does not mean those tests passed.

This repository includes tests of the mod's public sources and evidence protocols.
Tests of the private launcher, local accounts and desktop configuration stay in
the development environment. Published scenarios are test code; do not include
them in the production mod.
