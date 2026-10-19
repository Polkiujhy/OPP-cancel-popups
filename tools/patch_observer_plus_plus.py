#!/usr/bin/env python3
"""Patch one known local Observer PlusPlus into a new, byte-verified dependency.

Only our transform/snippets ship. The source mod, generated foreign library and
MPQ remain local. No Battle.net identifier or original dependency is replaced.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'src/observer-plusplus-patches'
MANIFEST = ASSETS / 'track-unit-kills-v1.json'
GALAXY = 'Base.SC2Data/Lib7805B319.galaxy'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(directory):
    paths = sorted(Path(directory).rglob('*'))
    if any(path.is_symlink() for path in paths):
        raise ValueError('Dependency symlinks are not accepted')
    return {path.relative_to(directory).as_posix(): digest(path) for path in paths if path.is_file()}


def transformation():
    spec = json.loads(MANIFEST.read_text())
    assert spec['schema'] == 1 and set(spec['input_files']) == {'Triggers', GALAXY}
    assets = {name: (ASSETS / spec[name]).read_text() for name in ('start_asset', 'slot_asset')}
    return spec, assets


def replace_one(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Unknown/repeated source shape: ' + before[:100])
    return text.replace(before, after, 1)


def element_block(text, element_type, identity):
    pattern = r'        <Element Type="' + element_type + r'" Id="' + identity + r'">[\s\S]*?        </Element>'
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise ValueError('Unknown/duplicate XML element: ' + identity)
    return matches[0].group()


def transform_bytes(triggers, galaxy):
    """Pure exact transform; all non-target XML and Galaxy bytes are retained."""
    spec, assets = transformation()
    original = {'Triggers': triggers, GALAXY: galaxy}
    if {name: hashlib.sha256(data).hexdigest() for name, data in original.items()} != spec['input_files']:
        raise ValueError('Unknown or already patched input: full input SHA256 mismatch')
    xml = triggers.decode('utf-8')
    newline = '\r\n' if '\r\n' in xml else '\n'
    parsed = ET.fromstring(xml)
    library = parsed.find("Library[@Id='" + spec['library'] + "']")
    assert library is not None
    trigger = library.find("Element[@Type='Trigger'][@Id='" + spec['trigger'] + "']")
    assert trigger is not None and trigger.find('Disabled') is None
    assert trigger.find("Event[@Id='99346820']") is not None
    assert len(trigger.findall('Condition')) == 2
    assert library.find("Element[@Id='" + spec['start_action'] + "']") is None
    assert library.find("Element[@Id='" + spec['slot_action'] + "']") is None
    for kind in ('neutral', 'baneling'):
        identity = spec[kind + '_parameter']
        node = library.find("Element[@Type='Param'][@Id='" + identity + "']")
        assert node is not None and node.find('FunctionCall').attrib['Id'] == spec[kind + '_original_call']
        old = element_block(xml, 'Param', identity)
        parameter_def = re.search(r'            <ParameterDef[^\r\n]+', old).group()
        new = (f'        <Element Type="Param" Id="{identity}">\n' + parameter_def + '\n'
               '            <CustomType Type="int"/>\n            <ScriptCode>\n                '
               + escape(spec[kind + '_expression']) + '\n            </ScriptCode>\n        </Element>')
        xml = replace_one(xml, old, new.replace('\n', newline))
    old = element_block(xml, 'Trigger', spec['trigger'])
    anchor = '            <Action Type="FunctionCall" Library="7805B319" Id="' + spec['neutral_action'] + '"/>'
    before_ref = '            <Action Type="FunctionCall" Library="7805B319" Id="' + spec['start_action'] + '"/>'
    after_ref = '            <Action Type="FunctionCall" Library="7805B319" Id="' + spec['slot_action'] + '"/>'
    changed = replace_one(old, anchor, before_ref + newline + anchor + newline + after_ref)
    xml = replace_one(xml, old, changed)
    additions = []
    for kind, asset in (('start', 'start_asset'), ('slot', 'slot_asset')):
        additions.append('        <Element Type="FunctionCall" Id="' + spec[kind + '_action'] + '">\n'
                         '            <FunctionDef Type="FunctionDef" Library="Ntve" Id="00000123"/>\n'
                         '            <ScriptCode>\n' + ''.join('                ' + escape(line) + '\n' for line in assets[asset].splitlines())
                         + '            </ScriptCode>\n        </Element>\n')
    # Insert inside the target library, retaining the other library verbatim.
    start = xml.index('<Library Id="' + spec['library'] + '">')
    end = xml.index('    </Library>', start)
    xml = xml[:end] + ''.join(additions).replace('\n', newline) + xml[end:]
    ET.fromstring(xml)
    code = galaxy.decode('utf-8')
    code_newline = '\r\n' if '\r\n' in code else '\n'
    begin = code.index('bool ' + spec['callback'] + ' (')
    end = code.index('\nvoid lib7805B319_gt_TrackUnitKills_Init', begin)
    body = code[begin:end]
    def script(asset):
        return ''.join('    ' + line + code_newline for line in assets[asset].splitlines())
    anchor = '    if ((lv_playerSlot == 15)) {'
    body = replace_one(body, anchor, script('start_asset') + code_newline + anchor)
    body = replace_one(body, 'lib7805B319_gf_OppositePlayerSlot(UnitGetOwner(lv_deadUnit))',
                       'lib7805B319_gf_OppositePlayerSlot((UnitGetOwner(lv_deadUnit) - 1))')
    body = replace_one(body, 'lv_playerSlot = UnitGetOwner(lv_deadUnit);', 'lv_playerSlot = ' + spec['baneling_expression'] + ';')
    anchor = '    if ((lib7805B319_gf_isStructure(lv_killedUnitType) == false)) {'
    body = replace_one(body, anchor, script('slot_asset') + code_newline + anchor)
    return {'Triggers': xml.encode('utf-8'), GALAXY: (code[:begin] + body + code[end:]).encode('utf-8')}


def verify_archive(archive, components, expected_files, mpqcli):
    """Read every expected member; byte comparison, not merely an MPQ checksum."""
    assert inventory(components) == expected_files, 'Frozen dependency components changed'
    for name in expected_files:
        actual = subprocess.check_output([str(mpqcli), 'read', name.replace('/', '\\'), str(archive)])
        assert actual == (components / name).read_bytes(), 'Dependency MPQ member mismatch: ' + name


def transform_identity():
    spec, _ = transformation()
    return {'manifest_sha256': digest(MANIFEST), 'patcher_sha256': digest(Path(__file__)),
            'asset_sha256': {spec[key]: digest(ASSETS / spec[key]) for key in ('start_asset', 'slot_asset')}}


def verify_report(report_path, components, archive, installed, mpqcli):
    report = json.loads(Path(report_path).read_text())
    spec, _ = transformation()
    assert report['schema'] == 1 and report['patch_id'] == spec['patch_id']
    assert report['input_files'] == spec['input_files'] and report['transform'] == transform_identity()
    assert report['dependency_name'] == Path(components).name == Path(installed).name
    assert report['components'] == report['output_directory']
    assert Path(installed).resolve() == Path(report['installed']['path']).resolve(), 'Verify the actual declared live installation'
    assert {name: report['source_files'][name] for name in spec['input_files']} == spec['input_files']
    assert report['byte_verified'] is True
    assert digest(archive) == report['archive']['sha256'] == digest(installed) == report['installed']['sha256']
    changed = {name for name in report['source_files'] if report['source_files'][name] != report['output_files'][name]}
    assert changed == set(spec['input_files']) and set(report['source_files']) == set(report['output_files'])
    verify_archive(Path(archive), Path(components), report['output_files'], mpqcli)
    # The installed bytes have the identical full digest and every frozen MPQ
    # member was read above. Do not trust the report's declared install path.
    return report


def patch(source, output, mpqcli, install_dir):
    source, output, mpqcli, install_dir = map(lambda path: Path(path).resolve(), (source, output, mpqcli, install_dir))
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*\.SC2Mod', output.name) or output.name.casefold() == source.name.casefold():
        raise ValueError('Use a new, separately named SC2Mod')
    if source == output or source in output.parents or output in source.parents:
        raise ValueError('Source/output must be separate directories')
    archive = Path(str(output) + '.mpq')
    report_path = Path(str(output) + '.patch.json')
    installed = install_dir / output.name
    for path in (output, archive, report_path, installed):
        if path.exists() or path.is_symlink():
            raise ValueError('Immutable output collision: ' + str(path))
    source_files = inventory(source)
    changed = transform_bytes((source / 'Triggers').read_bytes(), (source / GALAXY).read_bytes())
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, output)
    for name, data in changed.items():
        (output / name).write_bytes(data)
    output_files = inventory(output)
    assert set(source_files) == set(output_files)
    assert {name for name in source_files if source_files[name] != output_files[name]} == set(changed)
    subprocess.run([str(mpqcli), 'create', str(output), '-g', 'starcraft2', '-o', str(archive)], check=True, capture_output=True)
    verify_archive(archive, output, output_files, mpqcli)
    install_dir.mkdir(parents=True, exist_ok=True)
    with installed.open('xb') as target:
        target.write(archive.read_bytes())
    spec, _ = transformation()
    report = {'schema': 1, 'patch_id': spec['patch_id'], 'dependency_name': output.name,
              'input_files': spec['input_files'], 'source_files': source_files, 'output_files': output_files,
              'archive': {'path': str(archive), 'sha256': digest(archive)},
              'installed': {'path': str(installed), 'sha256': digest(installed)},
              'components': str(output), 'output_directory': str(output),
              'transform': transform_identity(), 'byte_verified': True}
    with report_path.open('x') as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
    return report_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mpqcli', type=Path, required=True)
    parser.add_argument('--install-dir', type=Path, required=True)
    args = parser.parse_args()
    print(patch(args.source, args.output, args.mpqcli, args.install_dir))


if __name__ == '__main__':
    main()
