# OPP Cancel Popups — release 1.4

**Language / Język:** [Polski](https://github.com/Polkiujhy/OPP-cancel-popups/blob/main/distribution/README-INTEGRATION.md) | **English**

Cancellation notifications for StarCraft II observers and referees. This release
covers construction, active and queued units/upgrades, add-ons, cancellable morphs,
and warp-ins interrupted by the loss of Warp Prism or Pylon power.

## Playing with the mod

In SC2, select **Custom → Melee → a map → Create with Mod** and search for
**OPP Cancel Popups**. The playable mod is available on Battle.net:

| Region | Overlay version | Author |
| --- | --- | --- |
| EU | 1.4 | Auddi |
| US | 1.1 | Polkiujhy |
| KR / Asia | 1.1 | Auddi |

Version numbers are regional; all three publications contain the same code.
Each is **Public / Unlocked** and uses the separately published dependency
**Observer PlusPlus - Popup Fix 1.0**, also available in EU/US/KR.
SC2 downloads the dependencies when you launch the mod. Playing does not require
running the patcher or installing source files from GitHub.

## Changes in 1.4

- Pending notifications with the same owner, category and type merge throughout
  the queue: Oracle, Phoenix, Oracle becomes Oracle ×2, then Phoenix. A pending
  group's age does not split it into separate entries.
- All six add-ons support cancellation through either the parent building or
  the add-on. Labels identify the parent: **Tech Lab - Barracks/Factory/Starport**
  and **Reactor - Barracks/Factory/Starport**.
- Cancellable Morph/MorphPlacement processes are supported, including Lair, Hive,
  Greater Spire, Ravager, Lurker, Baneling, Brood Lord, Overseer, transport Overlord,
  Planetary Fortress, Orbital Command and both Gateway/Warp Gate directions.
  The notification shows the final morph target.
- Closing a Warp Prism or destroying the supplying Prism/Pylon counts the
  warp-ins actually interrupted, by unit type and owner. Each unit is counted
  once. Retained alternative power and completion do not create cancellations.
- The separate Obs++ fix corrects BattleReport player indices that caused errors
  on interrupted warp-ins. The report and normal combat statistics remain enabled.

The display retains three fixed rows below production, the owner's colour,
an icon, a name and a large **CANCELLED** status. A group remains visible for
five game seconds; another cancellation in an active group increments its count
and refreshes the timer. After expiry, a new cancellation starts a new count.
Further groups wait in a separate queue. Ongoing research and GameHeart Denied
notifications are preserved. Notifications are for observers/referees only;
debug mode is disabled.

## Obs++ dependency and patch sources

**The overlay alone does not fix the original Observer PlusPlus dependency.**
The playable release uses **Observer PlusPlus - Popup Fix 1.0**. For your own
integration, select that Battle.net dependency in the editor instead of the
original Observer PlusPlus. Do not include both Obs++ copies at once.
Keep Void Multi and WCS GameHeart.

Original Observer PlusPlus: **nice__username / ESLMaps**.
The full Obs++, its libraries and assets are not included in this repository
or the ZIP. We publish our patcher, the supported-input manifest and short patch
snippets. The [patcher instructions and fix details](https://github.com/Polkiujhy/OPP-cancel-popups/blob/main/OBSERVER-PLUSPLUS-PATCH.en.md)
are for authors working with local components. The patcher accepts only the
specified, unchanged input; it must not be applied again to Popup Fix.

## Integration package contents

- `files/`: our library, Triggers, registration, layout, styles and strings.
- `source/`: seven editable Galaxy modules.
- `tools/generate_mod.py` and `tools/galaxy_sources.json`: generator and module order.
- `tools/patch_observer_plus_plus.py` and `src/observer-plusplus-patches/`:
  our dependency fix, without the full Obs++.
- `SHA256SUMS`: checksums of the other files in the package.

The ZIP is an integration package for mod authors, not a standalone playable mod.
It excludes private test maps, banks, replays, caches, accounts and binary tools.

## Integrating into your mod

1. Work on a copy of the target mod. Select compatible dependencies in the editor:
   Void Multi, WCS GameHeart and **Observer PlusPlus - Popup Fix 1.0**.
   When integrating directly into Obs++ sources, apply the BattleReport fix in
   that copy without making the mod depend on itself.
2. Check whether library `C0DEC0DE`, symbols `OPP_*`, styles `OPPCancel*` or frames
   `OPPCancelRow*` already exist. Do not install the overlay both as a dependency
   and by merging its sources directly.
3. Copy our two `LibC0DEC0DE*.galaxy` files and
   `UI/Layout/OPPCancelPopups.SC2Layout`, preserving their paths in `Base.SC2Data`.
4. **Merge Triggers:** place `<Library Id="C0DEC0DE">` under the existing
   `<TriggerData>` root. Preserve other libraries. CustomScript and the
   initialization trigger let the editor regenerate Galaxy.
5. Merge `<TriggerLibs Id="C0DEC0DE"/>` into the existing `CGame id="Dflt"`
   using the supplied `GameData.xml`. Do not create a second element with the same ID.
6. Add one Include for our layout to the existing DescIndex. Merge our styles
   into FontStyles and **all** `OPP/` keys into GameStrings, including the six
   add-on labels. Preserve the target mod's other entries.
7. When working with components, merge missing entries from
   `files/ComponentList.entries.xml`. Package files do not replace the target
   mod's DocumentInfo, DocumentHeader or complete ComponentList.
8. Compile the document in the editor and inspect the library after saving.
   `OPP_Init()` runs through Map Initialization; do not add another call.
   GameHeart must initialize before the research adapter.
9. Run Test Document, replay checks and role tests in a private lobby.
   Check cancellations, grouping, no duplicate GH alerts, five-second timers,
   perspective changes and the absence of notifications for active players.

Integration requires `LibGHLo_h` symbols, `upgradeNotifications` structures and
the GameHeart interface. Another UI or a modified GameHeart may require changes.
Our `OPPCancelStack` container has a fixed position and uses the shared GameHeart
notification toggle.

Edit `source/*.galaxy`, then run:

```bash
python3 tools/generate_mod.py
python3 tools/generate_mod.py --check
```

The generator updates our files in `files/`. Merge them into the target document
again after changes. Neither the generator nor XML validation compiles Galaxy.

## Validation and limitations

The code was checked in SC2 **5.0.17.98310**: 188 Python tests, 13 native
configurations, error-free compilation, Test Document, new replays, Rewind/seek,
pause/speed changes and perspectives. Trials covered 17 add-on configurations,
the morph matrix, Oracle/Void Ray/Phoenix ×5, interrupted warp-in power and
11 real BattleReport cases. Compilation with the public dependency and package
code consistency were also confirmed before publication.

A real shared match with multiple clients in observer/referee/active-player
roles and the user's final visual acceptance remain open for this package.
Some Default-interface scenes showed font/layout and Zealot actor warnings;
these were not ScriptErrors. Integration into another mod requires its own
acceptance checks. Stock manual warp-in cancellation remains unchanged.
