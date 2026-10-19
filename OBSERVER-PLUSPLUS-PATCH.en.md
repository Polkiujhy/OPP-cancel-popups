# Observer PlusPlus BattleReport fix

**Language / Język:** [Polski](OBSERVER-PLUSPLUS-PATCH.md) | **English**

## Published Battle.net dependency — 2026-10-19

**Observer PlusPlus - Popup Fix 1.0** is available in **EU, US and KR**, all
**Public / Unlocked** (EU/KR: Auddi, US: Polkiujhy). The playable
**OPP Cancel Popups** EU 1.4 / US 1.1 / KR 1.1 already uses this dependency;
SC2 downloads it when launching the mod. Normal use does not require the patcher.

For your own integration, select Popup Fix 1.0 in the editor dependencies
instead of the original Observer PlusPlus. Do not include both Obs++ copies.
Original Observer PlusPlus is by **nice__username / ESLMaps**. GitHub/the ZIP
contains only our patcher, manifest and short patch snippets. The full dependency,
its libraries and assets are not part of the GitHub publication.

The patcher below is for authors working with local components. It accepts only
byte-identical input with the specified SHA256 hashes; rejecting another version
is intentional. Do not apply it to the already patched Popup Fix 1.0.
The Cancel Popups overlay MPQ **does not fix the original dependency**.
The fix affects BattleReport statistics inside Observer PlusPlus, so the setup
requires the overlay and a compatible patched Obs++ copy.

## Confirmed error and accounting

The pre-fix trial recorded 1082 real `UnitDied` events. All 203 cancelled warp-ins
had the neutral killer `KillingPlayer=16`, including five units owned by player 2.
Cancellation notifications worked, but Obs++ reported statistics-indexing errors.
That historical trial remains failed.

In the frozen `Lib7805B319.galaxy:1512–1517`, neutral killer16 becomes slot 15.
The code then passes owner1/2 to `OppositePlayerSlot`, which expects slot 0/1
(`:1155–1169`). Owner2 yields −1. Index ranges and numbering conventions must agree.

The fixed callback preserves normal combat credit through `killer-1`.
For killer16 it uses `OppositePlayerSlot(owner-1)`. The original Triggers comment
“Banelings always belong to enemy player” also defines the Baneling branch:
all its counters go to the owner's opposing slot, including the unit count before
the later type/resource accounting. We do not change owners, killers,
KillOnCancel, native ConstructCancel events or combat rules.

Remove exits the callback before any statistics change. The final guard rejects
slots outside 0/1 before the first array read/write. Normal real deaths still
increase the correct counters; the report and its trigger remain enabled.

## Supported source and reproducible patch

The supported input is one specific, unchanged EU Observer PlusPlus component
copy, identified by full SHA256 hashes:

- Galaxy: `dc489e014c281deeaf1d326b4a7b042dc45e6650f4eabe2f11e186a2f341aa00`.
- Triggers: `9e1fd8806c80d1d5559755ed51e3810b03cda8c0a264cd6b86f9de461775f1af`.

Our manifest is `src/observer-plusplus-patches/track-unit-kills-v1.json`.
It contains only transformation identifiers and short expressions/guards we wrote.
The patcher rejects unknown bytes, repeated application and existing output
directories, archives, reports or installation files. It does not overwrite
the original dependency.

The actual Triggers graph uses library 7805B319, callback D3F37C35,
neutral Param 6C9458E6 and Baneling Param 8A08DB2C. Other elements and files
remain byte-identical. Our CustomScript actions use the existing FunctionDef
Ntve 00000123; `CustomType=int/ScriptCode` parameters follow the pattern in
the local `NativeLib.TriggerLib:43652`. The existing callback, its event/conditions
and actual report actions are preserved. Galaxy receives the same transformation
so editor regeneration retains the fix. Compilation and comparison of actual
regenerated code are separate gates; XML validation does not compile Galaxy.

Example from the repository directory (the package uses the same paths and
supports any working directory):

```bash
python3 /sciezka/do/paczki/tools/patch_observer_plus_plus.py \
  --source /sciezka/do/lokalnego/ObserverPlusPlus.SC2Mod \
  --output /sciezka/do/build/ObserverPlusPlus_Patched.SC2Mod \
  --mpqcli /sciezka/do/lokalnego/mpqcli \
  --install-dir /sciezka/do/StarCraft-II/Mods
```

Replace the example paths with your own. `mpqcli` is an explicitly selected
local tool; binaries and third-party assets are not included in the package.
The patcher creates a new directory, `<output>.mpq` and `<output>.patch.json`;
it reads every MPQ file back and compares its bytes, then installs under a new name.
The report includes hashes of inputs, every output file, archive/installation,
our patcher, manifest and snippets. Only Triggers and one Galaxy library change.

## Identifying the running setup

The local test workflow saves a staging report and a receipt: a bank identifying
the setup actually loaded by SC2. Both contain `observer_patch_manifest`,
`observer_patch_manifest_sha256`, the dependency name and its files/hashes.
A report path alone does not prove file identity.

Freeze the original report, output directory and exact MPQ.
The `verify_runtime_provenance.py` validator accepts the complete set:

```text
--observer-patch-manifest <zamrozony-report>
--observer-dependency-directory <zamrozony-katalog-o-oryginalnej-nazwie>
--observer-dependency-archive <zamrozony-MPQ>
```

The placeholders refer to the frozen report, directory with its original name
and MPQ. The validator checks receipt/report consistency, our current transformations,
the actual installation, every file in the frozen directory and every MPQ readback.
Trials with the old dependency are never relabelled as trials of the fixed version.

## Required runtime evidence

The `obspp-battle-report-acceptance` scenario contains 11 real cases:
normal credited combat on both sides, native killer16 after interrupted warp-ins
for owner1/2, Baneling owner1/2, Remove owner1/2, unsupported killer3 for owner1/2
victims, and natural warp-in completion. Warp1 closes a Prism; Warp2 destroys it
using an actual enemy Marine. Cancellation signals are not synthesized.
Fixed Pylons power the production buildings away from warp-in locations;
the completion control uses a new gate away from the previous live gate.
Two real non-lethal Marine hits on a Nexus keep the natural battle timer active
during that control, with a separate positive Absorbed trace and correct attacker.
The fixture does not write battle timers.

An independent trace records actual Created/Order/ConstructCancel/ConstructComplete
and UnitDied events with tag, owner/type, time, killer and Remove.
A read-only bridge reads both actual statistics slots: unit count, types/amounts,
minerals, gas, supply, battle state and the enabled trigger. Supply is also read
inside UnitDied, using the native property available at that lifecycle stage.
The validator requires exact deltas, including the additional Prism death in Warp2.
Remove, unsupported killers and completion do not change report counters.
Our notification counters increase exactly once in each of the two real warp-in
cancellations; the remaining controls add zero.

A separate engine trial confirmed that explicit `UnitRemove` does not emit
`UnitDied`. Both players' removal controls therefore use the real
`TriggerAddEventUnitRemoved` (`natives.galaxy:4402`). They record a live, valid
target before the action, verify the same handle and saved tag in the callback,
then independently require `UnitIsValid=false` and no remaining life.
Metadata is not read from an invalid object. The callback records validity and
reads the native tag only while the handle remains valid. There must be no
UnitDied/ConstructCancel/ConstructComplete, and all report and overlay deltas
must be zero. We do not synthesize UnitDied with a Remove flag. This API check
is not presented as coverage of another engine death with `c_deathTypeRemove`.
The early guard for that flag remains unchanged in the patch.

Disabling or superficially replacing the callback cannot pass this test:
real deaths must increase the correct slots and specific type/resource counters.
A control trial with the callback deliberately disabled must be rejected;
the correct code is restored before further tests. Full acceptance requires
the same fixed dependency in warp-in and regression scenarios, error-free
compilation and no new `ScriptErrors`.

## BattleReport fix results

These results describe local development trials from 2026-10-19:

| Check | Result |
| --- | --- |
| Patcher and dependency archive | All 38 MPQ files read back and compared byte for byte. |
| Editor save and regeneration | Every non-empty line of the fixed Galaxy retained; error-free compilation. |
| BattleReport statistics | 11/11 cases passed, exact changes in both slots, no new ScriptErrors. |
| Warp-in cancellations | 203 cancellations, 200 power-source correlations, 56 fragments and 129 retention cycles passed. |
| Mixed regression | 29 cancellation sources and 23 notification groups; running-file identity, logs and rendered notifications checked. |
| Deliberately disabled callback | The validator rejected missing statistics increments after an actual unit death. |

In total, 13 configurations passed with the same fixed dependency.
Role tests in a real shared match with multiple clients and the user's final
visual acceptance remain separate open items; this table does not pass them.

Scenario/validator sources and execution requirements are documented in the
[functional test guide](tests/functional/README.en.md).
Standalone Python validator tests do not replace SC2 trials.
