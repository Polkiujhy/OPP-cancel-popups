#!/usr/bin/env python3
"""Tie a runtime map receipt to staged hashes and byte-preserved private artifacts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from acceptance_bank import read_bank
from patch_observer_plus_plus import verify_report as verify_observer_patch

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(receipt_path, report_path, canonical_path, archive_path, *, observer_patch_manifest=None,
           observer_dependency_directory=None, observer_dependency_archive=None):
    report = json.loads(report_path.read_text())
    receipt = read_bank(receipt_path)['Provenance']
    metadata = report['runtime_provenance']
    assert receipt['Recorded'] == '1'
    assert receipt_path.stem == metadata['bank_name'], 'Receipt belongs to another revision'
    assert all(receipt[key] == value for key, value in metadata.items()), 'Runtime/staging provenance mismatch'
    assert receipt['canonical_galaxy_sha256'] == report['canonical_galaxy_sha256'] == digest(canonical_path)
    assert receipt['mod_archive_sha256'] == report['archive_sha256'] == digest(archive_path)
    assert report['byte_verified'] is True
    assert receipt['revision'] == report['revision'] and receipt['fixture'] == report['fixture']
    assert receipt['private_mod'] == Path(report['mod']).name
    assert receipt['private_map'] == Path(report['map']).name
    assert json.loads(receipt['dependencies']) == report['dependencies']
    assert json.loads(receipt['module_sha256']) == report['module_sha256']
    assert json.loads(receipt['canonical_file_sha256']) == report['canonical_file_sha256']
    canonical_dir = canonical_path.parent.parent
    actual_files = {path.relative_to(canonical_dir).as_posix(): digest(path)
                    for path in canonical_dir.rglob('*') if path.is_file()}
    assert actual_files == report['canonical_file_sha256'], 'Production assets/source drifted between final fixture runs'
    manifest = json.loads((ROOT / 'tools/galaxy_sources.json').read_text())
    assert set(report['module_sha256']) == set(manifest), 'Receipt omits a production module'
    assert all(report['module_sha256'][name] == digest(ROOT / 'source' / name) for name in manifest)
    observer = None
    supplied = (observer_patch_manifest, observer_dependency_directory, observer_dependency_archive)
    if any('observer_patch_manifest' in fields for fields in (metadata, report, receipt)) or any(value is not None for value in supplied):
        assert all(value is not None for value in supplied), 'Patched dependency requires frozen manifest, directory and MPQ'
        assert digest(observer_patch_manifest) == receipt['observer_patch_manifest_sha256'] == report['observer_patch_manifest_sha256']
        declared = json.loads(Path(observer_patch_manifest).read_text())
        assert declared == json.loads(receipt['observer_patch_manifest']) == report['observer_patch_manifest']
        observer = verify_observer_patch(observer_patch_manifest, observer_dependency_directory,
                                         observer_dependency_archive, Path(declared['installed']['path']), Path(os.environ.get('OPP_MPQCLI', ROOT / 'tools/mpqcli')))
        assert 'file:Mods/' + observer['dependency_name'] in report['dependencies']
    return {'result': 'PASS', 'scope': 'Staged/runtime identity and frozen archive bytes; no behavior/role claim',
            'revision': receipt['revision'], 'fixture': receipt['fixture'],
            'canonical_galaxy_sha256': receipt['canonical_galaxy_sha256'],
            'mod_archive_sha256': receipt['mod_archive_sha256'],
            'dependencies': report['dependencies'], 'receipt_sha256': digest(receipt_path),
            'observer_patch': observer}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt', type=Path)
    parser.add_argument('stage_report', type=Path)
    parser.add_argument('--canonical', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True, help='Frozen installed private MPQ from this exact run')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--observer-patch-manifest', type=Path)
    parser.add_argument('--observer-dependency-directory', type=Path)
    parser.add_argument('--observer-dependency-archive', type=Path)
    args = parser.parse_args()
    output = json.dumps(verify(args.receipt, args.stage_report, args.canonical, args.archive,
                              observer_patch_manifest=args.observer_patch_manifest,
                              observer_dependency_directory=args.observer_dependency_directory,
                              observer_dependency_archive=args.observer_dependency_archive), ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(output)
    print(output, end='')


if __name__ == '__main__':
    main()
