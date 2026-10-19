"""Prevent the editor XML-margin handling from deleting executable source."""
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('generate_mod', ROOT / 'tools/generate_mod.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class ScriptMarginTests(unittest.TestCase):
    def test_runtime_catalog_registers_the_generated_library(self):
        mod = ROOT / 'files'
        library_id = ET.fromstring(generator.products()['Triggers']).find('Library').get('Id')
        components = ET.parse(mod / 'ComponentList.entries.xml')
        self.assertEqual(components.find("DataComponent[@Type='gada']").text, 'GameData')
        catalog = ET.parse(mod / 'Base.SC2Data/GameData/GameData.xml')
        registrations = catalog.findall("CGame[@id='Dflt']/TriggerLibs")
        self.assertEqual([entry.get('Id') for entry in registrations], [library_id])

    def test_library_code_survives_editor_xml_margin_removal(self):
        xml = ET.fromstring(generator.products()['Triggers'])
        block = xml.find("./Library/Element[@Type='CustomScript']/ScriptCode").text
        lines = block.splitlines()
        self.assertEqual(lines[0], '')
        self.assertEqual(lines[-1], ' ' * 12)
        self.assertTrue(all(line.startswith(' ' * 16) for line in lines[1:-1]))
        recovered = '\n'.join(line[16:] for line in lines[1:-1]) + '\n'
        expected = '\n'.join((ROOT / 'source' / name).read_text().rstrip()
                             for name in generator.SOURCES) + '\n'
        self.assertEqual(recovered, expected)
        self.assertIn('void OPP_Init () {', recovered)

    def test_action_uses_the_same_preserved_margin(self):
        xml = ET.fromstring(generator.products()['Triggers'])
        block = xml.find("./Library/Element[@Id='00000011']/ScriptCode").text
        self.assertEqual(block, '\n                OPP_Init();\n            ')


if __name__ == '__main__':
    unittest.main()
