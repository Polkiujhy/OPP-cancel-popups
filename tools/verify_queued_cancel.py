#!/usr/bin/env python3
"""Verify real SC2 cancellations of running and waiting production entries."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def verify(path):
    sections = {
        s.get('name'): {k.get('name'): next(iter(k.find('Value').attrib.values())) for k in s}
        for s in ET.parse(path).getroot()
    }
    labels = {d['Label']: d for d in sections.values() if 'Label' in d}
    failures = []

    def expect(label, key, expected):
        actual = labels.get(label, {}).get(key)
        if actual != str(expected):
            failures.append(f'{label}/{key}: expected {expected!r}, got {actual!r}')

    orders = sections.get('Orders', {})
    for prefix, count in [('Train', 5), ('CancelTrain', 5), ('Research', 3), ('CancelResearch', 3)]:
        for i in range(count):
            if orders.get(prefix + str(i)) != '1':
                failures.append(f'Orders/{prefix}{i}: order not accepted')
    expect('FiveQueued', 'Used', 5)
    expect('ThreeUpgradesQueued', 'Used', 3)
    for i in range(2, 5):
        label = f'AfterTrainCancel{i}'
        expect(label, 'Used', 4 - i)
        expect(label, 'UnitCancels', i + 1)
        expect(label, 'ResearchOwn', 0)
        expect(label, 'Row0Name', 'SCV')
        expect(label, 'Row0Status', f'Cancelled ×{i + 1}')
    # TerranBuildingArmor is named Neosteel Armor in the tested multiplayer data.
    upgrades = ['Neosteel Armor', 'Terran Infantry Armor Level 1', 'Terran Infantry Weapons Level 1']
    for i in range(3):
        label = f'AfterResearchCancel{i}'
        expect(label, 'Used', 2 - i)
        expect(label, 'ResearchOwn', i + 1)
        expect(label, 'UnitCancels', 5)
        for row in range(i + 1):
            expect(label, f'Row{row}Name', upgrades[row])
            expect(label, f'Row{row}Status', 'Cancelled')
            expect(label, f'Row{row}ObserverVisible', 1)
    for label in ['EmptyCancel', 'Destroyed', 'Completed']:
        expect(label, 'UnitCancels', 5)
        expect(label, 'ResearchOwn', 3)
        for row in range(3):
            expect(label, f'Row{row}ObserverVisible', 0)
    if not any(d.get('Label') == 'TrainComplete' for d in sections.values()):
        failures.append('No natural TrainComplete event recorded')
    for label in ['FiveQueued', 'AfterTrainCancel2', 'AfterTrainCancel3', 'AfterTrainCancel4',
                  'ThreeUpgradesQueued', 'AfterResearchCancel0', 'AfterResearchCancel1',
                  'AfterResearchCancel2', 'EmptyCancel', 'Destroyed', 'Completed']:
        expect(label, 'InitializationCount', 1)
        for player in (1, 2):
            for row in range(3):
                expect(label, f'Row{row}Player{player}Visible', 0)
    return {'bank': str(path), 'passed': not failures, 'failures': failures,
            'scope': 'SC2 runtime queue removals, counts, deduplication, negative controls and observer routing; multi-client visual acceptance is separate.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bank', type=Path)
    result = verify(parser.parse_args().bank)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
