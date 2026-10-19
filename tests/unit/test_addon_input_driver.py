"""Input protocol guards and timing evidence, without any UI/native calls."""
import copy
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import drive_addon_acceptance as driver


def ready_bank():
    case = 'ThreeFacilitiesTechLabParent'
    ready = {'Remaining': '3', 'GameSpeed': '0'}
    for index, object_type in enumerate(driver.GROUPS[case]):
        ready.update({f'Child{index}Type': object_type, f'Child{index}Alive': '1',
                      f'Child{index}Constructing': '1', f'Child{index}Tag': str(index + 10),
                      f'ParentSelected{index}': '1'})
    return {'Probe': {'Fixture': 'addon-acceptance'},
            'Pending': {'Case': case, 'Ready': '1', 'Remaining': '3',
                        'Time': '20', 'GameSpeed': '0', 'GameRate': '0.6'},
            case: {'Count': '3', 'SelectChildren': '0'}, case + '/Ready': ready}


def restored_bank():
    bank = {}
    for case in driver.GROUPS:
        bank[case] = {'OriginalSpeed': '4', 'RestoredSpeed': '4', 'RestoredTime': '22'}
        bank[case + '/Ready'] = {'GameSpeed': '0'}
        bank[case + '/After'] = {'GameSpeed': '0', 'Time': '22'}
        bank[case + '/Expired'] = {'GameSpeed': '4', 'Time': '28'}
    bank['NegativeChildDeath/Before'] = {'GameSpeed': '4'}
    bank['RetentionHeld/After'] = {'GameSpeed': '4'}
    bank['Event900'] = {'Case': 'NegativeComplete', 'GameSpeed': '4'}
    bank['Pending'] = {'Ready': '0', 'Remaining': '0', 'GameSpeed': '0'}
    return bank


class ReadinessAndProgressTests(unittest.TestCase):
    def setUp(self):
        self.bank = ready_bank()
        self.before = driver.ready_context(self.bank)

    def test_real_fixture_selection_and_slower_metadata_are_required(self):
        self.assertEqual(self.before['count'], 3)
        self.assertEqual(self.before['selected'], 'parents')
        mutations = [('Probe', 'Fixture', 'other'), ('Pending', 'Ready', '0'),
                     ('Pending', 'Remaining', '0'), ('Pending', 'GameSpeed', '4'),
                     ('Pending', 'GameRate', 'nan'), ('Pending', 'Time', 'inf'),
                     (self.before['case'] + '/Ready', 'Child0Constructing', '0'),
                     (self.before['case'] + '/Ready', 'ParentSelected0', '0'),
                     (self.before['case'] + '/Ready', 'Child0Type', 'StarportReactor')]
        for section, key, value in mutations:
            with self.subTest(section=section, key=key):
                bank = copy.deepcopy(self.bank)
                bank[section][key] = value
                with self.assertRaises(AssertionError):
                    driver.ready_context(bank)

    def test_stale_heartbeat_never_requests_a_blind_tab(self):
        self.assertEqual(driver.progress_result(self.before, self.bank), 'wait')
        self.bank['Pending']['Time'] = '20.25'
        self.assertEqual(driver.progress_result(self.before, self.bank), 'wait')
        self.bank['Pending']['Time'] = '20.5'
        self.assertEqual(driver.progress_result(self.before, self.bank), 'unchanged')

    def test_actual_remaining_delta_drives_progress_and_completion(self):
        self.bank['Pending']['Remaining'] = '2'
        self.assertEqual(driver.progress_result(self.before, self.bank), 'progress')
        self.bank['Pending']['Remaining'] = '0'
        self.assertEqual(driver.progress_result(self.before, self.bank), 'complete')
        self.bank['Pending']['Remaining'] = '4'
        with self.assertRaises(AssertionError):
            driver.progress_result(self.before, self.bank)

    def test_wrong_case_or_unfinished_phase_cannot_be_silently_skipped(self):
        self.bank['Pending']['Case'] = 'other'
        with self.assertRaises(AssertionError):
            driver.progress_result(self.before, self.bank)
        self.bank[self.before['case'] + '/After'] = {'Remaining': '0'}
        self.assertEqual(driver.progress_result(self.before, self.bank), 'complete')

    def test_restoration_is_required_before_expiry_and_all_later_controls(self):
        bank = restored_bank()
        driver.require_restored_speed(bank)
        case = next(iter(driver.GROUPS))
        for section, key, value in [(case, 'RestoredSpeed', '0'), (case, 'RestoredTime', '29'),
                                     (case + '/Expired', 'GameSpeed', '0'),
                                     ('NegativeChildDeath/Before', 'GameSpeed', '0'),
                                     ('RetentionHeld/After', 'GameSpeed', '0'),
                                     ('Event900', 'GameSpeed', '0')]:
            with self.subTest(section=section, key=key):
                broken = copy.deepcopy(bank)
                broken[section][key] = value
                with self.assertRaises(AssertionError):
                    driver.require_restored_speed(broken)


class GuardedDelegationTests(unittest.TestCase):
    def test_every_input_is_delegated_with_exact_pid_title_and_unchanged_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / 'guarded-ui.py'
            helper.write_text('# no actual input during tests\n')
            digest = hashlib.sha256(helper.read_bytes()).hexdigest()
            run = Mock()
            driver.send_key(helper, digest, 123, 'Escape', run=run)
            args, kwargs = run.call_args
            self.assertEqual(args[0], [sys.executable, str(helper), 'key', 'Escape'])
            self.assertEqual(kwargs['env']['SC2_UI_PID'], '123')
            self.assertEqual(kwargs['env']['SC2_UI_TITLE'], 'StarCraft II')
            self.assertTrue(kwargs['check'])
            for pid, key in ((0, 'Escape'), (123, 'Return')):
                run.reset_mock()
                with self.assertRaises(AssertionError):
                    driver.send_key(helper, digest, pid, key, run=run)
                run.assert_not_called()
            helper.write_text('# changed helper\n')
            with self.assertRaises(AssertionError):
                driver.send_key(helper, digest, 123, 'Tab', run=run)
            run.assert_not_called()

    def test_rejected_focus_guard_aborts_instead_of_falling_back_to_native_input(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / 'guarded-ui.py'
            helper.write_text('# mocked guarded helper\n')
            digest = hashlib.sha256(helper.read_bytes()).hexdigest()
            run = Mock(side_effect=subprocess.CalledProcessError(1, ['guarded-helper']))
            with self.assertRaises(subprocess.CalledProcessError):
                driver.send_key(helper, digest, 123, 'Tab', run=run)
            self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
