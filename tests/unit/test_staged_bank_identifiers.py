"""Generated bank IDs must equal physical SC2 stems and stored fragment names."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from prepare_functional_source import prepare_bank_identifiers


class StagedBankIdentifierTests(unittest.TestCase):
    def test_direct_and_all_known_fragment_builders_use_one_alphanumeric_base(self):
        source = ('bank a = BankLoad("OPPBuildingCancelTest", 1);\n'
                  'bank b = BankLoad("OPPBuildingCancelTestMorphCatalog", 1);\n'
                  'bank c = BankLoad("OPPBuildingCancelTest" + "Window", 1);\n'
                  'fragment = "OPPBuildingCancelTest_Prism_" + label;\n'
                  'bank d = BankLoad(fragment, 1);\n'
                  'name = "OPPBuildingCancelTest" + "_Retention" + IntToString(chunk);\n'
                  'bank e = BankLoad(name, 1);\n'
                  'chunkName = "OPPBuildingCancelTest" + "Matrix" + IntToString(chunk);\n'
                  'bank f = BankLoad(chunkName, 1);\n'
                  'BankValueSetFromString(main, "Fragments", "Bank0", fragment);\n')
        expected = source.replace('OPPBuildingCancelTest_Prism_', 'OPPBuildingCancelv95Prism')
        expected = expected.replace('OPPBuildingCancelTest', 'OPPBuildingCancelv95').replace('"_Retention"', '"Retention"')
        self.assertEqual(prepare_bank_identifiers(source, 'v95'), expected)
        self.assertEqual(prepare_bank_identifiers(expected, 'v95'), expected)

    def test_case_section_snapshot_names_and_examples_are_unchanged(self):
        source = ('// BankLoad("OPPBuildingCancelTest_Prism_", 1);\n'
                  '/* BankLoad("OPPBuildingCancelTest", 1); */\n'
                  'string example = "BankLoad(\\"OPPBuildingCancelTest\\", 1)";\n'
                  'string caseName = "OPPBuildingCancelTest_Prism_";\n'
                  'BankValueSetFromString(out, "Case_Section", "OPPBuildingCancelTest", "_Retention");\n'
                  'OPP_Snapshot("Prism_Case/Before_Ready");\n'
                  'bank real = BankLoad("OPPBuildingCancelTest", 1);\n')
        expected = source.replace('bank real = BankLoad("OPPBuildingCancelTest", 1);',
                                  'bank real = BankLoad("OPPBuildingCancelv95", 1);')
        self.assertEqual(prepare_bank_identifiers(source, 'v95'), expected)

    def test_actual_addon_and_prism_manifest_builders_keep_variable_identity(self):
        cases = {
            'addon-acceptance': 'name = "OPPBuildingCancelv95" + "Retention" + IntToString(chunk);',
            'prism-acceptance': 'OPP_PA_Fragment = "OPPBuildingCancelv95Prism" + fragment;',
            'morph-acceptance': 'chunkName = "OPPBuildingCancelv95" + "Matrix" + IntToString(chunk);',
            'morph-scope-segmented': 'chunkName = "OPPBuildingCancelv95" + "Chunk" + IntToString(chunk);',
        }
        for fixture, assignment in cases.items():
            with self.subTest(fixture=fixture):
                path = ROOT / 'tests/functional/scenarios' / (fixture + '.galaxy')
                original = path.read_text()
                staged = prepare_bank_identifiers(original, 'v95')
                self.assertIn(assignment, staged)
                # Actual BankLoad(variable) and manifest writes retain the same variable.
                self.assertEqual(re.findall(r'BankLoad\([A-Za-z_]\w*, 1\)', staged),
                                 re.findall(r'BankLoad\([A-Za-z_]\w*, 1\)', original))
                self.assertEqual(re.findall(r'BankValueSetFromString[^;]+;', staged),
                                 re.findall(r'BankValueSetFromString[^;]+;', original))
                self.assertEqual(path.read_text(), original)

    def test_every_fixture_direct_bank_prefix_is_safe_without_rewriting_other_strings(self):
        for path in (ROOT / 'tests/functional/scenarios').glob('*.galaxy'):
            original = path.read_text()
            if 'BankLoad(' not in original:
                continue
            with self.subTest(fixture=path.name):
                staged = prepare_bank_identifiers(original, 'v95')
                names = re.findall(r'BankLoad\("([A-Za-z0-9_]+)"', staged)
                self.assertTrue(all(re.fullmatch(r'[A-Za-z0-9]+', name) for name in names))
                # Fixture names and source unit catalog strings stay historical.
                self.assertEqual(re.findall(r'"(?:Case|Fixture|ExpectedName)"[^;]+;', staged),
                                 re.findall(r'"(?:Case|Fixture|ExpectedName)"[^;]+;', original))

    def test_unknown_bank_literal_or_non_ascii_revision_is_rejected(self):
        for revision in ('v_95', '../95', 'ż95'):
            with self.subTest(revision=revision), self.assertRaises(SystemExit):
                prepare_bank_identifiers('BankLoad("OPPBuildingCancelTest", 1);', revision)
        with self.assertRaises(SystemExit):
            prepare_bank_identifiers('name = "OPPBuildingCancelTest_bad/suffix"; BankLoad(name, 1);', 'v95')


if __name__ == '__main__':
    unittest.main()
