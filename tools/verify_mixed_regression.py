#!/usr/bin/env python3
"""Verify real mixed adapter sources, conserved groups, five-second UI and GH controls."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from acceptance_bank import read_bank, number, trace
from verify_queue_aggregation import queued, visible, status


PREFIX = [('Oracle', 1, 2, 2), ('Phoenix', 1, 2, 1), ('BarracksTechLab', 1, 0, 1),
          ('Lair', 1, 0, 1), ('SCV', 2, 2, 5), ('TerranInfantryArmorsLevel1', 1, 1, 1)]
BLOCKERS = [('Pylon', 1, 0, 1), ('SupplyDepot', 2, 0, 1), ('SpawningPool', 1, 0, 1)]
METRICS = {'UnitCancels': 11, 'Buildings': 6, 'Research': 1, 'Morphs': 1, 'Prisms': 3}
DEATH_CASES = {
    'PrismDeath': (2, ('Zealot', 'Zealot'), ('Oracle', 1, 2, 1), 'A'),
    'PylonDeath': (1, ('Stalker', 'Sentry'), ('SCV', 2, 2, 1), 'Pylon'),
    'OverlapMixed': (2, ('Zealot', 'Stalker', 'Sentry'), ('Oracle', 1, 2, 1), 'B'),
}


def plain(value):
    return re.sub(r'<[^>]*>', '', value).replace('\xa0', ' ').strip()


def icon(value):
    return value.replace('\\', '/').casefold()


def identity(row):
    return row['key'], row['owner'], row['kind'], row['count']


def check_rows(fields, wanted, expected, *, near=False):
    actual = visible(fields)
    assert [identity(row) for row in actual] == wanted, (actual, wanted)
    for row in actual:
        assert row['name'] == expected[row['key'] + 'Name']
        assert plain(row['status']) == status(row['count'])
        rendered = fields[f'Row{row["row"]}Icon']
        assert rendered and icon(rendered) == icon(expected[row['key'] + 'Icon'])
        assert 0 < row['remaining'] <= 0.75 if near else 4.5 <= row['remaining'] <= 5
    return actual


def require_orders(events, tag, ability, command, count, phase):
    result = [event for event in events if event['Label'] == 'Order' and event['Tag'] == tag
              and event['Ability'] == ability and event['Command'] == str(command) and event['Phase'] == phase]
    assert len(result) == count, (tag, ability, command, count, result)
    return result


def queue_items(fields):
    assert fields['Alive'] == '1'
    result = []
    for slot in range(1, 6):
        count = int(fields[f'Slot{slot}Count'])
        assert count in (0, 1), 'Single-item queue fixture changed'
        if count:
            result.append(fields[f'Slot{slot}'])
    return result


def gh(fields, name, *, denied=False, near=False):
    assert fields['GHActive'] == '1' and fields['GHMatches'] == '1', 'One actual GH facility slot required'
    assert fields['GH0Name'] == name and fields['GH0Visible'] == '1'
    assert fields['GH0Status'] == ('2' if denied else '1')
    if denied:
        assert plain(fields['GH0Label']).casefold() == 'denied'
        remaining = number(fields, 'GH0Remaining')
        assert 0 < remaining <= 0.75 if near else 4.5 <= remaining <= 5
    else:
        assert plain(fields['GH0Label']).casefold() != 'cancelled', 'Queued cancel duplicated GH notification'


def credited_death(bank, events, key, tag, owner):
    damage = bank['Damage']
    assert damage[key + 'Ready'] == '1' and damage[key + 'Effect']
    assert damage[key + 'Tag'] == tag and damage[key + 'Owner'] == str(owner)
    assert damage[key + 'KillingPlayer'] == str(3 - owner) and int(damage[key + 'KillingTag']) > 0
    died = [event for event in events if event['Label'] == 'Died' and event['Tag'] == tag]
    assert len(died) == 1, ('One actual credited source death required', key, died)
    event = died[0]
    assert event['Owner'] == str(owner) and event['Alive'] == event['Removed'] == '0'
    assert event['KillingPlayer'] == damage[key + 'KillingPlayer']
    assert event['KillingTag'] == damage[key + 'KillingTag']
    assert event['Time'] == damage[key + 'Time']
    return event


def same_deadlines(shown, near):
    first, last = visible(shown), visible(near)
    assert [identity(row) for row in first] == [identity(row) for row in last]
    elapsed = number(near, 'Time') - number(shown, 'Time')
    assert elapsed > 0
    for early, late in zip(first, last):
        assert abs(early['remaining'] - late['remaining'] - elapsed) <= 0.0625, 'Timer reset or shortened before natural expiry'


def verify_death_case(bank, events, label):
    owner, types, train, provider = DEATH_CASES[label]
    relevant = [event for event in events if event['Supplement'] == '1' and event['Case'] == label]
    initial, before, after = (bank[label + '/' + suffix] for suffix in ('Initial', 'Before', 'After'))
    train_shown = bank[label + '/TrainShown']
    assert not visible(initial) and not queued(initial)
    assert number(initial, 'Time') >= number(bank['DeniedExpired'], 'Time')
    assert before['WarpCount'] == str(len(types))
    assert after['WarpCount'] == before['WarpCount']
    created = [event for event in relevant if event['Label'] == 'WarpCreated']
    cancels = [event for event in relevant if event['Label'] == 'ConstructCancel']
    assert len(created) == len(cancels) == len(types)
    assert Counter(event['Object'] for event in created) == Counter(types)
    tags = [event['ChildTag'] for event in created]
    assert len(set(tags)) == len(tags) and all(int(tag) > 0 for tag in tags)
    assert before[provider + 'Alive'] == '1' and before[provider + 'Owner'] == str(owner)
    assert before[provider + 'Type'] == ('Pylon' if provider == 'Pylon' else 'WarpPrismPhasing')
    death_key = label + ('KillPylon' if provider == 'Pylon' else 'Kill' + provider)
    died = credited_death(bank, relevant, death_key, before[provider + 'Tag'], owner)
    assert died['Object'] == before[provider + 'Type']
    assert not require_orders(relevant, before[provider + 'Tag'], 'TransportMode', 0, 0, label)
    for index, event in enumerate(created):
        key = f'Warp{index}'
        assert int(event['Tag']) > 0 and event['ChildAlive'] == event['ChildConstructing'] == '1'
        assert event['ChildOwner'] == str(owner) and event['Ability'] == 'WarpGateTrain'
        command = {'Zealot': 0, 'Stalker': 1, 'Sentry': 5}[event['Object']]
        start = require_orders(relevant, event['Tag'], 'WarpGateTrain', command, 1, 'SupplementSetup')[0]
        assert start['Owner'] == str(owner) and start['Alive'] == '1'
        assert number(start, 'Time') <= number(event, 'Time')
        assert before[key + 'Tag'] == event['ChildTag'] and before[key + 'Type'] == event['Object']
        assert before[key + 'Owner'] == str(owner)
        for field in ('Tag', 'Type', 'Owner'):
            assert after[key + field] == before[key + field], 'Cancelled child identity changed'
        assert before[key + 'Alive'] == before[key + 'Constructing'] == before[key + 'From' + provider] == '1'
        assert int(before[key + 'Power']) > 0 and after[key + 'Alive'] == '0'
        for other in {'A', 'B', 'Pylon'} - {provider}:
            assert before[key + 'From' + other] == ('1' if label == 'OverlapMixed' and other == 'A' else '0')
        actual = [cancel for cancel in cancels if cancel['ChildTag'] == event['ChildTag']]
        assert len(actual) == 1 and actual[0]['Tag'] == event['Tag'] and actual[0]['Object'] == event['Object']
        assert number(event, 'Time') <= number(died, 'Time') <= number(actual[0], 'Time') <= number(died, 'Time') + 0.0625
    assert not any(event['Label'] == 'Order' and event['Ability'] == 'Warpable' for event in relevant)
    queued_before, queued_after = bank[label + '/TrainBefore'], bank[label + '/TrainAfter']
    assert queue_items(queued_before) == [train[0]] and queue_items(queued_after) == []
    queue_ability = 'que5CancelToSelection' if train[0] == 'SCV' else 'que5'
    train_order = require_orders(relevant, queued_before['Tag'], queue_ability, 0, 1, label)[0]
    train_cancel = [event for event in relevant if event['Label'] == 'TrainCancel' and event['Tag'] == queued_before['Tag']]
    assert len(train_cancel) == 1 and train_cancel[0]['Tag'] == train_order['Tag']
    assert train_cancel[0]['Owner'] == str(train[1]) and train_cancel[0]['Object'] == train[0]
    assert train_cancel[0]['Time'] == train_order['Time']
    assert number(train_order, 'Time') < number(died, 'Time'), 'Other owner/adapter must interleave with provider loss'
    check_rows(train_shown, [train], bank['Expected'])
    assert not queued(train_shown)
    assert int(train_shown['UnitCancels']) - int(before['UnitCancels']) == 1
    assert int(train_shown['Displayed']) - int(before['Displayed']) == 1
    for field in ('Prisms', 'Warps'):
        assert train_shown[field] == before[field], 'Train path misclassified as warp loss'
    if label == 'OverlapMixed':
        kept, dedup = bank[label + '/Kept'], bank[label + '/Dedup']
        close = require_orders(relevant, before['ATag'], 'TransportMode', 0, 1, label)[0]
        execute = [event for event in relevant if event['Label'] == 'Ability' and event['Tag'] == before['ATag']
                   and event['Ability'] == 'TransportMode' and event['Command'] == '0' and event['Stage'] == '-3']
        assert len(execute) == 1 and execute[0]['Time'] == close['Time']
        assert execute[0]['Alive'] == close['Alive'] == '1'
        assert number(close, 'Time') < number(kept, 'Time') <= number(died, 'Time')
        for index in range(len(types)):
            key = f'Warp{index}'
            for field in ('Tag', 'Type', 'Owner'):
                assert kept[key + field] == dedup[key + field] == before[key + field]
            assert before[key + 'FromA'] == '1'
            assert kept[key + 'Alive'] == kept[key + 'Constructing'] == kept[key + 'FromB'] == '1'
            assert kept[key + 'FromA'] == '0' and int(kept[key + 'Power']) > 0
        for field in ('UnitCancels', 'Prisms', 'Warps', 'Displayed'):
            assert kept[field] == train_shown[field], 'Preserved other field must publish zero'
            assert dedup[field] == after[field], 'Later closed-source death double counted a child'
        assert queued(kept) == []
        later = credited_death(bank, relevant, label + 'KillClosedA', before['ATag'], owner)
        assert number(later, 'Time') > max(number(cancel, 'Time') for cancel in cancels)
        assert [identity(row) for row in visible(dedup)] == [identity(row) for row in visible(after)]
        assert queued(dedup) == queued(after)
    wanted = Counter((object_type, owner, 2, copies) for object_type, copies in Counter(types).items())
    wanted[train] += 1
    active = [identity(row) for row in visible(after)]
    pending = queued(after)
    assert Counter(active + pending) == wanted, ('Exact source/group conservation', label, active, pending, wanted)
    assert active[0] == train and len(active) == min(3, len(wanted))
    assert len(pending) == (1 if label == 'OverlapMixed' else 0)
    assert int(after['Displayed']) - int(initial['Displayed']) == len(active)
    check_rows(after, active, bank['Expected'])
    for row in visible(after):
        deadline = number(after, 'Time') + row['remaining']
        if identity(row) == train:
            assert abs(deadline - number(train_order, 'Time') - 5) <= 0.0625
        else:
            last_cancel = max(number(event, 'Time') for event in cancels if event['Object'] == row['key'])
            assert last_cancel + 5 <= deadline <= last_cancel + 5.25, 'Warp group must receive five seconds after actual cancellation/publication'
    check_rows(bank[label + '/Near'], active, bank['Expected'], near=True)
    assert queued(bank[label + '/Near']) == pending
    same_deadlines(after, bank[label + '/Near'])
    wave, expired = bank[label + '/Wave'], bank[label + '/Expired']
    if pending:
        check_rows(wave, pending, bank['Expected'])
        first_deadline = min(number(after, 'Time') + row['remaining'] for row in visible(after))
        for row in visible(wave):
            assert abs(number(wave, 'Time') + row['remaining'] - first_deadline - 5) <= 0.0625, 'Drained group did not receive its own five seconds'
        check_rows(bank[label + '/WaveNear'], pending, bank['Expected'], near=True)
        same_deadlines(wave, bank[label + '/WaveNear'])
    else:
        assert not visible(wave)
    assert not queued(wave) and not visible(expired) and not queued(expired)
    assert number(wave, 'Time') >= max(number(after, 'Time') + row['remaining'] for row in visible(after))
    if pending:
        assert number(expired, 'Time') >= max(number(wave, 'Time') + row['remaining'] for row in visible(wave))
    for metric in ('Buildings', 'Research', 'Morphs', 'Preserved'):
        assert initial[metric] == before[metric] == expired[metric], 'Supplement altered preserved base adapters/GH control'
    assert before['UnitCancels'] == initial['UnitCancels']
    for metric, delta in (('UnitCancels', len(types) + 1), ('Prisms', len(types)), ('Warps', len(types)), ('Displayed', len(wanted))):
        assert int(expired[metric]) - int(initial[metric]) == delta, (label, metric, delta)
    assert int(after['UnitCancels']) - int(before['UnitCancels']) == len(types) + 1
    assert int(after['Prisms']) - int(before['Prisms']) == len(types)
    assert int(after['Warps']) - int(before['Warps']) == len(types)
    return {'cancellations': len(types) + 1, 'warp_cancellations': len(types),
            'train_cancellations': 1, 'displayed_groups': len(wanted), 'overflow': 0,
            'child_tags': tags, 'preserved_other_field_zero': label == 'OverlapMixed'}


def verify_supplement(bank, events):
    results = {label: verify_death_case(bank, events, label) for label in DEATH_CASES}
    assert len({tag for result in results.values() for tag in result['child_tags']}) == 7
    first, last = bank['DeniedExpired'], bank['SupplementFinished']
    assert not visible(last) and not queued(last)
    assert int(last['UnitCancels']) - int(first['UnitCancels']) == 10
    assert int(last['Prisms']) - int(first['Prisms']) == int(last['Warps']) - int(first['Warps']) == 7
    assert int(last['Displayed']) - int(first['Displayed']) == 9
    assert bank['Finished']['WarpCount'] == '10'
    previous = first
    for label in DEATH_CASES:
        initial = bank[label + '/Initial']
        for metric in ('UnitCancels', 'Buildings', 'Research', 'Morphs', 'Preserved', 'Prisms', 'Warps', 'Displayed'):
            assert initial[metric] == previous[metric], ('Unaccounted events between supplement cases', label, metric)
        previous = bank[label + '/Expired']
    for metric in ('UnitCancels', 'Buildings', 'Research', 'Morphs', 'Preserved', 'Prisms', 'Warps', 'Displayed'):
        assert last[metric] == previous[metric]
    return {'source_cancellations': 10, 'warp_cancellations': 7, 'train_cancellations': 3,
            'displayed_groups': 9, 'overflow_cancellations': 0, 'cases': results}


def split_protocol_trace(bank):
    assert bank['Probe']['Fixture'] == 'mixed-regression'
    assert bank['Probe']['Protocol'] == '2', 'Base-only mixed fixture does not cover the death contract'
    all_events = trace(bank)
    assert bank['BaseFinished']['Done'] == '1'
    base_count = int(bank['BaseFinished']['Events'])
    assert bank['Finished']['BaseEvents'] == str(base_count) and 0 < base_count < len(all_events)
    events = all_events[:base_count]
    assert all(event['Supplement'] == '0' and event['Case'] == '' for event in events)
    assert all(event['Supplement'] == '1' and event['Case'] in DEATH_CASES for event in all_events[base_count:])
    assert {event['Case'] for event in all_events[base_count:]} == set(DEATH_CASES)
    assert number(events[-1], 'Time') <= number(bank['BaseFinished'], 'Time') <= number(all_events[base_count], 'Time')
    return events, all_events


def verify(path):
    bank = read_bank(path)
    events, all_events = split_protocol_trace(bank)
    expected = bank['Expected']
    snapshots = {key: fields for key, fields in bank.items() if 'UIReady' in fields}
    required = {'Baseline', 'Blocked', 'RunningResearch', 'Pending', 'Expired', 'ResetShown', 'ResetNear',
                'ResetExpired', 'DeniedBefore', 'DeniedAfter', 'DeniedNear', 'DeniedExpired'} | {
                    f'{kind}{i}' for kind in ('Wave', 'Near') for i in range(4)}
    extra = {'SupplementFinished'}
    for label in DEATH_CASES:
        extra |= {label + '/' + suffix for suffix in ('Initial', 'Before', 'TrainShown', 'After', 'Near', 'Wave', 'Expired')}
    extra |= {'OverlapMixed/' + suffix for suffix in ('Kept', 'Dedup', 'WaveNear')}
    assert snapshots.keys() == required | extra
    for fields in snapshots.values():
        assert fields['Init'] == fields['UIReady'] == '1'
        assert fields['QueueDetails'] == '1'
        assert sum(item[3] for item in queued(fields)) == int(fields['QueuedCancels'])
        assert all(fields[f'Overflow{owner}Kind{kind}'] == '0' for owner in (1, 2) for kind in range(3))
        for row in range(3):
            assert fields[f'Row{row}Player1'] == fields[f'Row{row}Player2'] == '0'
    baseline, pending = bank['Baseline'], bank['Pending']
    assert not visible(baseline) and not queued(baseline)
    check_rows(bank['Blocked'], BLOCKERS, expected)
    actual_pending = queued(pending)
    assert actual_pending[:6] == PREFIX
    assert Counter(actual_pending[6:9]) == Counter((kind, 2, 2, 1) for kind in ('Zealot', 'Stalker', 'Sentry'))
    assert actual_pending[9:] == [('FactoryReactor', 2, 0, 1)]
    assert len(actual_pending) == 10 and sum(item[3] for item in actual_pending) == 15
    assert [identity(row) for row in visible(pending)] == BLOCKERS
    for key, delta in METRICS.items():
        assert int(pending[key]) - int(baseline[key]) == delta, (key, delta)
    assert int(pending['Displayed']) - int(baseline['Displayed']) == 3
    rendered = []
    for wave in range(4):
        fields, near = bank[f'Wave{wave}'], bank[f'Near{wave}']
        wanted = actual_pending[wave * 3:(wave + 1) * 3]
        rendered.extend(check_rows(fields, wanted, expected))
        check_rows(near, wanted, expected, near=True)
        assert number(near, 'Time') - number(fields, 'Time') == 4.5
        assert queued(fields) == queued(near) == actual_pending[(wave + 1) * 3:]
        assert int(fields['Displayed']) - int(baseline['Displayed']) == 3 + min((wave + 1) * 3, 10)
    assert sum(row['count'] for row in rendered) + sum(item[3] for item in BLOCKERS) == 18
    expired = bank['Expired']
    assert not visible(expired) and not queued(expired)
    assert int(expired['Displayed']) - int(baseline['Displayed']) == 13
    check_rows(bank['ResetShown'], [('Oracle', 1, 2, 1)], expected)
    check_rows(bank['ResetNear'], [('Oracle', 1, 2, 1)], expected, near=True)
    assert not visible(bank['ResetExpired']) and not queued(bank['ResetExpired'])
    assert int(bank['ResetExpired']['Displayed']) - int(baseline['Displayed']) == 14
    for key, delta in METRICS.items():
        assert int(bank['ResetExpired'][key]) - int(baseline[key]) == delta + (key == 'UnitCancels')

    # Independent engine sources: real queues lose exactly the requested items,
    # backed by actual Cancel order events, not just UnitIssueOrder returning true.
    assert bank['Orders'] and all(value == '1' for value in bank['Orders'].values())
    assert queue_items(bank['AirBefore']) == ['Oracle', 'Phoenix', 'Oracle']
    assert queue_items(bank['TrainBefore']) == ['SCV'] * 5
    assert queue_items(bank['ResearchBefore']) == ['TerranInfantryWeaponsLevel1', 'TerranInfantryArmorsLevel1']
    assert queue_items(bank['ResearchAfterQueuedCancel']) == ['TerranInfantryWeaponsLevel1']
    assert queue_items(bank['AirAfter']) == queue_items(bank['TrainAfter']) == []
    require_orders(events, bank['AirBefore']['Tag'], 'que5', 0, 3, 'Burst')
    require_orders(events, bank['AirBefore']['Tag'], 'que5', 0, 1, 'Reset')
    require_orders(events, bank['TrainBefore']['Tag'], 'que5CancelToSelection', 0, 5, 'Burst')
    require_orders(events, bank['ResearchBefore']['Tag'], 'que5', 0, 1, 'Burst')
    for object_type in ('Pylon', 'SupplyDepot', 'SpawningPool'):
        tag = bank['Sources'][object_type + 'Tag']
        assert int(tag) > 0 and bank['Sources'][object_type + 'Constructing'] == '1'
        assert bank['Sources'][object_type + 'Type'] == object_type
        starts = [event for event in events if event['Label'] == 'ConstructStart' and event['ChildTag'] == tag and event['Object'] == object_type]
        cancels = [event for event in events if event['Label'] == 'ConstructCancel' and event['ChildTag'] == tag and event['Object'] == object_type]
        assert len(starts) == len(cancels) == 1
        require_orders(events, tag, 'BuildInProgress', 0, 1, 'Burst')
    for object_type, ability in (('BarracksTechLab', 'BarracksAddOns'), ('FactoryReactor', 'FactoryAddOns')):
        created = [event for event in events if event['Label'] == 'AddonCreated' and event['Object'] == object_type]
        assert len(created) == 1 and created[0]['Ability'] == ability and int(created[0]['ChildTag']) > 0
        cancels = [event for event in events if event['Label'] == 'ConstructCancel' and event['ChildTag'] == created[0]['ChildTag'] and event['Object'] == object_type]
        assert len(cancels) == 1
        orders = require_orders(events, created[0]['Tag'], ability, 30, 1, 'Burst')
        assert orders[0]['Time'] == cancels[0]['Time']
    lair_tag = bank['Sources']['LairTag']
    morph_events = [event for event in events if event['Label'] == 'Ability' and event['Tag'] == lair_tag and event['Ability'] == 'UpgradeToLair' and event['Command'] == '0']
    stages = Counter(event['Stage'] for event in morph_events)
    assert stages['-3'] == stages['-4'] == 1 and stages['-6'] == 0, 'Real morph Execute/Cancel, no Complete required'
    cancel_order = require_orders(events, lair_tag, 'UpgradeToLair', 1, 1, 'Burst')[0]
    cancel_event = next(event for event in morph_events if event['Stage'] == '-4')
    execute_event = next(event for event in morph_events if event['Stage'] == '-3')
    assert cancel_order['Time'] == cancel_event['Time']
    assert number(execute_event, 'Time') <= number(cancel_event, 'Time')
    assert all(event['Alive'] == '1' and event['Owner'] == '1' for event in (execute_event, cancel_event, cancel_order))
    created = [event for event in events if event['Label'] == 'WarpCreated']
    assert len(created) == 3 and Counter(event['Object'] for event in created) == Counter(('Zealot', 'Stalker', 'Sentry'))
    assert len({event['ChildTag'] for event in created}) == 3
    assert all(int(event['ChildTag']) > 0 and int(event['Tag']) > 0 and event['ChildAlive'] == event['ChildConstructing'] == '1' and event['ChildOwner'] == '2' for event in created)
    close_order = require_orders(events, bank['Sources']['PrismTag'], 'TransportMode', 0, 1, 'Burst')[0]
    close_execute = [event for event in events if event['Label'] == 'Ability' and event['Tag'] == bank['Sources']['PrismTag'] and event['Ability'] == 'TransportMode' and event['Command'] == '0' and event['Stage'] == '-3']
    assert len(close_execute) == 1 and close_execute[0]['Time'] == close_order['Time']
    assert close_execute[0]['Alive'] == close_order['Alive'] == '1'
    for event in created:
        cancels = [cancel for cancel in events if cancel['Label'] == 'ConstructCancel' and cancel['ChildTag'] == event['ChildTag'] and cancel['Object'] == event['Object']]
        assert len(cancels) == 1
        assert cancels[0]['Tag'] == event['Tag'] and cancels[0]['Object'] == event['Object']
        assert cancels[0]['Time'] == close_order['Time']
    assert sum(event['Label'] == 'ConstructCancel' for event in events) == 8
    name = expected['TerranInfantryWeaponsLevel1Name']
    gh(bank['Baseline'], name)
    gh(bank['RunningResearch'], name)
    assert bank['Baseline']['GH0Slot'] == bank['RunningResearch']['GH0Slot']
    for label in ('DeniedBefore', 'DeniedAfter', 'DeniedNear', 'DeniedExpired'):
        assert not visible(bank[label]) and not queued(bank[label])
        for metric in ('UnitCancels', 'Buildings', 'Research', 'Displayed'):
            assert bank[label][metric] == bank['ResetExpired'][metric], 'GH control duplicated into own popup queue'
    gh(bank['DeniedBefore'], name)
    gh(bank['DeniedAfter'], name, denied=True)
    gh(bank['DeniedNear'], name, denied=True, near=True)
    assert not any(bank['DeniedExpired'].get(f'GH{i}Visible') == '1' for i in range(int(bank['DeniedExpired']['GHMatches'])))
    assert int(bank['DeniedAfter']['Preserved']) - int(bank['DeniedBefore']['Preserved']) == 1
    assert sum(event['Label'] == 'Died' and event['Tag'] == bank['Sources']['DeniedTag'] for event in events) == 1
    assert sum(event['Label'] == 'ResearchCancel' and event['Tag'] == bank['Sources']['DeniedTag'] for event in events) == 1
    credited_death(bank, events, 'Denied', bank['Sources']['DeniedTag'], 2)
    supplement = verify_supplement(bank, all_events)
    assert int(bank['SupplementFinished']['Displayed']) - int(baseline['Displayed']) == 23
    for label, total in (('ResetExpired', 19), ('SupplementFinished', 29)):
        assert sum(int(bank[label][metric]) - int(baseline[metric]) for metric in ('UnitCancels', 'Buildings', 'Research')) == total
    return {'result': 'PASS', 'scope': 'Local mixed real source/UI regression; replay and current multi-client roles separate',
            'source_cancellations': 29, 'base_source_cancellations': 19, 'burst_cancellations': 18, 'pending_groups': 10,
            'pending_cancellations': 15, 'displayed_groups': 23, 'base_displayed_groups': 14, 'overflow_cancellations': 0,
            'supplement': supplement, 'gh_running_preserved': True, 'gh_denied_preserved': True,
            'base_events': len(events), 'events': len(all_events),
            'active_player_visibility_samples_false': len(snapshots) * 6,
            'bank': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bank', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = json.dumps(verify(args.bank), ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(output)
    print(output, end='')


if __name__ == '__main__':
    main()
