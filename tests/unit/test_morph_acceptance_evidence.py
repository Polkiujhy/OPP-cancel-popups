"""Test evidence parsing with synthetic banks; these are never SC2 runtime proof."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('morph_acceptance_evidence_validator',
                                              ROOT / 'tools/verify_morph_acceptance.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

def write_bank(path, bank):
    root = ET.Element('Bank')
    # Deliberately reverse persistence order: evidence sequence comes from the
    # EventN identity, not the arbitrary order of sections saved by SC2.
    for name, fields in reversed(list(bank.items())):
        section = ET.SubElement(root, 'Section', name=name)
        for key, value in fields.items():
            ET.SubElement(ET.SubElement(section, 'Key', name=key), 'Value', string=str(value))
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def snapshot(morphs=0, buildings=0, units=0):
    result = {'Init': '1', 'UIReady': '1', 'ResolverErrors': '0',
              'Morphs': str(morphs), 'Buildings': str(buildings), 'Units': str(units),
              'PendingGroups': '0', 'QueuedCopies': '0', 'PeakRecords': '2'}
    for row in range(3):
        result.update({f'Row{row}Visible': '0', f'Row{row}Player1': '0', f'Row{row}Player2': '0'})
    return result


def show_row(output, fields, row=0, count=1):
    for name, value in {'Visible': '1', 'Key': fields['Target'], 'Owner': fields['Owner'],
                        'Kind': fields['Kind'], 'Name': fields['ExpectedName'],
                        'Icon': fields['ExpectedIcon'], 'Count': str(count),
                        'Status': 'Cancelled' + (f' ×{count}' if count > 1 else ''),
                        'Remaining': '4.8125'}.items():
        output[f'Row{row}{name}'] = value


class ProtocolBuilder:
    """Declared wire-format examples, with no reproduction of Galaxy logic."""
    def __init__(self, icons):
        self.icons = {(icon['ability'], icon['target']): icon for icon in icons['icons']}
        self.clock = 10
        self.tag = 100

    def event(self, bank, case, fields, label, stage, time, command='0', alive='1'):
        index = 1 + sum(key.startswith('Event') and key[5:].isdigit() for key in bank)
        bank[f'Event{index}'] = {'Case': case, 'Tag': fields['Tag'], 'Ability': fields['Ability'],
                                'Owner': fields['Owner'], 'Alive': alive, 'Label': label,
                                'Stage': str(stage), 'Command': command, 'Time': str(time)}

    def case(self, bank, case, source, ability, target, positive=True, owner=1,
             tag=None, time=None, completed=False, instant=False, counter=1, kind='0'):
        self.clock += 10
        self.tag += 1
        when = self.clock if time is None else time
        kind = str(kind)  # Explicit declared wire-format expectation, no catalog resolver.
        fields = {'Source': source, 'Ability': ability, 'Target': target, 'ResolvedTarget': target,
                  'Saved': '1', 'Evidence': 'real-engine-attempt', 'Created': '1',
                  'Tag': str(self.tag if tag is None else tag), 'Owner': str(owner), 'Kind': kind,
                  'StartAccepted': '1', 'CancelAccepted': '1', 'AliveAfter': '1',
                  'ResolverErrors': '0', 'ExpectedName': target, 'ExpectedIcon': '',
                  'ExpectedAsset': '', 'IconOracle': '', 'EarliestExecuteCancel': '1',
                  'ExecuteCancelTime': str(when), 'ExecuteEvents': '0', 'CancelEvents': '0',
                  'CompleteEvents': '0', 'CancelOrders': '0',
                  'BeforeMorphs': '0', 'BeforeBuildings': '0', 'BeforeUnits': '0',
                  'AfterMorphs': str(counter if positive else 0),
                  'AfterBuildings': str(counter if positive and kind == '0' else 0),
                  'AfterUnits': str(counter if positive and kind == '2' else 0)}
        oracle = self.icons.get((ability, target))
        if oracle:
            fields.update(ExpectedIcon=oracle['expected_asset'], ExpectedAsset=oracle['expected_asset'],
                          IconOracle=oracle['catalog'] + ':' + oracle['entry'] + '.' + oracle['field'])
        bank[case] = fields
        bank[case + '/Before'] = snapshot()
        after = snapshot(fields['AfterMorphs'], fields['AfterBuildings'], fields['AfterUnits'])
        bank[case + '/After'] = after
        if positive:
            fields.update(ExecuteEvents='1', CancelEvents='1', CancelOrders='1')
            self.event(bank, case, fields, 'Ability', -3, when)
            self.event(bank, case, fields, 'Order', 0, when, command='1')
            self.event(bank, case, fields, 'Ability', -4, when)
            show_row(after, fields)
        elif completed:
            fields.update(ExecuteEvents='1', CompleteEvents='1', TypeAfter=target)
            self.event(bank, case, fields, 'Ability', -3, when)
            self.event(bank, case, fields, 'Ability', -6, when if instant else when + 0.125)
        return fields

    @staticmethod
    def finish(bank, **extra):
        bank['Finished'] = {'Done': '1', 'Events': str(sum(key.startswith('Event') and key[5:].isdigit() for key in bank)),
                            **{key: str(value) for key, value in extra.items()}}


class FocusedMorphEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.icons = json.loads(validator.ICONS_PATH.read_text())
        self.builder = ProtocolBuilder(self.icons)
        self.bank = {'Probe': {'Fixture': 'morph-acceptance',
                               'IconsSHA256': hashlib.sha256(validator.ICONS_PATH.read_bytes()).hexdigest()}}
        self.builder.case(self.bank, 'FirstLair', 'Hatchery', 'UpgradeToLair', 'Lair')

    def test_saved_first_case_passes_without_forging_the_full_fixture_done(self):
        self.assertNotIn('Finished', self.bank)
        result = validator.verify_first_lair(self.bank)
        self.assertEqual(result['pair']['ability'], 'UpgradeToLair')
        self.assertIn('Focused', result['scope'])
        self.assertIn('no full fixture claim', result['scope'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'saved-prefix.SC2Bank'
            write_bank(path, self.bank)
            self.assertEqual(validator.verify_first_lair(path)['pair'], result['pair'])

    def test_engine_cancel_may_arrive_before_or_after_the_order_callback(self):
        expected = validator.verify_first_lair(self.bank)['pair']
        self.bank['Event2'], self.bank['Event3'] = self.bank['Event3'], self.bank['Event2']
        self.assertEqual(validator.verify_first_lair(self.bank)['pair'], expected)

    def test_missing_actual_execute_cancel_or_order_rejects_even_with_positive_scalars(self):
        for key in ('Event1', 'Event2', 'Event3'):
            with self.subTest(missing=key):
                bank = copy.deepcopy(self.bank)
                del bank[key]
                with self.assertRaises(AssertionError):
                    validator.verify_first_lair(bank)

    def test_identity_liveness_exact_time_and_actual_execute_are_required(self):
        changes = [('Event2', 'Time', '20.0625'), ('Event2', 'Tag', '999'),
                   ('Event3', 'Ability', 'OtherMorph'), ('Event3', 'Owner', '2'),
                   ('Event3', 'Alive', '0'), ('Event2', 'Command', '0'),
                   ('Event1', 'Time', '20.0625')]
        for section, key, value in changes:
            with self.subTest(section=section, key=key):
                bank = copy.deepcopy(self.bank)
                bank[section][key] = value
                with self.assertRaises(AssertionError):
                    validator.verify_first_lair(bank)

    def test_completion_and_duplicate_cancel_do_not_substitute_for_one_cancelled_attempt(self):
        for stage in ('-6', '-4'):
            with self.subTest(extra_stage=stage):
                bank = copy.deepcopy(self.bank)
                bank['Event4'] = dict(bank['Event3'], Stage=stage)
                bank['FirstLair']['CompleteEvents' if stage == '-6' else 'CancelEvents'] = '1' if stage == '-6' else '2'
                with self.assertRaises(AssertionError):
                    validator.verify_first_lair(bank)

    def test_publication_disabled_wrong_target_category_icon_count_or_timer_is_red(self):
        changes = [('FirstLair', 'AfterMorphs', '0'), ('FirstLair', 'AfterBuildings', '0'),
                   ('FirstLair', 'ResolvedTarget', 'Hive'), ('FirstLair', 'Target', 'Hive'),
                   ('FirstLair/After', 'Row0Kind', '2'), ('FirstLair/After', 'Row0Owner', '2'),
                   ('FirstLair/After', 'Row0Key', 'Hatchery'), ('FirstLair/After', 'Row0Name', 'Hatchery'),
                   ('FirstLair/After', 'Row0Icon', 'cancel.dds'), ('FirstLair/After', 'Row0Count', '2'),
                   ('FirstLair/After', 'Row0Status', 'Cancelled ×2'), ('FirstLair/After', 'Row0Remaining', '0')]
        for section, key, value in changes:
            with self.subTest(section=section, key=key):
                bank = copy.deepcopy(self.bank)
                bank[section][key] = value
                with self.assertRaises(AssertionError):
                    validator.verify_first_lair(bank)

    def test_matching_wrong_icon_in_both_expectation_and_ui_cannot_defeat_frozen_oracle(self):
        self.bank['FirstLair'].update(ExpectedIcon='cancel.dds', ExpectedAsset='cancel.dds')
        self.bank['FirstLair/After']['Row0Icon'] = 'cancel.dds'
        with self.assertRaises(AssertionError):
            validator.verify_first_lair(self.bank)


class AutocastRestartEvidenceTests(unittest.TestCase):
    """The observed native protocol: issue now, paired end and restart next tick."""
    def setUp(self):
        self.builder = ProtocolBuilder(json.loads(validator.ICONS_PATH.read_text()))
        self.bank = {}
        self.case = 'AutocastRestart'
        fields = self.builder.case(self.bank, self.case, 'Gateway',
                                   'MorphBuildingGatewayWarpGateFree', 'WarpGate', time=20)
        fields['ExecuteEvents'] = '2'
        self.bank['Event2']['Time'] = self.bank['Event3']['Time'] = '20.0625'
        self.bank['Event4'] = dict(self.bank['Event1'], Time='20.0625')

    def require(self, bank=None):
        return validator.verify_case(self.bank if bank is None else bank, self.case, 'Gateway',
                                     'MorphBuildingGatewayWarpGateFree', 'WarpGate', True,
                                     earliest=True, autocast_restart=True)

    def test_immediate_issue_and_exact_next_tick_native_pair_restart_pass(self):
        pair = self.require()
        self.assertEqual((pair['execute_time'], pair['time']), ('20', '20.0625'))

    def test_both_ending_callback_orders_belong_to_first_generation(self):
        self.bank['Event2'], self.bank['Event3'] = self.bank['Event3'], self.bank['Event2']
        self.require()

    def test_ordinary_earliest_contract_still_rejects_next_tick_delivery(self):
        with self.assertRaises(AssertionError):
            validator.verify_case(self.bank, self.case, 'Gateway',
                                  'MorphBuildingGatewayWarpGateFree', 'WarpGate', True, earliest=True)

    def test_missing_execute_order_cancel_or_real_restart_is_rejected(self):
        for key in ('Event1', 'Event2', 'Event3', 'Event4'):
            with self.subTest(missing=key):
                bank = copy.deepcopy(self.bank)
                del bank[key]
                with self.assertRaises(AssertionError):
                    self.require(bank)

    def test_cancel_issue_must_be_in_first_execute_and_delivery_exactly_one_tick_later(self):
        bank = copy.deepcopy(self.bank)
        bank[self.case]['ExecuteCancelTime'] = '20.0625'
        with self.assertRaises(AssertionError):
            self.require(bank)
        for time in ('20', '20.125'):
            with self.subTest(delivery=time):
                bank = copy.deepcopy(self.bank)
                for key in ('Event2', 'Event3', 'Event4'):
                    bank[key]['Time'] = time
                with self.assertRaises(AssertionError):
                    self.require(bank)
        for key in ('Event2', 'Event3', 'Event4'):
            with self.subTest(unpaired_time=key):
                bank = copy.deepcopy(self.bank)
                bank[key]['Time'] = '20.125'
                with self.assertRaises(AssertionError):
                    self.require(bank)

    def test_restart_requires_same_tag_ability_owner_and_liveness(self):
        for key, value in [('Tag', '999'), ('Ability', 'OtherMorph'), ('Owner', '2'), ('Alive', '0')]:
            with self.subTest(key=key):
                bank = copy.deepcopy(self.bank)
                bank['Event4'][key] = value
                with self.assertRaises(AssertionError):
                    self.require(bank)

    def test_same_time_restart_cannot_precede_the_first_generations_ending_pair(self):
        self.bank['Event2'], self.bank['Event4'] = self.bank['Event4'], self.bank['Event2']
        with self.assertRaises(AssertionError):
            self.require()

    def test_extra_execute_cancel_or_complete_cannot_pad_the_protocol(self):
        for stage, counter, value in [('-3', 'ExecuteEvents', '3'), ('-4', 'CancelEvents', '2'),
                                      ('-6', 'CompleteEvents', '1')]:
            with self.subTest(extra_stage=stage):
                bank = copy.deepcopy(self.bank)
                bank['Event5'] = dict(bank['Event4'], Stage=stage)
                bank[self.case][counter] = value
                with self.assertRaises(AssertionError):
                    self.require(bank)

    def test_exact_single_publication_and_actual_ui_remain_mandatory(self):
        changes = [(self.case, 'AfterMorphs', '0'), (self.case, 'AfterBuildings', '0'),
                   (self.case + '/After', 'Row0Count', '2'),
                   (self.case + '/After', 'Row0Icon', 'cancel.dds'),
                   (self.case + '/After', 'Row0Kind', '2')]
        for section, key, value in changes:
            with self.subTest(section=section, key=key):
                bank = copy.deepcopy(self.bank)
                bank[section][key] = value
                with self.assertRaises(AssertionError):
                    self.require(bank)


class CompletionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.builder = ProtocolBuilder(json.loads(validator.ICONS_PATH.read_text()))
        self.bank = {}
        self.case = 'CompletedMode'
        self.builder.case(self.bank, self.case, 'Thor', 'ThorAPMode', 'ThorAP',
                          positive=False, completed=True, kind='2')

    def test_actual_execute_and_complete_prove_a_completed_negative_control(self):
        validator.require_completion(self.bank, self.case)

    def test_removing_execute_or_complete_is_red_despite_unchanged_complete_scalars(self):
        for key in ('Event1', 'Event2'):
            with self.subTest(missing=key):
                bank = copy.deepcopy(self.bank)
                del bank[key]
                with self.assertRaises(AssertionError):
                    validator.require_completion(bank, self.case)

    def test_completion_requires_same_identity_and_owner_and_must_follow_execute(self):
        for key, value in [('Tag', '999'), ('Ability', 'OtherMorph'), ('Owner', '2'), ('Time', '19')]:
            with self.subTest(key=key):
                bank = copy.deepcopy(self.bank)
                bank['Event2'][key] = value
                with self.assertRaises(AssertionError):
                    validator.require_completion(bank, self.case)

    def test_instant_completion_requires_the_same_exact_mission_time(self):
        with self.assertRaises(AssertionError):
            validator.require_completion(self.bank, self.case, instant=True)
        self.bank['Event2']['Time'] = self.bank['Event1']['Time']
        validator.require_completion(self.bank, self.case, instant=True)

    def test_real_cancel_is_not_a_completed_negative_control(self):
        self.bank['Event3'] = dict(self.bank['Event2'], Stage='-4')
        with self.assertRaises(AssertionError):
            validator.require_completion(self.bank, self.case)


class MatrixFragmentIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.paths = [Path(f'CandidateMatrix{i}.SC2Bank') for i in range(16)]
        self.manifest = {'Matrix': {f'Chunk{i}': path.stem for i, path in enumerate(self.paths)}}
        self.fragments = {}
        for chunk, path in enumerate(self.paths):
            start, end = chunk * 20, min((chunk + 1) * 20, 301)
            fragment = {'Probe': {'Fixture': 'morph-matrix-chunk', 'Chunk': str(chunk),
                                   'MatrixSHA256': 'matrix-hash', 'IconsSHA256': 'icons-hash'},
                        'Finished': {'Done': '1', 'Events': str(end - start),
                                     'StartLink': str(start), 'EndLinkExclusive': str(end)}}
            fragment.update({f'Link{i}': {} for i in range(start, end)})
            fragment.update({f'Event{i - start + 1}': {'Case': f'Link{i}'} for i in range(start, end)})
            self.fragments[path] = fragment

    def chunks(self, paths=None):
        with patch.object(validator, 'read_bank', side_effect=lambda path: self.fragments[path]):
            return validator.matrix_chunks(self.manifest, self.paths if paths is None else paths,
                                           'matrix-hash', 'icons-hash')[0]

    def test_every_closed_fragment_is_consumed_once(self):
        self.assertEqual(set(self.chunks()), set(range(16)))

    def test_missing_or_duplicate_fragments_cannot_pass_by_done_scalar(self):
        with self.assertRaises(AssertionError):
            self.chunks(self.paths[:-1])
        with self.assertRaises(AssertionError):
            self.chunks(self.paths[:-1] + [self.paths[0]])

    def test_unfinished_wrong_hash_wrong_revision_or_incomplete_range_is_rejected(self):
        changes = [('Finished', 'Done', '0'), ('Finished', 'Events', '21'),
                   ('Finished', 'EndLinkExclusive', '19'),
                   ('Probe', 'MatrixSHA256', 'older-matrix'), ('Probe', 'IconsSHA256', 'older-icons')]
        for section, key, value in changes:
            with self.subTest(section=section, key=key):
                fields = self.fragments[self.paths[0]][section]
                previous = fields[key]
                fields[key] = value
                with self.assertRaises(AssertionError):
                    self.chunks()
                fields[key] = previous
        self.manifest['Matrix']['Chunk0'] = 'OlderRevisionMatrix0'
        with self.assertRaises(AssertionError):
            self.chunks()

    def test_missing_link_or_missing_event_is_rejected_even_when_done_is_one(self):
        for key in ('Link0', 'Event1'):
            with self.subTest(missing=key):
                bank = self.fragments[self.paths[0]]
                removed = bank.pop(key)
                with self.assertRaises(AssertionError):
                    self.chunks()
                bank[key] = removed


class RetentionFragmentIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.paths = [Path(f'CandidateRetention{i}.SC2Bank') for i in range(4)]
        self.manifest = {'RetentionHeld': {f'Chunk{i}': path.stem for i, path in enumerate(self.paths)}}
        self.fragments = {}
        for chunk, path in enumerate(self.paths):
            start, end = chunk * 40, min((chunk + 1) * 40, 129)
            fragment = {'Probe': {'Fixture': 'morph-retention', 'Chunk': str(chunk)},
                        'Finished': {'Done': '1', 'Events': str(end - start),
                                     'StartCycle': str(start), 'EndCycleExclusive': str(end)}}
            fragment.update({f'Event{i - start + 1}': {'Case': f'Cycle{i}'} for i in range(start, end)})
            self.fragments[path] = fragment

    def chunks(self, paths=None):
        with patch.object(validator, 'read_bank', side_effect=lambda path: self.fragments[path]):
            return validator.retention_chunks(self.manifest, self.paths if paths is None else paths)

    def test_all_129_cycles_require_all_four_closed_fragments(self):
        self.assertEqual(set(self.chunks()), set(range(4)))
        with self.assertRaises(AssertionError):
            self.chunks(self.paths[:3])
        with self.assertRaises(AssertionError):
            self.chunks(self.paths[:3] + [self.paths[0]])

    def test_unfinished_truncated_wrong_range_or_wrong_case_is_rejected(self):
        changes = [('Finished', 'Done', '0'), ('Finished', 'Events', '41'),
                   ('Finished', 'EndCycleExclusive', '39'), ('Event1', 'Case', 'Cycle999')]
        for section, key, value in changes:
            with self.subTest(section=section, key=key):
                fields = self.fragments[self.paths[0]][section]
                previous = fields[key]
                fields[key] = value
                with self.assertRaises(AssertionError):
                    self.chunks()
                fields[key] = previous
        del self.fragments[self.paths[0]]['Event1']
        with self.assertRaises(AssertionError):
            self.chunks()


class RetainedProcessEvidenceTests(unittest.TestCase):
    """Independent wire-format observations surround all 129 declared cycles."""
    def setUp(self):
        builder = ProtocolBuilder(json.loads(validator.ICONS_PATH.read_text()))
        self.bank = {}
        fields = builder.case(self.bank, 'RetentionHeld', 'Hatchery', 'UpgradeToLair', 'Lair', time=100)
        fields.update(Cycles='129', Lengthened='1', LengthenedActor='1', LengthenedStats='1',
                      StillAlive='1', StillExecuting='0', ObservedStartedExecutes='1')
        self.bank['Event1']['Time'] = '10'
        for label, time in [('StartState', '10.125'), ('BeforeCancelState', '99.875'),
                            ('AfterCancelState', '100.1875')]:
            self.bank['RetentionHeld/' + label] = {
                'Time': time, 'Exists': '1', 'Alive': '1', 'Tag': fields['Tag'],
                'Owner': '1', 'Type': 'Hatchery', 'HasMorphOrder': '1', 'OrderCount': '1',
                'Order0Ability': 'UpgradeToLair', 'Order0Command': '0', 'CommandExecuting': '0'}
        self.bank['RetentionHeld/AfterCancelState'].update(HasMorphOrder='0', OrderCount='0',
                                                        Order0Ability='', Order0Command='-1')
        self.bank['HeldTrace'] = {'Closed': '1', 'Events': '3'}
        for index in range(1, 4):
            self.bank[f'HeldEvent{index}'] = dict(self.bank[f'Event{index}'])
        self.cycles = [{'case': f'Cycle{index}', 'tag': str(200 + index), 'ability': 'ThorAPMode',
                        'execute_time': str(20 + index * 0.5), 'time': str(20.125 + index * 0.5)}
                       for index in range(129)]

    def require(self, bank=None, cycles=None):
        evidence = self.bank if bank is None else bank
        result = validator.require_retained_process(evidence, self.cycles if cycles is None else cycles)
        validator.verify_case(evidence, 'RetentionHeld', 'Hatchery', 'UpgradeToLair', 'Lair', True)
        return result

    def test_native_current_order_and_unbroken_trace_prove_retention_without_command_state_bit(self):
        result = self.require()
        self.assertEqual(result['events'], 3)
        self.assertTrue(result['native_order_observed_before_and_after_cycles'])

    def test_both_native_cancel_callback_orders_are_allowed(self):
        self.bank['HeldEvent2'], self.bank['HeldEvent3'] = self.bank['HeldEvent3'], self.bank['HeldEvent2']
        self.require()

    def test_actual_order_lifetime_and_identity_are_required_on_both_sides_of_cycles(self):
        changes = [('Exists', '0'), ('Alive', '0'), ('HasMorphOrder', '0'), ('OrderCount', '0'),
                   ('Order0Ability', 'OtherMorph'), ('Order0Command', '1'),
                   ('Tag', '999'), ('Owner', '2'), ('Type', 'Lair')]
        for label in ('StartState', 'BeforeCancelState'):
            for key, value in changes:
                with self.subTest(label=label, key=key):
                    bank = copy.deepcopy(self.bank)
                    bank['RetentionHeld/' + label][key] = value
                    with self.assertRaises(AssertionError):
                        self.require(bank)

    def test_missing_native_observation_or_protocol_metadata_is_rejected(self):
        for label in ('StartState', 'BeforeCancelState', 'AfterCancelState'):
            with self.subTest(missing=label):
                bank = copy.deepcopy(self.bank)
                del bank['RetentionHeld/' + label]
                with self.assertRaises(KeyError):
                    self.require(bank)
        for key in ('Evidence', 'Created'):
            with self.subTest(missing=key):
                bank = copy.deepcopy(self.bank)
                del bank['RetentionHeld'][key]
                with self.assertRaises(KeyError):
                    self.require(bank)
        bank = copy.deepcopy(self.bank)
        del bank['RetentionHeld/BeforeCancelState']['Order0Ability']
        with self.assertRaises(KeyError):
            self.require(bank)

    def test_cancelled_held_process_must_release_its_native_current_order(self):
        for key, value in [('HasMorphOrder', '1'), ('OrderCount', '1'),
                           ('Order0Ability', 'UpgradeToLair'), ('Order0Command', '0')]:
            with self.subTest(key=key):
                bank = copy.deepcopy(self.bank)
                bank['RetentionHeld/AfterCancelState'][key] = value
                with self.assertRaises(AssertionError):
                    self.require(bank)

    def test_trace_must_close_without_missing_events_or_intermediate_end_restart(self):
        for key in ('HeldEvent1', 'HeldEvent2', 'HeldEvent3'):
            with self.subTest(missing=key):
                bank = copy.deepcopy(self.bank)
                del bank[key]
                with self.assertRaises(AssertionError):
                    self.require(bank)
        bank = copy.deepcopy(self.bank)
        bank['HeldTrace']['Closed'] = '0'
        with self.assertRaises(AssertionError):
            self.require(bank)
        for stage in ('-3', '-4', '-5', '-6'):
            with self.subTest(intermediate_or_extra_stage=stage):
                bank = copy.deepcopy(self.bank)
                bank['HeldEvent4'] = dict(bank['HeldEvent1'], Stage=stage, Time='50')
                bank['HeldTrace']['Events'] = '4'
                with self.assertRaises(AssertionError):
                    self.require(bank)

    def test_independent_trace_must_match_the_same_live_tag_ability_owner_and_native_callbacks(self):
        for key, value in [('Case', 'OtherCase'), ('Tag', '999'), ('Ability', 'OtherMorph'),
                           ('Owner', '2'), ('Alive', '0'), ('Time', '100.0625')]:
            with self.subTest(key=key):
                bank = copy.deepcopy(self.bank)
                bank['HeldEvent3'][key] = value
                with self.assertRaises(AssertionError):
                    self.require(bank)

    def test_all_129_cycle_times_must_fall_between_the_native_active_order_observations(self):
        with self.assertRaises(AssertionError):
            self.require(cycles=self.cycles[:-1])
        for label, time in [('StartState', '21'), ('BeforeCancelState', '80'), ('AfterCancelState', '99')]:
            with self.subTest(label=label):
                bank = copy.deepcopy(self.bank)
                bank['RetentionHeld/' + label]['Time'] = time
                with self.assertRaises(AssertionError):
                    self.require(bank)

    def test_one_real_publication_and_rendered_held_target_remain_mandatory(self):
        for section, key, value in [('RetentionHeld', 'AfterMorphs', '0'),
                                    ('RetentionHeld', 'AfterBuildings', '0'),
                                    ('RetentionHeld/After', 'Row0Count', '2'),
                                    ('RetentionHeld/After', 'Row0Icon', 'cancel.dds')]:
            with self.subTest(section=section, key=key):
                bank = copy.deepcopy(self.bank)
                bank[section][key] = value
                with self.assertRaises(AssertionError):
                    self.require(bank)


class MainBankIntegrityTests(unittest.TestCase):
    def test_unfinished_main_bank_is_rejected_before_any_cases_or_fragments_are_consumed(self):
        with patch.object(validator, 'read_bank', return_value={'Finished': {'Done': '0'}}):
            with self.assertRaises(AssertionError):
                validator.verify(Path('unfinished.SC2Bank'), [], [], Path('unused-baseline.json'))

    def test_done_does_not_replace_a_complete_contiguous_trace(self):
        with self.assertRaises(AssertionError):
            validator.finished({'Finished': {'Done': '1', 'Events': '3'}, 'Event1': {}, 'Event3': {}})


class SceneryIsolationEvidenceTests(unittest.TestCase):
    """Declared bank fields prove geometry/lifetime, without simulating SC2."""
    def setUp(self):
        self.bank = {}
        for label, time in [('Before', '100'), ('After', '200'), ('AfterMatrix', '300')]:
            fields = {'Time': time}
            for owner, y in [(1, '61'), (2, '59')]:
                prefix = f'Pylon{owner}'
                fields.update({prefix + 'Tag': str(40 + owner), prefix + 'Owner': str(owner),
                               prefix + 'Type': 'Pylon', prefix + 'Alive': '1',
                               prefix + 'X': '65', prefix + 'Y': y})
            self.bank['SceneryIsolation/' + label] = fields
        self.chunks = {8: {}, 9: {}}
        for link in range(167, 181):
            self.chunks[link // 20][f'Link{link}'] = {'CreatedX': '35', 'CreatedY': '105', 'SavedTime': '150'}

    def require(self):
        return validator.require_scenery_isolation(self.bank, self.chunks)

    def test_original_power_fixtures_and_actual_creation_positions_are_required(self):
        result = self.require()
        self.assertEqual(result['source_links'], list(range(167, 181)))
        self.assertEqual(result['power_tags'], ['41', '42'])

    def test_dead_replaced_moved_or_wrong_power_fixture_is_rejected(self):
        changes = [('Pylon1Alive', '0'), ('Pylon2Tag', '99'), ('Pylon1Owner', '2'),
                   ('Pylon2Type', 'Nexus'), ('Pylon1X', '70')]
        for label in ('After', 'AfterMatrix'):
            for key, value in changes:
                with self.subTest(label=label, key=key):
                    bank = copy.deepcopy(self.bank)
                    bank['SceneryIsolation/' + label][key] = value
                    with self.assertRaises(AssertionError):
                        validator.require_scenery_isolation(bank, self.chunks)

    def test_missing_real_coordinates_or_overlap_with_power_is_rejected(self):
        for key in ('CreatedX', 'CreatedY'):
            with self.subTest(missing=key):
                chunks = copy.deepcopy(self.chunks)
                del chunks[8]['Link173'][key]
                with self.assertRaises(KeyError):
                    validator.require_scenery_isolation(self.bank, chunks)
        self.chunks[8]['Link173'].update(CreatedX='65', CreatedY='61')
        with self.assertRaises(AssertionError):
            self.require()

    def test_missing_late_power_observation_or_unobserved_scenery_interval_is_rejected(self):
        bank = copy.deepcopy(self.bank)
        del bank['SceneryIsolation/AfterMatrix']
        with self.assertRaises(KeyError):
            validator.require_scenery_isolation(bank, self.chunks)
        self.chunks[9]['Link180']['SavedTime'] = '201'
        with self.assertRaises(AssertionError):
            self.require()


class IsolatedBaselineProofTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'isolated.SC2Bank'
        self.entry = copy.deepcopy(json.loads(validator.MATRIX_PATH.read_text())['matrix'][181])
        self.entry['isolated_evidence']['bank'] = str(self.path)
        self.fields = {'Saved': '1', 'NotRecreated': '1',
                       'Evidence': 'baseline-isolated-noncancellable-proof',
                       'Target': self.entry['target'], 'ResolvedTarget': self.entry['target'],
                       'StageCount': str(len(self.entry['stages']))}
        self.fields.update({f'Stage{i}': value for i, value in enumerate(self.entry['stages'])})
        section = self.entry['isolated_evidence']['section']
        common = {'Case': section, 'Tag': '42', 'Ability': self.entry['ability'],
                  'Label': 'Ability', 'Command': '0', 'Time': '8.8125', 'Alive': '1'}
        self.proof = {'Finished': {'Done': '1', 'Events': '19'},
                      section: {'SavedAttemptComplete': '1', 'ExecuteEvents': '1',
                                'CompleteEvents': '1', 'CancelEvents': '0', 'CancelOrderEvents': '0',
                                'DuringCancelHidden': '1', 'DuringCancelDisabled': '1'},
                      'Event0': dict(common, Label='Created', Command='-1', Stage='0')}
        self.proof.update({f'Event{i}': dict(common, Stage=str(i - 2)) for i in range(2, 18)})
        self.proof['Event1'] = dict(common, Stage='-3')
        self.proof['Event18'] = dict(common, Stage='-6', Time='11.75')
        self.fragment = {'Link181': self.fields}
        self.persist()

    def persist(self, rebind_hash=True):
        write_bank(self.path, self.proof)
        if rebind_hash:
            self.entry['isolated_evidence']['sha256'] = hashlib.sha256(self.path.read_bytes()).hexdigest()

    def require(self):
        validator.require_isolated_proof(self.entry, self.fields, self.fragment)

    def test_complete_hashed_isolated_proof_remains_explicitly_baseline_only(self):
        self.require()
        self.assertEqual(self.fields['NotRecreated'], '1')
        self.assertFalse(validator.events(self.fragment, 'Link181'))

    def test_changed_proof_bytes_are_rejected_before_consuming_the_trace(self):
        self.path.write_bytes(self.path.read_bytes() + b'\n')
        with self.assertRaises(AssertionError):
            self.require()

    def test_done_cannot_hide_missing_execute_complete_or_middle_trace_even_with_a_rebound_hash(self):
        for key in ('Event1', 'Event18', 'Event10'):
            with self.subTest(missing=key):
                removed = self.proof.pop(key)
                self.persist()
                with self.assertRaises(AssertionError):
                    self.require()
                self.proof[key] = removed
        self.proof['Finished']['Done'] = '0'
        self.persist()
        with self.assertRaises(AssertionError):
            self.require()

    def test_matching_scalars_cannot_replace_correct_same_attempt_execute_and_complete(self):
        changes = [('Ability', 'OtherMorph'), ('Tag', '999'), ('Command', '1'),
                   ('Case', 'Link182/Default'), ('Stage', '-4'), ('Time', '8')]
        for key, value in changes:
            with self.subTest(key=key):
                previous = self.proof['Event18'][key]
                self.proof['Event18'][key] = value
                self.persist()
                with self.assertRaises(AssertionError):
                    self.require()
                self.proof['Event18'][key] = previous

    def test_current_target_stage_drift_or_fictitious_candidate_runtime_is_rejected(self):
        for key in ('Target', 'ResolvedTarget', 'Stage0'):
            with self.subTest(key=key):
                previous = self.fields[key]
                self.fields[key] = 'OtherTarget'
                with self.assertRaises(AssertionError):
                    self.require()
                self.fields[key] = previous
        self.fragment['Event1'] = {'Case': 'Link181'}
        with self.assertRaises(AssertionError):
            self.require()


if __name__ == '__main__':
    unittest.main()
