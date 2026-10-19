#!/usr/bin/env python3
"""Verify real SC2 UI controls, timers and queue conservation from the acceptance bank."""
import argparse
import hashlib
import json
from pathlib import Path
from verify_morph_scope_baseline import read_bank


def visible(snapshot):
    result = []
    for row in range(3):
        key = f'Row{row}'
        if snapshot[key + 'Visible'] == '1':
            result.append({'row': row, 'name': snapshot[key + 'Name'],
                           'status': snapshot[key + 'Status'],
                           'count': int(snapshot[key + 'Count']),
                           'owner': int(snapshot[key + 'Owner']),
                           'kind': int(snapshot[key + 'Kind']),
                           'key': snapshot[key + 'Key'],
                           'remaining': float(snapshot[key + 'Remaining'])})
    return result


def queued(snapshot):
    return [(snapshot[f'Queue{i}Key'], int(snapshot[f'Queue{i}Owner']),
             int(snapshot[f'Queue{i}Kind']), int(snapshot[f'Queue{i}Copies']))
            for i in range(int(snapshot['QueueGroups']))]


def status(count):
    return 'Cancelled' + (f' ×{count}' if count > 1 else '')


def check_rows(snapshot, expected, near_expiry=False):
    rows = visible(snapshot)
    assert [(row['name'], row['count']) for row in rows] == expected, (rows, expected)
    for row in rows:
        assert row['status'] == status(row['count']), row
        if near_expiry:
            assert 0 < row['remaining'] <= 0.75, row
        else:
            assert 4.5 <= row['remaining'] <= 5.0, row
    return rows


def verify(path):
    bank = read_bank(path)
    assert bank['Probe']['Fixture'] == 'queue-aggregation-acceptance'
    assert bank['Finished']['Done'] == '1'
    snapshots = [values for values in bank.values() if 'UIReady' in values]
    assert snapshots
    for snapshot in snapshots:
        assert snapshot['Init'] == snapshot['UIReady'] == '1'
        for row in range(3):
            assert snapshot[f'Row{row}Player1'] == snapshot[f'Row{row}Player2'] == '0'
        assert 0 <= int(snapshot['QueueGroups']) <= 128
        assert int(snapshot['QueuedCancels']) >= int(snapshot['QueueGroups'])
        if snapshot['QueueDetails'] == '1':
            pending = queued(snapshot)
            assert sum(item[3] for item in pending) == int(snapshot['QueuedCancels'])
    initial = bank['Age/Initial']
    assert queued(initial) == [('Oracle', 1, 2, 2), ('Phoenix', 1, 2, 1)]
    late = bank['Age/Late']
    assert float(late['Time']) - float(initial['Time']) > 10
    assert queued(late) == [('Oracle', 1, 2, 3), ('Phoenix', 1, 2, 1)]
    check_rows(bank['Age/Shown'], [('Oracle', 3), ('Phoenix', 1)])
    check_rows(bank['Age/NearExpiry'], [('Oracle', 3), ('Phoenix', 1)], near_expiry=True)
    assert not visible(bank['Age/Expired'])

    assert queued(bank['Identity/Pending']) == [('SameID', 1, 2, 2), ('SameID', 2, 2, 1),
                                                ('SameID', 1, 0, 1), ('SameID', 1, 1, 1),
                                                ('OtherID', 1, 2, 1)]
    first = check_rows(bank['Identity/First'], [('UnitOwner1', 2), ('UnitOwner2', 1), ('BuildingOwner1', 1)])
    assert [(row['owner'], row['kind']) for row in first] == [(1, 2), (2, 2), (1, 0)]
    second = check_rows(bank['Identity/Second'], [('ResearchOwner1', 1), ('UnitOtherType', 1)])
    assert [(row['owner'], row['kind']) for row in second] == [(1, 1), (1, 2)]
    assert queued(bank['Empty/Pending']) == [('', 1, 0, 1), ('', 1, 0, 1)]
    check_rows(bank['Empty/Shown'], [('Unkeyed1', 1), ('Unkeyed2', 1)])

    drain = bank['Drain/ShownAndMerged']
    assert int(drain['QueueGroups']) == 0
    row = visible(drain)[0]
    assert row['name'] == 'Oracle' and row['count'] == 3 and row['status'] == status(3)
    assert row['remaining'] == 5.0

    full = bank['Capacity/Full']
    assert 0 < int(full['Head']) < 128, 'Ring must start away from zero to exercise wrap-around.'
    assert int(full['QueueGroups']) == 128
    assert int(full['QueuedCancels']) == 130
    assert queued(full) == [(f'Pending{i}', 1, 2, 3 if i == 0 else 1) for i in range(128)]
    assert full['Overflow2Kind1'] == '2'
    assert all(full[f'Overflow{owner}Kind{kind}'] == '0'
               for owner in [1, 2] for kind in range(3) if (owner, kind) != (2, 1))
    rendered = []
    overflow = []
    for wave in range(43):
        snapshot = bank[f'Capacity/Wave{wave}']
        expected_pending = max(128 - 3 * (wave + 1), 0)
        assert int(snapshot['QueueGroups']) == int(snapshot['QueuedCancels']) == expected_pending
        for row in visible(snapshot):
            assert 4.5 <= row['remaining'] <= 5.0, (wave, row)
            assert row['status'] == status(row['count']), (wave, row)
            if row['key']:
                rendered.append(row)
            else:
                overflow.append(row)
    assert [(row['name'], row['count']) for row in rendered] == [(f'Pending{i}', 3 if i == 0 else 1) for i in range(128)]
    assert sum(row['count'] for row in rendered) == 130
    assert len(overflow) == 1
    assert overflow[0]['owner'] == 2 and overflow[0]['kind'] == 1
    assert overflow[0]['name'].startswith('2') and 'upgrade' in overflow[0]['name'].lower()
    assert not visible(bank['Capacity/Expired'])
    assert int(bank['Capacity/Expired']['QueueGroups']) == 0
    assert all(bank['Capacity/Expired'][f'Overflow{owner}Kind{kind}'] == '0'
               for owner in [1, 2] for kind in range(3))

    air = {}
    for label, name in [('Oracle', 'Oracle'), ('VoidRay', 'Void Ray'), ('Phoenix', 'Phoenix')]:
        assert all(bank[label][f'{kind}{i}'] == '1' for kind in ['Start', 'Cancel'] for i in range(5))
        before, pending = bank[label + '/Before'], bank[label + '/Pending']
        assert int(pending['UnitCancels']) - int(before['UnitCancels']) == 5, label
        assert int(pending['QueueGroups']) == 1 and int(pending['QueuedCancels']) == 5, label
        check_rows(bank[label + '/Shown'], [(name, 5)])
        check_rows(bank[label + '/NearExpiry'], [(name, 5)], near_expiry=True)
        assert not visible(bank[label + '/Expired']), label
        air[label] = 5
    return {'result': 'PASS', 'bank': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'pending_age_seconds': float(late['Time']) - float(initial['Time']),
            'capacity': {'groups': 128, 'grouped_cancellations': 130, 'overflow_cancellations': 2,
                         'rendered_normal_groups': len(rendered), 'rendered_overflow_groups': len(overflow)},
            'actual_stargate_cancellations': air, 'snapshots': len(snapshots),
            'active_player_visibility_samples_false': len(snapshots) * 6,
            'cases': ['pending A/B/A', 'pending age >10s', 'owner/kind/catalog ID',
                      'unkeyed FIFO', 'Drain shown group merge', 'ring wrap-around',
                      'capacity duplicate before overflow', 'actual Stargate x5', 'full five-second exposure']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bank', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify(args.bank)
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
