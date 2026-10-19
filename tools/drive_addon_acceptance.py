#!/usr/bin/env python3
"""Send real ESC/TAB through an explicitly supplied, PID/workspace-guarded UI helper.

This drives addon-acceptance only. Acceptance still requires its strict engine/UI
validator, original banks, screenshots and runtime logs; successful input is not PASS.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from acceptance_bank import read_bank
from verify_addon_acceptance import GROUPS

ROOT = Path(__file__).resolve().parents[1]
POLL_SECONDS = 0.05
# Pending is saved each .25 game seconds. Wait for a fresh additional tick,
# rather than deciding that ESC did nothing from a stale disk snapshot.
PROGRESS_GAME_WINDOW = 0.3125


def ready_context(bank):
    assert bank['Probe']['Fixture'] == 'addon-acceptance', 'Wrong fixture bank'
    pending = bank['Pending']
    case = pending['Case']
    assert case in GROUPS, 'Unknown addon acceptance case'
    assert pending['Ready'] == '1', 'Keyboard phase is not ready'
    count = len(GROUPS[case])
    remaining = int(pending['Remaining'])
    assert 0 < remaining <= count, 'No live cancellation targets'
    ready = bank[case + '/Ready']
    assert ready['Remaining'] == str(count) and bank[case]['Count'] == str(count)
    children = case.endswith('Child')
    assert bank[case]['SelectChildren'] == str(int(children))
    for index, object_type in enumerate(GROUPS[case]):
        assert ready[f'Child{index}Type'] == object_type
        assert ready[f'Child{index}Alive'] == ready[f'Child{index}Constructing'] == '1'
        assert int(ready[f'Child{index}Tag']) > 0
        assert ready[f'ChildSelected{index}' if children else f'ParentSelected{index}'] == '1'
    assert pending['GameSpeed'] == ready['GameSpeed'] == '0', 'Fixture-only Slower phase required'
    game_time, rate = float(pending['Time']), float(pending['GameRate'])
    assert math.isfinite(game_time) and math.isfinite(rate) and rate > 0
    return {'case': case, 'remaining': remaining, 'time': game_time,
            'speed': int(pending['GameSpeed']), 'rate': rate,
            'selected': 'children' if children else 'parents', 'count': count}


def progress_result(before, bank):
    pending = bank.get('Pending', {})
    if pending.get('Case') != before['case']:
        after = bank.get(before['case'] + '/After', {})
        assert after.get('Remaining') == '0', 'Fixture changed case without completing the previous targets'
        return 'complete'
    remaining = int(pending['Remaining'])
    assert 0 <= remaining <= before['remaining'], 'Target count increased during one input'
    if remaining < before['remaining']:
        return 'complete' if remaining == 0 else 'progress'
    assert pending.get('Ready') == '1', 'Fixture stopped without cancelling its targets'
    now = float(pending['Time'])
    assert math.isfinite(now) and now >= before['time'], 'Pending heartbeat moved backwards'
    return 'unchanged' if now - before['time'] >= PROGRESS_GAME_WINDOW else 'wait'


def send_key(helper, helper_hash, pid, key, *, run=subprocess.run):
    assert isinstance(pid, int) and pid > 0, 'An exact game PID is mandatory'
    assert key in ('Escape', 'Tab'), 'Only the observed addon keyboard protocol is allowed'
    assert helper.is_absolute() and helper.is_file() and not helper.is_symlink()
    assert hashlib.sha256(helper.read_bytes()).hexdigest() == helper_hash, 'Guarded helper changed during the run'
    # The external helper retains its unique PID/title, workspace5, fullscreen,
    # Hyprland focus and exact XWayland target checks on EVERY input. No native
    # input implementation or unguarded fallback lives in this driver.
    environment = dict(os.environ, SC2_UI_PID=str(pid), SC2_UI_TITLE='StarCraft II')
    run([sys.executable, str(helper), 'key', key], env=environment, check=True, timeout=30)


def require_restored_speed(bank):
    """Arrangement proof in addition to, never instead of, strict popup checks."""
    original = bank[next(iter(GROUPS))]['OriginalSpeed']
    assert original in {'0', '1', '2', '3', '4'}
    for case in GROUPS:
        setup = bank[case]
        after, expired = bank[case + '/After'], bank[case + '/Expired']
        assert setup['OriginalSpeed'] == setup['RestoredSpeed'] == expired['GameSpeed'] == original
        assert bank[case + '/Ready']['GameSpeed'] == after['GameSpeed'] == '0'
        assert float(after['Time']) <= float(setup['RestoredTime']) < float(expired['Time'])
    # Later source/negative/retention/boundary controls must use the original
    # speed too. Group Created events precede the temporary speed change.
    for name, fields in bank.items():
        # Pending is the last saved keyboard heartbeat, not a live speed getter.
        if 'GameSpeed' not in fields or name == 'Pending':
            continue
        if name.startswith('Event'):
            case = fields['Case']
        else:
            case = name.split('/')[0]
        if case not in GROUPS:
            assert fields['GameSpeed'] == original, ('Speed leaked beyond keyboard phase', name)


def save_inputs(path, steps):
    path.write_text(json.dumps(steps, ensure_ascii=False, indent=2) + '\n')


def wait_for_progress(bank_path, before, deadline):
    while time.monotonic() < deadline:
        try:
            bank = read_bank(bank_path)
        except (ET.ParseError, OSError):
            time.sleep(POLL_SECONDS)
            continue
        result = progress_result(before, bank)
        if result != 'wait':
            return result, bank
        time.sleep(POLL_SECONDS)
    raise RuntimeError('No fresh Pending heartbeat after input; refusing a blind Tab/ESC')


def drive(pid, revision, helper, bank_path, output, screens, *, first_only=False, timeout=900):
    assert re.fullmatch(r'[A-Za-z0-9]+', revision), 'Revision must be ASCII alphanumeric'
    assert pid > 0 and helper.is_absolute() and helper.is_file() and not helper.is_symlink()
    assert bank_path.stem == 'OPPBuildingCancel' + revision, 'Bank belongs to another revision'
    helper_hash = hashlib.sha256(helper.read_bytes()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as initial:
        initial.write('[]\n')
    screens.mkdir(parents=True, exist_ok=True)
    steps, completed, captured = [], set(), set()
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        try:
            bank = read_bank(bank_path)
        except (ET.ParseError, OSError):
            time.sleep(POLL_SECONDS)
            continue
        assert bank['Probe']['Fixture'] == 'addon-acceptance'
        for case in captured:
            if bank.get(case + '/After', {}).get('Remaining') == '0':
                assert any(step['case'] == case and step['key'] == 'Escape' for step in steps)
                completed.add(case)
        if bank.get('Finished', {}).get('Done') == '1':
            assert completed == set(GROUPS), ('All 17 physical cases must finish', completed)
            require_restored_speed(bank)
            print('All 17 input cases completed; strict acceptance validation remains required.', flush=True)
            return
        if first_only and bank.get('SingleStarportTechLabParent/After', {}).get('Remaining') == '0':
            print('First case completed: PARTIAL input control only.', flush=True)
            return
        pending = bank.get('Pending', {})
        if pending.get('Ready') != '1' or pending.get('Remaining') == '0':
            time.sleep(POLL_SECONDS)
            continue
        before = ready_context(bank)
        case = before['case']
        assert case not in completed, 'Completed case unexpectedly became ready again'
        assert sum(step['case'] == case for step in steps) < before['count'] * 3 + 4, 'Input attempt limit exceeded'
        if case not in captured:
            screenshot = screens / f'addon-{revision}-{case}-ready.png'
            assert not screenshot.exists(), 'Refusing to overwrite ready screenshot'
            subprocess.run(['grim', '-o', 'HDMI-A-1', str(screenshot)], check=True, timeout=15)
            captured.add(case)
        send_key(helper, helper_hash, pid, 'Escape')
        step = dict(case=case, key='Escape', input='PID/workspace scoped XTest helper',
                    pid=pid, revision=revision, helper=str(helper), helper_sha256=helper_hash,
                    selected=before['selected'], before_remaining=before['remaining'],
                    before_game_time=before['time'], game_speed=before['speed'], game_rate=before['rate'])
        steps.append(step)
        save_inputs(output, steps)
        # Includes fresh disk heartbeat time, not the old fixed .4s wall sleep.
        result, after = wait_for_progress(bank_path, before, time.monotonic() + max(3, 1 / before['rate']))
        step['after_pending_case'] = after.get('Pending', {}).get('Case')
        step['after_remaining'] = (after[case + '/After']['Remaining']
                                   if step['after_pending_case'] != case
                                   else after['Pending']['Remaining'])
        step['progress'] = result
        save_inputs(output, steps)
        if result == 'complete':
            completed.add(case)
        elif result == 'unchanged':
            # Recheck all initial physical-selection/readiness guards against
            # the latest bank before the old observed subgroup action.
            current = ready_context(after)
            assert current['case'] == case
            send_key(helper, helper_hash, pid, 'Tab')
            steps.append(dict(case=case, key='Tab', input='PID/workspace scoped XTest helper',
                              pid=pid, revision=revision, helper=str(helper), helper_sha256=helper_hash,
                              before_remaining=current['remaining'], before_game_time=current['time'],
                              reason='Fresh Pending heartbeat confirms ESC left target count unchanged'))
            save_inputs(output, steps)
        print(case + ': ' + result, flush=True)
    raise RuntimeError('Addon input driver timeout; no acceptance claimed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pid', type=int)
    parser.add_argument('revision')
    parser.add_argument('--ui-helper', type=Path, required=True)
    parser.add_argument('--bank', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--screens', type=Path)
    parser.add_argument('--first-only', action='store_true')
    args = parser.parse_args()
    bank = args.bank
    if bank is None:
        cfg = json.loads((ROOT / 'local.json').read_text())
        bank = Path(cfg['documents']) / 'Banks' / ('OPPBuildingCancel' + args.revision + '.SC2Bank')
    drive(args.pid, args.revision, args.ui_helper, bank,
          args.output or ROOT / 'reports/editor-validation' / ('addon-' + args.revision + '-esc-inputs.json'),
          args.screens or ROOT / 'reports/editor-validation', first_only=args.first_only)


if __name__ == '__main__':
    main()
