#!/usr/bin/env python3
"""Prepare owned fixture source for a private editor document; never launch or publish."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "tests/functional/scenarios"

FIXTURE_BRIDGES = {
    'queue-aggregation-acceptance': ('queue-aggregation-bridge.galaxy',),
    'queue-age-breakcheck': ('queue-aggregation-bridge.galaxy',),
    'addon-acceptance': ('addon-acceptance-bridge.galaxy',),
    'morph-acceptance': ('morph-acceptance-bridge.galaxy',),
    'prism-acceptance': ('prism-acceptance-bridge.galaxy',),
    'mixed-regression': ('queue-aggregation-bridge.galaxy', 'mixed-regression-bridge.galaxy'),
    'obspp-battle-report-acceptance': ('obspp-battle-report-bridge.galaxy',),
}

GALAXY_NONCODE = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"')

GALAXY_FUNCTION = re.compile(
    r'^[ \t]*(?P<result>void|bool|int|fixed|string|text|unit|unitgroup|bank|timer|point|abilcmd)'
    r'[ \t]+(?P<name>[A-Za-z_]\w*)[ \t]*'
    r'\((?P<arguments>[^(){};]*)\)[ \t]*(?P<ending>[;{])', re.MULTILINE)

def galaxy_code_mask(source):
    return GALAXY_NONCODE.sub(lambda match: ''.join('\n' if char == '\n' else ' ' for char in match.group()), source)

def galaxy_signature(header):
    arguments = header['arguments'].strip()
    types = []
    for argument in arguments.split(',') if arguments else ():
        parameter = re.fullmatch(r'\s*([A-Za-z_]\w*)\s+[A-Za-z_]\w*\s*', argument)
        if parameter is None:
            raise SystemExit('Unsupported private bridge parameter syntax: ' + header['name'])
        types.append(parameter[1])
    return header['result'], tuple(types)

def strip_loaded_bridge_prototypes(source, bridge_sources):
    """Runtime loads dependency definitions first; retain raw fixture prototypes.

    Only same-signature forward declarations backed by a definition in an
    actually appended bridge are removed from generated map source. Definitions,
    unrelated forwards and the raw fixture files remain unchanged. Compiler-only
    clones can include the dependency body after headers when forwards are absent.
    """
    definitions = {}
    for bridge in bridge_sources:
        for header in GALAXY_FUNCTION.finditer(galaxy_code_mask(bridge)):
            if header['ending'] != '{':
                continue
            name = header['name']
            if name in definitions:
                raise SystemExit('Duplicate loaded private bridge definition: ' + name)
            definitions[name] = galaxy_signature(header)
    pieces = []
    removed = []
    cursor = 0
    for header in GALAXY_FUNCTION.finditer(galaxy_code_mask(source)):
        if header['ending'] != ';' or header['name'] not in definitions:
            continue
        name = header['name']
        if galaxy_signature(header) != definitions[name]:
            raise SystemExit('Fixture/private bridge signature mismatch: ' + name)
        pieces.append(source[cursor:header.start()])
        # Preserve source line numbers without redeclaring an already defined function.
        pieces.append('\n' * source[header.start():header.end()].count('\n'))
        cursor = header.end()
        removed.append(name)
    pieces.append(source[cursor:])
    return ''.join(pieces), removed

def prepare_bank_identifiers(source, revision):
    """Only bank-name expressions change; SC2 drops underscores on disk.

    Fixture bank expressions start with OPPBuildingCancelTest, either directly
    in BankLoad or in a variable passed to it. Rewrite only their string tokens,
    keeping Case/section labels, comments and every other string untouched.
    """
    if not re.fullmatch(r'[A-Za-z0-9]+', revision):
        raise SystemExit('Use an ASCII alphanumeric bank revision.')
    mask = galaxy_code_mask(source)
    expressions = []
    variables = set()
    for call in re.finditer(r'\bBankLoad\s*\(', mask):
        start = call.end()
        depth = 0
        end = start
        while end < len(mask):
            char = mask[end]
            if char == ',' and depth == 0:
                break
            if char == '(':
                depth += 1
            elif char == ')':
                if depth == 0:
                    raise SystemExit('Unrecognized BankLoad arguments.')
                depth -= 1
            end += 1
        if end == len(mask):
            raise SystemExit('Unterminated BankLoad arguments.')
        name = mask[start:end].strip()
        if re.fullmatch(r'[A-Za-z_]\w*', name):
            variables.add(name)
        else:
            expressions.append((start, end))
    for name in variables:
        for assignment in re.finditer(r'\b' + re.escape(name) + r'\s*=(?!=)', mask):
            start = assignment.end()
            end = mask.find(';', start)
            if end < 0:
                raise SystemExit('Unterminated bank-name assignment: ' + name)
            expressions.append((start, end))
    edits = {}
    for start, end in expressions:
        expression = source[start:end]
        tokens = [token for token in GALAXY_NONCODE.finditer(expression)
                  if token.group().startswith('"')]
        if not tokens or not tokens[0].group().startswith('"OPPBuildingCancelTest'):
            continue
        # Current bank builders use only literal fragments plus alphanumeric
        # case names/IntToString. A new literal grammar needs an explicit review.
        for index, token in enumerate(tokens):
            value = token.group()[1:-1]
            if not re.fullmatch(r'[A-Za-z0-9_]*', value):
                raise SystemExit('Unsupported fixture bank-name literal: ' + value)
            if index == 0:
                value = value.replace('OPPBuildingCancelTest', 'OPPBuildingCancel' + revision, 1)
            value = value.replace('_', '')
            edits[(start + token.start(), start + token.end())] = json.dumps(value)
    for (start, end), replacement in sorted(edits.items(), reverse=True):
        source = source[:start] + replacement + source[end:]
    return source

def morph_acceptance_source(source):
    """Freeze independent pre-production expectations into this private fixture."""
    path = ROOT / 'tests/functional/scenarios/morph-acceptance-matrix.json'
    matrix = json.loads(path.read_text())['matrix']
    icons_path = ROOT / 'tests/functional/scenarios/morph-acceptance-icons.json'
    icons = json.loads(icons_path.read_text())['icons']
    lines = ['// Private fixture expectations; no production catalog whitelist.',
             'string OPP_MA_MatrixHash = ' + json.dumps(hashlib.sha256(path.read_bytes()).hexdigest()) + ';',
             'string OPP_MA_IconsHash = ' + json.dumps(hashlib.sha256(icons_path.read_bytes()).hexdigest()) + ';']
    fields = {'Source': 'source', 'AbilityId': 'ability', 'FinalTarget': 'target',
              'Classification': 'classification', 'ExecutionPolicy': 'execution_policy'}
    lines.extend(f'string[301] OPP_MA_{name};' for name in fields)
    lines.extend(['int[14] OPP_MA_RepeatLinks;', 'void OPP_MA_ExpectedLinks0 () {'])
    for row in matrix:
        if row['link'] > 0 and row['link'] % 40 == 0:
            lines.extend(['}', f'void OPP_MA_ExpectedLinks{row["link"] // 40} () {{'])
        for name, key in fields.items():
            lines.append(f'    OPP_MA_{name}[{row["link"]}] = {json.dumps(row.get(key, ""))};')
    lines.extend(['}', 'void OPP_MA_ExpectedIcons () {'])
    for icon in icons:
        key = 'OPPMorphFixture/Icon/' + icon['ability'] + '/' + icon['target'] + '/'
        lines.append(f'    DataTableSetInt(true, {json.dumps(key + "Catalog")}, c_gameCatalog{icon["catalog"]});')
        for field, value in {'Entry': icon['entry'], 'Field': icon['field'],
                             'Asset': icon['expected_asset'],
                             'Reference': icon['catalog'] + ':' + icon['entry'] + '.' + icon['field']}.items():
            lines.append(f'    DataTableSetString(true, {json.dumps(key + field)}, {json.dumps(value)});')
    for index, link in enumerate((50, 52, 55, 58, 59, 60, 62, 65, 67, 10, 11, 46, 47, 86)):
        lines.append(f'    OPP_MA_RepeatLinks[{index}] = {link};')
    lines.extend(['}', 'void OPP_MA_ExpectedInit () {'])
    for chunk in range(8):
        lines.append(f'    OPP_MA_ExpectedLinks{chunk}();')
        lines.append('    Wait(0.0625, c_timeGame);')
    lines.extend(['    OPP_MA_ExpectedIcons();', '}'])
    return '\n'.join(lines) + '\n' + source

SUPPORTED = ('queue-aggregation-acceptance', 'addon-acceptance', 'morph-acceptance',
             'prism-acceptance', 'obspp-battle-report-acceptance', 'mixed-regression',
             'natural-building', 'building-cancel', 'queued-cancel', 'queue-click',
             'aggregation-units', 'popup-position', 'prism-direct-order-probe')

def prepare(scenario, revision, output):
    if scenario not in SUPPORTED or not re.fullmatch(r'[A-Za-z0-9]+', revision):
        raise ValueError('Choose a supported scenario and an ASCII alphanumeric revision.')
    if output.exists() or output.is_symlink():
        raise ValueError('Choose a new output directory; previous evidence stays immutable.')
    raw = SCENARIOS / (scenario + '.galaxy')
    source = raw.read_text()
    if scenario == 'morph-acceptance':
        source = (SCENARIOS / 'morph-retention-state.galaxy').read_text() + '\n' + morph_acceptance_source(source)
    bridges = [(SCENARIOS / name).read_text() for name in FIXTURE_BRIDGES.get(scenario, ())]
    source, removed = strip_loaded_bridge_prototypes(source, bridges)
    source = prepare_bank_identifiers(source, revision)
    output.mkdir(parents=True)
    (output / 'map-custom-script.galaxy').write_text('include "TriggerLibs/NativeLib"\n' + source)
    (output / 'private-mod-bridge.galaxy').write_text('\n\n'.join(bridges))
    if scenario == 'prism-acceptance':
        (output / 'PRIVATE-TEST-ONLY-data.xml').write_bytes((SCENARIOS / 'prism-acceptance-data.xml').read_bytes())
    report = {'purpose': 'Source preparation only; editor compilation, game run and replay still required',
              'scenario': scenario, 'revision': revision, 'entrypoint': 'OPP_Test_Run(false, true);',
              'bank_prefix': 'OPPBuildingCancel' + revision,
              'raw_source_sha256': hashlib.sha256(raw.read_bytes()).hexdigest(),
              'bridges': list(FIXTURE_BRIDGES.get(scenario, ())),
              'removed_loaded_bridge_prototypes': removed,
              'fixture_xml_override': scenario == 'prism-acceptance',
              'files_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()},
              'compiled': False, 'runtime_verified': False}
    (output / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scenario', choices=SUPPORTED)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.scenario, args.revision, args.output), indent=2))

if __name__ == '__main__':
    main()
