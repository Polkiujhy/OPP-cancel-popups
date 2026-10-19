"""Reject stale receipts and modified frozen artifacts; no SC2 process is launched."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import verify_runtime_provenance as provenance


class RuntimeProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        env_patch = patch.dict(os.environ, {'OPP_MPQCLI': str(self.root / 'tools/mpqcli')})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        (self.root / 'tools').mkdir()
        (self.root / 'source').mkdir(parents=True)
        self.canonical = self.root / 'candidate/Base.SC2Data/LibC0DEC0DE.galaxy'
        self.canonical.parent.mkdir(parents=True)
        self.canonical.write_bytes(b'// generated candidate\n')
        (self.root / 'candidate/Triggers').write_bytes(b'<TriggerData/>')
        self.archive = self.root / 'frozen.SC2Mod'
        self.archive.write_bytes(b'preserved installed MPQ bytes\x00')
        manifest = ['opp_popup_ui.galaxy', 'opp_bootstrap.galaxy']
        for name in manifest:
            (self.root / 'source' / name).write_text('// ' + name + '\n')
        (self.root / 'tools/galaxy_sources.json').write_text(json.dumps(manifest))
        modules = {name: provenance.digest(self.root / 'source' / name) for name in manifest}
        files = {path.relative_to(self.root / 'candidate').as_posix(): provenance.digest(path)
                 for path in (self.root / 'candidate').rglob('*') if path.is_file()}
        deps = ['file:Mods/VoidMulti.SC2Mod', 'file:Mods/privateGH.SC2Mod']
        self.metadata = {'bank_name': 'OPPRuntimetest1', 'revision': 'test1', 'fixture': 'mixed-regression',
                         'canonical_galaxy_sha256': provenance.digest(self.canonical),
                         'mod_archive_sha256': provenance.digest(self.archive),
                         'fixture_source_sha256': hashlib.sha256(b'fixture').hexdigest(),
                         'private_mod': 'Private_test1.SC2Mod', 'private_map': 'Private_test1.SC2Map',
                         'dependencies': json.dumps(deps), 'module_sha256': json.dumps(modules),
                         'canonical_file_sha256': json.dumps(files)}
        self.report_data = {'runtime_provenance': self.metadata.copy(), 'revision': 'test1',
                            'fixture': 'mixed-regression', 'byte_verified': True,
                            'archive_sha256': self.metadata['mod_archive_sha256'],
                            'canonical_galaxy_sha256': self.metadata['canonical_galaxy_sha256'],
                            'module_sha256': modules, 'canonical_file_sha256': files, 'dependencies': deps,
                            'mod': '/private/Private_test1.SC2Mod', 'map': '/private/Private_test1.SC2Map'}
        self.report = self.root / 'stage.json'
        self.report.write_text(json.dumps(self.report_data))
        self.receipt = self.root / 'OPPRuntimetest1.SC2Bank'
        self.write_receipt()
        self.root_patch = patch.object(provenance, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def write_receipt(self, changed=None):
        root = ET.Element('Bank')
        section = ET.SubElement(root, 'Section', name='Provenance')
        fields = dict(self.metadata, Recorded='1', Time='0')
        fields.update(changed or {})
        for name, value in fields.items():
            key = ET.SubElement(section, 'Key', name=name)
            ET.SubElement(key, 'Value', string=str(value))
        self.receipt.write_text(ET.tostring(root, encoding='unicode'))

    def verify(self):
        return provenance.verify(self.receipt, self.report, self.canonical, self.archive)

    def test_matches_recorded_revision_code_assets_and_frozen_mpq(self):
        self.assertEqual(self.verify()['result'], 'PASS')

    def test_stale_revision_or_missing_recording_never_matches_the_stage_report(self):
        for changes in ({'revision': 'old'}, {'Recorded': '0'}, {'fixture': 'old-fixture'},
                        {'mod_archive_sha256': '0' * 64}):
            self.write_receipt(changes)
            with self.subTest(changes=changes), self.assertRaises(AssertionError):
                self.verify()

    def test_archive_asset_and_source_modifications_are_detected(self):
        for path in (self.archive, self.root / 'candidate/Triggers', self.root / 'source/opp_popup_ui.galaxy'):
            original = path.read_bytes()
            path.write_bytes(original + b'changed')
            with self.subTest(path=path), self.assertRaises(AssertionError):
                self.verify()
            path.write_bytes(original)

    def test_omitted_module_cannot_be_hidden_by_a_matching_receipt_and_report(self):
        modules = dict(self.report_data['module_sha256'])
        modules.pop('opp_bootstrap.galaxy')
        report = copy.deepcopy(self.report_data)
        report['module_sha256'] = modules
        report['runtime_provenance']['module_sha256'] = json.dumps(modules)
        self.report.write_text(json.dumps(report))
        self.write_receipt({'module_sha256': json.dumps(modules)})
        with self.assertRaises(AssertionError):
            self.verify()

    def test_patched_receipt_cannot_fall_back_to_unverified_declared_dependency(self):
        report = copy.deepcopy(self.report_data)
        report['runtime_provenance']['observer_patch_manifest'] = '{}'
        report['runtime_provenance']['observer_patch_manifest_sha256'] = '0' * 64
        self.report.write_text(json.dumps(report))
        self.write_receipt({'observer_patch_manifest': '{}', 'observer_patch_manifest_sha256': '0' * 64})
        with self.assertRaisesRegex(AssertionError, 'requires frozen'):
            self.verify()

    def test_patched_provenance_binds_exact_frozen_report_and_live_install(self):
        manifest = self.root / 'patch.json'
        declared = {'dependency_name': 'PatchedPrivate.SC2Mod', 'installed': {'path': '/live/Mods/PatchedPrivate.SC2Mod'}}
        manifest.write_text(json.dumps(declared))
        fields = {'observer_patch_manifest': json.dumps(declared), 'observer_patch_manifest_sha256': provenance.digest(manifest)}
        report = copy.deepcopy(self.report_data)
        report.update(observer_patch_manifest=declared, observer_patch_manifest_sha256=fields['observer_patch_manifest_sha256'])
        report['dependencies'].append('file:Mods/PatchedPrivate.SC2Mod')
        report['runtime_provenance'].update(fields, dependencies=json.dumps(report['dependencies']))
        self.report.write_text(json.dumps(report))
        self.write_receipt(dict(fields, dependencies=json.dumps(report['dependencies'])))
        frozen, archive = self.root / 'PatchedPrivate.SC2Mod', self.root / 'dep.mpq'
        with patch.object(provenance, 'verify_observer_patch', return_value=declared) as verify_patch:
            result = provenance.verify(self.receipt, self.report, self.canonical, self.archive,
                                       observer_patch_manifest=manifest, observer_dependency_directory=frozen,
                                       observer_dependency_archive=archive)
            self.assertEqual(result['observer_patch'], declared)
            verify_patch.assert_called_once_with(manifest, frozen, archive, Path(declared['installed']['path']), self.root / 'tools/mpqcli')
        manifest.write_text(manifest.read_text() + ' ')
        with self.assertRaises(AssertionError):
            provenance.verify(self.receipt, self.report, self.canonical, self.archive,
                              observer_patch_manifest=manifest, observer_dependency_directory=frozen,
                              observer_dependency_archive=archive)


if __name__ == '__main__':
    unittest.main()
