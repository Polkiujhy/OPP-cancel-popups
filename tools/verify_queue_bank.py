#!/usr/bin/env python3
"""Verify recorded SC2 control state from the 138-cancellation stress fixture."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def verify(path):
    sections = {
        section.get('name'): {
            key.get('name'): next(iter(key.find('Value').attrib.values()))
            for key in section
        }
        for section in ET.parse(path).getroot()
    }
    errors = []

    def expect(condition, message):
        if not condition:
            errors.append(message)

    expect(sections.get('Setup', {}).get('Accepted') == '138', '138 cancel orders were not accepted')
    names = ['Pylon', 'Supply Depot', 'Spawning Pool']
    ordinary = 0
    for batch in range(46):
        data = sections.get(f'Batch{batch}')
        if data is None:
            errors.append(f'Missing Batch{batch}; fixture has not finished')
            continue
        expect(data.get('BuildingCancels') == '138', f'Batch{batch}: missing or duplicated event')
        expect(abs(float(data['GameTime']) - (8.25 + batch * 5)) < .0625, f'Batch{batch}: unexpected game-time interval')
        expected_displayed = min(3 * (batch + 1), 131) + (batch >= 43) + (batch >= 44)
        expect(int(data['Displayed']) == expected_displayed, f'Batch{batch}: display count')
        for row in range(3):
            prefix = f'Row{row}'
            for player in (1, 2):
                expect(data.get(f'{prefix}Player{player}Visible') == '0', f'Batch{batch}/{prefix}: visible to active player {player}')
            index = batch * 3 + row
            expected = None
            if index < 131:
                expected = (names[index % 3], 'Local Player' if index % 2 == 0 else 'Player 2')
                ordinary += 1
            elif batch == 43 and row == 2:
                expected = ('3 additional building cancellations', 'Local Player')
            elif batch == 44 and row == 0:
                expected = ('4 additional building cancellations', 'Player 2')
            expect(data.get(prefix + 'ObserverVisible') == ('1' if expected else '0'), f'Batch{batch}/{prefix}: observer visibility')
            if expected:
                expect((data.get(prefix + 'Name'), data.get(prefix + 'Owner')) == expected, f'Batch{batch}/{prefix}: FIFO content/owner or overflow total')
    return {
        'bank': str(path), 'scope': 'real SC2 dialog properties; not a live spectator/referee client test',
        'ordinary_rows_checked': ordinary, 'overflow_expected': {'player1': 3, 'player2': 4},
        'errors': errors, 'passed': not errors,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bank', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify(args.bank)
    rendered = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(rendered)
    print(rendered)
    raise SystemExit(not result['passed'])
