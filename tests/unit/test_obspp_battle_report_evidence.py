"""Synthetic evidence-boundary tests; SC2 produces the actual acceptance bank."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import verify_obspp_battle_report as validator


def fields():
    result = {'BattleActive': '1', 'TrackEnabled': '1'}
    for metric in ('Units', 'Warps', 'Prisms', 'Buildings', 'Morphs'):
        result[metric] = '0'
    for slot in (0, 1):
        for metric in ('Units', 'Minerals', 'Gas', 'Supply', 'Types'):
            result[f'Slot{slot}{metric}'] = '0'
    return result


def protocol(case='Combat1'):
    owner = {'Combat1': 2, 'Combat2': 1}.get(case, int(case[-1]) if case[-1].isdigit() else 2)
    object_type = 'Stalker' if case.startswith('Combat') else 'Baneling' if case.startswith('Baneling') else 'Marine'
    remove, invalid = case.startswith('Remove'), case.startswith('Invalid')
    killer = 16 if remove else 3 if invalid else 3 - owner
    before, after = fields(), fields()
    bank = {case: {'Done': '1', 'TargetTag': '100', 'TargetOwner': str(owner), 'TargetType': object_type,
                   'TargetAlive': '1', 'TargetValid': '1', 'TargetMinerals': '125', 'TargetGas': '50', 'TargetSupply': '2',
                   'AttackerOwner': str(killer), 'AttackerTag': '900'},
            case + '/Before': before, case + '/After': after, 'Finished': {'Events': '1'},
            'Event1': {'Case': case, 'Label': 'Died', 'UnitTag': '100', 'UnitOwner': str(owner),
                       'UnitType': object_type, 'UnitAlive': '0', 'Removed': '1' if remove else '0',
                       'KillingPlayer': str(killer), 'KillingTag': '0' if remove else '900', 'DeathSupply': '2'}}
    if remove:
        before['Time'], after['Time'] = '20', '20.25'
        after.update(TargetValid='0', TargetAlive='0')
        bank['Event1'] = {'Case': case, 'Label': 'Removed', 'Time': '20',
                          'EventUnitPresent': '1', 'EventMatchesTarget': '1',
                          'EventUnitValid': '0', 'EventUnitAlive': '0', 'EventUnitTag': '0',
                          'RemovedTargetTag': '100', 'RemovedTargetOwner': str(owner), 'RemovedTargetType': 'Marine'}
    if not remove and not invalid:
        slot = 2 - owner
        after.update({f'Slot{slot}Units': '1', f'Slot{slot}Minerals': '125', f'Slot{slot}Gas': '50',
                      f'Slot{slot}Supply': '2', f'Slot{slot}Types': '1',
                      f'Slot{slot}Type0': object_type, f'Slot{slot}Type0Count': '1'})
    return bank


class BattleReportEvidenceTests(unittest.TestCase):
    def test_disabled_or_noop_callback_cannot_pass_actual_normal_death_counts(self):
        bank = protocol()
        self.assertEqual(validator.verify_case(bank, 'Combat1')['battle_slot'], 0)
        for key, value in (('TrackEnabled', '0'), ('BattleActive', '0'), ('Slot0Units', '0'),
                           ('Slot0Minerals', '0'), ('Slot0Gas', '0'), ('Slot0Type0Count', '2')):
            with self.subTest(key=key):
                broken = copy.deepcopy(bank)
                broken['Combat1/After'][key] = value
                with self.assertRaises(AssertionError):
                    validator.verify_case(broken, 'Combat1')

    def test_baneling_owner_two_is_opponent_slot_zero_in_every_counter(self):
        bank = protocol('Baneling2')
        self.assertEqual(validator.verify_case(bank, 'Baneling2')['battle_slot'], 0)
        bank['Baneling2/After']['Slot1Units'] = '1'
        with self.assertRaises(AssertionError):
            validator.verify_case(bank, 'Baneling2')

    def test_removed_units_and_unsupported_killers_change_no_report_or_own_count(self):
        for case in ('Remove1', 'Remove2', 'Invalid1', 'Invalid2'):
            bank = protocol(case)
            self.assertEqual(validator.verify_case(bank, case)['battle_units'], 0)
            for key in ('Slot0Units', 'Slot1Minerals', 'Units'):
                broken = copy.deepcopy(bank)
                broken[case + '/After'][key] = '1'
                with self.subTest(case=case, key=key), self.assertRaises(AssertionError):
                    validator.verify_case(broken, case)

    def test_remove_requires_real_removed_identity_live_before_invalid_after_and_no_fabricated_death(self):
        bank = protocol('Remove2')
        self.assertEqual(validator.verify_case(bank, 'Remove2')['removals'], 1)
        changes = [('Event1', 'Label', 'MissingRemoved'), ('Event1', 'EventMatchesTarget', '0'),
                   ('Event1', 'RemovedTargetTag', '999'), ('Event1', 'RemovedTargetOwner', '1'),
                   ('Event1', 'RemovedTargetType', 'Stalker'), ('Event1', 'EventUnitPresent', '0'),
                   ('Event1', 'EventUnitTag', '100'), ('Event1', 'Time', '19'),
                   ('Remove2', 'TargetValid', '0'), ('Remove2/After', 'TargetValid', '1'),
                   ('Remove2/After', 'TargetAlive', '1')]
        for section, key, value in changes:
            broken = copy.deepcopy(bank)
            broken[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(AssertionError):
                validator.verify_case(broken, 'Remove2')
        # A valid handle during its callback is acceptable only with its actual
        # native tag, followed by the independently observed invalid handle.
        bank['Event1'].update(EventUnitValid='1', EventUnitTag='100')
        validator.verify_case(bank, 'Remove2')
        for label in ('Died', 'ConstructCancel', 'ConstructComplete'):
            broken = copy.deepcopy(bank)
            broken['Finished']['Events'] = '2'
            broken['Event2'] = {'Case': 'Remove2', 'Label': label}
            with self.subTest(label=label), self.assertRaises(AssertionError):
                validator.verify_case(broken, 'Remove2')

    def test_real_death_identity_credit_and_remove_reason_are_mandatory(self):
        bank = protocol()
        for key, value in (('UnitTag', '999'), ('UnitOwner', '1'), ('KillingPlayer', '0'),
                           ('KillingTag', '0'), ('Removed', '1'), ('UnitAlive', '1')):
            broken = copy.deepcopy(bank)
            broken['Event1'][key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError):
                validator.verify_case(broken, 'Combat1')
        bank['Event1']['Label'] = 'DeclaredDeath'
        with self.assertRaises(AssertionError):
            validator.verify_case(bank, 'Combat1')


if __name__ == '__main__':
    unittest.main()
