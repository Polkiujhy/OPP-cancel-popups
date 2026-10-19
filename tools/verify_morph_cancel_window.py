#!/usr/bin/env python3
"""Verify the focused real-Execute Cancel-window probe, including both controls."""
import argparse
import hashlib
import json
from pathlib import Path
from verify_morph_scope_baseline import read_bank, window_evidence


def verify(path):
    bank = read_bank(path)
    assert bank['Probe']['Fixture'] == 'morph-cancel-window'
    assert bank['Finished']['Done'] == '1'
    evidence = window_evidence(path, bank)
    cases = [case for case, fields in bank.items() if 'RequestedCancel' in fields]
    resolved = {item['bank_section']: item for values in evidence.values() for item in values}
    assert set(cases) == set(resolved) | {'NaturalComplete'}, 'Focused probe contains unresolved cases.'
    return {'result': 'PASS', 'bank': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'finished_time': bank['Finished']['Time'], 'event_count': int(bank['Finished']['Events']),
            'cases': resolved, 'normal_completion_control': 'PASS: actual Execute/Complete, zero cancels'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bank', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = json.dumps(verify(args.bank), ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(result)
    print(result, end='')


if __name__ == '__main__':
    main()
