"""The evidence validator must go red when real identity/publication proof is lost."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('prism_acceptance_validator', ROOT / 'tools/verify_prism_acceptance.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def single_close_bank():
    case = 'SingleClose'
    before = {'WarpCount': '3', 'Units': '10', 'Warps': '4', 'Prisms': '4', 'ATag': '700'}
    after = {'WarpCount': '3', 'Units': '13', 'Warps': '7', 'Prisms': '7', 'PendingGroups': '0'}
    bank = {'Probe': {'Fixture': 'prism-acceptance-fragment', 'Fragment': case},
            'Finished': {'Done': '1', 'Events': '11'}, case: {'Saved': '1'},
            case + '/Before': before, case + '/Correlated': after}
    for i, object_type in enumerate(('Zealot', 'Stalker', 'Sentry')):
        tag = str(100 + i)
        gate = str(200 + i)
        before.update({f'Warp{i}StartedTag': tag, f'Warp{i}StartedOwner': '1',
                       f'Warp{i}StartedType': object_type, f'Warp{i}Alive': '1',
                       f'Warp{i}Constructing': '1', f'Warp{i}Power': '2',
                       f'Warp{i}FromA': '1', f'Warp{i}FromB': '0', f'Warp{i}FromPylon': '0',
                       f'Warp{i}ExpectedName': object_type,
                       f'Warp{i}ExpectedIcon': validator.expected_icon(object_type)})
        after[f'Warp{i}Alive'] = '0'
        after.update({f'Row{i}Visible': '1', f'Row{i}Owner': '1', f'Row{i}Kind': '2',
                      f'Row{i}Key': object_type, f'Row{i}Count': '1', f'Row{i}Name': object_type,
                      f'Row{i}Icon': validator.expected_icon(object_type), f'Row{i}Status': 'Cancelled',
                      f'Row{i}Remaining': '4.9375'})
        bank[f'{case}/Before/Warp{i}'] = {'Generation': str(i + 1)}
        bank[f'{case}/Correlated/Warp{i}'] = {
            'Generation': str(i + 1), 'Tag': tag, 'Cancelled': '1', 'Decided': '1',
            'Sent': '1', 'Direct': '0', 'End': '12', 'Providers': '1',
            'Provider0Generation': '1', 'Provider0Tag': '700', 'Provider0Alive': '1',
            'Provider0Current': '0', 'Provider0Lost': '1', 'Provider0LostTime': '12',
            'Provider0Death': '0', 'Provider0DeathTime': '12', 'Provider0CloseOrder': '1', 'Provider0CloseExecute': '1',
            'Provider0CloseOrderTime': '12', 'Provider0CloseExecuteTime': '12'}
        bank[f'Event{i + 1}'] = {'Case': case, 'Label': 'Created', 'Time': '11.75',
                                  'UnitTag': tag, 'UnitOwner': '1', 'UnitType': object_type,
                                  'UnitAlive': '1', 'UnitConstructing': '1',
                                  'ProgressTag': gate, 'Detail': 'WarpGateTrain'}
        bank[f'Event{i + 4}'] = {'Case': case, 'Label': 'Order', 'Time': '11.75',
                                  'UnitTag': gate, 'Ability': 'WarpGateTrain', 'Command': str((0, 1, 5)[i])}
        bank[f'Event{i + 9}'] = {'Case': case, 'Label': 'ConstructCancel', 'Time': '12',
                                  'UnitTag': gate, 'UnitAlive': '1', 'ProgressTag': tag,
                                  'Detail': object_type}
    for number, label in ((7, 'Ability'), (8, 'Order')):
        bank[f'Event{number}'] = {'Case': case, 'Label': label, 'Time': '12',
                                   'UnitTag': '700', 'UnitAlive': '1', 'Ability': 'TransportMode',
                                   'Command': '0', 'Stage': '-3' if label == 'Ability' else '0'}
    return bank


def direct_variant_bank():
    """Synthetic protocol checks; actual engine proof remains verify_case's job."""
    case = 'DirectOnly'
    return {case: {'EvidenceMode': 'real-engine-fixture-xml-cancellable-variant',
                   'FixtureCancelable': '1', 'FixtureCancelReady': '1',
                   'FixtureCancelChildLive': '1',
                   'FixtureCancelHidden': '0', 'FixtureCancelDisabled': '0', 'FixtureCancelPolls': '1',
                   'DirectAccepted': '1'}}


def stock_negative_bank():
    """Synthetic negative-protocol input, not a substitute for v101 artifacts."""
    ready = {'Ready': '1', 'Time': '8.1875', 'ChildTag': '100', 'GateTag': '200',
             'ChildAlive': '1', 'ChildConstructing': '1', 'ChildSelected1': '1',
             'ChildType': 'Zealot', 'FromPrism': '1', 'Power': '2',
             'QueueUsed': '0', 'ProducerQueueCancelHidden': '1',
             'Units': '0', 'Warps': '0', 'Prisms': '0', 'CancelEvents': '0', 'CompleteEvents': '0'}
    return {'Probe': {'Fixture': 'prism-direct-order-probe', 'StartAccepted': '1'},
            'Finished': {'Done': '1', 'Events': '2', 'FailedToStart': '0', 'ObservationElapsed': '1'},
            'ProbeReady': ready, 'After': dict(ready, Time='28.4375'),
            'Abilities': {'WarpableCancelConstant': '0'},
            'CatalogAbility3': {'Ability': 'Warpable', 'Cancelable': '0', 'CancelHidden': '1',
                                'Class': '36', 'Exists': '1', 'Enabled': '1', 'CancelCommand': '0'},
            'Event1': {'Label': 'Created', 'Time': '8', 'ChildTag': '100', 'SourceTag': '200',
                       'Detail': 'WarpGateTrain', 'ChildAlive': '1', 'ChildConstructing': '1'},
            'Event2': {'Label': 'Order', 'Time': '8', 'Ability': 'WarpGateTrain',
                       'SourceTag': '200', 'Command': '0'}}


def stock_escape():
    return {'key': 'Escape', 'selected_tag': '100', 'ready_game_time': '8.1875',
            'pid': 123, 'epoch': 1792410077, 'input': 'Exact workspace5/PID scoped XTest'}


def cleanup_protocol_bank():
    """Synthetic lifecycle boundary input; not real engine acceptance evidence."""
    case = 'SingleClose'
    fields = {'Policy': 'credited-children-before-providers', 'Done': '1',
              'RemainingLive': '0', 'Targets': '2', 'Started': '20', 'ChildrenDone': '20.125',
              'ProvidersStarted': '20.125', 'ProvidersDone': '20.25', 'Finished': '20.4375'}
    for metric in ('Units', 'Warps', 'Prisms'):
        fields[metric + 'Before'] = fields[metric + 'After'] = '3'
    bank = {'Probe': {'Fragment': case}, 'SingleClose/Cleanup': fields,
            'Finished': {'DeathClosed': '1', 'DeathOverflow': '0', 'DeathEvents': '2'}}
    for index, (object_type, phase, when) in enumerate((('Zealot', 'children', '20'),
                                                       ('WarpGate', 'providers', '20.125'))):
        prefix = f'Target{index}'
        tag = str(100 + index)
        fields.update({prefix + 'Tag': tag, prefix + 'Phase': phase, prefix + 'Time': when,
                       prefix + 'Type': object_type, prefix + 'Owner': '1',
                       prefix + 'Present': '1', prefix + 'Alive': '1', prefix + 'Ready': '1',
                       prefix + 'AttackerTag': '900'})
        bank[f'Death{index + 1}'] = {'Case': case, 'Phase': phase, 'Time': when,
                                    'UnitTag': tag, 'UnitOwner': '1', 'UnitType': object_type,
                                    'UnitAlive': '0', 'UnitPresent': '1', 'KillingPlayer': '2',
                                    'KillingTag': '900', 'Removed': '0'}
    return bank


class CleanupLifecycleEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.bank = cleanup_protocol_bank()

    def test_real_credited_targets_close_without_extra_cancellation_counts(self):
        result = validator.verify_death_lifecycle(self.bank)
        self.assertEqual(result, {'deaths': 2, 'credited_cleanup_targets': 2, 'closed': True})

    def test_terminal_flags_cannot_hide_a_missing_extra_or_duplicate_death(self):
        for key, value in (('DeathClosed', '0'), ('DeathOverflow', '1'), ('DeathEvents', '3')):
            with self.subTest(key=key):
                bank = copy.deepcopy(self.bank)
                bank['Finished'][key] = value
                with self.assertRaises(AssertionError):
                    validator.verify_death_lifecycle(bank)
        for mutation in ('missing', 'duplicate', 'extra'):
            with self.subTest(mutation=mutation):
                bank = copy.deepcopy(self.bank)
                if mutation == 'missing':
                    del bank['Death2']
                elif mutation == 'duplicate':
                    bank['Death2']['UnitTag'] = '100'
                else:
                    bank['Death3'] = dict(bank['Death2'], UnitTag='999')
                with self.assertRaises(AssertionError):
                    validator.verify_death_lifecycle(bank)

    def test_neutral_removed_wrong_killer_or_wrong_phase_cleanup_is_red(self):
        changes = [('KillingPlayer', '0'), ('KillingTag', '0'), ('KillingPlayer', '1'),
                   ('UnitTag', '999'), ('Phase', ''), ('Removed', '1'),
                   ('UnitAlive', '1'), ('Time', '20.1875')]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                bank = copy.deepcopy(self.bank)
                bank['Death1'][key] = value
                with self.assertRaises(AssertionError):
                    validator.verify_death_lifecycle(bank)

    def test_unsettled_children_extra_alerts_or_live_cleanup_targets_are_red(self):
        changes = [('UnitsAfter', '4'), ('WarpsAfter', '4'), ('PrismsAfter', '4'),
                   ('RemainingLive', '1'), ('Done', '0'), ('Target0Ready', '0'),
                   ('ChildrenDone', '20'), ('ProvidersStarted', '20'), ('Targets', '1'),
                   ('Target0Time', '20.125')]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                bank = copy.deepcopy(self.bank)
                bank['SingleClose/Cleanup'][key] = value
                with self.assertRaises(AssertionError):
                    validator.verify_death_lifecycle(bank)

    def test_independent_trace_must_bind_actual_scenario_provider_death(self):
        bank = copy.deepcopy(self.bank)
        bank['Death3'] = dict(bank['Death2'], UnitTag='700', UnitType='Pylon', Phase='', Time='19')
        bank['Finished']['DeathEvents'] = '3'
        # Keep actual callback order monotonic while making the provider's
        # scenario trace and independent trace disagree on the killer.
        bank['Death1'], bank['Death2'], bank['Death3'] = bank['Death3'], bank['Death1'], bank['Death2']
        bank['Event1'] = dict(bank['Death1'], Label='ProviderDied')
        validator.verify_death_lifecycle(bank)
        bank['Event1']['KillingPlayer'] = '0'
        with self.assertRaises(AssertionError):
            validator.verify_death_lifecycle(bank)


class FocusedEngineEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.bank = single_close_bank()

    def test_closed_complete_single_case_has_an_explicitly_focused_result(self):
        result = validator.verify_single_close(self.bank)
        self.assertEqual(result['case']['published'], 3)
        self.assertIn('Focused', result['scope'])

    def test_done_does_not_replace_created_cancel_execute_or_order_events(self):
        for key in ('Event1', 'Event4', 'Event7', 'Event8', 'Event9'):
            with self.subTest(missing=key):
                bank = copy.deepcopy(self.bank)
                del bank[key]
                with self.assertRaises(AssertionError):
                    validator.verify_single_close(bank)

    def test_wrong_child_producer_source_time_or_loss_reason_is_red(self):
        changes = [('Event1', 'UnitTag', '999'), ('Event9', 'ProgressTag', '999'),
                   ('Event9', 'UnitTag', '999'), ('Event7', 'UnitTag', '999'),
                   ('Event8', 'Time', '11'), ('Event7', 'Stage', '-6'),
                   ('SingleClose/Correlated/Warp0', 'Provider0Death', '1'),
                   ('SingleClose/Correlated/Warp0', 'Provider0LostTime', '11'),
                   ('SingleClose/Correlated/Warp0', 'Provider0Current', '1'),
                   ('SingleClose/Correlated/Warp0', 'Generation', '999')]
        for section, key, value in changes:
            with self.subTest(section=section, key=key):
                bank = copy.deepcopy(self.bank)
                bank[section][key] = value
                with self.assertRaises(AssertionError):
                    validator.verify_single_close(bank)

    def test_disabled_publication_wrong_count_target_category_or_timer_is_red(self):
        changes = [('SingleClose/Correlated', 'Units', '10'),
                   ('SingleClose/Correlated', 'Warps', '4'),
                   ('SingleClose/Correlated', 'Prisms', '4'),
                   ('SingleClose/Correlated/Warp0', 'Sent', '0'),
                   ('SingleClose/Correlated', 'Row0Key', 'WarpPrism'),
                   ('SingleClose/Correlated', 'Row0Kind', '0'),
                   ('SingleClose/Correlated', 'Row0Owner', '2'),
                   ('SingleClose/Correlated', 'Row0Count', '2'),
                   ('SingleClose/Correlated', 'Row0Remaining', '0')]
        for section, key, value in changes:
            with self.subTest(section=section, key=key):
                bank = copy.deepcopy(self.bank)
                bank[section][key] = value
                with self.assertRaises(AssertionError):
                    validator.verify_single_close(bank)

    def test_matching_fake_icon_in_both_ui_and_runtime_expectation_is_red(self):
        self.bank['SingleClose/Before']['Warp0ExpectedIcon'] = 'cancel.dds'
        self.bank['SingleClose/Correlated']['Row0Icon'] = 'cancel.dds'
        with self.assertRaises(AssertionError):
            validator.verify_single_close(self.bank)

    def test_later_actual_source_death_does_not_erase_an_earlier_cancel(self):
        for i in range(3):
            fields = self.bank[f'SingleClose/Correlated/Warp{i}']
            fields['Provider0Death'] = '1'
            fields['Provider0DeathTime'] = '12.0625'
            fields['Provider0Alive'] = '0'
        self.bank['Event12'] = {'Case': 'SingleClose', 'Label': 'ProviderDied',
                                'UnitTag': '700', 'Time': '12.0625', 'UnitAlive': '0',
                                'UnitType': 'WarpPrism', 'UnitOwner': '1', 'KillingPlayer': '2', 'KillingTag': '900'}
        self.bank['Finished']['Events'] = '12'
        self.assertEqual(validator.verify_single_close(self.bank)['case']['published'], 3)
        self.bank['SingleClose/Correlated/Warp0']['Provider0DeathTime'] = '12'
        with self.assertRaises(AssertionError):
            validator.verify_single_close(self.bank)

    def test_a_finished_scalar_cannot_hide_a_missing_or_duplicate_trace_event(self):
        self.bank['Finished']['Events'] = '12'
        with self.assertRaises(AssertionError):
            validator.verify_single_close(self.bank)


class DirectVariantProtocolTests(unittest.TestCase):
    def setUp(self):
        self.bank = direct_variant_bank()

    def test_xml_variant_is_not_mislabelled_as_an_actual_stock_manual_action(self):
        result = validator.verify_direct_variant(self.bank, 'DirectOnly')
        self.assertIn('fixture-only', result['positive'])
        self.assertIn('Separate SHA-paired', result['stock'])

    def test_loaded_value_and_real_command_availability_must_be_explicit(self):
        changes = [('EvidenceMode', 'stock-manual-action'),
                   ('FixtureCancelable', '0'), ('DirectAccepted', '0'),
                   ('FixtureCancelReady', '0'), ('FixtureCancelChildLive', '0'), ('FixtureCancelHidden', '1'),
                   ('FixtureCancelDisabled', '1'), ('FixtureCancelPolls', '0')]
        for key, value in changes:
            with self.subTest(key=key):
                bank = copy.deepcopy(self.bank)
                bank['DirectOnly'][key] = value
                with self.assertRaises(AssertionError):
                    validator.verify_direct_variant(bank, 'DirectOnly')


class StockNegativeProtocolTests(unittest.TestCase):
    def setUp(self):
        self.bank = stock_negative_bank()
        self.escape = stock_escape()

    def test_real_selected_child_survives_actual_escape_in_stock_data(self):
        self.assertEqual(validator.verify_stock_negative(self.bank, self.escape)['tag'], '100')

    def test_stock_child_must_survive_full_observation_without_publication(self):
        changes = [('Time', '8.25'), ('Units', '1'), ('Warps', '1'), ('Prisms', '1'),
                   ('CancelEvents', '1'), ('CompleteEvents', '1'), ('ChildTag', '999'),
                   ('ChildAlive', '0'), ('ChildConstructing', '0'), ('ChildSelected1', '0')]
        for key, value in changes:
            with self.subTest(key=key):
                bank = copy.deepcopy(self.bank)
                bank['After'][key] = value
                with self.assertRaises(AssertionError):
                    validator.verify_stock_negative(bank, self.escape)

    def test_stock_trace_cannot_hide_real_order_cancel_or_missing_created(self):
        for label in ('Order', 'ConstructCancel', 'ConstructComplete'):
            with self.subTest(label=label):
                bank = copy.deepcopy(self.bank)
                bank['Event3'] = {'Label': label, 'Time': '9', 'Ability': 'Warpable'}
                bank['Finished']['Events'] = '3'
                with self.assertRaises(AssertionError):
                    validator.verify_stock_negative(bank, self.escape)
        self.bank['Event1']['ChildTag'] = '999'
        with self.assertRaises(AssertionError):
            validator.verify_stock_negative(self.bank, self.escape)

    def test_stock_data_and_real_input_identity_must_match(self):
        for key, value in (('Cancelable', '1'), ('CancelHidden', '0')):
            with self.subTest(key=key):
                bank = copy.deepcopy(self.bank)
                bank['CatalogAbility3'][key] = value
                with self.assertRaises(AssertionError):
                    validator.verify_stock_negative(bank, self.escape)
        for key, value in (('key', 'Cancel'), ('selected_tag', '999'), ('ready_game_time', '0'), ('pid', 0)):
            with self.subTest(key=key):
                escape = dict(self.escape, **{key: value})
                with self.assertRaises(AssertionError):
                    validator.verify_stock_negative(self.bank, escape)


class DataVariantProvenanceTests(unittest.TestCase):
    def test_variant_requires_identical_production_and_exact_private_data_hash(self):
        hashes = {name: validator.hashlib.sha256((ROOT / 'source' / name).read_bytes()).hexdigest()
                  for name in json.loads((ROOT / 'tools/galaxy_sources.json').read_text())}
        stock = {'Recorded': '1', 'fixture': 'prism-direct-order-probe',
                 'canonical_galaxy_sha256': 'canonical', 'canonical_file_sha256': '{}',
                 'module_sha256': json.dumps(hashes), 'dependencies': '["VoidMulti"]'}
        candidate = dict(stock, fixture='prism-acceptance', fixture_data_sha256=json.dumps({
            validator.PRIVATE_DATA: validator.hashlib.sha256((ROOT / validator.PRIVATE_DATA).read_bytes()).hexdigest()}))
        validator.verify_variant_provenance(candidate, stock)
        for key, value in (('canonical_galaxy_sha256', 'other'), ('module_sha256', '{}'),
                           ('canonical_file_sha256', '{"changed": "data"}'), ('fixture_data_sha256', '{}')):
            with self.subTest(key=key):
                broken = dict(candidate, **{key: value})
                with self.assertRaises(AssertionError):
                    validator.verify_variant_provenance(broken, stock)
        with self.assertRaises(AssertionError):
            validator.verify_variant_provenance(candidate, dict(stock, fixture_data_sha256=candidate['fixture_data_sha256']))

    def test_full_stock_pair_cannot_be_omitted(self):
        with self.assertRaises(AssertionError):
            validator.verify_stock_pair(None, None, None, Path('main.SC2Bank'))

    def test_fresh_stock_capture_and_real_input_keep_explicit_sha_anchors(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory)
            manifest = capture / 'original-capture.json'
            manifest.write_text('{"revision":"newStockRevision"}')
            escape = capture / 'actual-esc.json'
            escape.write_text('{"key":"Escape","pid":123}')
            manifest_hash = validator.hashlib.sha256(manifest.read_bytes()).hexdigest()
            escape_hash = validator.hashlib.sha256(escape.read_bytes()).hexdigest()
            validator.verify_stock_hash_binding(capture, escape, manifest_hash, escape_hash)
            for path in (manifest, escape):
                original = path.read_bytes()
                path.write_bytes(original + b'changed')
                with self.subTest(path=path), self.assertRaises(AssertionError):
                    validator.verify_stock_hash_binding(capture, escape, manifest_hash, escape_hash)
                path.write_bytes(original)
            with self.assertRaises(AssertionError):
                validator.verify_stock_hash_binding(capture, escape, None, None)


class ProviderDeathEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.proof = copy.deepcopy(single_close_bank()['SingleClose/Correlated/Warp0'])
        self.proof.update(End='12.0625', Provider0Death='1', Provider0DeathTime='12',
                          Provider0Alive='0', Provider0CloseOrder='0', Provider0CloseExecute='0')
        self.trace = [{'Label': 'ProviderDied', 'UnitTag': '700', 'Time': '12', 'UnitAlive': '0',
                       'UnitType': 'Pylon', 'UnitOwner': '1', 'KillingPlayer': '2', 'KillingTag': '900'}]

    def test_actual_credited_death_can_cancel_on_its_following_tick_without_order(self):
        validator.verify_power_evidence(self.proof, self.trace)
        self.proof['End'] = '12'
        validator.verify_power_evidence(self.proof, self.trace)

    def test_missing_wrong_or_neutral_death_never_replaces_engine_evidence(self):
        with self.assertRaises(AssertionError):
            validator.verify_power_evidence(self.proof, [])
        for key, value in (('UnitTag', '999'), ('Time', '11'), ('UnitAlive', '1'),
                           ('KillingPlayer', '0'), ('KillingTag', '0')):
            with self.subTest(key=key):
                trace = [dict(self.trace[0], **{key: value})]
                with self.assertRaises(AssertionError):
                    validator.verify_power_evidence(self.proof, trace)

    def test_live_power_removed_handle_or_outside_tick_cannot_publish(self):
        changes = [('Provider0Current', '1'), ('Provider0Death', '0'),
                   ('Provider0Lost', '0'), ('Provider0LostTime', '11'), ('End', '12.125')]
        for key, value in changes:
            with self.subTest(key=key):
                proof = dict(self.proof, **{key: value})
                with self.assertRaises(AssertionError):
                    validator.verify_power_evidence(proof, self.trace)


class MomentEvidenceTests(unittest.TestCase):
    def moment(self, case, close_time):
        bank = {case: {'CreatedTime': '20', 'NaturalDuration': '5'},
                case + '/Before': {'WarpCount': '1', 'Warp0Alive': '1', 'Warp0Constructing': '1',
                                   'Warp0StartedTag': '100', 'Warp0Progress': '100', 'ATag': '700'},
                'Event1': {'Case': case, 'Label': 'Created', 'UnitTag': '100', 'UnitType': 'Zealot', 'Time': '20'}}
        for number, label in ((2, 'Ability'), (3, 'Order')):
            bank[f'Event{number}'] = {'Case': case, 'Label': label, 'Ability': 'TransportMode',
                                     'Command': '0', 'Stage': '-3', 'UnitTag': '700',
                                     'UnitAlive': '1', 'Time': close_time}
        return bank

    def natural(self):
        return {'Event1': {'Case': 'NaturalComplete', 'Label': 'Created', 'UnitTag': '1000',
                           'ProgressTag': '2000', 'UnitType': 'Zealot', 'Time': '10'},
                'Event2': {'Case': 'NaturalComplete', 'Label': 'ConstructComplete',
                           'ProgressTag': '1000', 'UnitTag': '2000', 'Detail': 'Zealot', 'Time': '15'}}

    def test_getter_100_does_not_hide_real_early_or_late_physical_timing(self):
        validator.verify_moment(self.moment('Moment0', '20.0625'), 'Moment0')
        validator.verify_moment(self.moment('Moment1', '24'), 'Moment1', self.natural())

    def test_late_close_requires_real_completion_reference_and_active_child(self):
        bank = self.moment('Moment1', '24')
        for key, value in (('WarpCount', '0'), ('Warp0Alive', '0'), ('Warp0Constructing', '0')):
            with self.subTest(key=key, value=value):
                broken = copy.deepcopy(bank)
                broken['Moment1/Before'][key] = value
                with self.assertRaises(AssertionError):
                    validator.verify_moment(broken, 'Moment1', self.natural())
        for time in ('20.0625', '23.9375', '25'):
            with self.subTest(time=time), self.assertRaises(AssertionError):
                validator.verify_moment(self.moment('Moment1', time), 'Moment1', self.natural())
        with self.assertRaises(AssertionError):
            validator.verify_moment(bank, 'Moment1', {'Event1': self.natural()['Event1']})
        with self.assertRaises(AssertionError):
            validator.verify_moment(self.moment('Moment0', '20.1875'), 'Moment0')

    def test_authorized_late_failure_stays_fail_manual_pending_and_other_cases_stay_strict(self):
        with patch.object(validator, 'verify_case', side_effect=AssertionError('actual late evidence failed')):
            result = validator.verify_standard_case({}, 'Moment1', (), {}, allow_late_manual=True)
            self.assertEqual((result['result'], result['manual']), ('FAIL', 'PENDING'))
            with self.assertRaises(AssertionError):
                validator.verify_standard_case({}, 'Moment1', (), {})
            with self.assertRaises(AssertionError):
                validator.verify_standard_case({}, 'Moment0', (), {}, allow_late_manual=True)


class FullFixtureIntegrityTests(unittest.TestCase):
    def test_unfinished_main_is_rejected_before_fragments_are_consumed(self):
        bank = {'Probe': {'Fixture': 'prism-acceptance'}, 'Finished': {'Done': '0'}}
        with patch.object(validator, 'read_bank', return_value=bank):
            with self.assertRaises(AssertionError):
                validator.verify(Path('main.SC2Bank'), [])

    def test_every_exact_revision_fragment_is_required(self):
        bank = {'Probe': {'Fixture': 'prism-acceptance'},
                'Finished': {'Done': '1', 'Fragments': '2'},
                'Fragments': {'Bank0': 'New_SingleClose', 'Bank1': 'New_Retention0'}}
        with patch.object(validator, 'read_bank', return_value=bank):
            for paths in ([Path('New_SingleClose.SC2Bank')],
                          [Path('New_SingleClose.SC2Bank'), Path('Old_Retention0.SC2Bank')],
                          [Path('New_SingleClose.SC2Bank'), Path('New_SingleClose.SC2Bank')]):
                with self.subTest(paths=paths):
                    with self.assertRaises(AssertionError):
                        validator.verify(Path('main.SC2Bank'), paths)


if __name__ == '__main__':
    unittest.main()
