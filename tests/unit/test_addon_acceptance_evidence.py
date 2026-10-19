"""Acceptance validators reject missing engine evidence and misleading UI counts."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import verify_addon_acceptance as validator


class AddonPairEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.case = 'SingleStarportTechLabParent'
        self.trace = [
            {'Label': 'Created', 'Case': self.case, 'Time': '8', 'UnitTag': '10',
             'ProgressTag': '20', 'Ability': 'StarportAddOns', 'Command': '0', 'Object': 'StarportTechLab'},
            {'Label': 'Order', 'Case': self.case, 'Time': '9', 'UnitTag': '10',
             'ProgressTag': '0', 'Ability': 'StarportAddOns', 'Command': '30', 'Object': ''},
            {'Label': 'ConstructCancel', 'Case': self.case, 'Time': '9', 'UnitTag': '10',
             'ProgressTag': '20', 'Ability': '', 'Command': '0', 'Object': 'StarportTechLab'},
        ]

    def pair(self, trace=None, child_route=False):
        return validator.require_pair(self.trace if trace is None else trace,
                                      self.case, '20', '10', 'StarportTechLab', child_route)

    def test_both_callback_orders_preserve_the_same_attempt(self):
        self.assertEqual(self.pair()['child_tag'], '20')
        self.assertEqual(self.pair([self.trace[0], self.trace[2], self.trace[1]])['child_tag'], '20')

    def test_child_route_requires_the_childs_explicit_cancel(self):
        trace = copy.deepcopy(self.trace)
        trace[1].update(UnitTag='20', Ability='BuildInProgress', Command='0')
        self.assertEqual(self.pair(trace, child_route=True)['route'], 'child')
        with self.assertRaises(AssertionError):
            self.pair(trace, child_route=False)

    def test_missing_creation_or_construct_cancel_cannot_pass_by_order_acceptance(self):
        for index in (0, 2):
            with self.subTest(omitted=index), self.assertRaises(AssertionError):
                self.pair([event for position, event in enumerate(self.trace) if position != index])

    def test_ability_complete_is_not_a_construct_cancel(self):
        trace = copy.deepcopy(self.trace)
        trace[2].update(Label='Ability', Stage='-6')
        with self.assertRaises(AssertionError):
            self.pair(trace)

    def test_parent_child_type_ability_and_exact_mission_time_must_match(self):
        changes = [(0, 'UnitTag', '11'), (0, 'Ability', 'FactoryAddOns'),
                   (2, 'UnitTag', '11'), (2, 'ProgressTag', '21'),
                   (2, 'Object', 'FactoryTechLab'), (1, 'Time', '9.0625'),
                   (1, 'Ability', 'TerranBuild'), (1, 'Command', '0')]
        for index, key, value in changes:
            with self.subTest(index=index, key=key):
                trace = copy.deepcopy(self.trace)
                trace[index][key] = value
                with self.assertRaises(AssertionError):
                    self.pair(trace)

    def test_duplicate_child_cancel_is_rejected(self):
        with self.assertRaises(AssertionError):
            self.pair(self.trace + [self.trace[2]])

    def test_missing_tail_of_trace_is_rejected_even_when_finished_says_done(self):
        bank = {'Finished': {'Done': '1', 'Events': '3'}, 'Event1': self.trace[0], 'Event3': self.trace[2]}
        with self.assertRaises(AssertionError):
            validator.checked_trace(bank)


class AddonFocusedCaseTests(unittest.TestCase):
    def setUp(self):
        AddonPairEvidenceTests.setUp(self)
        self.bank = {
            self.case: {'Count': '1', 'TimedOut': '0', 'SelectChildren': '0', 'Started0': '1',
                        'OriginalChild0Type': 'StarportTechLab', 'OriginalChild0Tag': '20',
                        'Parent0Tag': '10', 'OriginalChildIcon0': 'starport-techlab.dds'},
            self.case + '/Ready': {'Remaining': '1', 'Child0Type': 'StarportTechLab',
                                   'Child0Alive': '1', 'Child0Constructing': '1', 'Child0Tag': '20', 'Child0Owner': '1',
                                   'ChildSelected0': '0', 'ParentSelected0': '1',
                                   'Buildings': '0', 'Units': '0'},
            self.case + '/After': {'Remaining': '0', 'Child0Alive': '0', 'Buildings': '1', 'Units': '0',
                                   'Row0Visible': '1', 'Row1Visible': '0', 'Row2Visible': '0',
                                   'Row0Key': 'StarportTechLab', 'Row0Name': 'Tech Lab - Starport',
                                   'Row0Status': 'Cancelled', 'Row0Count': '1',
                                   'Row0Icon': 'starport-techlab.dds', 'Row0Remaining': '4.5', 'Row0Owner': '1', 'Row0Kind': '0'},
        }
        self.inputs = [{'case': self.case, 'key': 'Escape'}]

    def test_focused_case_checks_one_completed_real_escape_without_claiming_full_fixture(self):
        result = validator.verify_group_case(self.bank, self.case, self.inputs, self.trace)
        self.assertEqual(result['cancellations'], 1)
        self.assertNotIn('result', result)

    def test_disabled_parent_halt_path_is_red_despite_real_engine_cancel(self):
        self.bank[self.case + '/After']['Buildings'] = '0'
        with self.assertRaises(AssertionError):
            validator.verify_group_case(self.bank, self.case, self.inputs, self.trace)

    def test_no_real_escape_log_cannot_pass(self):
        with self.assertRaises(AssertionError):
            validator.verify_group_case(self.bank, self.case, [], self.trace)

    def test_generic_old_name_wrong_icon_and_double_popup_counter_fail(self):
        for key, value in [('Row0Name', 'Tech Lab'), ('Row0Icon', 'cancel.dds'),
                           ('Buildings', '2'), ('Row0Status', 'Cancelled ×2'), ('Row0Remaining', '0'),
                           ('Row0Owner', '2'), ('Row0Kind', '2')]:
            with self.subTest(key=key):
                bank = copy.deepcopy(self.bank)
                bank[self.case + '/After'][key] = value
                with self.assertRaises(AssertionError):
                    validator.verify_group_case(bank, self.case, self.inputs, self.trace)


class AddonRetentionFragmentTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {'RetentionHeld': {f'Chunk{i}': f'Candidate_Retention{i}' for i in range(4)}}
        self.paths = [Path(f'copied-fragment-{i}.SC2Bank') for i in range(4)]
        self.fragments = {}
        for chunk, path in enumerate(self.paths):
            start, end = chunk * 40, min((chunk + 1) * 40, 129)
            fragment = {'Probe': {'Chunk': str(chunk), 'BankName': f'Candidate_Retention{chunk}'},
                        'Finished': {'Done': '1', 'NextCycle': str(end), 'Events': str(end - start)}}
            fragment.update({f'Event{i - start + 1}': {'Case': f'Cycle{i}'} for i in range(start, end)})
            self.fragments[path] = fragment

    def chunks(self, paths=None):
        from unittest.mock import patch
        with patch.object(validator, 'read', side_effect=lambda path: self.fragments[path]):
            return validator.retention_chunks(self.manifest, self.paths if paths is None else paths)

    def test_copied_filenames_are_allowed_when_runtime_names_match_the_manifest(self):
        self.assertEqual(set(self.chunks()), set(range(4)))

    def test_missing_or_duplicate_chunks_cannot_pass_by_done_scalar(self):
        with self.assertRaises(AssertionError):
            self.chunks(self.paths[:3])
        with self.assertRaises(AssertionError):
            self.chunks([*self.paths[:3], self.paths[0]])

    def test_unfinished_retention_fragment_is_rejected_with_a_complete_trace(self):
        self.fragments[self.paths[0]]['Finished']['Done'] = '0'
        with self.assertRaises(AssertionError):
            self.chunks()

    def test_wrong_revision_missing_case_or_truncated_trace_is_rejected(self):
        changes = [('Probe', 'BankName', 'OlderCandidate_Retention0'),
                   ('Finished', 'NextCycle', '39'), ('Finished', 'Events', '41')]
        for section, key, value in changes:
            with self.subTest(key=key):
                old = self.fragments[self.paths[0]][section][key]
                self.fragments[self.paths[0]][section][key] = value
                with self.assertRaises(AssertionError):
                    self.chunks()
                self.fragments[self.paths[0]][section][key] = old


class AddonFinishedAndLiftEvidenceTests(unittest.TestCase):
    def test_unfinished_main_bank_is_rejected_before_any_case_or_input_is_consumed(self):
        from unittest.mock import patch
        with patch.object(validator, 'read', return_value={'Finished': {'Done': '0'}}):
            with self.assertRaises(AssertionError):
                validator.verify(Path('unfinished.SC2Bank'), Path('unused-input.json'), [])

    def setUp(self):
        self.bank = {
            'NegativeComplete': {'ParentTag': '10', 'ChildTag': '20', 'ChildType': 'StarportTechLab',
                                 'ChildAliveAfter': '1', 'ChildConstructingAfter': '0'},
            'NegativeLift': {'ParentTag': '10', 'ChildTag': '20', 'ChildType': 'StarportTechLab',
                             'ParentType': 'Starport', 'ParentTypeAfter': 'StarportFlying',
                             'ParentAlive': '1', 'LiftAccepted': '1', 'ChildAlive': '1',
                             'ChildAliveAfter': '1', 'ChildConstructing': '0', 'ChildConstructingAfter': '0'},
            'NegativeLift/Before': {'Buildings': '67', 'Units': '0'},
            'NegativeLift/After': {'Buildings': '67', 'Units': '0'},
        }
        self.trace = [{'Label': 'ConstructComplete', 'Case': 'NegativeComplete',
                       'UnitTag': '10', 'ProgressTag': '20'}]

    def test_completed_addon_survives_actual_lift_without_counter_delta(self):
        validator.verify_lift_case(self.bank, self.trace)

    def test_accepted_order_does_not_substitute_for_a_flying_parent_and_completed_child(self):
        for key, value in [('ParentTypeAfter', 'Starport'), ('ChildConstructing', '1'),
                           ('ChildConstructingAfter', '1'), ('ChildAliveAfter', '0'),
                           ('ParentTag', '11'), ('ChildTag', '21')]:
            with self.subTest(key=key):
                bank = copy.deepcopy(self.bank)
                bank['NegativeLift'][key] = value
                with self.assertRaises(AssertionError):
                    validator.verify_lift_case(bank, self.trace)

    def test_missing_completion_engine_cancel_or_counter_growth_is_rejected(self):
        with self.assertRaises(AssertionError):
            validator.verify_lift_case(self.bank, [])
        with self.assertRaises(AssertionError):
            validator.verify_lift_case(self.bank, self.trace + [
                {'Label': 'ConstructCancel', 'Case': 'NegativeLift', 'UnitTag': '10', 'ProgressTag': '20'}])
        self.bank['NegativeLift/After']['Buildings'] = '68'
        with self.assertRaises(AssertionError):
            validator.verify_lift_case(self.bank, self.trace)


if __name__ == '__main__':
    unittest.main()
