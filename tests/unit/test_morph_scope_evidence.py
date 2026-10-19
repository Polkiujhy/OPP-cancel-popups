"""Reject insufficient historical traces when supplementing the runtime matrix."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('morph_scope', ROOT / 'tools/verify_morph_scope_baseline.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class SupplementEvidenceTests(unittest.TestCase):
    def setUp(self):
        common = {'Case': 'Example', 'UnitTag': '10', 'UnitAlive': '1', 'UnitOwner': '1',
                  'UnitType': 'Gateway', 'Ability': 'UpgradeToWarpGate'}
        self.events = [dict(common, Label='Created', Time='8', Stage='0'),
                       dict(common, Label='Ability', Time='8.25', Stage='-3', Command='0'),
                       dict(common, Label='Order', Time='9', Stage='0', Command='1'),
                       dict(common, Label='Ability', Time='9', Stage='-4', Command='0')]

    def evidence(self, events):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.SC2Bank'
            root = ET.Element('Bank')
            values = {'Finished': {'Done': '1'}}
            values.update({f'Event{index + 1}': event for index, event in enumerate(events)})
            for name, fields in values.items():
                section = ET.SubElement(root, 'Section', name=name)
                for key, value in fields.items():
                    ET.SubElement(ET.SubElement(section, 'Key', name=key), 'Value', string=value)
            ET.ElementTree(root).write(path)
            return validator.supplemental_cancellations([path])

    def test_complete_live_trace_records_exact_evidence(self):
        result = self.evidence(self.events)[('Gateway', 'UpgradeToWarpGate')]
        self.assertEqual(len(result), 1)
        evidence = result[0]
        self.assertEqual(evidence['tag'], '10')
        self.assertEqual(evidence['time'], '9')
        self.assertEqual(evidence['source_created_event'], 'Event1')
        self.assertEqual(evidence['execute_event'], 'Event2')
        self.assertEqual(evidence['cancel_order_event'], 'Event3')
        self.assertEqual(evidence['ability_cancel_event'], 'Event4')
        self.assertEqual(len(evidence['sha256']), 64)

    def test_cancel_callback_may_precede_order_callback(self):
        events = self.events[:2] + [self.events[3], self.events[2]]
        self.assertEqual(len(self.evidence(events)[('Gateway', 'UpgradeToWarpGate')]), 1)

    def test_liveness_identity_and_exact_time_are_required(self):
        for index, key, value in [(3, 'UnitAlive', '0'), (2, 'UnitAlive', '0'),
                                  (2, 'UnitTag', '11'), (2, 'Ability', 'OtherMorph'),
                                  (2, 'Time', '9.0625'), (1, 'Time', '9.0625'),
                                  (0, 'UnitAlive', '0')]:
            with self.subTest(index=index, key=key, value=value):
                events = copy.deepcopy(self.events)
                events[index][key] = value
                self.assertEqual(self.evidence(events), {})

    def test_source_creation_and_actual_execute_are_required(self):
        self.assertEqual(self.evidence(self.events[1:]), {})
        self.assertEqual(self.evidence([self.events[0], *self.events[2:]]), {})

    def test_finished_previous_generation_cannot_supply_execute(self):
        complete = dict(self.events[1], Stage='-6', Time='8.5')
        events = self.events[:2] + [complete] + self.events[2:]
        self.assertEqual(self.evidence(events), {})


class FragmentIntegrityTests(unittest.TestCase):
    def test_truncated_trace_does_not_pass_by_scalar_counters(self):
        with self.assertRaises(AssertionError):
            validator.checked_events({'Event0': {}, 'Event2': {}}, 3, 'truncated bank')

    def test_missing_chunk_files_do_not_pass_a_finished_manifest(self):
        manifest = {'Finished': {'Done': '1', 'CatalogLinks': '301',
                                 'CompletedLinks': '292', 'Chunks': '8'},
                    'Probe': {'ChunkCapacity': '40'}}
        with self.assertRaises(AssertionError):
            validator.segmented_prefix(manifest, [])

    def test_scenery_with_a_manual_morph_button_is_not_classified_unavailable(self):
        bank = {'Link292': {'MetadataSaved': '1', 'CardCount': '1',
                            'Ability': 'SceneryMorph', 'Interruptible': '0', 'ShowProgress': '0',
                            'Uncommandable': '1', 'Unselectable': '1', 'Untargetable': '0',
                            'SourceRace': 'Neut', 'SourceCategories': 'Scenery'},
                'Link292/Card0': {'ButtonCount': '1'},
                'Link292/Card0/Button0': {'Type': 'AbilCmd', 'AbilCmd': 'SceneryMorph,Execute'}}
        classification, metadata = validator.scenery_metadata(bank, 'Link292')
        self.assertTrue(classification.startswith('unresolved'))
        self.assertEqual(metadata['own_morph_commands'], ['SceneryMorph,Execute'])


if __name__ == '__main__':
    unittest.main()
