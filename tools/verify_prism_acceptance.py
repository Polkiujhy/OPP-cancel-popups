#!/usr/bin/env python3
"""Verify actual warp-child/provider events, publication, UI and closed fragments."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


TYPES = {'Zealot', 'Stalker', 'Sentry', 'HighTemplar', 'DarkTemplar', 'Adept'}
ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DATA = 'tests/functional/scenarios/prism-acceptance-data.xml'
STANDARD = {
    # created, actual Construct Cancel indices, published indices, Prism count
    'SingleClose': (3, (0, 1, 2), (0, 1, 2), 3),
    'CloseThenLaterDeath': (3, (0, 1, 2), (0, 1, 2), 3),
    'SeparateCloseAndKill': (4, (0, 1, 2, 3), (0, 1, 2, 3), 4),
    'OverlapKeep': (3, (), (), 0),
    'PylonKeep': (3, (), (), 0),
    'NaturalComplete': (3, (), (), 0),
    'KilledOnly': (3, (0, 1, 2), (0, 1, 2), 3),
    'DirectOnly': (3, (0,), (0,), 0),
    'DirectAndClose': (3, (0, 1, 2), (0, 1, 2), 2),
    'MixedCloseThenKill': (3, (0, 1, 2), (0, 1, 2), 3),
    'MixedKillThenClose': (3, (0, 1, 2), (0, 1, 2), 3),
    'BothClose': (3, (0, 1, 2), (0, 1, 2), 3),
    'TwoOwners': (4, (0, 1, 2, 3), (0, 1, 2, 3), 4),
    'PylonKilled': (3, (0, 1, 2), (0, 1, 2), 3),
    'OverlapKilledKeep': (3, (), (), 0),
    'BothKilledAB': (3, (0, 1, 2), (0, 1, 2), 3),
    'BothKilledBA': (3, (0, 1, 2), (0, 1, 2), 3),
    'SeparateBothKilled': (4, (0, 1, 2, 3), (0, 1, 2, 3), 4),
    'TwoOwnersKilled': (4, (0, 1, 2, 3), (0, 1, 2, 3), 4),
    'DirectAndKill': (3, (0, 1, 2), (0, 1, 2), 2),
    'PylonKilledKeep': (3, (), (), 0),
    'LatePrismClose': (3, (0, 1, 2), (0, 1, 2), 3),
    'LatePylonKeep': (3, (), (), 0),
    'NaturalPhasing': (3, (), (), 0),
    'NaturalPylon': (3, (), (), 0),
    'Moment0': (1, (0,), (0,), 1),
    'Moment1': (1, (0,), (0,), 1),
    'FullRows': (3, (0, 1, 2), (0, 1, 2), 3),
    'FullQueue': (3, (0, 1, 2), (0, 1, 2), 3),
    'FullRowsKilled': (3, (0, 1, 2), (0, 1, 2), 3),
    'FullQueueKilled': (3, (0, 1, 2), (0, 1, 2), 3),
}


def read_bank(path):
    return {section.attrib['name']: {
        key.attrib['name']: next(iter(key)).attrib[next(iter(next(iter(key)).attrib))]
        for key in section.findall('Key')}
        for section in ET.parse(path).getroot().findall('Section')}


def finished(bank):
    assert bank['Finished']['Done'] == '1', 'Fragment never finished'
    count = int(bank['Finished']['Events'])
    assert {key for key in bank if re.fullmatch(r'Event\d+', key)} == {
        f'Event{i}' for i in range(1, count + 1)}, 'Truncated/noncontiguous engine trace'
    assert bank['Finished'].get('Overflow', '0') == '0', 'Fixture child registry overflow'


def events(bank, case):
    return [bank[key] for key in sorted(bank, key=lambda key: int(key[5:]) if re.fullmatch(r'Event\d+', key) else -1)
            if re.fullmatch(r'Event\d+', key) and bank[key]['Case'] == case]


def verify_death_lifecycle(bank):
    """Require credited cleanup deaths, closed trace and zero extra own alerts."""
    terminal = bank['Finished']
    assert terminal['DeathClosed'] == '1', 'Death trace was not closed before BankRemove'
    assert terminal['DeathOverflow'] == '0', 'Independent death trace overflow'
    count = int(terminal['DeathEvents'])
    assert 0 < count <= 256
    assert {key for key in bank if re.fullmatch(r'Death\d+', key)} == {
        f'Death{i}' for i in range(1, count + 1)}, 'Truncated/noncontiguous independent death trace'
    trace = [bank[f'Death{i}'] for i in range(1, count + 1)]
    assert len({death['UnitTag'] for death in trace}) == count, 'Duplicate actual UnitDied identity'
    assert [float(death['Time']) for death in trace] == sorted(float(death['Time']) for death in trace)
    for death in trace:
        assert int(death['UnitTag']) > 0 and death['UnitType']
        assert death['UnitPresent'] == '1' and death['UnitAlive'] == '0'
        assert death['Removed'] in ('0', '1')
        assert death['Phase'] in ('', 'children', 'providers', 'retention-preparation')

    label = bank['Probe']['Fragment']
    if re.fullmatch(r'Retention\d+', label):
        cases = {f'Cycle{i}' for i in range(int(terminal['StartCycle']), int(terminal['EndCycleExclusive']))}
    else:
        cases = {label}
    assert all(death['Case'] in cases for death in trace)
    suffix = '/Preparation' if label == 'RetentionStart' else '/Cleanup'
    expected_sections = {case + suffix for case in cases}
    assert {name for name in bank if name.endswith(('/Preparation', '/Cleanup'))} == expected_sections
    matched = set()
    targets_total = 0
    for section in expected_sections:
        fields = bank[section]
        case = section.rsplit('/', 1)[0]
        preparation = label == 'RetentionStart'
        assert fields['Policy'] == ('credited-unused-gates' if preparation else 'credited-children-before-providers')
        assert fields['Done'] == '1' and fields['RemainingLive'] == '0'
        assert all(fields[metric + 'Before'] == fields[metric + 'After'] for metric in ('Units', 'Warps', 'Prisms')), (case, 'Cleanup created extra cancellation alerts')
        started, ended = float(fields['Started']), float(fields['Finished'])
        assert ended - started >= 0.3125
        if preparation:
            assert fields['HeldAlive'] == fields['HeldConstructing'] == '1'
        else:
            children_done = float(fields['ChildrenDone'])
            providers_start, providers_done = float(fields['ProvidersStarted']), float(fields['ProvidersDone'])
            assert started + 0.125 <= children_done == providers_start
            assert providers_start + 0.125 <= providers_done <= ended - 0.1875
        targets = int(fields['Targets'])
        assert 0 < targets <= 20
        if preparation:
            assert targets == 3
        assert {int(match[1]) for key in fields if (match := re.fullmatch(r'Target(\d+)Tag', key))} == set(range(targets))
        target_tags = set()
        for index in range(targets):
            prefix = f'Target{index}'
            tag, phase = fields[prefix + 'Tag'], fields[prefix + 'Phase']
            assert tag not in target_tags and int(tag) > 0
            target_tags.add(tag)
            assert fields[prefix + 'Present'] == fields[prefix + 'Alive'] == fields[prefix + 'Ready'] == '1'
            owner = int(fields[prefix + 'Owner'])
            assert owner in (1, 2) and int(fields[prefix + 'AttackerTag']) > 0
            when = float(fields[prefix + 'Time'])
            assert started <= when <= ended
            if preparation:
                assert phase == 'retention-preparation' and fields[prefix + 'Type'] == 'WarpGate'
                deadline = ended - 0.1875
            elif phase == 'children':
                assert fields[prefix + 'Type'] in TYPES and when < providers_start
                deadline = children_done
            else:
                assert phase == 'providers' and fields[prefix + 'Type'] in ('WarpGate', 'WarpPrism', 'WarpPrismPhasing', 'Pylon', 'Probe')
                assert when >= providers_start
                deadline = providers_done
            deaths = [death for death in trace if death['UnitTag'] == tag]
            assert len(deaths) == 1, (case, 'Actual credited cleanup death required', tag)
            death = deaths[0]
            assert death['Case'] == case and death['Phase'] == phase
            assert death['UnitOwner'] == str(owner) and death['UnitType'] == fields[prefix + 'Type']
            assert death['KillingPlayer'] == str(3 - owner) and death['KillingTag'] == fields[prefix + 'AttackerTag']
            assert death['Removed'] == '0', 'Live UnitRemove is not credited cleanup'
            assert when <= float(death['Time']) <= deadline
            matched.add(tag)
        targets_total += targets
    assert {death['UnitTag'] for death in trace if death['Phase']} == matched, 'Unattributed cleanup death'
    # ProviderDied is the scenario trace used by the power proof. The independent
    # callback must carry exactly the same actual death and killer identity.
    for event in bank.values():
        if event.get('Label') != 'ProviderDied':
            continue
        deaths = [death for death in trace if death['UnitTag'] == event['UnitTag']]
        assert len(deaths) == 1
        assert all(deaths[0][key] == event[key] for key in ('Case', 'Time', 'UnitType', 'UnitOwner', 'KillingPlayer', 'KillingTag'))
        assert deaths[0]['Phase'] == ''
    return {'deaths': count, 'credited_cleanup_targets': targets_total, 'closed': True}


def plain(value):
    return re.sub(r'<[^>]*>', '', value).replace('\xa0', ' ').strip()


def icon(value):
    return value.replace('\\', '/').casefold().rsplit('/', 1)[-1]


def expected_icon(object_type):
    return 'btn-unit-protoss-' + object_type.casefold() + '.dds'


def rows(fields):
    return [dict(index=row, **{key: fields[f'Row{row}{key}'] for key in (
        'Owner', 'Kind', 'Count', 'Key', 'Name', 'Status', 'Icon', 'Remaining')})
        for row in range(3) if fields[f'Row{row}Visible'] == '1']


def groups(fields):
    result = Counter()
    for row in rows(fields):
        result[(row['Owner'], row['Key'])] += int(row['Count'])
    for offset in range(int(fields['PendingGroups'])):
        prefix = f'Queue{offset}'
        assert fields[prefix + 'Kind'] == '2'
        result[(fields[prefix + 'Owner'], fields[prefix + 'Key'])] += int(fields[prefix + 'Count'])
    return result


def check_ui(fields, before, indices, *, blocked=False):
    wanted = Counter((before[f'Warp{i}StartedOwner'], before[f'Warp{i}StartedType']) for i in indices)
    if blocked:
        assert len(rows(fields)) == 3
        assert all(row['Key'].startswith('PrismBlock') for row in rows(fields))
        actual = Counter((fields[f'Queue{i}Owner'], fields[f'Queue{i}Key'])
                         for i in range(int(fields['PendingGroups'])))
        assert actual == wanted
        assert all(fields[f'Queue{i}Count'] == '1' for i in range(int(fields['PendingGroups'])))
        return
    assert groups(fields) == wanted, (groups(fields), wanted)
    for row in rows(fields):
        object_type = row['Key']
        assert row['Kind'] == '2'
        index = next(i for i in indices if before[f'Warp{i}StartedType'] == object_type
                     and before[f'Warp{i}StartedOwner'] == row['Owner'])
        assert row['Name'] == before[f'Warp{index}ExpectedName']
        assert icon(row['Icon']) == icon(before[f'Warp{index}ExpectedIcon']) == expected_icon(object_type)
        status = plain(row['Status']).casefold()
        assert 'cancelled' in status
        assert ('×' + row['Count']) in status.replace(' ', '') if int(row['Count']) > 1 else '×' not in status
        assert 4.6 <= float(row['Remaining']) <= 5.0, row


def provider_edges(fields):
    return [{key: fields[f'Provider{i}{key}'] for key in (
        'Generation', 'Tag', 'Alive', 'Current', 'Lost', 'LostTime', 'Death', 'DeathTime',
        'CloseOrder', 'CloseExecute', 'CloseOrderTime', 'CloseExecuteTime')}
        for i in range(int(fields['Providers']))]


def require_close(trace, source_tag):
    execute = [event for event in trace if event['Label'] == 'Ability'
               and event.get('Ability') == 'TransportMode' and event.get('Command') == '0'
               and event['Stage'] == '-3' and event['UnitTag'] == source_tag]
    orders = [event for event in trace if event['Label'] == 'Order'
              and event.get('Ability') == 'TransportMode' and event.get('Command') == '0'
              and event['UnitTag'] == source_tag]
    assert len(execute) == len(orders) == 1, ('Missing real close', source_tag)
    assert execute[0]['Time'] == orders[0]['Time']
    assert execute[0]['UnitAlive'] == orders[0]['UnitAlive'] == '1'
    return execute[0]['Time']


def require_death(trace, source_tag):
    deaths = [event for event in trace if event['Label'] == 'ProviderDied' and event['UnitTag'] == source_tag]
    assert len(deaths) == 1, ('Actual provider death required', source_tag)
    death = deaths[0]
    assert death['UnitAlive'] == '0'
    assert death['UnitType'] in ('Pylon', 'WarpPrism', 'WarpPrismPhasing')
    assert int(death['KillingTag']) > 0
    assert int(death['KillingPlayer']) == 3 - int(death['UnitOwner']), 'Credited enemy source, not neutral UnitKill'
    return death['Time']


def verify_power_evidence(proof, trace):
    edges = provider_edges(proof)
    assert edges and all(edge['Current'] == '0' for edge in edges)
    lost = [edge for edge in edges if edge['Lost'] == '1']
    assert lost
    last = max(float(edge['LostTime']) for edge in lost)
    delta = float(proof['End']) - last
    assert delta in (0, 0.0625), 'Source loss must match this child cancellation or its following engine tick'
    last_death = False
    for edge in edges:
        assert int(edge['Generation']) > 0 and int(edge['Tag']) > 0
        if edge['Death'] == '1':
            assert require_death(trace, edge['Tag']) == edge['DeathTime']
        if edge['Lost'] != '1' or float(edge['LostTime']) != last:
            continue
        death = edge['Death'] == '1' and edge['DeathTime'] == edge['LostTime']
        closed = edge['CloseOrder'] == edge['CloseExecute'] == '1' and edge['CloseOrderTime'] == edge['CloseExecuteTime'] == edge['LostTime']
        assert death or closed, 'Invalid/removed provider handles do not prove destruction'
        if closed:
            assert require_close(trace, edge['Tag']) == edge['LostTime']
        last_death |= death
    assert delta == 0 or last_death, 'Closure alone retains exact-time correlation'


def verify_case(bank, case, spec, *, birth=None):
    """Single real case helper: also used by focused publication break checks."""
    count, cancelled_indices, published_indices, prisms = spec
    assert bank[case]['Saved'] == '1'
    before = bank[case + '/Before']
    after = bank[case + '/Correlated']
    trace = events(bank, case)
    birth_trace = birth if birth is not None else trace
    created = [event for event in birth_trace if event['Label'] == 'Created']
    assert len(created) == count == int(before['WarpCount']), (case, 'Actual created instances required')
    tags = [before[f'Warp{i}StartedTag'] for i in range(count)]
    assert len(set(tags)) == count and all(int(tag) > 0 for tag in tags)
    for i, event in enumerate(created):
        assert event['UnitTag'] == tags[i]
        assert event['UnitOwner'] == before[f'Warp{i}StartedOwner']
        assert event['UnitType'] == before[f'Warp{i}StartedType']
        assert event['UnitConstructing'] == event['UnitAlive'] == '1'
        assert event['Detail'] == 'WarpGateTrain' and int(event['ProgressTag']) > 0
        starts = [order for order in birth_trace if order['Label'] == 'Order'
                  and order.get('Ability') == 'WarpGateTrain' and order['UnitTag'] == event['ProgressTag']
                  and order['Time'] == event['Time']]
        assert len(starts) == 1, (case, 'Actual producer WarpTrain order required')
        if case.startswith('Type'):
            assert starts[0]['Command'] == bank[case]['ExpectedCommand']
        assert before[f'Warp{i}Alive'] == before[f'Warp{i}Constructing'] == '1'
        assert int(before[f'Warp{i}Power']) >= 1
        assert any(before[f'Warp{i}From{source}'] == '1' for source in ('A', 'B', 'Pylon'))
        generation = int(bank[f'{case}/Before/Warp{i}']['Generation'])
        assert generation > 0
        proof = bank[f'{case}/Correlated/Warp{i}']
        assert int(proof['Generation']) == generation and proof['Tag'] == tags[i]
        assert proof['Sent'] == str(int(i in published_indices))
        if i in cancelled_indices:
            assert proof['Cancelled'] == proof['Decided'] == '1'
            assert after[f'Warp{i}Alive'] == '0'
        else:
            assert proof['Cancelled'] == proof['Sent'] == '0'
    cancels = [event for event in trace if event['Label'] == 'ConstructCancel']
    assert Counter(event['ProgressTag'] for event in cancels) == Counter(tags[i] for i in cancelled_indices), (case, 'Exact actual cancellation identities required')
    for event in cancels:
        index = tags.index(event['ProgressTag'])
        assert event['Detail'] == before[f'Warp{index}StartedType']
        assert event['UnitTag'] == created[index]['ProgressTag']
        assert event['UnitAlive'] == '1'
        assert event['Time'] == bank[f'{case}/Correlated/Warp{index}']['End']
    for metric in ('Units', 'Warps'):
        assert int(after[metric]) - int(before[metric]) == len(published_indices), (case, metric)
    assert int(after['Prisms']) - int(before['Prisms']) == prisms
    if case.startswith('FullQueue'):
        blocked = bank[case + '/Blocked']
        assert blocked['PendingGroups'] == after['PendingGroups'] == '128'
        def pending_target(fields):
            return sum(int(fields[f'Queue{i}Count']) for i in range(int(fields['PendingGroups']))
                       if fields[f'Queue{i}Key'] == 'Zealot' and fields[f'Queue{i}Owner'] == '1')
        assert pending_target(blocked) == 1 and pending_target(after) == 4
        drained = rows(bank[case + '/Drained'])
        assert len(drained) == 1 and drained[0]['Key'] == 'Zealot' and drained[0]['Count'] == '4'
        assert drained[0]['Kind'] == '2' and drained[0]['Owner'] == '1'
        assert drained[0]['Name'] == before['Warp0ExpectedName']
        assert icon(drained[0]['Icon']) == expected_icon('Zealot')
        assert '×4' in plain(drained[0]['Status']).replace(' ', '')
        assert 4.6 <= float(drained[0]['Remaining']) <= 5.0
    elif case.startswith('FullRows'):
        check_ui(after, before, published_indices, blocked=True)
        check_ui(bank[case + '/Drained'], before, published_indices)
    else:
        check_ui(after, before, published_indices)
    # Every positive edge needs physical closure or death evidence. The ledger
    # never replaces the actual child ConstructCancel/order/source events.
    for i in published_indices:
        proof = bank[f'{case}/Correlated/Warp{i}']
        if proof['Direct'] == '1':
            direct = [event for event in trace if event['Label'] == 'Order'
                      and event.get('Ability') == 'Warpable' and event.get('Command') == '0'
                      and event['UnitTag'] == tags[i] and event['Time'] == proof['End']]
            assert len(direct) == 1, (case, 'Explicit child Cancel required')
            continue
        verify_power_evidence(proof, trace)
    return {'case': case, 'tags': tags, 'cancelled': len(cancels),
            'published': len(published_indices), 'prisms': prisms}


def verify_single_close(bank_or_path):
    """Require one finished real SingleClose; never claim the full suite passed."""
    bank = read_bank(bank_or_path) if isinstance(bank_or_path, (str, Path)) else bank_or_path
    finished(bank)
    assert bank['Probe']['Fixture'] == 'prism-acceptance-fragment'
    assert bank['Probe']['Fragment'] == 'SingleClose'
    result = verify_case(bank, 'SingleClose', STANDARD['SingleClose'])
    before = bank['SingleClose/Before']
    assert all(before[f'Warp{i}FromA'] == '1' and before[f'Warp{i}FromB'] == before[f'Warp{i}FromPylon'] == '0' for i in range(3))
    require_close(events(bank, 'SingleClose'), before['ATag'])
    return {'result': 'PASS', 'scope': 'Focused completed real SingleClose only.', 'case': result}


def verify_direct_variant(bank, case):
    """Require the XML-loaded positive variant, never claim stock availability."""
    assert case in ('DirectOnly', 'DirectAndClose', 'DirectAndKill')
    fields = bank[case]
    assert fields['EvidenceMode'] == 'real-engine-fixture-xml-cancellable-variant'
    assert fields['FixtureCancelable'] == '1'
    assert fields['FixtureCancelReady'] == fields['FixtureCancelChildLive'] == '1'
    assert fields['FixtureCancelHidden'] == fields['FixtureCancelDisabled'] == '0'
    assert 1 <= int(fields['FixtureCancelPolls']) <= 16
    assert fields['DirectAccepted'] == '1'
    # The real child/order/cancel/count/dedup assertions remain in verify_case.
    return {'case': case, 'positive': 'real-engine fixture-only XML Cancelable=1 variant',
            'stock': 'Separate SHA-paired real ESC negative; never stock direct availability'}


def verify_stock_negative(bank, escape):
    """Physical stock child + real input; no injected cancellation signals."""
    finished(bank)
    assert bank['Probe']['Fixture'] == 'prism-direct-order-probe'
    assert bank['Probe']['StartAccepted'] == '1'
    assert bank['Finished']['FailedToStart'] == '0'
    assert bank['Finished']['ObservationElapsed'] == '1'
    ready, after = bank['ProbeReady'], bank['After']
    assert ready['Ready'] == '1'
    tag = ready['ChildTag']
    assert int(tag) > 0 and after['ChildTag'] == tag
    for fields in (ready, after):
        assert fields['ChildAlive'] == fields['ChildConstructing'] == fields['ChildSelected1'] == '1'
        assert fields['ChildType'] == 'Zealot'
        assert fields['FromPrism'] == '1' and int(fields['Power']) >= 1
        assert fields['QueueUsed'] == '0' and fields['ProducerQueueCancelHidden'] == '1'
        assert all(fields[key] == '0' for key in ('Units', 'Warps', 'Prisms', 'CancelEvents', 'CompleteEvents'))
    assert float(after['Time']) - float(ready['Time']) >= 20
    abilities = [fields for name, fields in bank.items() if name.startswith('CatalogAbility')
                 and fields.get('Ability') == 'Warpable']
    assert len(abilities) == 1
    ability = abilities[0]
    assert ability['Cancelable'] == '0' and ability['CancelHidden'] == '1'
    assert ability['Class'] == '36' and ability['Exists'] == ability['Enabled'] == '1'
    assert ability['CancelCommand'] == bank['Abilities']['WarpableCancelConstant'] == '0'
    trace = [bank[f'Event{i}'] for i in range(1, int(bank['Finished']['Events']) + 1)]
    created = [event for event in trace if event['Label'] == 'Created' and event.get('ChildTag') == tag]
    assert len(created) == 1
    child = created[0]
    assert child['Detail'] == 'WarpGateTrain' and child['ChildAlive'] == child['ChildConstructing'] == '1'
    assert child['SourceTag'] == ready['GateTag']
    assert len([event for event in trace if event['Label'] == 'Order'
                and event.get('Ability') == 'WarpGateTrain' and event['SourceTag'] == child['SourceTag']
                and event['Time'] == child['Time'] and event['Command'] == '0']) == 1
    assert not any(event['Label'] in ('ConstructCancel', 'ConstructComplete') or
                   (event['Label'] == 'Order' and float(event['Time']) >= float(ready['Time']))
                   for event in trace)
    assert escape['key'] == 'Escape' and escape['selected_tag'] == tag
    assert escape['ready_game_time'] == ready['Time']
    assert int(escape['pid']) > 0 and float(escape['epoch']) > 0
    assert escape['input'] == 'Exact workspace5/PID scoped XTest'
    return {'tag': tag, 'observation_game_seconds': float(after['Time']) - float(ready['Time']),
            'classification': 'Stock Cancelable=0 unavailable; real ESC produced no Order/Cancel'}


def verify_variant_provenance(candidate, stock):
    """The only accepted data difference is the explicit private XML variant."""
    assert candidate['Recorded'] == stock['Recorded'] == '1'
    assert candidate['fixture'] == 'prism-acceptance' and stock['fixture'] == 'prism-direct-order-probe'
    assert candidate['canonical_galaxy_sha256'] == stock['canonical_galaxy_sha256']
    assert json.loads(candidate['canonical_file_sha256']) == json.loads(stock['canonical_file_sha256'])
    modules = json.loads(candidate['module_sha256'])
    assert modules == json.loads(stock['module_sha256'])
    manifest = json.loads((ROOT / 'tools/galaxy_sources.json').read_text())
    assert set(modules) == set(manifest) and len(modules) == 7
    assert all(modules[name] == hashlib.sha256((ROOT / 'source' / name).read_bytes()).hexdigest() for name in manifest)
    assert json.loads(candidate['dependencies']) == json.loads(stock['dependencies'])
    assert json.loads(stock.get('fixture_data_sha256', '{}')) == {}
    assert json.loads(candidate['fixture_data_sha256']) == {
        PRIVATE_DATA: hashlib.sha256((ROOT / PRIVATE_DATA).read_bytes()).hexdigest()}


def verify_stock_hash_binding(capture_path, input_path, capture_sha256, input_sha256):
    assert all(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value)
               for value in (capture_sha256, input_sha256)), 'Explicit immutable stock manifest/input SHA required'
    assert hashlib.sha256((capture_path / 'original-capture.json').read_bytes()).hexdigest() == capture_sha256
    assert hashlib.sha256(input_path.read_bytes()).hexdigest() == input_sha256


def verify_stock_pair(capture_path, input_path, receipt_path, main_path, *, capture_sha256=None, input_sha256=None):
    """Consume immutable original stock banks, map/MPQ hashes and actual ESC log."""
    assert capture_path is not None and input_path is not None and receipt_path is not None, 'Full acceptance requires the separate stock ESC capture and candidate runtime receipt'
    capture_path, input_path, receipt_path = map(Path, (capture_path, input_path, receipt_path))
    verify_stock_hash_binding(capture_path, input_path, capture_sha256, input_sha256)
    capture = json.loads((capture_path / 'original-capture.json').read_text())
    revision = capture['revision']
    assert re.fullmatch(r'[A-Za-z0-9]+', revision), 'Invalid immutable stock revision'
    bank_name, receipt_name = 'OPPBuildingCancel' + revision + '.SC2Bank', 'OPPRuntime' + revision + '.SC2Bank'
    report_name, archive_name = 'popup-' + revision + '.json', 'OPP_Dev_Popup_' + revision + '.SC2Mod.mpq'
    required = {bank_name, receipt_name, report_name, archive_name,
                'EditorTest.SC2Map/MapScript.galaxy', 'EditorTest.SC2Map/Triggers',
                'EditorTest.SC2Map/ComponentList.SC2Components', 'EditorTest.SC2TestConfig'}
    assert required <= set(capture['files'])
    for name, digest in capture['files'].items():
        assert hashlib.sha256((capture_path / name).read_bytes()).hexdigest() == digest, ('Stock original artifact changed', name)
    stock = read_bank(capture_path / receipt_name)['Provenance']
    candidate = read_bank(receipt_path)['Provenance']
    report = json.loads((capture_path / report_name).read_text())
    assert report['byte_verified'] is True
    assert stock['revision'] == report['revision'] == revision
    assert stock['bank_name'] == Path(receipt_name).stem
    assert all(stock[key] == value for key, value in report['runtime_provenance'].items())
    assert stock['mod_archive_sha256'] == report['archive_sha256'] == capture['installed_mpq_sha256'] == capture['files'][archive_name]
    assert stock['canonical_galaxy_sha256'] == report['canonical_galaxy_sha256']
    assert json.loads(stock['module_sha256']) == report['module_sha256'] == capture['production_sources']
    assert receipt_path.stem == candidate['bank_name']
    assert main_path.stem == 'OPPBuildingCancel' + candidate['revision']
    verify_variant_provenance(candidate, stock)
    result = verify_stock_negative(read_bank(capture_path / bank_name), json.loads(input_path.read_text()))
    result.update(canonical_galaxy_sha256=candidate['canonical_galaxy_sha256'],
                  stock_mod_archive_sha256=stock['mod_archive_sha256'],
                  candidate_mod_archive_sha256=candidate['mod_archive_sha256'],
                  sha256={str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (
                      capture_path / 'original-capture.json', capture_path / bank_name,
                      capture_path / receipt_name, input_path, receipt_path)})
    return result


def natural_zealot_duration(bank):
    trace = events(bank, 'NaturalComplete')
    born = [event for event in trace if event['Label'] == 'Created' and event['UnitType'] == 'Zealot']
    assert len(born) == 1
    complete = [event for event in trace if event['Label'] == 'ConstructComplete' and event['ProgressTag'] == born[0]['UnitTag']]
    assert len(complete) == 1 and complete[0]['UnitTag'] == born[0]['ProgressTag']
    assert complete[0]['Detail'] == 'Zealot'
    duration = float(complete[0]['Time']) - float(born[0]['Time'])
    assert duration > 0
    return duration


def verify_moment(bank, case, natural=None):
    """Use actual Created/close/ConstructComplete times; progress getter is 100."""
    assert case in ('Moment0', 'Moment1')
    before = bank[case + '/Before']
    assert before['WarpCount'] == before['Warp0Alive'] == before['Warp0Constructing'] == '1'
    trace = events(bank, case)
    born = [event for event in trace if event['Label'] == 'Created']
    assert len(born) == 1 and born[0]['UnitTag'] == before['Warp0StartedTag']
    assert born[0]['UnitType'] == 'Zealot' and born[0]['Time'] == bank[case]['CreatedTime']
    elapsed = float(require_close(trace, before['ATag'])) - float(born[0]['Time'])
    if case == 'Moment0':
        assert 0 <= elapsed <= 0.125, 'Early close must follow physical Created within two game ticks'
    else:
        assert natural is not None, 'Late close requires the actual natural completion reference'
        duration = natural_zealot_duration(natural)
        assert duration == float(bank[case]['NaturalDuration'])
        assert duration * 0.8 <= elapsed <= duration * 0.8 + 0.125, 'Late close did not reach measured 80% natural duration'


def verify_standard_case(bank, case, spec, natural, *, allow_late_manual=False):
    """Only the explicitly authorized late case can remain an honest manual gap."""
    try:
        result = verify_case(bank, case, spec)
        if case in ('Moment0', 'Moment1'):
            verify_moment(bank, case, natural)
        return result
    except (AssertionError, KeyError) as error:
        if not allow_late_manual or case != 'Moment1':
            raise
        return {'case': case, 'result': 'FAIL', 'manual': 'PENDING',
                'reason': str(error) or 'Late cancellation engine evidence failed'}


def visibility(bank):
    samples = 0
    for fields in bank.values():
        if 'UIReady' not in fields:
            continue
        assert fields['UIReady'] == fields['Init'] == '1'
        for row in range(3):
            for player in (1, 2):
                assert fields[f'Row{row}Player{player}'] == '0'
                samples += 1
    return samples


def verify(main_path, fragment_paths, *, stock_capture=None, stock_input=None, runtime_receipt=None,
           stock_capture_sha256=None, stock_input_sha256=None, allow_late_manual=False):
    main = read_bank(main_path)
    assert main['Probe']['Fixture'] == 'prism-acceptance'
    assert main['Finished']['Done'] == '1', 'Main fixture never finished'
    names = [main['Fragments'][f'Bank{i}'] for i in range(int(main['Finished']['Fragments']))]
    assert len(names) == len(set(names)) == len(fragment_paths)
    assert {path.stem for path in fragment_paths} == set(names), 'Require every exact revision fragment'
    assert main['Probe']['DataVariant'] == 'fixture-xml-cancelable-1' and main['Probe']['LoadedCancelable'] == '1'
    stock_negative = verify_stock_pair(stock_capture, stock_input, runtime_receipt, main_path,
                                      capture_sha256=stock_capture_sha256, input_sha256=stock_input_sha256)
    fragments = {}
    death_lifecycle = {}
    samples = visibility(main)
    for path in fragment_paths:
        bank = read_bank(path)
        finished(bank)
        assert bank['Probe']['Fixture'] == 'prism-acceptance-fragment'
        label = bank['Probe']['Fragment']
        assert label not in fragments and path.stem in names
        # This remains strict even when the user explicitly defers Moment1.
        death_lifecycle[label] = verify_death_lifecycle(bank)
        fragments[label] = bank
        samples += visibility(bank)
    type_cases = {key: value for key, value in main['Types'].items() if key.startswith('Type')}
    assert set(type_cases.values()) == TYPES and len(type_cases) == len(TYPES), 'All effective WarpGateTrain targets required'
    inventory = [main[f'Inventory{i}'] for i in range(int(main['Inventory']['Abilities']))]
    linked = [entry for entry in inventory if int(entry['Sources']) > 0]
    assert [entry['Ability'] for entry in linked] == ['WarpGateTrain'], 'Structural scope mismatch: an additional source-linked WarpTrain needs real acceptance cases'
    expected_commands = {f'Type{i}': linked[0][f'Target{i}'] for i in range(int(linked[0]['Commands'])) if linked[0][f'Target{i}']}
    assert type_cases == expected_commands, 'Runtime WarpTrain inventory and actual command cases differ'
    required = set(STANDARD) | set(type_cases) | {'RetentionStart', 'RetentionHeld'} | {f'Retention{i}' for i in range(17)}
    assert set(fragments) == required
    verify_single_close(fragments['SingleClose'])
    natural = fragments['NaturalComplete']
    results = [verify_standard_case(fragments[case], case, spec, natural, allow_late_manual=allow_late_manual)
               for case, spec in STANDARD.items()]
    for case, target in type_cases.items():
        bank = fragments[case]
        assert bank[case]['ExpectedType'] == target
        assert int(bank[case]['ExpectedCommand']) == int(case[4:])
        assert bank[case + '/Before']['Warp0StartedType'] == target
        results.append(verify_case(bank, case, (1, (0,), (0,), 1)))

    for case in ('OverlapKeep', 'OverlapKilledKeep', 'MixedCloseThenKill', 'MixedKillThenClose', 'BothClose', 'BothKilledAB', 'BothKilledBA'):
        fields = fragments[case][case + '/Before']
        assert all(fields[f'Warp{i}FromA'] == fields[f'Warp{i}FromB'] == '1' for i in range(3))
    for case in ('MixedCloseThenKill', 'MixedKillThenClose'):
        bank = fragments[case]
        trace = events(bank, case)
        fields = bank[case + '/Before']
        close_time = require_close(trace, fields['ATag'])
        death = [event for event in trace if event['Label'] == 'ProviderDied' and event['UnitTag'] == fields['BTag']]
        assert len(death) == 1 and death[0]['Time'] == close_time
        for i in range(3):
            edges = provider_edges(bank[f'{case}/Correlated/Warp{i}'])
            assert len([edge for edge in edges if edge['Death'] == '1' and edge['DeathTime'] == edge['LostTime'] == close_time]) == 1
    bank = fragments['CloseThenLaterDeath']
    trace = events(bank, 'CloseThenLaterDeath')
    before = bank['CloseThenLaterDeath/Before']
    close_time = float(require_close(trace, before['ATag']))
    deaths = [event for event in trace if event['Label'] == 'ProviderDied' and event['UnitTag'] == before['ATag']]
    assert len(deaths) == 1 and float(deaths[0]['Time']) == close_time + 0.0625
    assert float(deaths[0]['Time']) < float(bank['CloseThenLaterDeath/Correlated']['Time'])
    separate = fragments['SeparateCloseAndKill']['SeparateCloseAndKill/Before']
    assert [(separate[f'Warp{i}FromA'], separate[f'Warp{i}FromB']) for i in range(4)] == [('1', '0'), ('1', '0'), ('0', '1'), ('0', '1')]
    assert {fragments['TwoOwners']['TwoOwners/Before'][f'Warp{i}StartedOwner'] for i in range(4)} == {'1', '2'}
    assert {fragments['TwoOwnersKilled']['TwoOwnersKilled/Before'][f'Warp{i}StartedOwner'] for i in range(4)} == {'1', '2'}
    death_cases = {
        'KilledOnly': ('A',), 'SeparateCloseAndKill': ('B',),
        'MixedCloseThenKill': ('B',), 'MixedKillThenClose': ('B',),
        'PylonKilled': ('Pylon',), 'OverlapKilledKeep': ('A',),
        'BothKilledAB': ('A', 'B'), 'BothKilledBA': ('B', 'A'),
        'SeparateBothKilled': ('A', 'B'), 'TwoOwnersKilled': ('A', 'B'),
        'DirectAndKill': ('A',), 'PylonKilledKeep': ('Pylon',),
        'FullRowsKilled': ('A',), 'FullQueueKilled': ('A',)}
    for case, sources in death_cases.items():
        bank = fragments[case]
        before = bank[case + '/Before']
        trace = events(bank, case)
        expected = [before[source + 'Tag'] for source in sources]
        deaths = [event for event in trace if event['Label'] == 'ProviderDied']
        assert [event['UnitTag'] for event in deaths] == expected, (case, 'Exact death identities and operation order')
        assert all(require_death(trace, tag) for tag in expected)
    pylon = fragments['PylonKilled']['PylonKilled/Before']
    assert all(pylon[f'Warp{i}FromPylon'] == '1' and pylon[f'Warp{i}FromA'] == pylon[f'Warp{i}FromB'] == '0' for i in range(3))
    for case in ('SeparateBothKilled', 'TwoOwnersKilled'):
        fields = fragments[case][case + '/Before']
        assert [(fields[f'Warp{i}FromA'], fields[f'Warp{i}FromB']) for i in range(4)] == [('1', '0'), ('1', '0'), ('0', '1'), ('0', '1')]

    for case, source in (('LatePrismClose', 'B'), ('LatePylonKeep', 'Pylon'), ('NaturalPhasing', 'B'), ('NaturalPylon', 'Pylon')):
        bank = fragments[case]
        before, new = bank[case + '/Before'], bank[case + '/NewSource']
        assert all(before[f'Warp{i}From{source}'] == '0' and new[f'Warp{i}From{source}'] == '1'
                   and new[f'Warp{i}Alive'] == new[f'Warp{i}Constructing'] == '1' for i in range(3)), (case, 'New source must supply a still-running real warp')
        assert float(new['Time']) > float(before['Time'])
        trace = events(bank, case)
        source_tag = new[source + 'Tag']
        if case == 'NaturalPhasing':
            phases = [event for event in trace if event['Label'] == 'Ability' and event.get('Ability') == 'PhasingMode' and event['UnitTag'] == source_tag]
            assert any(event['Stage'] == '-3' for event in phases) and any(event['Stage'] == '-6' for event in phases)
        elif case == 'NaturalPylon':
            assert bank[case]['BuildAccepted'] == '1' and before['PylonConstructing'] == '1' and new['PylonConstructing'] == '0'
            complete = [event for event in trace if event['Label'] == 'ProviderComplete' and event['ProgressTag'] == source_tag]
            assert len(complete) == 1 and float(complete[0]['Time']) > float(before['Time'])
        else:
            created = [event for event in trace if event['Label'] == 'ProviderCreated' and event['UnitTag'] == source_tag]
            assert len(created) == 1 and float(created[0]['Time']) >= float(before['Time'])
    for case in ('NaturalComplete', 'OverlapKeep', 'OverlapKilledKeep', 'PylonKilledKeep', 'PylonKeep', 'LatePylonKeep', 'NaturalPhasing', 'NaturalPylon'):
        bank = fragments[case]
        fields = bank[case + '/Settled']
        assert all(fields[f'Warp{i}Alive'] == '1' and fields[f'Warp{i}Constructing'] == '0' for i in range(3)), (case, 'Natural successful completion required')
        completed = [event['ProgressTag'] for event in events(bank, case) if event['Label'] == 'ConstructComplete']
        assert Counter(completed) == Counter(fields[f'Warp{i}StartedTag'] for i in range(3)), (case, 'Actual successful Construct Complete identities required')
    direct_variants = [verify_direct_variant(fragments[case], case)
                       for case in ('DirectOnly', 'DirectAndClose', 'DirectAndKill')]

    start = fragments['RetentionStart']
    birth = events(start, 'RetentionStart')
    created_held = [event for event in birth if event['Label'] == 'Created']
    assert len(created_held) == 1 and created_held[0]['UnitTag'] == main['Retention']['HeldTag']
    held_state = start['RetentionStart/Held']
    assert held_state['Warp0Alive'] == held_state['Warp0Constructing'] == '1'
    held_generation = start['RetentionStart/Held/Warp0']['Generation']
    cycle_tags = set()
    for chunk in range(17):
        bank = fragments[f'Retention{chunk}']
        lo, hi = chunk * 8, min((chunk + 1) * 8, 129)
        assert int(bank['Finished']['StartCycle']) == lo and int(bank['Finished']['EndCycleExclusive']) == hi
        assert {event['Case'] for event in bank.values() if 'Label' in event} == {f'Cycle{i}' for i in range(lo, hi)}
        for cycle in range(lo, hi):
            result = verify_case(bank, f'Cycle{cycle}', (1, (0,), (0,), 1))
            assert result['tags'][0] not in cycle_tags
            cycle_tags.add(result['tags'][0])
            results.append(result)
    held_bank = fragments['RetentionHeld']
    assert held_bank['RetentionHeld/Before/Warp0']['Generation'] == held_generation
    assert held_bank['RetentionHeld/Before']['Warp0StartedTag'] == main['Retention']['HeldTag']
    results.append(verify_case(held_bank, 'RetentionHeld', (1, (0,), (0,), 1), birth=birth))
    assert int(main['Finished']['Records']) == 0 and int(main['Finished']['PeakRecords']) >= 2
    pending = [result for result in results if result.get('manual') == 'PENDING']
    return {'result': 'MANUAL_PENDING' if pending else 'PASS',
            'scope': 'Local real engine/UI Prism/Pylon power-loss acceptance on explicit XML Cancelable=1 variant, with separate stock ESC negative; any late FAIL is explicit, replay and multi-client evidence separate.',
            'cases': results, 'retention_cycles': len(cycle_tags), 'types': sorted(TYPES),
            'direct_cancel_class_probes': direct_variants,
            'stock_manual_cancel_negative': stock_negative,
            'manual_pending': pending,
            'independent_death_lifecycle': death_lifecycle,
            'active_player_visibility_samples_false': samples,
            'sha256': {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (main_path, *fragment_paths)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bank', type=Path)
    parser.add_argument('--fragment-bank', action='append', type=Path, default=[])
    parser.add_argument('--single-close-only', action='store_true')
    parser.add_argument('--stock-capture', type=Path, help='Immutable stock probe directory matching this production candidate')
    parser.add_argument('--stock-input', type=Path, help='Actual workspace/PID-scoped ESC input JSON')
    parser.add_argument('--runtime-receipt', type=Path, help='Receipt from this XML-variant full run')
    parser.add_argument('--stock-capture-sha256', help='Trusted SHA256 of original stock capture manifest')
    parser.add_argument('--stock-input-sha256', help='Trusted SHA256 of actual stock ESC input log')
    parser.add_argument('--allow-late-manual', action='store_true', help='User-authorized Moment1 FAIL remains MANUAL_PENDING; all other cases stay strict')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify_single_close(args.bank) if args.single_close_only else verify(
        args.bank, args.fragment_bank, stock_capture=args.stock_capture,
        stock_input=args.stock_input, runtime_receipt=args.runtime_receipt,
        stock_capture_sha256=args.stock_capture_sha256, stock_input_sha256=args.stock_input_sha256,
        allow_late_manual=args.allow_late_manual)
    output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(output)
    print(output, end='')


if __name__ == '__main__':
    main()
