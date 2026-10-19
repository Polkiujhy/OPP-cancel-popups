#!/usr/bin/env python3
"""Verify real production-panel CancelSlot clicks recorded by SC2."""
import argparse
import json
import xml.etree.ElementTree as ET


def verify(path):
    data = {s.get('name'): {k.get('name'): next(iter(k.find('Value').attrib.values())) for k in s}
            for s in ET.parse(path).getroot()}
    failures = []

    def expect(section, key, expected):
        actual = data.get(section, {}).get(key)
        if actual != str(expected):
            failures.append(f'{section}/{key}: expected {expected!r}, got {actual!r}')

    expect('Orders', 'SlowTrainSet', 1)
    expect('ResearchClickReady', 'Used', 3)
    for section in ('ResearchClickReady', 'ResearchClicked'):
        expect(section, 'First', 'TerranInfantryWeaponsLevel1')
        expect(section, 'GameHeartActive', 1)
        expect(section, 'GameHeartRunning', 1)
    expect('ResearchClicked', 'Used', 2)
    expect('ResearchClicked', 'ResearchOwn', 1)
    expect('ResearchClicked', 'Row0Name', 'Terran Infantry Armor Level 1')
    expect('ResearchClicked', 'Row0Status', 'Cancelled')
    expect('UnitClickReady', 'Used', 5)
    expect('UnitClickReady', 'UnitCancels', 0)
    expect('UnitClicked', 'Used', 4)
    expect('UnitClicked', 'First', 'SCV')
    expect('UnitClicked', 'UnitCancels', 1)
    expect('AllFiveCancelled', 'Used', 0)
    expect('AllFiveCancelled', 'UnitCancels', 5)
    expect('AllFiveCancelled', 'Row0Name', 'SCV')
    expect('AllFiveCancelled', 'Row0Status', 'Cancelled ×5')
    expect('Expired', 'UnitCancels', 5)
    for section in ('ResearchClicked', 'UnitClicked', 'AllFiveCancelled', 'Expired'):
        expect(section, 'ResearchOwn', 1)
    for ability in ('que5', 'que5CancelToSelection'):
        if not any(k.startswith('QueueOrder') and d.get('Ability') == ability and d.get('Command') == '1'
                   for k, d in data.items()):
            failures.append(f'No native CancelSlot order for {ability}')
    for section in ('ResearchClickReady', 'ResearchClicked', 'UnitClickReady', 'UnitClicked', 'AllFiveCancelled', 'Expired'):
        for row in range(3):
            for player in (1, 2):
                expect(section, f'Row{row}Player{player}Visible', 0)
            if section == 'Expired':
                expect(section, f'Row{row}ObserverVisible', 0)
    return {'bank': str(path), 'passed': not failures, 'failures': failures,
            'scope': 'Actual SC2 production-panel clicks on waiting entries, current GameHeart research preserved, five-unit count, expiry and observer control routing.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bank')
    result = verify(parser.parse_args().bank)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
