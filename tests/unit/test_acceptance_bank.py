"""Meaningful evidence protocol tests; these do not simulate the Galaxy adapters."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from acceptance_bank import read_bank, trace, number
from verify_mixed_regression import check_rows, gh, queue_items, require_orders


class BankProtocolTests(unittest.TestCase):
    def read(self, xml):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.SC2Bank'
            path.write_text(xml)
            return read_bank(path)

    def test_real_value_encodings_keep_text_markup_and_exact_time(self):
        result = self.read('<Bank version="1"><Section name="UI"><Key name="Status"><Value text="&lt;c val=\'FF0000\'&gt;Cancelled ×5&lt;/c&gt;"/></Key><Key name="Time"><Value fixed="9.0625"/></Key><Key name="Ready"><Value flag="1"/></Key></Section></Bank>')
        self.assertEqual(result['UI']['Status'], "<c val='FF0000'>Cancelled ×5</c>")
        self.assertEqual(number(result['UI'], 'Time'), 9.0625)
        self.assertEqual(result['UI']['Ready'], '1')

    def test_reject_duplicate_sections_and_keys_instead_of_silent_last_value(self):
        for xml in ('<Bank><Section name="A"/><Section name="A"/></Bank>',
                    '<Bank><Section name="A"><Key name="K"><Value int="1"/></Key><Key name="K"><Value int="2"/></Key></Section></Bank>'):
            with self.subTest(xml=xml), self.assertRaises(AssertionError):
                self.read(xml)

    def test_reject_missing_ambiguous_or_unknown_values(self):
        for value in ('', '<Value int="1"/><Value int="2"/>', '<Value int="1" flag="1"/>', '<Value guessed="PASS"/>'):
            with self.subTest(value=value), self.assertRaises(AssertionError):
                self.read('<Bank><Section name="A"><Key name="K">' + value + '</Key></Section></Bank>')

    def test_done_scalar_does_not_replace_closed_contiguous_trace(self):
        bank = {'Finished': {'Done': '1', 'Events': '2'}, 'Event1': {'Time': '8'}, 'Event2': {'Time': '8.0625'}}
        self.assertEqual(len(trace(bank)), 2)
        for mutation in ('missing', 'extra', 'unfinished', 'reversed', 'overflow'):
            broken = copy.deepcopy(bank)
            if mutation == 'missing':
                del broken['Event2']
            elif mutation == 'extra':
                broken['Event3'] = {'Time': '9'}
            elif mutation == 'unfinished':
                broken['Finished']['Done'] = '0'
            elif mutation == 'reversed':
                broken['Event2']['Time'] = '7'
            else:
                broken['Finished']['Overflow'] = '1'
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                trace(broken)

    def test_nonfinite_time_cannot_pass_a_comparison(self):
        for value in ('NaN', 'inf', '-inf'):
            with self.subTest(value=value), self.assertRaises(AssertionError):
                number({'Time': value}, 'Time')


class MixedEvidenceContractTests(unittest.TestCase):
    def row(self):
        fields = {f'Row{i}Visible': '0' for i in range(3)}
        fields.update({f'Row0{key}': value for key, value in {
            'Visible': '1', 'Name': 'Oracle', 'Status': 'Cancelled ×2', 'Count': '2',
            'Owner': '1', 'Kind': '2', 'Key': 'Oracle', 'Remaining': '4.875',
            'Icon': 'Assets\\Textures\\btn-unit-protoss-oracle.dds'}.items()})
        return fields

    def test_rendered_identity_status_icon_and_full_timer_are_independent_requirements(self):
        expected = {'OracleName': 'Oracle', 'OracleIcon': 'Assets/Textures/btn-unit-protoss-oracle.dds'}
        check_rows(self.row(), [('Oracle', 1, 2, 2)], expected)
        for key, value in {'Row0Count': '1', 'Row0Owner': '2', 'Row0Kind': '0',
                           'Row0Status': 'Cancelled', 'Row0Icon': 'missing.dds',
                           'Row0Remaining': '0.2', 'Row0Name': 'Warp Prism'}.items():
            broken = self.row()
            broken[key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError):
                check_rows(broken, [('Oracle', 1, 2, 2)], expected)

    def test_actual_queue_removal_needs_real_orders_from_same_producer_and_phase(self):
        fields = {'Alive': '1', 'Slot1Count': '1', 'Slot1': 'Oracle',
                  **{f'Slot{i}Count': '0' for i in range(2, 6)}}
        self.assertEqual(queue_items(fields), ['Oracle'])
        event = {'Label': 'Order', 'Tag': '123', 'Ability': 'que5', 'Command': '0', 'Phase': 'Burst'}
        self.assertEqual(require_orders([event], '123', 'que5', 0, 1, 'Burst'), [event])
        for key, value in {'Tag': '124', 'Ability': 'UpgradeToLair', 'Command': '1', 'Phase': 'Reset'}.items():
            broken = dict(event, **{key: value})
            with self.subTest(key=key), self.assertRaises(AssertionError):
                require_orders([broken], '123', 'que5', 0, 1, 'Burst')

    def test_denied_requires_original_gh_name_status_visibility_and_own_timer(self):
        fields = {'GHActive': '1', 'GHMatches': '1', 'GH0Name': 'Terran Infantry Weapons Level 1',
                  'GH0Visible': '1', 'GH0Status': '2', 'GH0Label': 'Denied', 'GH0Remaining': '4.875'}
        gh(fields, fields['GH0Name'], denied=True)
        for key, value in {'GHMatches': '2', 'GH0Visible': '0', 'GH0Status': '1',
                           'GH0Label': 'Cancelled', 'GH0Remaining': '0.1'}.items():
            with self.subTest(key=key), self.assertRaises(AssertionError):
                gh(dict(fields, **{key: value}), fields['GH0Name'], denied=True)


if __name__ == '__main__':
    unittest.main()
