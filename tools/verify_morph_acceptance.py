#!/usr/bin/env python3
"""Accept real morph cancellations and actual UI; keep baseline validators historical."""
import argparse
from collections import Counter
import hashlib
from functools import lru_cache
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / 'tests/functional/scenarios/morph-acceptance-matrix.json'
ICONS_PATH = ROOT / 'tests/functional/scenarios/morph-acceptance-icons.json'
REPEAT_LINKS = (50, 52, 55, 58, 59, 60, 62, 65, 67, 10, 11, 46, 47, 86)


@lru_cache(maxsize=1)
def icon_oracles():
    result = {}
    for icon in json.loads(ICONS_PATH.read_text())['icons']:
        identity = (icon['ability'], icon['target'])
        if identity in result:
            for key in ('catalog', 'entry', 'field', 'expected_asset'):
                assert result[identity][key] == icon[key], (identity, key)
        result[identity] = icon
    return result


def asset_key(value):
    return value.replace('\\', '/').casefold()


def read_bank(path):
    """Reading a saved prefix is allowed only for the explicitly focused check."""
    return {section.get('name'): {key.get('name'): next(iter(key.find('Value').attrib.values()))
                                 for key in section.findall('Key')}
            for section in ET.parse(path).getroot().findall('Section')}


def events(bank, case=None):
    keys = sorted((key for key in bank if key.startswith('Event') and key[5:].isdigit()),
                  key=lambda key: int(key[5:]))
    result = [bank[key] for key in keys]
    return [event for event in result if case is None or event.get('Case') == case]


def finished(bank):
    assert bank['Finished']['Done'] == '1', 'Full acceptance requires a closed fixture'
    count = int(bank['Finished']['Events'])
    names = {key for key in bank if key.startswith('Event') and key[5:].isdigit()}
    assert names == {f'Event{i}' for i in range(1, count + 1)}, 'Truncated/noncontiguous engine trace'


def rows(snapshot):
    return [{name: snapshot[f'Row{i}{field}']
             for name, field in [('key', 'Key'), ('owner', 'Owner'), ('kind', 'Kind'),
                                 ('name', 'Name'), ('icon', 'Icon'), ('count', 'Count'),
                                 ('status', 'Status'), ('remaining', 'Remaining')]}
            for i in range(3) if snapshot[f'Row{i}Visible'] == '1']


def check_ui(snapshot, fields, count=1, exact=True):
    visible = rows(snapshot)
    matches = [row for row in visible if row['key'] == fields['Target']
               and row['owner'] == fields['Owner'] and row['kind'] == fields['Kind']]
    assert len(matches) == 1, (fields['Target'], visible)
    if exact:
        assert len(visible) == 1, visible
    row = matches[0]
    assert row['name'] == fields['ExpectedName'] and row['name'], row
    assert row['icon'] == fields['ExpectedIcon'] and row['icon'], row
    assert int(row['count']) == count, row
    assert row['status'] == 'Cancelled' + (f' ×{count}' if count > 1 else ''), row
    assert 4.5 <= float(row['remaining']) <= 5.0, row
    return row


def require_pair(bank, case, expected_cancels=1, earliest=False, autocast_restart=False):
    fields = bank[case]
    trace = events(bank, case)
    tag, ability = fields['Tag'], fields['Ability']
    assert int(tag) > 0
    assert all(event['Tag'] == tag and event['Ability'] == ability for event in trace), case
    assert all(event['Owner'] == fields['Owner'] for event in trace), case
    executes = [event for event in trace if event['Label'] == 'Ability'
                and event['Command'] == '0' and event['Stage'] == '-3']
    cancels = [event for event in trace if event['Label'] == 'Ability'
               and event['Command'] == '0' and event['Stage'] == '-4']
    completes = [event for event in trace if event['Label'] == 'Ability'
                 and event['Command'] == '0' and event['Stage'] == '-6']
    orders = [event for event in trace if event['Label'] == 'Order' and event['Command'] == '1']
    assert executes and len(executes) == int(fields['ExecuteEvents']), (case, 'Real Execute required')
    assert len(cancels) == int(fields['CancelEvents']) == expected_cancels, (case, cancels)
    assert len(completes) == int(fields['CompleteEvents']), case
    assert len(orders) == int(fields['CancelOrders']) == expected_cancels, (case, orders)
    assert not completes, (case, 'Cancellation must not be replaced with completion')
    assert Counter(event['Time'] for event in cancels) == Counter(event['Time'] for event in orders), case
    assert all(event['Alive'] == '1' for event in cancels + orders), case
    assert float(executes[0]['Time']) <= float(cancels[0]['Time']), case
    if autocast_restart:
        # Native autocast dispatch defers this immediate callback-issued order
        # by exactly one simulation tick. The ending pair still precedes the
        # restarted Execute on the same tag, even at the same mission time.
        assert earliest and case == 'AutocastRestart'
        assert (fields['Source'], ability, fields['Target']) == ('Gateway', 'MorphBuildingGatewayWarpGateFree', 'WarpGate')
        assert len(executes) == 2 and len(trace) == 4 and expected_cancels == 1, case
        assert fields['EarliestExecuteCancel'] == '1'
        assert fields['ExecuteCancelTime'] == executes[0]['Time'], (case, 'Cancel must be issued inside the first Execute callback')
        assert cancels[0]['Time'] == orders[0]['Time'] == executes[1]['Time'], case
        assert float(cancels[0]['Time']) - float(executes[0]['Time']) == 0.0625, (case, 'Expected exactly one native autocast dispatch tick')
        assert all(event['Alive'] == '1' for event in trace), case
        assert trace.index(executes[0]) < min(trace.index(orders[0]), trace.index(cancels[0])), case
        assert max(trace.index(orders[0]), trace.index(cancels[0])) < trace.index(executes[1]), (case, 'Ending pair must belong to the first Execute generation')
    elif earliest:
        assert fields['EarliestExecuteCancel'] == '1', (case, 'Earliest Execute callback was not tested')
        assert fields['ExecuteCancelTime'] == executes[0]['Time'] == cancels[0]['Time'], case
    return {'case': case, 'tag': tag, 'ability': ability, 'time': cancels[0]['Time'],
            'execute_time': executes[0]['Time']}


def require_completion(bank, case, instant=False):
    """A zero cancel counter alone cannot prove a completed negative control."""
    fields = bank[case]
    trace = events(bank, case)
    assert all(event['Tag'] == fields['Tag'] and event['Ability'] == fields['Ability']
               and event['Owner'] == fields['Owner'] for event in trace), case
    executes = [event for event in trace if event['Label'] == 'Ability'
                and event['Command'] == '0' and event['Stage'] == '-3']
    completes = [event for event in trace if event['Label'] == 'Ability'
                 and event['Command'] == '0' and event['Stage'] == '-6']
    cancels = [event for event in trace if event['Label'] == 'Ability'
               and event['Command'] == '0' and event['Stage'] == '-4']
    assert len(executes) == int(fields['ExecuteEvents']) >= 1, (case, 'Real Execute required')
    assert len(completes) == int(fields['CompleteEvents']) == len(executes), (case, 'Real completion required')
    assert not cancels and fields['CancelEvents'] == '0', case
    for execute, complete in zip(executes, completes):
        assert float(execute['Time']) <= float(complete['Time']), case
        if instant:
            assert execute['Time'] == complete['Time'], (case, 'Instant completion needs the same mission time')


def verify_case(bank, case, source, ability, target, positive, *, earliest=False,
                snapshot=True, counter_before=None, exact_ui=True, counter_expected=None,
                autocast_restart=False):
    """Shared by the focused break check and every real full-suite attempt."""
    fields = bank[case]
    assert fields['Saved'] == '1' and fields['Evidence'] == 'real-engine-attempt', case
    assert (fields['Source'], fields['Ability'], fields['Target']) == (source, ability, target), case
    assert fields['ResolvedTarget'] == target, (case, fields['ResolvedTarget'], target)
    assert fields['Created'] == '1' and int(fields['Tag']) > 0, case
    assert fields['ResolverErrors'] == '0', (case, 'Unresolved catalogue target/icon')
    expected = int(positive) if counter_expected is None else counter_expected
    before = {name: int(fields['Before' + name]) for name in ('Morphs', 'Buildings', 'Units')}
    if counter_before is not None:
        before = {name: int(counter_before[name]) for name in before}
    delta = {name: int(fields['After' + name]) - before[name] for name in before}
    assert delta['Morphs'] == expected, (case, delta)
    assert delta['Buildings'] == (expected if fields['Kind'] == '0' else 0), (case, delta)
    assert delta['Units'] == (expected if fields['Kind'] == '2' else 0), (case, delta)
    pair = None
    if positive:
        assert fields['StartAccepted'] == fields['CancelAccepted'] == fields['AliveAfter'] == '1', case
        assert fields['ExpectedIcon'] and fields['ExpectedName'], case
        oracle = icon_oracles()[(ability, target)]
        reference = oracle['catalog'] + ':' + oracle['entry'] + '.' + oracle['field']
        assert fields['IconOracle'] == reference, (case, 'Independent icon oracle differs')
        assert fields['ExpectedAsset'] == oracle['expected_asset']
        assert asset_key(fields['ExpectedIcon']) == asset_key(oracle['expected_asset']), (case, fields['ExpectedIcon'], oracle)
        pair = require_pair(bank, case, earliest=earliest, autocast_restart=autocast_restart)
        if snapshot:
            check_ui(bank[case + '/After'], fields, exact=exact_ui)
    elif snapshot:
        assert not rows(bank[case + '/After']), (case, rows(bank[case + '/After']))
    return pair


def verify_first_lair(bank_or_path):
    """One actually saved case is enough for a red/green break check, never full PASS."""
    bank = read_bank(bank_or_path) if isinstance(bank_or_path, (str, Path)) else bank_or_path
    assert bank['Probe']['Fixture'] == 'morph-acceptance'
    assert bank['Probe']['IconsSHA256'] == hashlib.sha256(ICONS_PATH.read_bytes()).hexdigest()
    pair = verify_case(bank, 'FirstLair', 'Hatchery', 'UpgradeToLair', 'Lair', True, earliest=True)
    return {'result': 'PASS', 'scope': 'Focused completed FirstLair engine/UI case only; no full fixture claim.', 'pair': pair}


def visibility(bank):
    samples = 0
    for fields in bank.values():
        if 'UIReady' not in fields:
            continue
        assert fields['UIReady'] == fields['Init'] == '1'
        assert fields['ResolverErrors'] == '0'
        for row in range(3):
            for player in (1, 2):
                assert fields[f'Row{row}Player{player}'] == '0'
                samples += 1
    return samples


def matrix_chunks(bank, paths, matrix_hash, icons_hash):
    assert len(paths) == 16, 'Every closed matrix fragment is mandatory'
    chunks = {}
    samples = 0
    for path in paths:
        fragment = read_bank(path)
        finished(fragment)
        index = int(fragment['Probe']['Chunk'])
        assert index in range(16) and index not in chunks
        assert fragment['Probe']['Fixture'] == 'morph-matrix-chunk'
        assert fragment['Probe']['MatrixSHA256'] == matrix_hash
        assert fragment['Probe']['IconsSHA256'] == icons_hash
        assert path.stem == bank['Matrix'][f'Chunk{index}'], (path, 'Wrong revision fragment')
        start, end = index * 20, min((index + 1) * 20, 301)
        assert int(fragment['Finished']['StartLink']) == start
        assert int(fragment['Finished']['EndLinkExclusive']) == end
        actual_links = {key for key in fragment if key.startswith('Link') and key[4:].isdigit()}
        assert actual_links == {f'Link{i}' for i in range(start, end)}
        samples += visibility(fragment)
        chunks[index] = fragment
    return chunks, samples


def retention_chunks(bank, paths):
    assert len(paths) == 4, 'All four closed retention fragments are mandatory'
    chunks = {}
    for path in paths:
        fragment = read_bank(path)
        finished(fragment)
        index = int(fragment['Probe']['Chunk'])
        assert index in range(4) and index not in chunks
        assert fragment['Probe']['Fixture'] == 'morph-retention'
        assert path.stem == bank['RetentionHeld'][f'Chunk{index}']
        start, end = index * 40, min((index + 1) * 40, 129)
        assert int(fragment['Finished']['StartCycle']) == start
        assert int(fragment['Finished']['EndCycleExclusive']) == end
        assert {event['Case'] for event in events(fragment)} == {f'Cycle{i}' for i in range(start, end)}
        chunks[index] = fragment
    return chunks


def require_scenery_isolation(bank, chunks):
    """Real collapse processes must leave both original power fixtures alive."""
    snapshots = [bank['SceneryIsolation/' + label] for label in ('Before', 'After', 'AfterMatrix')]
    times = [float(snapshot['Time']) for snapshot in snapshots]
    assert times == sorted(times), 'Scenery power observations are out of order'
    pylons = []
    for owner in (1, 2):
        prefix = f'Pylon{owner}'
        first = snapshots[0]
        tag = first[prefix + 'Tag']
        assert int(tag) > 0
        position = (float(first[prefix + 'X']), float(first[prefix + 'Y']))
        for snapshot in snapshots:
            assert snapshot[prefix + 'Alive'] == '1', (prefix, 'Power fixture died')
            assert snapshot[prefix + 'Type'] == 'Pylon' and snapshot[prefix + 'Owner'] == str(owner)
            assert snapshot[prefix + 'Tag'] == tag, (prefix, 'Power fixture was replaced')
            assert (float(snapshot[prefix + 'X']), float(snapshot[prefix + 'Y'])) == position
        pylons.append({'tag': tag, 'position': position})
    assert len({pylon['tag'] for pylon in pylons}) == 2
    for link in range(167, 181):
        fields = chunks[link // 20][f'Link{link}']
        position = (float(fields['CreatedX']), float(fields['CreatedY']))
        assert times[0] <= float(fields['SavedTime']) <= times[1], link
        for pylon in pylons:
            dx, dy = (coordinate - reference for coordinate, reference in zip(position, pylon['position']))
            assert dx * dx + dy * dy >= 20 * 20, (link, 'Collapse fixture overlaps a power fixture', position)
    return {'source_links': list(range(167, 181)), 'power_tags': [pylon['tag'] for pylon in pylons],
            'both_original_power_fixtures_alive_after_matrix': True}


def require_retained_process(bank, cycles):
    """Native current orders plus an unbroken independent held-tag trace."""
    fields = bank['RetentionHeld']
    assert fields['Evidence'] == 'real-engine-attempt' and fields['Created'] == '1'
    assert fields['Cycles'] == '129' and len(cycles) == 129
    assert fields['Lengthened'] == fields['LengthenedActor'] == fields['LengthenedStats'] == fields['StillAlive'] == '1'
    start, before, after = (bank['RetentionHeld/' + label]
                            for label in ('StartState', 'BeforeCancelState', 'AfterCancelState'))
    for state in (start, before, after):
        assert state['Exists'] == state['Alive'] == '1', 'Held native subject must stay live'
        assert (state['Tag'], state['Owner'], state['Type']) == (fields['Tag'], fields['Owner'], fields['Source'])
    for state in (start, before):
        assert state['HasMorphOrder'] == '1' and int(state['OrderCount']) >= 1
        assert state['Order0Ability'] == fields['Ability'] and state['Order0Command'] == '0', 'Actual current morph Execute order required'
    assert after['HasMorphOrder'] == '0' and after['OrderCount'] == '0'
    assert after['Order0Ability'] == '' and after['Order0Command'] == '-1'
    header = bank['HeldTrace']
    assert header['Closed'] == '1'
    count = int(header['Events'])
    names = {key for key in bank if key.startswith('HeldEvent') and key[9:].isdigit()}
    assert names == {f'HeldEvent{i}' for i in range(1, count + 1)}, 'Truncated independent held-tag trace'
    trace = [bank[f'HeldEvent{i}'] for i in range(1, count + 1)]
    assert len(trace) == 3, 'Held process must have one Execute, one order and one Cancel, with no intervening end/restart'
    identity = ('RetentionHeld', fields['Tag'], fields['Ability'], fields['Owner'])
    assert all((event['Case'], event['Tag'], event['Ability'], event['Owner']) == identity
               and event['Alive'] == '1' for event in trace)
    assert (trace[0]['Label'], trace[0]['Stage'], trace[0]['Command']) == ('Ability', '-3', '0')
    assert {(event['Label'], event['Stage'], event['Command']) for event in trace[1:]} == {('Order', '0', '1'), ('Ability', '-4', '0')}
    assert trace[1]['Time'] == trace[2]['Time']
    keys = ('Case', 'Tag', 'Ability', 'Owner', 'Alive', 'Label', 'Stage', 'Command', 'Time')
    assert Counter(tuple(event[key] for key in keys) for event in trace) == Counter(
        tuple(event[key] for key in keys) for event in events(bank, 'RetentionHeld')), 'Held observer and ordinary native callbacks differ'
    assert fields['ObservedStartedExecutes'] == fields['ExecuteEvents'] == '1'
    assert float(trace[0]['Time']) <= float(start['Time']) <= min(float(pair['execute_time']) for pair in cycles)
    assert max(float(pair['time']) for pair in cycles) <= float(before['Time']) <= float(trace[1]['Time']) <= float(after['Time'])
    return {'events': count, 'tag': fields['Tag'], 'native_order_observed_before_and_after_cycles': True}


def require_isolated_proof(entry, fields, fragment):
    assert fields['Saved'] == fields['NotRecreated'] == '1'
    assert fields['Evidence'] == 'baseline-isolated-noncancellable-proof'
    assert fields['ResolvedTarget'] == fields['Target'] == entry['target']
    assert int(fields['StageCount']) == len(entry['stages'])
    assert [fields[f'Stage{i}'] for i in range(len(entry['stages']))] == entry['stages']
    proof = entry['isolated_evidence']
    proof_path = ROOT / proof['bank']
    if not proof_path.is_file():
        proof_path = ROOT / 'tests/functional/baseline' / Path(proof['bank']).name
    assert hashlib.sha256(proof_path.read_bytes()).hexdigest() == proof['sha256']
    original = read_bank(proof_path)
    assert original['Finished']['Done'] == '1'
    # This historical probe used Event0..N-1, unlike the new acceptance fixture.
    count = int(original['Finished']['Events'])
    names = {key for key in original if key.startswith('Event') and key[5:].isdigit()}
    assert names == {f'Event{i}' for i in range(count)}, 'Truncated isolated baseline proof'
    attempt = original[proof['section']]
    assert attempt['SavedAttemptComplete'] == attempt['ExecuteEvents'] == attempt['CompleteEvents'] == '1'
    assert attempt['CancelEvents'] == attempt['CancelOrderEvents'] == '0'
    assert attempt['DuringCancelHidden'] == attempt['DuringCancelDisabled'] == '1'
    execute, complete = (original[proof[key]] for key in ('execute_event', 'complete_event'))
    assert execute['Stage'] == '-3' and complete['Stage'] == '-6'
    assert execute['Label'] == complete['Label'] == 'Ability'
    assert execute['Command'] == complete['Command'] == '0'
    assert execute['Ability'] == complete['Ability'] == entry['ability']
    assert execute['Tag'] == complete['Tag'] and int(execute['Tag']) > 0
    assert execute['Case'] == complete['Case'] == proof['section']
    assert float(execute['Time']) <= float(complete['Time'])
    assert not events(fragment, f'Link{entry["link"]}')


def verify(main_path, matrix_paths, retention_paths, baseline_path):
    bank = read_bank(main_path)
    finished(bank)
    first = verify_first_lair(bank)
    matrix_bytes = MATRIX_PATH.read_bytes()
    matrix_hash = hashlib.sha256(matrix_bytes).hexdigest()
    specification = json.loads(matrix_bytes)
    baseline = json.loads(baseline_path.read_text())
    assert hashlib.sha256(baseline_path.read_bytes()).hexdigest() == specification['baseline_json_sha256']
    assert baseline['result'] == 'PASS' and not baseline['unresolved_links']
    matrix = specification['matrix']
    assert len(matrix) == len(baseline['matrix']) == 301
    for entry, prior in zip(matrix, baseline['matrix']):
        for key in ('link', 'source', 'ability', 'target', 'classification', 'stages', 'source_bank'):
            assert entry[key] == prior[key], (entry['link'], 'Baseline drift', key)
    assert bank['Probe']['MatrixSHA256'] == matrix_hash
    icons_hash = hashlib.sha256(ICONS_PATH.read_bytes()).hexdigest()
    assert bank['Probe']['IconsSHA256'] == icons_hash
    icons = json.loads(ICONS_PATH.read_text())
    assert icons['baseline_sha256'] == specification['baseline_json_sha256']
    assert {icon['link'] for icon in icons['icons']} == {entry['link'] for entry in matrix if entry['classification'].startswith('cancellable')}
    assert bank['Finished']['MatrixLinks'] == '301' and bank['Finished']['Chunks'] == '16'
    samples = visibility(bank)
    chunks, fragment_samples = matrix_chunks(bank, matrix_paths, matrix_hash, icons_hash)
    samples += fragment_samples
    scenery = require_scenery_isolation(bank, chunks)
    pairs = [first['pair']]
    classifications = Counter()
    positive_abilities = set()
    for entry in matrix:
        link = entry['link']
        case = f'Link{link}'
        fragment = chunks[link // 20]
        fields = fragment[case]
        classification = entry['classification']
        classifications[classification] += 1
        assert fields['BaselineClassification'] == classification
        assert fields['ResolvedTarget'] == fields['Target'] == entry['target'], (case, fields)
        assert int(fields['StageCount']) == len(entry['stages'])
        assert [fields[f'Stage{i}'] for i in range(len(entry['stages']))] == entry['stages'], case
        if entry.get('execution_policy') == 'reuse-isolated-noncancellable-proof':
            require_isolated_proof(entry, fields, fragment)
            continue
        if classification == 'catalog-only-no-player-morph-command':
            assert fields['Saved'] == fields['NotRecreated'] == '1'
            assert fields['Evidence'] == 'baseline-metadata-no-player-command'
            assert fields['SourceRace'] == 'Neut'
            assert entry['metadata_evidence']['own_morph_commands'] == []
            assert entry['metadata_evidence']['mode'] == 'metadata-only-crash-prone-scenery'
            assert not events(fragment, case), 'Crash-prone scenery must not be recreated'
            continue
        positive = classification.startswith('cancellable')
        pair = verify_case(fragment, case, entry['source'], entry['ability'], entry['target'], positive, earliest=positive)
        if pair:
            pairs.append(pair)
            positive_abilities.add(entry['ability'])
        else:
            assert fields['CancelEvents'] == '0', (case, 'New actual cancellability needs a reviewed baseline classification')
            if classification in ('completed-despite-cancel', 'completed-before-cancel', 'instant-completion-same-simulation-time'):
                require_completion(fragment, case, instant=classification == 'instant-completion-same-simulation-time')
            if classification == 'unavailable-player-cancel-window':
                assert fields['EarliestExecuteCancel'] == '1'
                assert fields['AtExecuteCancelHidden'] == fields['AtExecuteCancelDisabled'] == '1'
                assert int(fields['ExecuteEvents']) >= 1 and int(fields['CompleteEvents']) >= 1
                require_completion(fragment, case)
    assert sum(amount for classification, amount in classifications.items() if classification.startswith('cancellable')) == 40
    assert len(positive_abilities) == 32

    for index, link in enumerate(REPEAT_LINKS):
        entry = matrix[link]
        tags = []
        for suffix in ('A', 'B'):
            case = f'Repeat{index}{suffix}'
            pairs.append(verify_case(bank, case, entry['source'], entry['ability'], entry['target'], True, earliest=True))
            tags.append(bank[case]['Tag'])
        assert tags[0] == tags[1], (index, 'Both cancellations must reuse the same actual tag')
    pairs.append(verify_case(bank, 'AutocastRestart', 'Gateway', 'MorphBuildingGatewayWarpGateFree', 'WarpGate', True,
                             earliest=True, autocast_restart=True))

    negatives = {
        'NegativeComplete': ('Thor', 'ThorAPMode', 'ThorAP'),
        'NegativeDeath': ('Hatchery', 'UpgradeToLair', 'Lair'),
        'NegativeRejected': ('Roach', 'MorphToRavager', 'Ravager'),
        'NegativeNoProcess': ('Hatchery', 'UpgradeToLair', 'Lair'),
        'NegativeMove': ('SpineCrawlerUprooted', 'SpineCrawlerRoot', 'SpineCrawler'),
        'NegativeMode': ('SiegeTank', 'SiegeMode', 'SiegeTankSieged'),
        'NegativeTransient': ('Roach', 'BurrowRoachDown', 'RoachBurrowed'),
    }
    for case, identity in negatives.items():
        verify_case(bank, case, *identity, False)
    assert bank['NegativeComplete']['TypeAfter'] == 'ThorAP' and bank['NegativeComplete']['CompleteEvents'] == '1'
    assert bank['NegativeDeath']['AliveAfter'] == '0' and int(bank['NegativeDeath']['ExecuteEvents']) == 1
    assert bank['NegativeRejected']['ExecuteEvents'] == bank['NegativeNoProcess']['ExecuteEvents'] == '0'
    assert bank['NegativeMove']['MoveAccepted'] == '1' and int(bank['NegativeMove']['ExecuteEvents']) >= 1
    assert bank['NegativeMove']['CompleteEvents'] == '0'
    assert any(event['Label'] == 'Ability' and event['Stage'] in ('-4', '-5')
               for event in events(bank, 'NegativeMove')), 'Actual interruption by Move is required'
    assert bank['NegativeMode']['CompleteEvents'] == bank['NegativeTransient']['CompleteEvents'] == '1'
    for case in ('NegativeComplete', 'NegativeMode', 'NegativeTransient'):
        require_completion(bank, case)

    parallel = []
    for index in range(3):
        case = f'Parallel{index}'
        pair = verify_case(bank, case, 'Hatchery', 'UpgradeToLair', 'Lair', True,
                           snapshot=False, counter_expected=3)
        parallel.append(pair)
        pairs.append(pair)
    assert len({pair['tag'] for pair in parallel}) == 3
    assert len({pair['time'] for pair in parallel}) == 1, 'Three distinct live processes must cancel in the same game instant'
    assert int(bank['Parallel/After']['Morphs']) - int(bank['Parallel/Before']['Morphs']) == 3
    assert int(bank['Parallel/After']['Buildings']) - int(bank['Parallel/Before']['Buildings']) == 3
    assert bank['Parallel/After']['Units'] == bank['Parallel/Before']['Units']
    final_parallel = rows(bank['Parallel/After'])
    assert {(row['owner'], row['key'], row['kind'], row['count']) for row in final_parallel} == {('1', 'Lair', '0', '2'), ('2', 'Lair', '0', '1')}
    for row in final_parallel:
        assert row['icon'] == bank['Parallel0']['ExpectedIcon'] and row['name'] == bank['Parallel0']['ExpectedName']

    for index, retention in retention_chunks(bank, retention_paths).items():
        start, end = index * 40, min((index + 1) * 40, 129)
        for cycle in range(start, end):
            pairs.append(verify_case(retention, f'Cycle{cycle}', 'Thor', 'ThorAPMode', 'ThorAP', True, earliest=True, snapshot=False))
    held = bank['RetentionHeld']
    retention = require_retained_process(bank, [pair for pair in pairs if pair['case'].startswith('Cycle')])
    assert int(bank['RetentionHeld/Before']['Morphs']) - int(bank['RetentionHeld/Held']['Morphs']) == 129
    pairs.append(verify_case(bank, 'RetentionHeld', 'Hatchery', 'UpgradeToLair', 'Lair', True, counter_before=bank['RetentionHeld/Before']))
    assert max(float(pair['time']) for pair in pairs if pair['case'].startswith('Cycle')) < float(pairs[-1]['time'])
    assert int(bank['RetentionHeld/Before']['PeakRecords']) >= 2

    fields = bank['FullQueue']
    pairs.append(verify_case(bank, 'FullQueue', 'Hatchery', 'UpgradeToLair', 'Lair', True, earliest=True, snapshot=False))
    before, after = bank['FullQueue/Before'], bank['FullQueue/After']
    assert before['PendingGroups'] == after['PendingGroups'] == '128'
    assert before['QueuedCopies'] == '1' and after['QueuedCopies'] == '2'
    assert after['QueuedKind'] == '0' and after['QueuedOwner'] == '1'
    assert after['QueuedName'] == fields['ExpectedName'] and after['QueuedIcon'] == fields['ExpectedIcon']
    check_ui(bank['FullQueue/Drained'], fields, count=2)
    for index in range(4):
        case = f'Boundary{index}'
        assert bank[case]['Saved'] == '1' and bank[case]['Evidence'] == 'synthetic-component-boundary'
        assert not events(bank, case), 'Synthetic pairing is not an engine trace'
        before, after = bank[case + '/Before'], bank[case + '/After']
        assert int(after['Morphs']) - int(before['Morphs']) == 1, case
        assert int(after['Buildings']) - int(before['Buildings']) == 1, case
        assert after['Units'] == before['Units'], case
        check_ui(after, bank[case])
    assert len({(pair['tag'], pair['ability'], pair['execute_time']) for pair in pairs}) == len(pairs), 'A real Execute generation must be counted once'
    # Every actual attempt has its own Execute/Cancel/order evidence. Boundary
    # probes are reported separately and cannot pad the real-case coverage.
    return {'result': 'PASS', 'scope': 'Full local engine/UI morph acceptance; replay/screenshots and multi-client roles require separate evidence.',
            'source_links': 301, 'positive_source_links': 40, 'positive_abilities': sorted(positive_abilities),
            'classifications': dict(classifications), 'real_cancellations': len(pairs), 'pairs': pairs,
            'reused_isolated_noncancellable_baseline_links': [181],
            'scenery_isolation': scenery,
            'retention_cycles': 129, 'synthetic_pairing_probes': 4,
            'retained_process': retention,
            'active_player_visibility_samples_false': samples,
            'hashes': {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in (main_path, *matrix_paths, *retention_paths, baseline_path, MATRIX_PATH, ICONS_PATH)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bank', type=Path)
    parser.add_argument('--matrix-bank', type=Path, action='append', default=[])
    parser.add_argument('--retention-bank', type=Path, action='append', default=[])
    parser.add_argument('--baseline', type=Path, default=ROOT / 'tests/functional/baseline/morph-scope-baseline.json')
    parser.add_argument('--first-lair-only', action='store_true', help='Check only an actually completed saved FirstLair case, without pretending the suite finished.')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.first_lair_only:
        result = verify_first_lair(args.bank)
    else:
        if not args.retention_bank:
            parser.error('Full acceptance requires four --retention-bank and all sixteen --matrix-bank fragments')
        result = verify(args.bank, args.matrix_bank, args.retention_bank, args.baseline)
    output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(output)
    print(output, end='')


if __name__ == '__main__':
    main()
