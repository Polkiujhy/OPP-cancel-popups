"""Exercise the distributable generator and protect immutable release outputs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('integration_packager', ROOT / 'tools/package_integration.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class IntegrationPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.output = Path(cls.directory.name)
        cls.name = 'OPP-CancelPopups-integration-candidate-test'
        cls.archive, _ = packager.package(cls.name, cls.output)
        cls.package = cls.output / cls.name
        cls.sources = json.loads((ROOT / 'tools/galaxy_sources.json').read_text())

    def test_package_contains_every_approved_module_and_identical_generated_bytes(self):
        canonical = {path.name for path in (ROOT / 'source').glob('*.galaxy')}
        self.assertEqual(set(self.sources), canonical)
        self.assertEqual(len(self.sources), len(canonical))
        self.assertEqual(self.sources[-1], 'opp_bootstrap.galaxy')
        self.assertIn('opp_morphs.galaxy', self.sources)
        self.assertEqual(json.loads((self.package / 'tools/galaxy_sources.json').read_text()), self.sources)
        self.assertEqual({path.name for path in (self.package / 'source').glob('*.galaxy')}, canonical)
        for source in self.sources:
            with self.subTest(source=source):
                self.assertEqual((self.package / 'source' / source).read_bytes(),
                                 (ROOT / 'source' / source).read_bytes())
        for relative in ('Triggers', 'Base.SC2Data/LibC0DEC0DE.galaxy', 'Base.SC2Data/LibC0DEC0DE_h.galaxy'):
            with self.subTest(product=relative):
                self.assertEqual((self.package / 'files' / relative).read_bytes(),
                                 (packager.MOD / relative).read_bytes())
        with zipfile.ZipFile(self.archive) as archive:
            self.assertIsNone(archive.testzip())
            expected = {self.name + '/' + path.relative_to(self.package).as_posix()
                        for path in self.package.rglob('*') if path.is_file()}
            self.assertEqual(set(archive.namelist()), expected)
            for path in self.package.rglob('*'):
                if path.is_file():
                    self.assertEqual(archive.read(self.name + '/' + path.relative_to(self.package).as_posix()),
                                     path.read_bytes())

    def test_extracted_generator_uses_its_own_manifest_from_an_unrelated_cwd(self):
        products = ('Triggers', 'Base.SC2Data/LibC0DEC0DE.galaxy', 'Base.SC2Data/LibC0DEC0DE_h.galaxy')
        repository_before = {relative: (packager.MOD / relative).read_bytes() for relative in products}
        with tempfile.TemporaryDirectory() as moved_directory, tempfile.TemporaryDirectory() as unrelated_cwd:
            moved = Path(moved_directory)
            with zipfile.ZipFile(self.archive) as archive:
                archive.extractall(moved)
            package = moved / self.name
            markers = []
            # Editing each independent packaged source catches a stale embedded
            # module list that omits Morph or any later production module.
            for index, source in enumerate(self.sources):
                marker = '// isolated-package-module-' + str(index)
                path = package / 'source' / source
                path.write_text(path.read_text().rstrip() + '\n' + marker + '\n')
                markers.append(marker)
            # The included manifest must remain authoritative after extraction.
            added_source = 'opp_package_contract_probe.galaxy'
            added_marker = '// isolated-package-new-manifest-entry'
            (package / 'source' / added_source).write_text(added_marker + '\n')
            manifest = package / 'tools/galaxy_sources.json'
            names = json.loads(manifest.read_text())
            names.insert(len(names) - 1, added_source)
            manifest.write_text(json.dumps(names) + '\n')
            markers.append(added_marker)
            subprocess.run([sys.executable, str(package / 'tools/generate_mod.py')],
                           cwd=unrelated_cwd, check=True, capture_output=True, text=True)
            subprocess.run([sys.executable, str(package / 'tools/generate_mod.py'), '--check'],
                           cwd=unrelated_cwd, check=True, capture_output=True, text=True)
            galaxy = (package / 'files/Base.SC2Data/LibC0DEC0DE.galaxy').read_text()
            xml = ET.parse(package / 'files/Triggers')
            block = xml.find("./Library/Element[@Type='CustomScript']/ScriptCode").text
            recovered = '\n'.join(line[16:] for line in block.splitlines()[1:-1]) + '\n'
            expected = '\n'.join((package / 'source' / name).read_text().rstrip() for name in names) + '\n'
            self.assertEqual(recovered, expected)
            for marker in markers:
                self.assertIn(marker, galaxy)
                self.assertIn(marker, recovered)
        for relative, before in repository_before.items():
            self.assertEqual((packager.MOD / relative).read_bytes(), before,
                             'Standalone package generation must not touch repository products')

    def test_checksums_describe_every_packaged_file_except_the_checksum_file(self):
        lines = (self.package / 'SHA256SUMS').read_text().splitlines()
        entries = dict(line.split('  ', 1)[::-1] for line in lines)
        expected = {path.relative_to(self.package).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in self.package.rglob('*') if path.is_file() and path.name != 'SHA256SUMS'}
        self.assertEqual(entries, expected)

    def test_owned_patch_ships_without_foreign_library_and_runs_from_another_cwd(self):
        owned = self.package / 'src/observer-plusplus-patches'
        self.assertEqual({path.name for path in owned.iterdir()},
                         {path.name for path in (ROOT / 'src/observer-plusplus-patches').iterdir() if path.is_file()})
        self.assertEqual((self.package / 'tools/patch_observer_plus_plus.py').read_bytes(),
                         (ROOT / 'tools/patch_observer_plus_plus.py').read_bytes())
        self.assertFalse(any('Lib7805B319' in path.name or path.suffix == '.mpq' for path in self.package.rglob('*')))
        with tempfile.TemporaryDirectory() as other:
            run = subprocess.run([sys.executable, str(self.package / 'tools/patch_observer_plus_plus.py'), '--help'],
                                 cwd=other, check=True, capture_output=True, text=True)
            self.assertIn('--install-dir', run.stdout)
            # Actual dependency/MPQ execution belongs to tests/functional.



class ImmutablePackageOutputTests(unittest.TestCase):
    def test_existing_historical_directory_and_zip_are_never_recreated(self):
        historical = 'OPP-CancelPopups-integration-1.3-20261018'
        for existing in ('directory', 'archive', 'both'):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                package = output / historical
                archive = output / (historical + '.zip')
                if existing in ('directory', 'both'):
                    package.mkdir()
                    (package / 'historical-sentinel').write_bytes(b'original release directory\x00')
                if existing in ('archive', 'both'):
                    archive.write_bytes(b'original release archive\x00')
                before = {path.relative_to(output): path.read_bytes()
                          for path in output.rglob('*') if path.is_file()}
                with self.assertRaisesRegex(SystemExit, 'immutable'):
                    packager.package(historical, output)
                after = {path.relative_to(output): path.read_bytes()
                         for path in output.rglob('*') if path.is_file()}
                self.assertEqual(after, before)
                self.assertEqual(package.exists(), existing in ('directory', 'both'))
                self.assertEqual(archive.exists(), existing in ('archive', 'both'))

    def test_existing_candidate_output_is_not_an_implicit_overwrite_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / 'candidate').mkdir()
            with self.assertRaises(SystemExit):
                packager.package('candidate', output)


class CandidateReadmeTests(unittest.TestCase):
    def test_explicit_candidate_readme_is_packaged_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            readme = output / 'candidate-notes.md'
            readme.write_text('Local candidate — final SC2 acceptance NOT RUN.\n')
            archive, _ = packager.package('readme-candidate', output, readme)
            self.assertEqual((output / 'readme-candidate/README.md').read_bytes(), readme.read_bytes())
            with zipfile.ZipFile(archive) as zipped:
                self.assertEqual(zipped.read('readme-candidate/README.md'), readme.read_bytes())

    def test_invalid_readme_is_rejected_before_creating_any_package_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            for readme in (output / 'missing.md', output):
                with self.subTest(readme=readme), self.assertRaises(SystemExit):
                    packager.package('invalid-readme', output, readme)
                self.assertFalse((output / 'invalid-readme').exists())
                self.assertFalse((output / 'invalid-readme.zip').exists())


if __name__ == '__main__':
    unittest.main()
