#!/usr/bin/env python3
"""Package our integration sources under a new name, never replacing a release."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / 'files'
MANIFEST = ROOT / 'tools/galaxy_sources.json'
FILES = (
    'Triggers', 'Base.SC2Data/LibC0DEC0DE.galaxy',
    'Base.SC2Data/LibC0DEC0DE_h.galaxy',
    'Base.SC2Data/GameData/GameData.xml',
    'Base.SC2Data/UI/Layout/DescIndex.SC2Layout',
    'Base.SC2Data/UI/Layout/OPPCancelPopups.SC2Layout',
    'Base.SC2Data/UI/FontStyles.SC2Style',
)


def package(name, output, readme=None):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name):
        raise SystemExit('Package name must be one plain directory name.')
    out = output.resolve() / name
    archive = out.parent / (name + '.zip')
    if out.exists() or out.is_symlink() or archive.exists() or archive.is_symlink():
        raise SystemExit('Choose a new package name/output; existing artifacts are immutable.')
    readme = Path(readme) if readme is not None else ROOT / 'distribution/README-INTEGRATION.md'
    if not readme.is_file():
        raise SystemExit('README must be an existing readable file.')
    readme_text = readme.read_text()
    sources = tuple(json.loads(MANIFEST.read_text()))
    subprocess.run([sys.executable, str(ROOT / 'tools/generate_mod.py'), '--check'], check=True)

    def write(relative, content):
        path = out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    out.mkdir(parents=True)
    for relative in FILES:
        write('files/' + relative, (MOD / relative).read_text())
    for source in sources:
        write('source/' + source, (ROOT / 'source' / source).read_text())
    strings = (MOD / 'enUS.SC2Data/LocalizedData/GameStrings.txt').read_text()
    write('files/enUS.SC2Data/LocalizedData/GameStrings.txt',
          '\n'.join(line for line in strings.splitlines() if line.startswith('OPP/')) + '\n')
    components = ET.parse(MOD / 'ComponentList.entries.xml').getroot()
    for child in list(components):
        if child.attrib.get('Type') == 'info':
            components.remove(child)
    write('files/ComponentList.entries.xml', ET.tostring(components, encoding='unicode') + '\n')
    generator = (ROOT / 'tools/generate_mod.py').read_text()
    generator = generator.replace("ROOT / 'src/OPP_CancelPopups.SC2Mod'", "ROOT / 'files'")
    generator = generator.replace("ROOT / 'source'", "ROOT / 'source'")
    write('tools/generate_mod.py', generator)
    write('tools/galaxy_sources.json', MANIFEST.read_text())
    # Only our exact-input transform and authored snippets ship. The complete
    # foreign library, generated dependency MPQ and local report never do.
    write('tools/patch_observer_plus_plus.py', (ROOT / 'tools/patch_observer_plus_plus.py').read_text())
    for path in sorted((ROOT / 'src/observer-plusplus-patches').iterdir()):
        if path.is_file():
            write('src/observer-plusplus-patches/' + path.name, path.read_text())
    write('OBSERVER-PLUSPLUS-PATCH.md', (ROOT / 'OBSERVER-PLUSPLUS-PATCH.md').read_text())
    write('README.md', readme_text)
    # Execute the included generator; it must work independently after extraction.
    subprocess.run([sys.executable, str(out / 'tools/generate_mod.py')], cwd=out, check=True)
    subprocess.run([sys.executable, str(out / 'tools/generate_mod.py'), '--check'], cwd=out, check=True)
    for relative in ('Triggers', 'Base.SC2Data/LibC0DEC0DE.galaxy', 'Base.SC2Data/LibC0DEC0DE_h.galaxy'):
        if (out / 'files' / relative).read_bytes() != (MOD / relative).read_bytes():
            raise SystemExit('Packaged generator changed canonical bytes: ' + relative)
    if {path.name for path in (out / 'source').glob('*.galaxy')} != set(sources):
        raise SystemExit('Packaged source set differs from its manifest.')
    for path in (out / 'files').rglob('*'):
        if path.is_file() and (path.suffix in ('.xml', '.SC2Layout', '.SC2Style') or path.name == 'Triggers'):
            ET.parse(path)
    paths = sorted(path for path in out.rglob('*') if path.is_file())
    write('SHA256SUMS', ''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(out).as_posix()}\n' for path in paths))
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(out.rglob('*')):
            if path.is_file():
                zipped.write(path, name + '/' + path.relative_to(out).as_posix())
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise SystemExit('Corrupt package ZIP.')
        for path in out.rglob('*'):
            if path.is_file() and zipped.read(name + '/' + path.relative_to(out).as_posix()) != path.read_bytes():
                raise SystemExit('Package ZIP byte mismatch: ' + str(path))
    return archive, len(paths) + 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True, help='New candidate name; existing outputs are never replaced.')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/integration', help='Parent directory of the named package and ZIP.')
    parser.add_argument('--readme', type=Path, help='Explicit candidate README; historical default remains unchanged.')
    args = parser.parse_args()
    archive, count = package(args.name, args.output, args.readme)
    print(f'Created and byte-verified: {archive}')
    print(f'Files: {count}; size: {archive.stat().st_size} bytes')


if __name__ == '__main__':
    main()
