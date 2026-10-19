#!/usr/bin/env python3
"""Verify the popup-position fixture's SC2 runtime bank (visual QA is separate)."""
import argparse
import json
import xml.etree.ElementTree as ET


def verify(path):
    data = {
        s.attrib['name']: {k.attrib['name']: next(iter(k.find('Value').attrib.values())) for k in s}
        for s in ET.parse(path).getroot()
    }
    failures = []

    def expect(section, key, expected):
        actual = data.get(section, {}).get(key)
        if actual != str(expected):
            failures.append(f'{section}/{key}: expected {expected!r}, got {actual!r}')

    sections = ['ThreeKinds', 'FourthQueued', 'FourthShown', 'Expired',
                'ResearchGroup0', 'ResearchGroup1', 'ResearchGroup2', 'ResearchExpired',
                'NoWorkers', 'WorkerRefreshed', 'CancelRefreshed', 'FinalExpired']
    for section in sections:
        expect(section, 'InitializationCount', 1)
        expect(section, 'UnitCancels', 1)
        expect(section, 'WorkersActive', 1)
        for player in (1, 2):
            expect(section, f'Workers{player}Killed', 2)
            for row in range(3):
                expect(section, f'Row{row}Player{player}Visible', 0)
    for key in ('TrainAccepted', 'ResearchAccepted', 'NormalResearchAccepted'):
        expect('Orders', key, 1)
    for section in ('ThreeKinds', 'FourthQueued'):
        expect(section, 'Displayed', 3)
        for row, name in enumerate(('Terran Infantry Weapons Level 1', 'SCV', 'Pylon')):
            expect(section, f'Row{row}Name', name)
            expect(section, f'Row{row}Status', 'Cancelled')
            expect(section, f'Row{row}ObserverVisible', 1)
        for player in (1, 2):
            expect(section, f'Workers{player}Visible', 1)
    expect('FourthQueued', 'BuildingCancels', 2)
    expect('FourthShown', 'Displayed', 4)
    expect('FourthShown', 'Row0Name', 'Supply Depot')
    expect('FourthShown', 'Row0ObserverVisible', 1)
    for row in (1, 2):
        expect('FourthShown', f'Row{row}ObserverVisible', 0)
    for i in range(3):
        section = f'ResearchGroup{i}'
        expect(section, 'ResearchOwn', i + 2)
        expect(section, 'Displayed', 5)
        expect(section, 'Row0Status', 'Cancelled' + (f' ×{i+1}' if i else ''))
        expect(section, 'Row0ObserverVisible', 1)
        for row in (1, 2):
            expect(section, f'Row{row}ObserverVisible', 0)
    for section in ('Expired', 'ResearchExpired', 'FinalExpired'):
        for row in range(3):
            expect(section, f'Row{row}ObserverVisible', 0)
    expect('ResearchExpired', 'ResearchOwn', 4)
    expect('NoWorkers', 'BuildingCancels', 3)
    expect('NoWorkers', 'Displayed', 6)
    expect('NoWorkers', 'Row0Name', 'Pylon')
    expect('NoWorkers', 'Row0ObserverVisible', 1)
    for player in (1, 2):
        expect('NoWorkers', f'Workers{player}Visible', 0)
    for section in ('WorkerRefreshed', 'CancelRefreshed'):
        expect(section, 'Workers1Visible', 1)
        expect(section, 'Workers2Visible', 0)
        expect(section, 'Row0Name', 'Pylon')
        expect(section, 'Row0ObserverVisible', 1)
        expect(section, 'Displayed', 6)
    expect('WorkerRefreshed', 'Row0Status', 'Cancelled')
    expect('CancelRefreshed', 'BuildingCancels', 4)
    expect('CancelRefreshed', 'Row0Status', 'Cancelled ×2')
    return {'bank': str(path), 'passed': not failures, 'failures': failures,
            'scope': 'SC2 runtime values, queue, grouping and recipients; screenshot/multi-client acceptance is separate.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bank')
    result = verify(parser.parse_args().bank)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
