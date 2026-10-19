#!/usr/bin/env python3
"""Accept addon cancellation engine pairs + actual UI; historical defect checks stay separate."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from verify_cancel_diagnostics import read

FAMILIES = ('Barracks', 'Factory', 'Starport')
NAMES = {family + kind: f'{title} - {family}' for family in FAMILIES
         for kind, title in [('TechLab', 'Tech Lab'), ('Reactor', 'Reactor')]}
GROUPS = {
    'SingleStarportTechLabParent': ['StarportTechLab'],
    'TwoStarportsTechLabParent': ['StarportTechLab'] * 2,
    'TwoStarportsTechLabChild': ['StarportTechLab'] * 2,
    'BarracksFactoryTechLabParent': ['BarracksTechLab', 'FactoryTechLab'],
    'FactoryStarportTechLabParent': ['FactoryTechLab', 'StarportTechLab'],
    'ThreeFacilitiesTechLabParent': [f + 'TechLab' for f in FAMILIES],
    'ThreeFacilitiesTechLabChild': [f + 'TechLab' for f in FAMILIES],
    'TwoFactoriesMixedParent': ['FactoryTechLab', 'FactoryReactor'],
    'TwoFactoriesMixedChild': ['FactoryTechLab', 'FactoryReactor'],
    'SixTechLabParent': [f + 'TechLab' for f in FAMILIES for _ in range(2)],
    'SixTechLabChild': [f + 'TechLab' for f in FAMILIES for _ in range(2)],
    'SingleStarportReactorParent': ['StarportReactor'],
    'SingleStarportReactorChild': ['StarportReactor'],
    'TwoStarportsReactorParent': ['StarportReactor'] * 2,
    'TwoStarportsReactorChild': ['StarportReactor'] * 2,
    'SixReactorParent': [f + 'Reactor' for f in FAMILIES for _ in range(2)],
    'SixReactorChild': [f + 'Reactor' for f in FAMILIES for _ in range(2)],
}


def checked_trace(bank):
    count = int(bank['Finished']['Events'])
    names = {key for key in bank if key.startswith('Event') and key[5:].isdigit()}
    assert names == {f'Event{i}' for i in range(1, count + 1)}, 'Truncated/noncontiguous engine trace'
    return [bank[f'Event{i}'] for i in range(1, count + 1)]


def require_pair(trace, case, child_tag, parent_tag, kind, child_route):
    """Neither an accepted order nor Ability Complete can stand in for this pair."""
    assert int(child_tag) > 0 and int(parent_tag) > 0 and kind in NAMES
    created = [event for event in trace if event.get('Label') == 'Created'
               and event.get('ProgressTag') == child_tag]
    assert len(created) == 1, (case, 'Actual addon creation required', child_tag)
    creation = created[0]
    assert creation['Case'] == case and creation['UnitTag'] == parent_tag and creation['Object'] == kind, case
    family = kind.removesuffix('TechLab').removesuffix('Reactor')
    assert creation['Ability'] == family + 'AddOns', case
    cancelled = [event for event in trace if event.get('Label') == 'ConstructCancel'
                 and event.get('ProgressTag') == child_tag]
    assert len(cancelled) == 1, (case, 'One actual child cancellation required', child_tag)
    cancel = cancelled[0]
    assert cancel['Case'] == case and cancel['UnitTag'] == parent_tag and cancel['Object'] == kind, case
    assert float(creation['Time']) <= float(cancel['Time']), case
    ability = 'BuildInProgress' if child_route else family + 'AddOns'
    command = '0' if child_route else '30'
    order_tag = child_tag if child_route else parent_tag
    orders = [event for event in trace if event.get('Label') == 'Order'
              and event.get('Case') == case and event.get('UnitTag') == order_tag
              and event.get('Ability') == ability and event.get('Command') == command
              and event.get('Time') == cancel['Time']]
    assert len(orders) == 1, (case, 'Explicit same-attempt/order-time pair required', child_tag)
    return {'child_tag': child_tag, 'parent_tag': parent_tag, 'type': kind,
            'time': cancel['Time'], 'route': 'child' if child_route else 'parent'}


def ui_rows(snapshot):
    return [{'key': snapshot[f'Row{i}Key'], 'name': snapshot[f'Row{i}Name'],
             'status': snapshot[f'Row{i}Status'], 'count': int(snapshot[f'Row{i}Count']),
             'icon': snapshot[f'Row{i}Icon'], 'remaining': float(snapshot[f'Row{i}Remaining']),
             'owner': int(snapshot[f'Row{i}Owner']), 'kind': int(snapshot[f'Row{i}Kind'])}
            for i in range(3) if snapshot[f'Row{i}Visible'] == '1']


def check_ui(snapshot, types, icons, exact=True):
    rows = ui_rows(snapshot)
    expected = Counter(types)
    assert len({row['key'] for row in rows}) == len(rows), 'Duplicated catalog group'
    actual = {row['key']: row for row in rows}
    if exact:
        assert set(actual) == set(expected), (actual, expected)
    for kind, amount in expected.items():
        row = actual[kind]
        assert row['name'] == NAMES[kind] and row['owner'] == 1 and row['kind'] == 0, row
        assert row['count'] == amount, row
        assert row['status'] == 'Cancelled' + (f' ×{amount}' if amount > 1 else ''), row
        assert row['icon'] and row['icon'] == icons[kind], row
        assert 0 < row['remaining'] <= 5.0, row
    return rows


def check_visibility(bank):
    samples = 0
    for snapshot in bank.values():
        if 'UIReady' not in snapshot:
            continue
        assert snapshot['UIReady'] == snapshot['Init'] == '1'
        for row in range(3):
            for player in (1, 2):
                assert snapshot[f'Row{row}Player{player}'] == '0'
                samples += 1
    return samples


def verify_group_case(bank, case, inputs, trace=None):
    """Focused completed-case check; never claims the unfinished full fixture passed."""
    types = GROUPS[case]
    pairs = []
    if trace is None:
        trace = [value for name, value in bank.items()
                 if name.startswith('Event') and name[5:].isdigit()]
    setup = bank[case]
    ready, after = (bank[case + '/' + phase] for phase in ('Ready', 'After'))
    child_route = case.endswith('Child')
    assert setup['Count'] == ready['Remaining'] == str(len(types)), case
    assert after['Remaining'] == setup['TimedOut'] == '0', case
    assert setup['SelectChildren'] == str(int(child_route)), case
    keys = [entry['key'] for entry in inputs if entry.get('case') == case]
    assert 'Escape' in keys and all(key in ('Escape', 'Tab') for key in keys), case
    if not child_route and len({kind.removesuffix('TechLab').removesuffix('Reactor') for kind in types}) > 1:
        assert 'Tab' in keys, (case, 'Real active-subgroup changes required')
    icons = {}
    for i, kind in enumerate(types):
        assert setup[f'Started{i}'] == '1', case
        assert setup[f'OriginalChild{i}Type'] == ready[f'Child{i}Type'] == kind, case
        assert ready[f'Child{i}Alive'] == ready[f'Child{i}Constructing'] == '1', case
        assert ready[f'Child{i}Tag'] == setup[f'OriginalChild{i}Tag'] and ready[f'Child{i}Owner'] == '1', case
        assert ready[f'ChildSelected{i}'] == str(int(child_route)), case
        assert ready[f'ParentSelected{i}'] == str(int(not child_route)), case
        assert after[f'Child{i}Alive'] == '0', case
        pairs.append(require_pair(trace, case, setup[f'OriginalChild{i}Tag'], setup[f'Parent{i}Tag'], kind, child_route))
        icons[kind] = setup[f'OriginalChildIcon{i}']
    assert int(after['Buildings']) - int(ready['Buildings']) == len(types), case
    assert after['Units'] == ready['Units'], case
    rows = check_ui(after, types, icons)
    return {'cancellations': len(types), 'keys': keys, 'rows': rows, 'pairs': pairs}


def retention_chunks(manifest, paths):
    """Require all closed, revision-matched fragments before consuming any cycles."""
    assert len(paths) == 4, 'All four closed retention banks are mandatory'
    chunks = {}
    for path in paths:
        fragment = read(path)
        assert fragment['Finished']['Done'] == '1', (path, 'Unfinished retention fragment')
        chunk = int(fragment['Probe']['Chunk'])
        assert chunk in range(4) and chunk not in chunks
        start, end = chunk * 40, min((chunk + 1) * 40, 129)
        assert int(fragment['Finished']['NextCycle']) == end
        trace = checked_trace(fragment)
        assert set(event['Case'] for event in trace) == {f'Cycle{i}' for i in range(start, end)}
        assert fragment['Probe']['BankName'] == manifest['RetentionHeld'][f'Chunk{chunk}'], (path, 'Wrong retention fragment')
        chunks[chunk] = (path, fragment, trace, start, end)
    return chunks


def verify_lift_case(bank, trace):
    """Real lift-off follows an engine-confirmed completed addon, without cancellation."""
    lift, complete = bank['NegativeLift'], bank['NegativeComplete']
    assert lift['ParentTag'] == complete['ParentTag'] and lift['ChildTag'] == complete['ChildTag']
    assert lift['ChildType'] == complete['ChildType'] == 'StarportTechLab'
    assert lift['ParentType'] == 'Starport' and lift['ParentTypeAfter'] == 'StarportFlying'
    assert lift['LiftAccepted'] == lift['ParentAlive'] == lift['ChildAlive'] == lift['ChildAliveAfter'] == '1'
    assert lift['ChildConstructing'] == lift['ChildConstructingAfter'] == '0'
    assert complete['ChildAliveAfter'] == '1' and complete['ChildConstructingAfter'] == '0'
    before, after = bank['NegativeLift/Before'], bank['NegativeLift/After']
    assert before['Buildings'] == after['Buildings'] and before['Units'] == after['Units']
    assert not any(event['Label'] == 'ConstructCancel' and event['Case'] == 'NegativeLift' for event in trace)
    assert any(event['Label'] == 'ConstructComplete' and event['Case'] == 'NegativeComplete'
               and event['ProgressTag'] == lift['ChildTag'] and event['UnitTag'] == lift['ParentTag'] for event in trace)


def verify(bank_path, input_path, retention_paths):
    bank = read(bank_path)
    assert bank['Finished']['Done'] == '1', 'Unfinished addon acceptance fixture'
    assert bank['Probe']['Fixture'] == 'addon-acceptance'
    assert all(value == '1' for value in bank['Setup'].values())
    inputs = json.loads(input_path.read_text())
    trace = checked_trace(bank)
    samples = check_visibility(bank)
    pairs = []
    groups = {}
    for case in GROUPS:
        result = verify_group_case(bank, case, inputs, trace)
        pairs.extend(result.pop('pairs'))
        assert bank[case + '/Expired']['Remaining'] == '0', case
        assert not ui_rows(bank[case + '/Expired']), case
        groups[case] = result
    for family in FAMILIES:
        for command, suffix in enumerate(('TechLab', 'Reactor')):
            last_tag = None
            parent_tag = None
            for route in ('Parent', 'Child', 'Repeat'):
                case = f'{family}{command}{route}'
                fields = bank[case]
                kind = family + suffix
                assert fields['Start'] == fields['Cancel'] == fields['ChildAlive'] == fields['ChildConstructing'] == '1', case
                assert fields['ChildType'] == kind and fields['ChildOwner'] == '1' and fields['ChildAliveAfter'] == '0', case
                assert int(fields['AfterBuildings']) - int(fields['BeforeBuildings']) == 1, case
                assert int(bank[case + '/After']['Buildings']) - int(bank[case + '/Before']['Buildings']) == 1, case
                assert bank[case + '/After']['Units'] == bank[case + '/Before']['Units'], case
                assert fields['ChildTag'] != last_tag, (case, 'Distinct child attempts required')
                if parent_tag:
                    assert fields['ParentTag'] == parent_tag, 'Repeat must use the same parent'
                last_tag, parent_tag = fields['ChildTag'], fields['ParentTag']
                pairs.append(require_pair(trace, case, fields['ChildTag'], fields['ParentTag'], kind, route == 'Child'))
                check_ui(bank[case + '/After'], [kind], {kind: fields['Icon']})
                assert not ui_rows(bank[case + '/Expired']), case

    for path, fragment, fragment_trace, start, end in retention_chunks(bank, retention_paths).values():
        for index in range(start, end):
            case = f'Cycle{index}'
            fields = fragment[case]
            assert fields['Start'] == fields['Cancel'] == fields['ChildAlive'] == fields['ChildConstructing'] == '1', case
            assert fields['ChildType'] == 'FactoryTechLab' and fields['ChildAliveAfter'] == '0', case
            assert int(fields['AfterBuildings']) - int(fields['BeforeBuildings']) == 1, case
            pairs.append(require_pair(fragment_trace, case, fields['ChildTag'], fields['ParentTag'], 'FactoryTechLab', index % 2 == 0))
    held = bank['RetentionHeld']
    assert held['Cycles'] == '129' and held['StillConstructing'] == held['Cancel'] == '1'
    assert held['ChildAliveAfter'] == '0'
    assert int(bank['RetentionHeld/Before']['Buildings']) - int(bank['RetentionHeld/Held']['Buildings']) == 129
    assert int(bank['RetentionHeld/After']['Buildings']) - int(bank['RetentionHeld/Before']['Buildings']) == 1
    pairs.append(require_pair(trace, 'RetentionHeld', held['ChildTag'], held['ParentTag'], 'StarportReactor', False))
    check_ui(bank['RetentionHeld/After'], ['StarportReactor'], {'StarportReactor': held['Icon']}, exact=False)
    assert not ui_rows(bank['RetentionHeld/Expired'])
    assert len(pairs) == 197
    assert len({item['child_tag'] for item in pairs}) == 197, 'A child attempt may be counted only once'

    negatives = ['NegativeEmptyHalt', 'NegativeChildDeath', 'NegativeParentDeath',
                 'NegativeLift', 'NegativeComplete', 'NegativeRejectedCancel', 'NegativeSCVHalt']
    for case in negatives:
        before, after = bank[case + '/Before'], bank[case + '/After']
        assert after['Buildings'] == before['Buildings'] and after['Units'] == before['Units'], case
        assert not ui_rows(before) and not ui_rows(after), case
    for case in ('NegativeChildDeath', 'NegativeParentDeath', 'NegativeComplete'):
        assert bank[case]['ChildAlive'] == bank[case]['ChildConstructing'] == bank[case]['Start'] == '1'
    assert bank['NegativeChildDeath']['ChildAliveAfter'] == '0'
    assert bank['NegativeParentDeath']['ParentAliveAfter'] == '0'
    verify_lift_case(bank, trace)
    assert bank['NegativeComplete']['ChildAliveAfter'] == '1'
    assert bank['NegativeComplete']['ChildConstructingAfter'] == '0'
    assert bank['NegativeRejectedCancel']['ChildAliveAfter'] == '1'
    assert any(e['Label'] == 'ConstructComplete' and e['Case'] == 'NegativeComplete'
               and e['ProgressTag'] == bank['NegativeComplete']['ChildTag'] for e in trace)
    scv = bank['NegativeSCVHalt']
    assert scv['Build'] == scv['Halt'] == scv['ConstructionAlive'] == scv['ConstructionConstructing'] == '1'
    assert scv['ConstructionType'] == 'SupplyDepot'
    assert any(e['Label'] == 'ConstructStart' and e['Case'] == 'NegativeSCVHalt'
               and e['ProgressTag'] == scv['ConstructionTag'] for e in trace)
    for case in ('Boundary0', 'Boundary1'):
        assert int(bank[case + '/After']['Buildings']) - int(bank[case + '/Before']['Buildings']) == 1
    assert int(bank['Finished/Final']['Buildings']) == 199, '197 real cancellations + two separately labelled boundary probes'
    assert int(bank['Finished/Final']['Units']) == 0
    return {'result': 'PASS', 'scope': 'Local Test Document engine/UI acceptance; screenshots and replay and multi-client roles require separate evidence.',
            'groups': groups, 'real_child_cancellations': len(pairs), 'pairs': pairs,
            'retention_cycles': 129, 'pairing_boundary_probes': 2, 'negative_cases': negatives,
            'active_player_visibility_samples_false': samples,
            'hashes': {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in (bank_path, input_path, *retention_paths)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bank', type=Path)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('--retention-bank', type=Path, action='append', default=[])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify(args.bank, args.inputs, args.retention_bank)
    output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(output)
    print(output, end='')


if __name__ == '__main__':
    main()
