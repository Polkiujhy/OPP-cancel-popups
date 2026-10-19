#!/usr/bin/env python3
"""Require actual native deaths/warp cancellation and both BattleReport slots."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from acceptance_bank import read_bank

CASES = ('Combat1', 'Combat2', 'Warp1', 'Warp2', 'Baneling1', 'Baneling2',
         'Remove1', 'Remove2', 'Invalid1', 'Invalid2', 'NaturalComplete')


def trace_for(bank, case):
    return [bank[f'Event{i}'] for i in range(1, int(bank['Finished']['Events']) + 1)
            if bank[f'Event{i}']['Case'] == case]


def type_counts(fields, slot):
    prefix = f'Slot{slot}'
    count = int(fields[prefix + 'Types'])
    assert 0 <= count <= 16
    result = Counter()
    for index in range(count):
        key = prefix + 'Type' + str(index)
        assert fields[key] and fields[key] not in result
        result[fields[key]] = int(fields[key + 'Count'])
        assert result[fields[key]] > 0
    return result


def verify_case(bank, case):
    assert case in CASES and bank[case]['Done'] == '1'
    data, before, after = bank[case], bank[case + '/Before'], bank[case + '/After']
    trace = trace_for(bank, case)
    deaths = [event for event in trace if event['Label'] == 'Died']
    removals = [event for event in trace if event['Label'] == 'Removed']
    assert before['TrackEnabled'] == after['TrackEnabled'] == '1'
    assert after['BattleActive'] == '1', 'The real callback must run in an active battle'
    if case != 'Combat1':
        assert before['BattleActive'] == '1'
    owner = int(data['TargetOwner'])
    expected_owner = {'Combat1': 2, 'Combat2': 1}.get(case, int(case[-1]) if case[-1].isdigit() else 2)
    assert owner == expected_owner
    tag = data['TargetTag']
    assert int(tag) > 0 and data['TargetAlive'] == '1'
    cancels = [event for event in trace if event['Label'] == 'ConstructCancel']
    completions = [event for event in trace if event['Label'] == 'ConstructComplete']
    expected_types = Counter()
    costs = {'Minerals': 0, 'Gas': 0, 'Supply': 0.0}
    count = 0
    credited_slot = None
    if case.startswith('Remove'):
        assert not deaths and not cancels and not completions, 'UnitRemove must not be relabelled as a death/cancel'
        assert len(removals) == 1, 'Actual UnitRemoved callback required'
        removed = removals[0]
        assert data['TargetValid'] == '1' and after['TargetValid'] == after['TargetAlive'] == '0'
        assert removed['EventUnitPresent'] == removed['EventMatchesTarget'] == '1'
        assert removed['RemovedTargetTag'] == tag and removed['RemovedTargetOwner'] == str(owner)
        assert removed['RemovedTargetType'] == data['TargetType'] == 'Marine'
        assert removed['EventUnitValid'] in ('0', '1') and removed['EventUnitAlive'] in ('0', '1')
        if removed['EventUnitValid'] == '1':
            assert removed['EventUnitTag'] == tag
        else:
            assert removed['EventUnitTag'] == removed['EventUnitAlive'] == '0'
        assert float(before['Time']) <= float(removed['Time']) <= float(after['Time'])
    elif case == 'NaturalComplete':
        assert not removals
        assert not deaths and not cancels and len(completions) == 1
        assert completions[0]['ProgressTag'] == tag and completions[0]['UnitTag'] == data['GateTag']
        assert after['TargetAlive'] == '1' and after['TargetConstructing'] == '0'
        hits = [event for event in trace if event['Label'] == 'KeepBattleDamage']
        assert len(hits) == 2 and data['KeepAliveType'] == 'Nexus' and data['KeepAliveOwner'] == '2'
        for hit in hits:
            assert hit['UnitTag'] == data['KeepAliveTag'] and hit['UnitType'] == 'Nexus' and hit['UnitOwner'] == '2'
            assert hit['UnitAlive'] == '1' and hit['KillingPlayer'] == '1'
            assert hit['KillingTag'] == data['KeepAttackerTag'] and int(hit['KillingTag']) > 0 and float(hit['Absorbed']) > 0
        assert float(hits[0]['Time']) <= float(before['Time']) < float(hits[1]['Time']) < float(after['Time'])
    else:
        assert not removals
        target = [event for event in deaths if event['UnitTag'] == tag]
        assert len(target) == 1
        death = target[0]
        assert death['UnitType'] == data['TargetType'] and death['UnitOwner'] == str(owner)
        assert death['UnitAlive'] == '0'
        if case.startswith('Invalid'):
            assert death['Removed'] == '0' and death['KillingPlayer'] == data['AttackerOwner'] == '3'
            assert death['KillingTag'] == data['AttackerTag'] and int(death['KillingTag']) > 0
            assert len(deaths) == 1
        else:
            credited_slot = 2 - owner
            assert death['Removed'] == '0'
            if case.startswith('Warp'):
                assert death['KillingPlayer'] == '16' and death['KillingTag'] == '0', 'Require the native neutral cancellation path'
            else:
                assert int(death['KillingPlayer']) == 3 - owner
                assert death['KillingTag'] == data['AttackerTag'] and int(death['KillingTag']) > 0
                assert int(data['AttackerOwner']) == 3 - owner
            expected_types[data['TargetType']] += 1
            costs = {metric: float(data['Target' + metric]) for metric in ('Minerals', 'Gas')}
            costs['Supply'] = float(death['DeathSupply'])
            count = 1
            if case == 'Warp2':
                source = [event for event in deaths if event['UnitTag'] == data['SourceTag']]
                assert len(source) == 1 and len(deaths) == 2
                source = source[0]
                assert source['Removed'] == '0' and source['UnitAlive'] == '0'
                assert source['UnitType'] == data['SourceType'] == 'WarpPrismPhasing' and source['UnitOwner'] == '2'
                assert source['KillingPlayer'] == data['AttackerOwner'] == '1'
                assert source['KillingTag'] == data['AttackerTag'] and int(source['KillingTag']) > 0
                assert float(death['Time']) - float(source['Time']) in (0, 0.0625)
                expected_types['WarpPrismPhasing'] += 1
                costs['Minerals'] += float(data['SourceMinerals'])
                costs['Gas'] += float(data['SourceGas'])
                costs['Supply'] += float(source['DeathSupply'])
                count = 2
            else:
                assert len(deaths) == 1
    warp = case.startswith('Warp') or case == 'NaturalComplete'
    if warp:
        assert data['StartAccepted'] == data['ChildCreated'] == data['FromSource'] == '1'
        assert int(data['GatePower']) >= 1
        assert data['TargetType'] == 'Zealot' and data['TargetConstructing'] == '1'
        born = [event for event in trace if event['Label'] == 'Created']
        assert len(born) == 1 and born[0]['UnitTag'] == tag and born[0]['UnitOwner'] == str(owner)
        assert born[0]['Ability'] == 'WarpGateTrain' and born[0]['ProgressTag'] == data['GateTag']
        starts = [event for event in trace if event['Label'] == 'Order' and event['Ability'] == 'WarpGateTrain']
        assert len(starts) == 1 and starts[0]['Command'] == '0'
        assert starts[0]['UnitTag'] == data['GateTag'] and starts[0]['Time'] == born[0]['Time']
        if case != 'NaturalComplete':
            assert len(cancels) == 1 and cancels[0]['ProgressTag'] == tag
            assert cancels[0]['UnitTag'] == data['GateTag'] and cancels[0]['Type'] == 'Zealot'
            assert cancels[0]['Time'] == next(event['Time'] for event in deaths if event['UnitTag'] == tag)
            assert not completions and after['TargetAlive'] == '0'
        if case == 'Warp1':
            closes = [event for event in trace if event['Label'] == 'Order' and event['Ability'] == 'TransportMode']
            assert len(closes) == 1 and closes[0]['UnitTag'] == data['SourceTag']
            assert closes[0]['Time'] == cancels[0]['Time'] and data['CloseAccepted'] == '1'
    else:
        assert not cancels and not completions
        assert data['TargetType'] == ('Stalker' if case.startswith('Combat') else 'Baneling' if case.startswith('Baneling') else 'Marine')
    for slot in range(2):
        selected = slot == credited_slot
        for metric in ('Units', 'Minerals', 'Gas', 'Supply'):
            wanted = count if metric == 'Units' else costs[metric]
            assert float(after[f'Slot{slot}{metric}']) - float(before[f'Slot{slot}{metric}']) == (wanted if selected else 0), (case, slot, metric)
        actual_types = type_counts(after, slot)
        actual_types.subtract(type_counts(before, slot))
        assert +actual_types == (expected_types if selected else Counter())
        assert all(value >= 0 for value in actual_types.values()), 'No prior unit counts may disappear'
    for metric in ('Units', 'Warps', 'Prisms', 'Buildings', 'Morphs'):
        wanted = 1 if case.startswith('Warp') and metric in ('Units', 'Warps', 'Prisms') else 0
        assert int(after[metric]) - int(before[metric]) == wanted, (case, 'False/duplicate own popup', metric)
    return {'case': case, 'deaths': len(deaths), 'removals': len(removals), 'battle_slot': credited_slot, 'battle_units': count,
            'actual_cancel': len(cancels)}


def verify(bank_or_path):
    bank = read_bank(bank_or_path) if isinstance(bank_or_path, (str, Path)) else bank_or_path
    assert bank['Probe']['Fixture'] == 'obspp-battle-report-acceptance'
    assert bank['Finished']['Done'] == '1' and bank['Finished']['Cases'] == str(len(CASES))
    count = int(bank['Finished']['Events'])
    assert {key for key in bank if re.fullmatch(r'Event\d+', key)} == {f'Event{i}' for i in range(1, count + 1)}
    assert {bank[f'Event{i}']['Case'] for i in range(1, count + 1)} == set(CASES)
    return {'result': 'PASS', 'scope': 'Actual native BattleReport accounting; provenance/compile/log/replay gates are separate.',
            'cases': [verify_case(bank, case) for case in CASES]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bank', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify(args.bank)
    result['sha256'] = hashlib.sha256(args.bank.read_bytes()).hexdigest()
    output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(output)
    print(output, end='')


if __name__ == '__main__':
    main()
