#!/usr/bin/env python3
"""Verify baseline cancellation defects from SC2 banks, not a fixed mod's acceptance.

Usage: verify_cancel_diagnostics.py full.SC2Bank focused.SC2Bank [gateway.SC2Bank]
The banks must be copied before Rewind, which can run fixture code again.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def read(path):
    result = {}
    for section in ET.parse(path).getroot().findall('Section'):
        values = {}
        for key in section.findall('Key'):
            value = key.find('Value')
            values[key.get('name')] = next(iter(value.attrib.values()))
        result[section.get('name')] = values
    assert result.get('Finished', {}).get('Done') == '1', f'Incomplete fixture: {path}'
    return result


def rows(snapshot):
    return [{'name': snapshot.get(f'Row{i}Name'), 'status': snapshot.get(f'Row{i}Status')}
            for i in range(3) if snapshot.get(f'Row{i}Visible') == '1']


def events(bank, case):
    return [values for name, values in bank.items()
            if name.startswith('Event') and values.get('Case') == case]


def delta(bank, case, before, after, counter):
    return int(bank[f'{case}/{after}'][counter]) - int(bank[f'{case}/{before}'][counter])


def deliberate_morph_cancels(bank, case):
    tag = bank[case]['During0Tag']
    trace = [values for name, values in bank.items() if name.startswith('Event') and values.get('UnitTag') == tag]
    orders = {(e['Time'], e['Ability']) for e in trace
              if e.get('Label') == 'Order' and e.get('Command') == '1'}
    return [e for e in trace if e.get('Label') == 'Ability' and e.get('Stage') == '-4'
            and e.get('UnitAlive') == '1' and (e['Time'], e['Ability']) in orders]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('full', type=Path)
    parser.add_argument('focused', type=Path)
    parser.add_argument('gateway', type=Path, nargs='?')
    args = parser.parse_args()
    full, focused = read(args.full), read(args.focused)
    result = {'scope': 'Baseline defect reproduction; not evidence of implemented fixes.',
              'banks': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in [args.full, args.focused] + ([args.gateway] if args.gateway else [])},
              'morphs': {}, 'addons': {}, 'air': {}, 'prism': {}, 'gateway': {}}
    for case in ['Lair', 'Hive', 'GreaterSpire', 'Ravager', 'Lurker', 'Baneling',
                 'BroodLord', 'Overseer', 'Dropperlord', 'Planetary', 'Orbital']:
        data = full[case]
        attempts = 2 if case in ('Lair', 'Orbital') else 1
        for i in range(attempts):
            assert data[f'Start{i}'] == data[f'Cancel{i}'] == '1', case
            assert delta(full, case, 'Before', f'After{i}', 'Buildings') == 0, case
            assert delta(full, case, 'Before', f'After{i}', 'Units') == 0, case
        cancelled = deliberate_morph_cancels(full, case)
        assert len(cancelled) == attempts, case
        result['morphs'][case] = {'cancellations': attempts, 'popup_delta': 0,
                                 'ability': cancelled[0]['Ability'],
                                 'targets': [v for k, v in sorted(cancelled[0].items()) if k.startswith('MorphTarget')]}
    for facility in ['Barracks', 'Factory', 'Starport']:
        for command in range(2):
            case = f'{facility}Addon{command}'
            data = focused[case]
            assert all(data.get(key) == '1' for key in ['StartParentRoute', 'CancelParentRoute', 'StartChildRoute', 'CancelChildRoute']), case
            assert data['ChildBeforeParentRouteConstructing'] == '1' and data['SavedChildAfterParentRouteAlive'] == '0', case
            assert delta(focused, case, 'BeforeParentRoute', 'AfterParentRoute', 'Buildings') == 0, case
            assert delta(focused, case, 'AfterParentRoute', 'AfterChildRoute', 'Buildings') == 1, case
            cancels = [e for e in events(focused, case) if e.get('Label') == 'ConstructCancel']
            assert len(cancels) == 2, case
            assert all(e['UnitTag'] == data['ParentTag'] for e in cancels), case
            result['addons'][case] = {'type': data['ChildBeforeParentRouteType'],
                                      'parent_popup_delta': 0, 'child_popup_delta': 1,
                                      'construction_event_parent_tag': data['ParentTag'],
                                      'native_child_available_during_construction': data['NativeLookupWhileBuildingPresent'] == '1'}
    for unit, name in [('Oracle', 'Oracle'), ('Void', 'Void Ray'), ('Phoenix', 'Phoenix')]:
        for busy in [False, True]:
            case = unit + ('Busy' if busy else 'Free')
            assert all(full[case].get(f'{kind}{i}') == '1' for kind in ['Start', 'Cancel'] for i in range(5)), case
            assert delta(full, case, 'Before', 'Immediate', 'Units') == 5, case
            observed = rows(full[f'{case}/NextRows' if busy else f'{case}/Immediate'])
            if busy:
                assert observed == [{'name': name, 'status': 'Cancelled'}] * 3, case
                assert rows(full[f'{case}/LastRows']) == [{'name': name, 'status': 'Cancelled'}] * 2, case
            else:
                assert observed == [{'name': name, 'status': 'Cancelled ×5'}], case
            result['air'][case] = {'counted': 5, 'visible': observed}
    for case in ['PrismClose', 'PrismComplete', 'PrismAlternate', 'PrismKilled']:
        assert all(focused[case].get(f'Start{i}') == '1' for i in range(3)), case
        during, settled = focused[f'{case}/During'], focused[f'{case}/After19']
        assert during['WarpCount'] == settled['WarpCount'] == '3', case
        assert all(during[f'Warp{i}Alive'] == during[f'Warp{i}Constructing'] == '1' for i in range(3)), case
        lost = case in ('PrismClose', 'PrismKilled')
        assert all(settled[f'Warp{i}Alive'] == ('0' if lost else '1') for i in range(3)), case
        assert all(settled[f'Warp{i}Constructing'] == '0' for i in range(3)), case
        assert delta(focused, case, 'Before', 'After19', 'Units') == 0, case
        cancelled = [e for e in events(focused, case) if e.get('Label') == 'ConstructCancel']
        assert len(cancelled) == (3 if lost else 0), case
        if lost:
            assert {e['Object'] for e in cancelled} == {'Zealot', 'Stalker', 'Sentry'}, case
        result['prism'][case] = {'lost': 3 if lost else 0, 'completed': 0 if lost else 3,
                                 'popup_delta': 0, 'construct_cancel_events': len(cancelled)}
    assert focused['MorphNatural']['SettledType'] == 'OrbitalCommand'
    assert delta(focused, 'MorphKilled', 'Before', 'After', 'Buildings') == 0
    assert delta(focused, 'MorphKilled', 'Before', 'After', 'Units') == 0
    banks = [full, focused]
    if args.gateway:
        gateway = read(args.gateway)
        banks.append(gateway)
        for case in ['ToWarpGateFree', 'ToWarpGatePaid', 'ToGatewayNormal', 'ToWarpGateFreeBypass', 'ToGatewayBypass']:
            cancelled = deliberate_morph_cancels(gateway, case)
            expected = 2 if case in ('ToWarpGateFree', 'ToGatewayNormal') else 1
            assert len(cancelled) == expected, case
            assert delta(gateway, case, 'Before', 'After' + str(expected - 1), 'Buildings') == 0, case
            assert delta(gateway, case, 'Before', 'After' + str(expected - 1), 'Units') == 0, case
            result['gateway'][case] = {'cancel_events': len(cancelled), 'ability': cancelled[0]['Ability'],
                                       'popup_delta': 0,
                                       'targets': [v for k, v in sorted(cancelled[0].items()) if k.startswith('MorphTarget')]}
    samples = 0
    for bank in banks:
        for values in bank.values():
            if 'UIReady' in values:
                assert values['UIReady'] == '1' and values['Init'] == '1'
                for row in range(3):
                    for player in range(1, 3):
                        assert values.get(f'Row{row}Player{player}') == '0'
                        samples += 1
    result['active_player_visibility_samples_false'] = samples
    result['baseline_checks'] = 'PASS'
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
