"""Strict reader for new acceptance banks; old diagnostic validators stay historical."""
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def read_bank(path):
    root = ET.parse(path).getroot()
    assert root.tag == 'Bank', 'Not an SC2 bank'
    result = {}
    for section in root.findall('Section'):
        name = section.attrib['name']
        assert name not in result, 'Duplicate bank section: ' + name
        values = {}
        for key in section.findall('Key'):
            field = key.attrib['name']
            assert field not in values, 'Duplicate bank key: ' + name + '/' + field
            children = list(key)
            assert len(children) == 1 and children[0].tag == 'Value', 'Missing/ambiguous bank value'
            attrs = children[0].attrib
            assert len(attrs) == 1 and next(iter(attrs)) in {'string', 'text', 'int', 'fixed', 'flag'}, 'Unknown bank value encoding'
            values[field] = next(iter(attrs.values()))
        result[name] = values
    return result


def number(fields, name):
    value = float(fields[name])
    assert math.isfinite(value), 'Nonfinite bank number: ' + name
    return value


def trace(bank):
    assert bank['Finished']['Done'] == '1', 'Fixture did not finish'
    assert bank['Finished'].get('Overflow', '0') == '0', 'Fixture registry overflow'
    count = int(bank['Finished']['Events'])
    assert count >= 0
    keys = {key for key in bank if re.fullmatch(r'Event\d+', key)}
    assert keys == {f'Event{i}' for i in range(1, count + 1)}, 'Truncated/noncontiguous event trace'
    result = [bank[f'Event{i}'] for i in range(1, count + 1)]
    times = [number(event, 'Time') for event in result]
    assert times == sorted(times), 'Engine trace time reversed'
    return result
