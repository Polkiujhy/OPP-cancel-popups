# Functional tests — with dependencies

**Language / Język:** [Polski](README.md) | **English**

There are two separate checks: running the patcher on real dependency components
and running scenarios in StarCraft II. Passing one does not pass the other.

## Obs++ patcher

Select compatible, **unpatched** components with SHA256 hashes from
`src/observer-plusplus-patches/track-unit-kills-v1.json` and a local mpqcli:

```bash
export OPP_OBSERVER_SOURCE=/sciezka/do/zgodnego-Observer.SC2Mod
export OPP_MPQCLI=/sciezka/do/mpqcli
python3 -m unittest discover -s tests/functional -v
```

Replace the example paths with your local components and tool. Three tests
check the actual Triggers/Galaxy transformation, preservation of the remaining
graph and files, readback of every MPQ file, refusal to patch again and detection
of replaced input. Outputs are created only in temporary directories; tests
install nothing into the running game. Without the input/tool, the suite fails
with a preparation error. Do not use the already patched Popup Fix as input.

Full Obs++ components, mpqcli and the SC2 installation are not part of this repo.
The playable public mod uses **Observer PlusPlus - Popup Fix 1.0** from Battle.net.

## SC2 scenarios

`scenarios/` contains our Galaxy scenarios, diagnostic bridges, expectation matrix
and test-only data. `baseline/` contains our frozen morph-scope report and one
isolated negative-control bank. These are historical validator inputs, not results
of a new run.

| Scenario | Bridge in the private overlay copy | Validator in tools/ |
| --- | --- | --- |
| queue-aggregation-acceptance | queue-aggregation-bridge | verify_queue_aggregation.py |
| addon-acceptance | addon-acceptance-bridge | verify_addon_acceptance.py |
| morph-acceptance | morph-acceptance-bridge | verify_morph_acceptance.py |
| prism-acceptance | prism-acceptance-bridge | verify_prism_acceptance.py |
| obspp-battle-report-acceptance | obspp-battle-report-bridge | verify_obspp_battle_report.py |
| mixed-regression | queue-aggregation-bridge + mixed-regression-bridge | verify_mixed_regression.py |

Additional files cover ordinary construction/completion, active and waiting
queues, real slot clicks, notification position, stock Warpable probes and
historical scope investigation. A file's existence does not mean its test passed.

### Preparing private trial sources

```bash
python3 tools/prepare_functional_source.py queue-aggregation-acceptance \
  --revision qa1 --output build/qa1-source
```

The tool launches neither the editor nor the game. It creates a new directory
with scenario code, a bridge and hash metadata without overwriting earlier outputs.
It gives banks a unique prefix and prepares morph expectations from the supplied
matrix. It does not stage a complete map or prove compilation.

1. In the editor, create a private test map and a separately named overlay copy
   with compatible Void Multi, GameHeart and Popup Fix 1.0 dependencies.
   The map needs active players 1/2, suitable terrain and space for the scenario's
   coordinates. Remove interfering melee triggers.
2. Append the generated `private-mod-bridge.galaxy` to library C0DEC0DE's
   CustomScript in the **private** copy; retain matching Galaxy after regeneration.
   Do not change production sources. When the bridge loads as a dependency,
   the prepared map code removes only the prototypes covered by that bridge.
3. Add `map-custom-script.galaxy` as the map's CustomScript and call
   `OPP_Test_Run(false, true);` once from Map Initialization. Preserve correct
   overlay/GameHeart initialization. Compile the full library context;
   viewing Built-In alone or missing dependency definitions does not pass compilation.
4. Private `prism-acceptance` also requires the generated
   `PRIVATE-TEST-ONLY-data.xml`: `Warpable.Cancelable=1`. This is only a positive
   adapter control. Record the loaded value and separately run the stock
   `prism-direct-order-probe` without the override. Never ship the override.
5. Run Test Document, perform the required real ESC/TAB/clicks and retain every
   bank and fragment, the map, MPQ, logs and replay. For add-ons,
   `drive_addon_acceptance.py` requires your explicitly selected helper that
   checks the target PID/window on every input. The desktop-specific helper
   is not included in this repository.
6. Run the appropriate validator on **new, complete** banks. Supply repeated
   `--matrix-bank`, `--retention-bank` or `--fragment-bank` arguments as needed.
   Each validator's `--help` lists its exact arguments.
7. Inspect the actual UI in the replay, including Rewind/seek, pause, speeds,
   perspectives and the normal client. Observer/referee/active-player roles
   require a real match with multiple clients; fixture control reads do not
   replace that test.

Examples for simple, complete trials:

```bash
python3 tools/verify_queue_aggregation.py /sciezka/nowa-proba.SC2Bank
python3 tools/verify_obspp_battle_report.py /sciezka/nowy-battlereport.SC2Bank
python3 tools/verify_mixed_regression.py /sciezka/nowy-mixed.SC2Bank
```

`--first-lair-only` and `--single-close-only` verify one scene, not the entire suite.
Explicit `--allow-late-manual` leaves the missing result as MANUAL_PENDING;
it does not turn it into PASS. `Done=1`, an accepted command or counters alone
are insufficient. Also check for new ScriptErrors, identify the running files
and retain complete traces of actual engine events.
