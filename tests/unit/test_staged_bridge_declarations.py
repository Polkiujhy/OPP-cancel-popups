"""Code-generation coverage for dependency-first SC2 map compilation order."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from prepare_functional_source import (FIXTURE_BRIDGES, GALAXY_FUNCTION, galaxy_code_mask,
                              strip_loaded_bridge_prototypes)


class LoadedBridgeDeclarationTests(unittest.TestCase):
    def test_every_current_bridge_fixture_removes_only_loaded_forward_declarations(self):
        expected_counts = {'queue-age-breakcheck': 3, 'queue-aggregation-acceptance': 4,
                           'addon-acceptance': 2, 'morph-acceptance': 6,
                           'prism-acceptance': 7, 'mixed-regression': 1,
                           'obspp-battle-report-acceptance': 1}
        self.assertEqual(set(FIXTURE_BRIDGES), set(expected_counts))
        for fixture, paths in FIXTURE_BRIDGES.items():
            with self.subTest(fixture=fixture):
                source_path = ROOT / 'tests/functional/scenarios' / (fixture + '.galaxy')
                original = source_path.read_text()
                bridges = [(ROOT / 'tests/functional/scenarios' / path).read_text() for path in paths]
                normalized, removed = strip_loaded_bridge_prototypes(original, bridges)
                self.assertEqual(len(removed), expected_counts[fixture])
                headers = list(GALAXY_FUNCTION.finditer(galaxy_code_mask(original)))
                definitions = [header.group() for header in headers if header['ending'] == '{']
                result_headers = list(GALAXY_FUNCTION.finditer(galaxy_code_mask(normalized)))
                self.assertEqual([header.group() for header in result_headers if header['ending'] == '{'], definitions)
                self.assertFalse(any(header['ending'] == ';' and header['name'] in removed for header in result_headers))
                self.assertEqual(normalized.count('\n'), original.count('\n'))
                # Compiler-only inputs still retain original forward declarations.
                self.assertEqual(source_path.read_text(), original)
                self.assertEqual(strip_loaded_bridge_prototypes(normalized, bridges), (normalized, []))

    def test_unloaded_declarations_calls_comments_strings_and_definitions_remain_intact(self):
        bridge = 'void OPP_Private (int owner, string name) { Native(owner); }\n'
        source = ('// void OPP_Private (int example, string name);\n'
                  '/*\nvoid OPP_Private (int sample, string name);\n*/\n'
                  'string example = "void OPP_Private (int sample, string name);";\n'
                  'void OPP_Unloaded (int owner);\n'
                  'void OPP_Private (int p, string label);\n'
                  'void Run () { OPP_Private(1, "Example"); }\n'
                  'void OPP_Private (int owner, string name) { Native(owner); }\n')
        normalized, names = strip_loaded_bridge_prototypes(source, [bridge])
        self.assertEqual(names, ['OPP_Private'])
        self.assertEqual(normalized, source.replace('void OPP_Private (int p, string label);', ''))
        self.assertEqual(strip_loaded_bridge_prototypes(source, []), (source, []))

    def test_whitespace_multiline_and_parameter_names_do_not_change_a_signature(self):
        bridge = 'void OPP_Private (int owner, bool enabled) { Native(); }\n'
        source = 'void OPP_Private (\n    int player,\n    bool on\n);\nvoid Run () { OPP_Private(1, true); }\n'
        normalized, names = strip_loaded_bridge_prototypes(source, [bridge])
        self.assertEqual(names, ['OPP_Private'])
        self.assertEqual(normalized, '\n\n\n\nvoid Run () { OPP_Private(1, true); }\n')

    def test_signature_drift_fails_instead_of_hiding_a_contract_error(self):
        bridge = 'void OPP_Private (int owner) { Native(owner); }\n'
        for prototype in ('bool OPP_Private (int owner);', 'void OPP_Private (string owner);',
                          'void OPP_Private ();'):
            with self.subTest(prototype=prototype), self.assertRaisesRegex(SystemExit, 'signature mismatch'):
                strip_loaded_bridge_prototypes(prototype, [bridge])


if __name__ == '__main__':
    unittest.main()
