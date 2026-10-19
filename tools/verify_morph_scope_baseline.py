#!/usr/bin/env python3
"""Classify measured Morph source links. Unresolved attempts never become PASS."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def read_bank(path):
    return {section.attrib['name']: {
        key.attrib['name']: next(iter(key.find('Value').attrib.values()))
        for key in section.findall('Key')
    } for section in ET.parse(path).getroot().findall('Section')}


def classify_attempt(attempt, trace):
    """Results derive from actual engine callbacks, not UnitIssueOrder success."""
    executed = [event for event in trace if event['Label'] == 'Ability'
                and event['Command'] == '0' and event['Stage'] == '-3']
    completed = [event for event in trace if event['Label'] == 'Ability'
                 and event['Command'] == '0' and event['Stage'] == '-6']
    cancelled = [event for event in trace if event['Label'] == 'Ability'
                 and event['Command'] == '0' and event['Stage'] == '-4']
    cancel_orders = [event for event in trace if event['Label'] == 'Order'
                     and event['Command'] == '1']
    assert len(executed) == int(attempt.get('ExecuteEvents', 0))
    assert len(completed) == int(attempt.get('CompleteEvents', 0))
    assert len(cancelled) == int(attempt.get('CancelEvents', 0))
    assert len(cancel_orders) == int(attempt.get('CancelOrderEvents', 0))
    explicit_cancels = [event for event in cancelled if event['Alive'] == '1'
                        and any(order['Time'] == event['Time']
                                and order['Tag'] == event['Tag'] for order in cancel_orders)]
    if explicit_cancels and executed:
        return 'cancellable', len(explicit_cancels)
    if completed and not cancelled:
        if int(attempt.get('BeforeCancelComplete', 0)):
            return 'completed-before-cancel', 0
        return 'completed-despite-cancel', 0
    if not executed and attempt.get('CreatedPresent') == '0':
        return 'unresolved-source-not-created', 0
    if not executed and attempt.get('BeforeHasAbility') == '0':
        return 'unresolved-ability-not-present', 0
    if not executed:
        return 'unresolved-start-not-observed', 0
    if cancelled:
        return 'unresolved-cancel-without-explicit-pair', 0
    return 'unresolved-process-not-settled', 0


def window_evidence(path, evidence_bank):
    """Require positive controls before accepting a measured unavailable Cancel window."""
    trace = {name: event for name, event in evidence_bank.items() if name.startswith('Event')}
    assert len(trace) == int(evidence_bank['Finished']['Events'])
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    results = {}
    for case, fields in evidence_bank.items():
        if 'RequestedCancel' not in fields:
            continue
        events = {name: event for name, event in trace.items() if event['Case'] == case}
        source_events = [(name, event) for name, event in events.items()
                         if event['Label'] == 'Created' and event['Type'] == fields['Source']
                         and event['Tag'] == fields['CreatedTag'] and event['Alive'] == '1']
        executed = [(name, event) for name, event in events.items()
                    if event['Label'] == 'Ability' and event['Ability'] == fields['Ability']
                    and event['Command'] == '0' and event['Stage'] == '-3']
        completed = [(name, event) for name, event in events.items()
                     if event['Label'] == 'Ability' and event['Ability'] == fields['Ability']
                     and event['Command'] == '0' and event['Stage'] == '-6']
        cancelled = [(name, event) for name, event in events.items()
                     if event['Label'] == 'Ability' and event['Ability'] == fields['Ability']
                     and event['Command'] == '0' and event['Stage'] == '-4']
        orders = [(name, event) for name, event in events.items()
                  if event['Label'] == 'Order' and event['Ability'] == fields['Ability']
                  and event['Command'] == '1']
        assert len(executed) == int(fields['ExecuteEvents']), case
        assert len(completed) == int(fields['CompleteEvents']), case
        assert len(cancelled) == int(fields['CancelEvents']), case
        assert len(orders) == int(fields['CancelOrderEvents']), case
        assert source_events and executed and fields['ExecuteWindowObserved'] == '1', case
        first_execute_name, first_execute = min(executed, key=lambda item: int(item[0][5:]))
        assert first_execute['Time'] == fields['AtExecuteTime'], case
        assert first_execute['Tag'] == fields['AtExecuteTag'] == fields['CreatedTag'], case
        assert first_execute['Type'] == fields['AtExecuteType'], case
        assert first_execute['Alive'] == fields['AtExecuteAlive'] == '1', case
        paired = [(name, event, order_name) for name, event in cancelled
                  for order_name, order in orders
                  if event['Alive'] == order['Alive'] == '1'
                  and event['Tag'] == order['Tag'] == fields['CreatedTag']
                  and event['Time'] == order['Time'] == fields['AtExecuteTime']]
        if case == 'NaturalComplete':
            assert fields['RequestedCancel'] == fields['CancelAttempted'] == '0'
            assert completed and not cancelled and not orders
            continue
        assert fields['RequestedCancel'] == fields['CancelAttempted'] == '1', case
        if case in ('PositiveLair', 'PositiveRavager'):
            assert len(paired) == 1 and not completed, (case, 'Positive control must really cancel.')
        result = None
        if paired:
            result = 'cancellable'
        elif (completed and not cancelled and not orders
              and fields.get('AtExecuteCancelHidden') == '1'
              and fields.get('AtExecuteCancelDisabled') == '1'
              and fields.get('AtExecuteExists') == '1'):
            result = 'unavailable-player-cancel-window'
        if result is None:
            continue
        evidence = {'bank': str(path), 'sha256': sha, 'bank_section': case,
                    'format': 'morph-cancel-window', 'source': fields['Source'],
                    'ability': fields['Ability'], 'tag': fields['CreatedTag'],
                    'time': fields['AtExecuteTime'], 'result': result,
                    'cancellations': len(paired), 'source_created_event': source_events[0][0],
                    'execute_event': first_execute_name,
                    'cancel_order_event': paired[0][2] if paired else 'none (disabled/hidden)',
                    'ability_cancel_event': paired[0][0] if paired else 'none (completed)',
                    'complete_events': [name for name, event in completed],
                    'window_cancel_hidden': fields.get('AtExecuteCancelHidden'),
                    'window_cancel_disabled': fields.get('AtExecuteCancelDisabled'),
                    'window_ability_enabled': fields.get('AtExecuteEnabled')}
        results.setdefault((fields['Source'], fields['Ability']), []).append(evidence)
    assert evidence_bank['PositiveLair']['CancelEvents'] == '1'
    assert evidence_bank['PositiveRavager']['CancelEvents'] == '1'
    assert evidence_bank['NaturalComplete']['CancelEvents'] == '0'
    return results


def supplemental_cancellations(paths):
    """Accept an older probe only with source + live execute + explicit engine cancel."""
    results = {}
    for path in paths:
        evidence_bank = read_bank(path)
        assert evidence_bank['Finished']['Done'] == '1', f'Incomplete supplement: {path}'
        if evidence_bank.get('Probe', {}).get('Fixture') == 'morph-cancel-window':
            for key, values in window_evidence(path, evidence_bank).items():
                results.setdefault(key, []).extend(values)
            continue
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        trace = sorted(((name, event) for name, event in evidence_bank.items()
                        if name.startswith('Event') and name[5:].isdigit()),
                       key=lambda item: int(item[0][5:]))
        for cancel_name, cancelled in trace:
            if not (cancelled.get('Label') == 'Ability' and cancelled.get('Stage') == '-4'
                    and cancelled.get('Command') == '0' and cancelled.get('UnitAlive') == '1'):
                continue
            ability, tag, time = cancelled['Ability'], cancelled['UnitTag'], cancelled['Time']
            order = next(((name, event) for name, event in trace
                          if event.get('Label') == 'Order' and event.get('Command') == '1'
                          and event.get('Ability') == ability and event.get('UnitTag') == tag
                          and event.get('Time') == time and event.get('UnitAlive') == '1'), None)
            executes = [(name, event) for name, event in trace
                        if event.get('Label') == 'Ability' and event.get('Stage') == '-3'
                        and event.get('Command') == '0' and event.get('Ability') == ability
                        and event.get('UnitTag') == tag and event.get('UnitAlive') == '1'
                        and float(event['Time']) <= float(time)
                        and int(name[5:]) < int(cancel_name[5:])]
            if not order or not executes:
                continue
            execute_name, executed = executes[-1]
            created = next(((name, event) for name, event in trace
                            if event.get('Label') == 'Created' and event.get('UnitTag') == tag
                            and event.get('UnitAlive') == '1'
                            and float(event['Time']) <= float(executed['Time'])), None)
            if not created:
                continue
            # A completed/cancelled previous generation cannot lend its Execute to a later Cancel.
            if any(event.get('Label') == 'Ability' and event.get('Stage') in ('-4', '-6')
                   and event.get('Command') == '0' and event.get('Ability') == ability
                   and event.get('UnitTag') == tag
                   and int(execute_name[5:]) < int(name[5:]) < int(cancel_name[5:])
                   for name, event in trace):
                continue
            source = created[1]['UnitType']
            results.setdefault((source, ability), []).append({
                'bank': str(path), 'sha256': sha, 'bank_section': cancelled['Case'],
                'format': 'cancel-diagnostics', 'source': source, 'ability': ability,
                'tag': tag, 'owner': cancelled['UnitOwner'], 'time': time,
                'source_created_event': created[0], 'execute_event': execute_name,
                'cancel_order_event': order[0], 'ability_cancel_event': cancel_name,
                'result': 'cancellable', 'cancellations': 1,
            })
    return results


def scenery_metadata(bank, case):
    fields = bank[case]
    assert fields['MetadataSaved'] == '1'
    cards = []
    commands = []
    for card in range(int(fields['CardCount'])):
        section = f'{case}/Card{card}'
        buttons = [bank[f'{section}/Button{button}']
                   for button in range(int(bank[section]['ButtonCount']))]
        cards.append(buttons)
        commands.extend(button['AbilCmd'] for button in buttons
                        if button['Type'] == 'AbilCmd' and button['AbilCmd'])
    own_commands = [command for command in commands
                    if command.split(',')[0] == fields['Ability']]
    inaccessible = (fields.get('Uncommandable') == '1'
                    or fields.get('Unselectable') == '1'
                    or fields.get('SourceRace') == 'Neut')
    classification = 'unresolved-scenery-player-availability'
    if (fields['Interruptible'] == '0' and fields['ShowProgress'] == '0'
            and not own_commands and inaccessible):
        classification = 'catalog-only-no-player-morph-command'
    return classification, {'mode': 'metadata-only-crash-prone-scenery',
                            'source_uncommandable': fields['Uncommandable'],
                            'source_unselectable': fields['Unselectable'],
                            'source_untargetable': fields['Untargetable'],
                            'source_race': fields['SourceRace'],
                            'source_categories': fields['SourceCategories'],
                            'show_progress': fields['ShowProgress'],
                            'command_cards': cards, 'own_morph_commands': own_commands}


def checked_events(bank, count, label):
    events = {name: value for name, value in bank.items()
              if name.startswith('Event') and name[5:].isdigit()}
    assert set(events) == {f'Event{i}' for i in range(count)}, (label, 'Truncated or non-contiguous trace')
    return events


def segmented_prefix(manifest, chunk_paths):
    assert manifest['Finished']['Done'] == '1'
    assert manifest['Finished']['CatalogLinks'] == '301'
    assert manifest['Finished']['CompletedLinks'] == '292'
    assert manifest['Finished']['Chunks'] == '8'
    assert manifest['Probe']['ChunkCapacity'] == '40'
    assert len(chunk_paths) == 8
    banks_by_link = {}
    events = {}
    fragments = []
    chunks_seen = set()
    for path in chunk_paths:
        bank = read_bank(path)
        assert bank['Probe']['Fixture'] == 'morph-scope-chunk', path
        chunk = int(bank['Probe']['Chunk'])
        assert 0 <= chunk < 8 and chunk not in chunks_seen, path
        chunks_seen.add(chunk)
        start, end = chunk * 40, min((chunk + 1) * 40, 292)
        descriptor = manifest[f'Chunk{chunk}']
        assert descriptor['Done'] == bank['Finished']['Done'] == '1', path
        assert int(bank['Probe']['StartLink']) == int(bank['Finished']['StartLink']) == int(descriptor['StartLink']) == start
        assert int(bank['Finished']['EndLinkExclusive']) == int(descriptor['EndLinkExclusive']) == end
        assert int(bank['Finished']['Links']) == end - start
        assert bank['Finished']['Events'] == descriptor['Events']
        chunk_events = checked_events(bank, int(bank['Finished']['Events']), path)
        assert all(start <= int(event['Case'].split('/')[0][4:]) < end for event in chunk_events.values())
        events.update({f'chunk{chunk}/{name}': value for name, value in chunk_events.items()})
        for index in range(start, end):
            assert f'Link{index}' in bank, (path, index)
            banks_by_link[index] = (bank, path)
        fragments.append({'bank': str(path), 'status': 'finished-chunk', 'start_link': start,
                          'end_link_exclusive': end, 'links': end - start,
                          'event_count': len(chunk_events)})
    assert set(banks_by_link) == set(range(292))
    return banks_by_link, events, sorted(fragments, key=lambda item: item['start_link'])


def verify(probe_path, catalog_path, supplement_paths=(), tail_path=None, chunk_paths=(), isolated_paths=()):
    probe, catalog = read_bank(probe_path), read_bank(catalog_path)
    supplements = supplemental_cancellations(supplement_paths)
    assert probe['Probe']['Fixture'] in ('morph-scope-baseline', 'morph-scope-segmented')
    assert catalog['Finished']['Done'] == '1'
    count = int(catalog['Meta']['SourceLinkCount'])
    tail = read_bank(tail_path) if tail_path else None
    prefix = count
    fragments = []
    limitations = []
    banks_by_link = {}
    segmented = probe['Probe']['Fixture'] == 'morph-scope-segmented'
    if segmented:
        assert tail is not None, 'Segmented prefix requires its separately finished nine-link tail.'
        banks_by_link, events, fragments = segmented_prefix(probe, chunk_paths)
        prefix = 292
        fragments.insert(0, {'bank': str(probe_path), 'status': 'finished-manifest', 'chunks': 8})
        limitations.append('The v76 monolithic bank hit the SC2 key limit and lost trace records; '
                           'it is excluded from acceptance evidence. Prefix0..291 was rerun in eight '
                           'individually finished banks and every trace/counter is checked.')
    elif tail is None:
        assert probe.get('Finished', {}).get('Done') == '1', 'A partial bank alone never passes.'
        assert int(probe['Finished']['Links']) == count
        prefix_events = int(probe['Finished']['Events'])
        events = {f'prefix/{name}': value for name, value in checked_events(probe, prefix_events, probe_path).items()}
        banks_by_link.update({index: (probe, probe_path) for index in range(count)})
        fragments.append({'bank': str(probe_path), 'status': 'finished', 'links': count})
    else:
        assert tail['Probe']['Fixture'] == 'morph-scope-tail'
        assert tail['Finished']['Done'] == '1'
        assert int(tail['Finished']['Links']) == count == 301
        assert int(tail['Finished']['TailLinks']) == 9
        prefix = int(probe['Progress']['Links'])
        assert prefix == int(tail['Probe']['PrefixCompletedLinks']) == 292
        prefix_events = int(probe['Progress']['Events'])
        events = {f'prefix/{name}': value for name, value in checked_events(probe, prefix_events, probe_path).items()}
        banks_by_link.update({index: (probe, probe_path) for index in range(prefix)})
        fragments.extend([{'bank': str(probe_path), 'status': 'completed-prefix-before-crash', 'links': prefix},
                          {'bank': str(tail_path), 'status': 'finished-tail', 'links': 9}])
        limitations.append('SC2 v76 ACCESS_VIOLATION on creating scenery Link292. '
                           'Only the 292 closed attempts saved before the crash are used; '
                           'six scenery links use separate runtime catalog/card availability evidence, '
                           'three remaining links use finished tail attempts. The crashed bank itself is not PASS.')
    if tail:
        assert tail['Probe']['Fixture'] == 'morph-scope-tail'
        assert tail['Finished']['Done'] == '1'
        assert int(tail['Finished']['Links']) == count == 301
        assert int(tail['Finished']['TailLinks']) == 9
        assert int(tail['Probe']['PrefixCompletedLinks']) == prefix == 292
        tail_events = {f'tail/{name}': value for name, value in checked_events(tail, int(tail['Finished']['Events']), tail_path).items()}
        events.update(tail_events)
        banks_by_link.update({index: (tail, tail_path) for index in range(prefix, count)})
        if segmented:
            fragments.append({'bank': str(tail_path), 'status': 'finished-tail', 'links': 9})
            limitations.append('SC2 v76 ACCESS_VIOLATION occurred when creating scenery Link292. '
                               'Links292..297 are never recreated: runtime catalog flags and complete '
                               'command cards prove their player availability classification. '
                               'Links298..300 have real completed tail attempts.')
    superseded = []
    isolated_indices = set()
    for path in isolated_paths:
        isolated = read_bank(path)
        assert isolated['Probe']['Fixture'] == 'morph-scope-isolated'
        assert isolated['Finished']['Done'] == '1'
        assert int(isolated['Finished']['Links']) == count
        assert isolated['Finished']['IsolatedLinks'] == '1'
        index = int(isolated['Probe']['IsolatedLink'])
        assert 0 <= index < count and index not in isolated_indices
        isolated_indices.add(index)
        case = f'Link{index}'
        assert isolated[case]['ExecutionMode'] == 'actual-isolated-attempt'
        prior_bank, prior_path = banks_by_link[index]
        prior_attempts = []
        for method in ['Default', 'Point']:
            section = f'{case}/{method}'
            if section not in prior_bank:
                continue
            previous = prior_bank[section]
            assert previous['SavedAttemptComplete'] == '1', (section, 'Superseded attempt must still be fully recorded.')
            trace = [event for event in events.values() if event['Case'] == section]
            result, cancelled = classify_attempt(previous, trace)
            prior_attempts.append({'bank_section': section, 'classification': result,
                                   'cancellations': cancelled,
                                   'created_alive': previous.get('CreatedAlive'),
                                   'before_alive': previous.get('BeforeAlive'),
                                   'start_accepted': previous.get('StartAccepted')})
        assert prior_attempts, 'An isolated proof must explicitly replace an existing recorded attempt.'
        superseded.append({'link': index, 'bank': str(prior_path), 'attempts': prior_attempts,
                           'replacement_bank': str(path), 'reason': 'Fresh-map isolated follow-up; prior evidence remains recorded, not silently accepted.'})
        events = {name: event for name, event in events.items()
                  if event['Case'].split('/')[0] != case}
        replacement_events = checked_events(isolated, int(isolated['Finished']['Events']), path)
        assert all(event['Case'].split('/')[0] == case for event in replacement_events.values())
        events.update({f'isolated{index}/{name}': event for name, event in replacement_events.items()})
        banks_by_link[index] = (isolated, path)
        fragments.append({'bank': str(path), 'status': 'finished-isolated-follow-up', 'link': index})
    ability_info = {values['Id']: (name, values) for name, values in catalog.items()
                    if name.startswith('Ability') and '/Stage' not in name}
    results = []
    for index in range(count):
        case = f'Link{index}'
        active_bank, source_path = banks_by_link[index]
        measured, expected = active_bank[case], catalog[f'SourceLink{index}']
        assert (measured['Source'], measured['Ability']) == (expected['Unit'], expected['Ability']), case
        assert measured['UnitCatalogIndex'] == expected['UnitCatalogIndex'], case
        assert measured['AbilArrayIndex'] == expected['AbilArrayIndex'], case
        ability_section, info = ability_info[measured['Ability']]
        stages = [catalog[f'{ability_section}/Stage{i}']
                  for i in range(int(info['StageCount']))]
        targets = [stage['Target'] for stage in stages if stage['TargetValid'] == '1']
        assert targets, case
        base_row = {'link': index, 'source': measured['Source'], 'ability': measured['Ability'],
                    'class': measured['Class'], 'interruptible_flag': info['Interruptible'],
                    'automatic_flag': measured.get('Automatic'),
                    'disable_abilities_flag': measured.get('DisableAbils'),
                    'execute_requirements': measured.get('ExecuteRequirements'),
                    'cancel_face': info['CancelFace'], 'target': targets[-1],
                    'stages': [stage['Target'] for stage in stages], 'source_bank': str(source_path)}
        if measured.get('ExecutionMode') == 'metadata-only-crash-prone-scenery':
            assert tail and 292 <= index <= 297
            classification, metadata = scenery_metadata(active_bank, case)
            results.append(dict(base_row, classification=classification, attempts=[],
                                supplemental_evidence=[], metadata_evidence=metadata))
            continue
        attempts = []
        for method in ['Default', 'Point']:
            section = f'{case}/{method}'
            if section not in active_bank:
                continue
            attempt = active_bank[section]
            if segmented or index >= prefix:
                assert attempt['SavedAttemptComplete'] == '1', section
            if attempt.get('CreatedPresent') == '1':
                for key in ['ExecuteEvents', 'CompleteEvents', 'CancelEvents', 'CancelOrderEvents',
                            'BeforeBuildings', 'AfterBuildings', 'BeforeUnits', 'AfterUnits', 'CreatedUnits']:
                    assert key in attempt, (section, 'Attempt not saved completely', key)
                assert int(attempt['AfterBuildings']) - int(attempt['BeforeBuildings']) == 0, section
                assert int(attempt['AfterUnits']) - int(attempt['BeforeUnits']) == 0, section
            trace = [event for event in events.values() if event['Case'] == section]
            result, cancelled = classify_attempt(attempt, trace)
            attempts.append({'bank_section': section, 'result': result,
                             'cancellations': cancelled,
                             'executed': int(attempt.get('ExecuteEvents', 0)),
                             'completed': int(attempt.get('CompleteEvents', 0)),
                             'start_accepted': attempt.get('StartAccepted'),
                             'cancel_accepted': attempt.get('CancelAccepted'),
                             'before_hidden': attempt.get('BeforeHidden'),
                             'before_disabled': attempt.get('BeforeDisabled'),
                             'before_has_ability': attempt.get('BeforeHasAbility'),
                             'natural_observation_start': attempt.get('NaturalObservationStart'),
                             'natural_observation_end': attempt.get('NaturalObservationEnd'),
                             'natural_end_alive': attempt.get('NaturalEndAlive'),
                             'time': attempt['Time']})
        assert attempts, case
        decisive = next((attempt for attempt in attempts if attempt['result'] == 'cancellable'), None)
        if decisive is None:
            decisive = next((attempt for attempt in attempts if not attempt['result'].startswith('unresolved')), attempts[-1])
        classification = decisive['result']
        automatic = measured.get('Automatic') == '1'
        decisive_data = active_bank[decisive['bank_section']]
        decisive_events = [event for event in events.values()
                           if event['Case'] == decisive['bank_section']]
        natural_start = decisive_data.get('NaturalObservationStart')
        natural_end = decisive_data.get('NaturalObservationEnd')
        unavailable_observed = (
            natural_start is not None and natural_end is not None
            and float(natural_end) - float(natural_start) >= 6
            and decisive_data.get('BeforeDisabled') == '1'
            and (decisive_data.get('NaturalEndAlive') == '1'
                 or any(event['Label'] in ('Died', 'Created')
                        and (event['Label'] == 'Died' or event['Type'] == targets[-1])
                        for event in decisive_events)))
        if (automatic and info['Interruptible'] == '0' and not info['CancelFace']
                and all(attempt['cancellations'] == 0 for attempt in attempts)
                and all(active_bank[attempt['bank_section']].get('CancelOrderEvents') == '0'
                        for attempt in attempts)):
            classification = 'automatic-no-manual-cancel'
        elif (measured.get('DisableAbils') == '1' and info['Interruptible'] == '0'
              and not info['CancelFace'] and unavailable_observed
              and all(attempt['cancellations'] == 0 for attempt in attempts)
              and decisive_data.get('CancelOrderEvents') == '0'):
            classification = 'unavailable-manual-command-observed-natural-lifecycle'
        elif info['Transient'] == '1' and classification.startswith('completed-'):
            decisive_trace = [event for event in events.values()
                              if event['Case'] == decisive['bank_section']
                              and event['Label'] == 'Ability' and event['Command'] == '0']
            executed = [event for event in decisive_trace if event['Stage'] == '-3']
            completed = [event for event in decisive_trace if event['Stage'] == '-6']
            if executed and all(any(finish['Time'] == start['Time']
                                    and finish['Tag'] == start['Tag']
                                    for finish in completed) for start in executed):
                classification = ('unresolved-instant-needs-earliest-cancel-probe'
                                  if info['Interruptible'] == '1'
                                  else 'instant-completion-same-simulation-time')
            elif info['Interruptible'] == '1':
                classification = 'unresolved-interruptible-no-cancel-pair'
        # A declared interruptible process which ignores this timing needs a tighter probe.
        elif classification.startswith('completed-') and info['Interruptible'] == '1':
            classification = 'unresolved-interruptible-no-cancel-pair'
        supplemental = supplements.get((measured['Source'], measured['Ability']), [])
        if classification.startswith('unresolved') and supplemental:
            if any(evidence['result'] == 'cancellable' for evidence in supplemental):
                classification = 'cancellable-supplemented-engine-trace'
            elif any(evidence['result'] == 'unavailable-player-cancel-window' for evidence in supplemental):
                classification = 'unavailable-player-cancel-window'
        results.append(dict(base_row, classification=classification, attempts=attempts,
                            supplemental_evidence=supplemental))
    classifications = Counter(item['classification'] for item in results)
    unresolved = [item['link'] for item in results if item['classification'].startswith('unresolved')]
    return {'result': 'INCOMPLETE' if unresolved else 'PASS',
            'scope': 'Measured forced-condition source-link baseline; not natural melee reachability or production acceptance.',
            'banks': {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in [probe_path, catalog_path, *chunk_paths, *supplement_paths, *isolated_paths, *([tail_path] if tail_path else [])]},
            'links': count, 'summary': dict(classifications), 'unresolved_links': unresolved,
            'fragments': fragments, 'limitations': limitations,
            'superseded_attempts': superseded,
            'matrix': results}


def write_markdown(result, path):
    lines = ['# Baseline rozszerzonego zakresu morfów — 2026-10-19', '',
             f"Wynik: **{result['result']}**. Próby: {result['links']} powiązań katalogowych.", '',
             'Każdy wiersz odwołuje się do rzeczywistego banku SC2. Dostępność przy',
             'wymuszonych zasobach, wyłączonych wymaganiach i testowym creepie nie',
             'dowodzi dostępności w standardowej rozgrywce. Wynik unresolved blokuje',
             'zmianę produkcji; samo przyjęcie rozkazu nie zalicza próby.', '',
             '| Wynik silnika | Liczba powiązań |', '| --- | --- |']
    lines.extend(f'| {name} | {count} |' for name, count in sorted(result['summary'].items()))
    if result['limitations']:
        lines += ['', 'Ograniczenia i rozdzielone fragmenty dowodów:', '']
        lines.extend(f"- {limitation}" for limitation in result['limitations'])
    if result['superseded_attempts']:
        lines += ['', 'Próby zastąpione odrębnym pomiarem na świeżej mapie:', '']
        lines.extend(f"- Link{item['link']}: `{item['bank']}` → `{item['replacement_bank']}`; "
                     f"poprzedni ślad sprawdzony, pierwotny wynik zachowany w JSON." for item in result['superseded_attempts'])
    lines += ['', '| Link | Źródło | Zdolność | Cel końcowy | Wynik | Bank/sekcja; czas gry |',
              '| --- | --- | --- | --- | --- | --- |']
    for item in result['matrix']:
        evidence = '; '.join(f"{Path(item['source_bank']).name}/{attempt['bank_section']} @ {attempt['time']}" for attempt in item['attempts'])
        if item.get('metadata_evidence'):
            metadata = item['metadata_evidence']
            evidence = (f"{Path(item['source_bank']).name}/Link{item['link']}: metadata only; "
                        f"uncommandable={metadata['source_uncommandable']}, "
                        f"unselectable={metadata['source_unselectable']}, race={metadata['source_race']}; "
                        f"own commands={len(metadata['own_morph_commands'])}; no creation after crash")
        if item['supplemental_evidence']:
            evidence += '; supplement: ' + '; '.join(
                f"{Path(attempt['bank']).name}/{attempt['bank_section']} @ {attempt['time']} "
                f"tag{attempt['tag']} ({attempt['source_created_event']}, {attempt['execute_event']}, "
                f"{attempt['cancel_order_event']}, {attempt['ability_cancel_event']})"
                for attempt in item['supplemental_evidence'])
        lines.append(f"| {item['link']} | {item['source']} | {item['ability']} | {item['target']} | {item['classification']} | {evidence} |")
    lines += ['', 'Banki i SHA256:', '']
    lines.extend(f'- `{name}` — `{sha}`' for name, sha in result['banks'].items())
    path.write_text('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('probe_bank', type=Path)
    parser.add_argument('catalog_bank', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--markdown', type=Path)
    parser.add_argument('--supplement-bank', type=Path, action='append', default=[],
                        help='Existing diagnostic bank with source-created/Execute/explicit Cancel evidence; repeatable.')
    parser.add_argument('--tail-bank', type=Path,
                        help='Finished nine-link fragment supplementing the 292 saved v76 attempts; never marks the crashed bank finished.')
    parser.add_argument('--chunk-bank', type=Path, action='append', default=[],
                        help='One individually finished prefix chunk; repeat exactly eight times for a segmented manifest.')
    parser.add_argument('--isolated-bank', type=Path, action='append', default=[],
                        help='Finished fresh-map follow-up replacing one explicitly retained unresolved attempt.')
    parser.add_argument('--allow-incomplete', action='store_true', help='Report unresolved probes without a nonzero exit; result remains INCOMPLETE.')
    args = parser.parse_args()
    result = verify(args.probe_bank, args.catalog_bank, args.supplement_bank, args.tail_bank, args.chunk_bank, args.isolated_bank)
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    if args.markdown:
        write_markdown(result, args.markdown)
    print(json.dumps({key: value for key, value in result.items() if key != 'matrix'}, ensure_ascii=False, indent=2))
    if result['result'] != 'PASS' and not args.allow_incomplete:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
