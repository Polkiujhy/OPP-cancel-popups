#!/usr/bin/env python3
"""Check runtime evidence from the aggregation-units Galaxy fixture (current grouped-unit behavior)."""
import argparse
import json
import xml.etree.ElementTree as ET


def verify(path):
    root = ET.parse(path).getroot()
    data = {
        section.attrib['name']: {
            key.attrib['name']: next(iter(key.find('Value').attrib.values()))
            for key in section
        }
        for section in root
    }
    failures = []

    def expect(section, key, value):
        actual = data.get(section, {}).get(key)
        if actual != str(value):
            failures.append(f'{section}/{key}: expected {value!r}, got {actual!r}')

    expect('Batch0', 'Status0', 'Cancelled')
    for batch in (1, 2):
        expect(f'Batch{batch}', 'Status0', 'Cancelled ×2')
        expect(f'Batch{batch}', 'Displayed', 1)
        expect(f'Batch{batch}', 'Row0ObserverVisible', 1)
    expect('Batch2', 'GameTime', 14)
    expect('Batch3', 'Row0ObserverVisible', 0)
    expect('SCV', 'CancelAccepted', 1)
    expect('Batch4', 'UnitCancels', 1)
    expect('Batch4', 'Row0Name', 'SCV')
    for row in range(3):
        expect('Drones', f'Start{row}', 1)
        expect('Drones', f'Cancel{row}', 1)
    expect('Batch5', 'Row0Name', 'Drone')
    expect('Batch5', 'Row0Status', 'Cancelled ×3')
    expect('Batch5', 'Row0ObserverVisible', 1)
    for row in (1, 2):
        expect('Batch5', f'Row{row}ObserverVisible', 0)
    for batch in (5, 6, 7):
        expect(f'Batch{batch}', 'UnitCancels', 4)
    expect('Batch8', 'Row0Name', 'Pylon')
    expect('Batch8', 'Status0', 'Cancelled')
    for row, name, status in ((0, 'Pylon', 'Cancelled ×2'),
                              (1, 'Pylon', 'Cancelled'),
                              (2, 'Supply Depot', 'Cancelled')):
        expect('Batch9', f'Row{row}Name', name)
        expect('Batch9', f'Row{row}Status', status)
        expect('Batch9', f'Row{row}ObserverVisible', 1)
    owners = data.get('Batch9', {})
    if owners.get('Row0Owner') == owners.get('Row1Owner'):
        failures.append('Batch9: the two Pylons must have different owners')
    for batch in range(10):
        for row in range(3):
            for player in (1, 2):
                expect(f'Batch{batch}', f'Row{row}Player{player}Visible', 0)
            if batch in (3, 6, 7):
                expect(f'Batch{batch}', f'Row{row}ObserverVisible', 0)
    return {'bank': str(path), 'passed': not failures, 'failures': failures,
            'scope': 'Local SC2 runtime control values; not multi-client or visual acceptance.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bank')
    result = verify(parser.parse_args().bank)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
