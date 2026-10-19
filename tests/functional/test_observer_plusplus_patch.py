"""Exact-input dependency patch, graph preservation and immutable local output."""
import hashlib
import os
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import patch_observer_plus_plus as patcher

SOURCE = Path(os.environ.get('OPP_OBSERVER_SOURCE', '/missing-observer-source'))
MPQCLI = Path(os.environ.get('OPP_MPQCLI', '/missing-mpqcli'))


class ObserverPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.is_dir() or not MPQCLI.is_file():
            raise RuntimeError('Functional tests require OPP_OBSERVER_SOURCE (matching unpatched components) and OPP_MPQCLI (local mpqcli executable). See tests/functional/README.md.')

    def inputs(self):
        return (SOURCE / 'Triggers').read_bytes(), (SOURCE / patcher.GALAXY).read_bytes()

    def test_exact_callback_and_xml_graph_changes_preserve_every_other_element(self):
        xml, galaxy = self.inputs()
        result = patcher.transform_bytes(xml, galaxy)
        self.assertEqual(set(result), {'Triggers', patcher.GALAXY})
        old, new = ETree(xml), ETree(result['Triggers'])
        changed = {key for key in old if old[key] != new[key]}
        self.assertEqual(changed, {('7805B319', 'D3F37C35'), ('7805B319', '6C9458E6'), ('7805B319', '8A08DB2C')})
        self.assertEqual(set(new) - set(old), {('7805B319', '0BB00001'), ('7805B319', '0BB00002')})
        before, after = galaxy.decode(), result[patcher.GALAXY].decode()
        begin = 'bool lib7805B319_gt_TrackUnitKills_Func ('
        end = 'void lib7805B319_gt_TrackUnitKills_Init ('
        self.assertEqual(before.split(begin)[0], after.split(begin)[0])
        self.assertEqual(before.split(end)[1], after.split(end)[1])
        spec, assets = patcher.transformation()
        graph = ET.fromstring(result['Triggers']).find("Library[@Id='7805B319']")
        for kind in ('neutral', 'baneling'):
            value = graph.find("Element[@Id='" + spec[kind + '_parameter'] + "']/ScriptCode").text.strip()
            self.assertEqual(value, spec[kind + '_expression'])
            self.assertIn(value, after)
        for kind in ('start', 'slot'):
            script = graph.find("Element[@Id='" + spec[kind + '_action'] + "']/ScriptCode").text
            recovered = '\n'.join(line[16:] for line in script.splitlines()[1:-1]) + '\n'
            self.assertEqual(recovered, assets[kind + '_asset'])
            self.assertIn('    ' + recovered.splitlines()[0], after)
        self.assertLess(after.index('EventUnitDamageDeathCheck(c_deathTypeRemove)', after.index(begin)),
                        after.index('lv_totalUnitsLost +=', after.index(begin)))

    def test_changed_unknown_or_already_patched_inputs_are_rejected(self):
        xml, galaxy = self.inputs()
        patched = patcher.transform_bytes(xml, galaxy)
        for pair in ((xml + b'changed', galaxy), (xml, galaxy + b'changed'),
                     (patched['Triggers'], patched[patcher.GALAXY])):
            with self.subTest(hashes=[hashlib.sha256(value).hexdigest() for value in pair]):
                with self.assertRaisesRegex(ValueError, 'SHA256'):
                    patcher.transform_bytes(*pair)

    def test_real_mpq_all_members_and_original_bytes_and_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            before = patcher.inventory(SOURCE)
            output, installed = base / 'PatchedPrivate.SC2Mod', base / 'Mods'
            report_path = patcher.patch(SOURCE, output, MPQCLI, installed)
            report = patcher.verify_report(report_path, output, Path(str(output) + '.mpq'),
                                          installed / output.name, MPQCLI)
            self.assertEqual(patcher.inventory(SOURCE), before)
            self.assertEqual({name for name in before if before[name] != report['output_files'][name]}, {'Triggers', patcher.GALAXY})
            with self.assertRaisesRegex(ValueError, 'collision'):
                patcher.patch(SOURCE, output, MPQCLI, installed)
            for path in (output / patcher.GALAXY, installed / output.name):
                original = path.read_bytes()
                path.write_bytes(original + b'changed')
                with self.subTest(path=path), self.assertRaises(AssertionError):
                    patcher.verify_report(report_path, output, Path(str(output) + '.mpq'),
                                          installed / output.name, MPQCLI)
                path.write_bytes(original)


def ETree(data):
    # Ignore formatting only in the semantic graph comparison; the patcher also
    # retains every non-target serialized XML byte by exact element surgery.
    result = {}
    for library in ET.fromstring(data).findall('Library'):
        for element in library.findall('Element'):
            for child in element.iter():
                if child.text is not None and not child.text.strip():
                    child.text = None
                child.tail = None
            result[(library.attrib['Id'], element.attrib['Id'])] = ET.tostring(element)
    return result


if __name__ == '__main__':
    unittest.main()
