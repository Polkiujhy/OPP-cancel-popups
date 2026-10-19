"""Synthetic bank-protocol tests; real engine acceptance requires a fresh SC2 run."""
import copy
from collections import Counter
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import verify_mixed_regression as validator
from acceptance_bank import read_bank, trace


def snapshot(time, groups=(), pending=(), *, units=12, warps=3, displayed=14, starts=None):
    fields = {'Time': str(time), 'UnitCancels': str(units), 'Prisms': str(warps),
              'Warps': str(warps), 'Buildings': '6', 'Research': '1', 'Morphs': '1',
              'Preserved': '1', 'Displayed': str(displayed), 'QueueGroups': str(len(pending)),
              'QueuedCancels': str(sum(group[3] for group in pending))}
    for row in range(3):
        fields[f'Row{row}Visible'] = '0'
    for row, group in enumerate(groups):
        object_type, owner, kind, count = group
        prefix = f'Row{row}'
        fields.update({prefix + 'Visible': '1', prefix + 'Key': object_type,
                       prefix + 'Owner': str(owner), prefix + 'Kind': str(kind),
                       prefix + 'Count': str(count), prefix + 'Name': object_type,
                       prefix + 'Status': validator.status(count),
                       prefix + 'Icon': object_type + '.dds',
                       prefix + 'Remaining': str(starts[group] + 5 - time)})
    for index, group in enumerate(pending):
        prefix = f'Queue{index}'
        fields.update({prefix + 'Key': group[0], prefix + 'Owner': str(group[1]),
                       prefix + 'Kind': str(group[2]), prefix + 'Copies': str(group[3])})
    return fields


def case_bank(label):
    """Known internally consistent protocol input, never claimed as SC2 evidence."""
    owner, types, train, provider = validator.DEATH_CASES[label]
    overlapping = label == 'OverlapMixed'
    death_time = 20.25 if overlapping else 20.125
    after_time = 20.5 if overlapping else 20.375
    groups = [train] + [(kind, owner, 2, count) for kind, count in Counter(types).items()]
    active, pending = groups[:3], groups[3:]
    starts = {group: (20 if group == train else death_time + 0.125) for group in groups}
    bank = {'Expected': {}, 'Damage': {}, 'DeniedExpired': {'Time': '10'}}
    for object_type in (*types, train[0]):
        bank['Expected'][object_type + 'Name'] = object_type
        bank['Expected'][object_type + 'Icon'] = object_type + '.dds'
    bank[label + '/Initial'] = snapshot(18)
    before = snapshot(20)
    before['WarpCount'] = str(len(types))
    providers = {'A': '700', 'B': '701', 'Pylon': '702'}
    for name, tag in providers.items():
        before.update({name + 'Tag': tag, name + 'Alive': '1', name + 'Owner': str(owner),
                       name + 'Type': 'Pylon' if name == 'Pylon' else 'WarpPrismPhasing'})
    events = []

    def event(label, when, **fields):
        result = {'Supplement': '1', 'Case': label_case, 'Phase': label_case,
                  'Label': label, 'Time': str(when), 'Tag': '0', 'Owner': '0', 'Alive': '1',
                  'Ability': '', 'Command': '0', 'Object': ''}
        result.update(fields)
        events.append(result)

    label_case = label
    for index, object_type in enumerate(types):
        child, producer = str(100 + index), str(200 + index)
        prefix = f'Warp{index}'
        before.update({prefix + 'Tag': child, prefix + 'Owner': str(owner),
                       prefix + 'Type': object_type, prefix + 'Alive': '1',
                       prefix + 'Constructing': '1', prefix + 'Power': '2'})
        for source in providers:
            before[prefix + 'From' + source] = '1' if source == provider or (overlapping and source == 'A') else '0'
        event('Order', 19.8125, Tag=producer, Owner=str(owner), Ability='WarpGateTrain',
              Command=str({'Zealot': 0, 'Stalker': 1, 'Sentry': 5}[object_type]), Phase='SupplementSetup')
        event('WarpCreated', 19.875, Tag=producer, Ability='WarpGateTrain', ChildTag=child,
              ChildOwner=str(owner), ChildAlive='1', ChildConstructing='1', Object=object_type)
        event('ConstructCancel', death_time + 0.0625, Tag=producer, ChildTag=child, Object=object_type)
    bank[label + '/Before'] = before
    queue_ability = 'que5CancelToSelection' if train[0] == 'SCV' else 'que5'
    event('Order', 20, Tag='900', Owner=str(train[1]), Ability=queue_ability)
    event('TrainCancel', 20, Tag='900', Owner=str(train[1]), Object=train[0])
    for suffix, count in (('TrainBefore', 1), ('TrainAfter', 0)):
        fields = {'Tag': '900', 'Alive': '1', **{f'Slot{i}Count': '0' for i in range(1, 6)}}
        fields.update(Slot1Count=str(count), Slot1=train[0])
        bank[label + '/' + suffix] = fields
    bank[label + '/TrainShown'] = snapshot(20.125, [train], units=13, displayed=15, starts=starts)

    def death(source, key, when):
        tag = providers[source]
        killer = str(3 - owner)
        fields = {key + 'Ready': '1', key + 'Effect': 'ActualWeaponDamage', key + 'Tag': tag,
                  key + 'Owner': str(owner), key + 'KillingPlayer': killer,
                  key + 'KillingTag': '800', key + 'Time': str(when)}
        bank['Damage'].update(fields)
        event('Died', when, Tag=tag, Owner=str(owner), Alive='0', Removed='0',
              Object='Pylon' if source == 'Pylon' else 'WarpPrismPhasing',
              KillingPlayer=killer, KillingTag='800')

    death(provider, label + ('KillPylon' if provider == 'Pylon' else 'Kill' + provider), death_time)
    after = snapshot(after_time, active, pending, units=13 + len(types), warps=3 + len(types),
                     displayed=14 + len(active), starts=starts)
    after['WarpCount'] = str(len(types))
    for index in range(len(types)):
        after[f'Warp{index}Alive'] = '0'
        for field in ('Tag', 'Type', 'Owner'):
            after[f'Warp{index}' + field] = before[f'Warp{index}' + field]
    bank[label + '/After'] = after
    if overlapping:
        event('Order', 20.125, Tag=providers['A'], Owner=str(owner), Ability='TransportMode')
        event('Ability', 20.125, Tag=providers['A'], Owner=str(owner), Ability='TransportMode', Stage='-3')
        kept = snapshot(20.25, [train], units=13, displayed=15, starts=starts)
        for index in range(len(types)):
            prefix = f'Warp{index}'
            for field in ('Tag', 'Type', 'Owner'):
                kept[prefix + field] = before[prefix + field]
            kept.update({prefix + 'Alive': '1', prefix + 'Constructing': '1', prefix + 'FromB': '1',
                         prefix + 'FromA': '0', prefix + 'Power': '2'})
        bank[label + '/Kept'] = kept
        death('A', label + 'KillClosedA', after_time)
        bank[label + '/Dedup'] = copy.deepcopy(after)
        bank[label + '/Dedup']['Time'] = str(after_time + 0.125)
    bank[label + '/Near'] = snapshot(24.75, active, pending, units=13 + len(types),
                                    warps=3 + len(types), displayed=14 + len(active), starts=starts)
    if pending:
        wave_starts = {group: 25 for group in pending}
        bank[label + '/Wave'] = snapshot(25.5, pending, units=13 + len(types), warps=3 + len(types),
                                        displayed=14 + len(groups), starts=wave_starts)
        bank[label + '/WaveNear'] = snapshot(29.75, pending, units=13 + len(types), warps=3 + len(types),
                                            displayed=14 + len(groups), starts=wave_starts)
    else:
        bank[label + '/Wave'] = snapshot(25.5, units=13 + len(types), warps=3 + len(types), displayed=14 + len(groups))
    bank[label + '/Expired'] = snapshot(30.5 if pending else 25.5, units=13 + len(types),
                                        warps=3 + len(types), displayed=14 + len(groups))
    events.sort(key=lambda item: float(item['Time']))
    return bank, events


class MixedDeathSourceEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.label = 'OverlapMixed'
        self.bank, self.events = case_bank(self.label)

    def verify(self, bank=None, events=None, label=None):
        return validator.verify_death_case(self.bank if bank is None else bank,
                                           self.events if events is None else events,
                                           self.label if label is None else label)

    def test_each_extra_case_requires_its_own_exact_source_and_group_counts(self):
        for label, counts in (('PrismDeath', (3, 2)), ('PylonDeath', (3, 3)), ('OverlapMixed', (4, 4))):
            with self.subTest(label=label):
                bank, events = case_bank(label)
                result = self.verify(bank, events, label)
                self.assertEqual((result['cancellations'], result['displayed_groups']), counts)

    def test_created_cancel_order_execute_and_death_cannot_be_replaced_by_done(self):
        for label in ('WarpCreated', 'ConstructCancel', 'Order', 'Ability', 'Died', 'TrainCancel'):
            with self.subTest(label=label):
                events = copy.deepcopy(self.events)
                index = next(i for i, event in enumerate(events) if event['Label'] == label)
                del events[index]
                with self.assertRaises(AssertionError):
                    self.verify(events=events)

    def test_duplicate_child_cancel_or_provider_death_is_red(self):
        for label in ('WarpCreated', 'ConstructCancel', 'Died'):
            with self.subTest(label=label):
                event = next(event for event in self.events if event['Label'] == label)
                with self.assertRaises(AssertionError):
                    self.verify(events=self.events + [event])

    def test_wrong_producer_child_owner_source_type_time_or_credit_is_red(self):
        mutations = [('WarpCreated', 'ChildTag', '999'), ('WarpCreated', 'ChildOwner', '1'),
                     ('WarpCreated', 'Ability', 'Train'), ('ConstructCancel', 'Tag', '999'),
                     ('ConstructCancel', 'Time', '21'), ('ConstructCancel', 'Object', 'Oracle'),
                     ('Died', 'Tag', '999'), ('Died', 'KillingPlayer', '0'),
                     ('Died', 'KillingTag', '0'), ('Died', 'Removed', '1'), ('Died', 'Alive', '1'),
                     ('TrainCancel', 'Time', '20.0625')]
        for label, key, value in mutations:
            with self.subTest(label=label, key=key):
                events = copy.deepcopy(self.events)
                next(event for event in events if event['Label'] == label)[key] = value
                with self.assertRaises(AssertionError):
                    self.verify(events=events)

    def test_power_survival_and_later_closed_source_death_must_publish_zero(self):
        mutations = [('Kept', 'Warp0FromB', '0'), ('Kept', 'Warp0Alive', '0'),
                     ('Kept', 'Warp0Constructing', '0'), ('Kept', 'Warp0FromA', '1'),
                     ('Kept', 'Prisms', '4'), ('Kept', 'UnitCancels', '14'),
                     ('Dedup', 'Prisms', '7'), ('Dedup', 'UnitCancels', '17'),
                     ('Before', 'Warp0FromB', '0'), ('Before', 'Warp0Tag', '999'),
                     ('Kept', 'Warp0Tag', '999'), ('Dedup', 'Warp0Type', 'Oracle')]
        for suffix, key, value in mutations:
            with self.subTest(suffix=suffix, key=key):
                bank = copy.deepcopy(self.bank)
                bank[self.label + '/' + suffix][key] = value
                with self.assertRaises(AssertionError):
                    self.verify(bank=bank)

    def test_consistently_shortened_timer_is_red_even_with_matching_near_deadline(self):
        bank = copy.deepcopy(self.bank)
        for suffix in ('After', 'Near'):
            fields = bank[self.label + '/' + suffix]
            fields['Row1Remaining'] = str(float(fields['Row1Remaining']) - 0.25)
        with self.assertRaises(AssertionError):
            self.verify(bank=bank)

    def test_target_name_icon_owner_count_timer_and_fourth_group_are_mandatory(self):
        mutations = [('After', 'Row1Name', 'Warp Prism'), ('After', 'Row1Icon', 'cancel.dds'),
                     ('After', 'Row1Owner', '1'), ('After', 'Row1Count', '2'),
                     ('After', 'Row1Status', 'Completed'), ('After', 'Row1Remaining', '0'),
                     ('Near', 'Row1Remaining', '0.75'), ('After', 'QueueGroups', '0'),
                     ('After', 'Queue0Copies', '2'), ('Wave', 'Row0Key', 'Oracle'),
                     ('Expired', 'UnitCancels', '17'), ('Expired', 'Displayed', '19')]
        for suffix, key, value in mutations:
            with self.subTest(suffix=suffix, key=key):
                bank = copy.deepcopy(self.bank)
                bank[self.label + '/' + suffix][key] = value
                with self.assertRaises(AssertionError):
                    self.verify(bank=bank)

    def test_bank_xml_roundtrip_does_not_relax_the_real_trace_protocol(self):
        bank = copy.deepcopy(self.bank)
        bank['Finished'] = {'Done': '1', 'Events': str(len(self.events))}
        bank.update({f'Event{i}': event for i, event in enumerate(self.events, 1)})
        root = ET.Element('Bank')
        for name, fields in bank.items():
            section = ET.SubElement(root, 'Section', name=name)
            for key, value in fields.items():
                ET.SubElement(ET.SubElement(section, 'Key', name=key), 'Value', string=value)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic-protocol.SC2Bank'
            ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)
            parsed = read_bank(path)
            self.assertEqual(self.verify(parsed, trace(parsed))['cancellations'], 4)


class MixedBaseSupplementBoundaryTests(unittest.TestCase):
    def bank(self):
        bank = {'Probe': {'Fixture': 'mixed-regression', 'Protocol': '2'},
                'BaseFinished': {'Done': '1', 'Events': '1', 'Time': '10'},
                'Finished': {'Done': '1', 'Events': '4', 'BaseEvents': '1'},
                'Event1': {'Supplement': '0', 'Case': '', 'Time': '9'}}
        bank.update({f'Event{i}': {'Supplement': '1', 'Case': label, 'Time': str(i + 10)}
                     for i, label in enumerate(validator.DEATH_CASES, 2)})
        return bank

    def test_split_retains_base_and_requires_all_three_closed_extra_cases(self):
        base, all_events = validator.split_protocol_trace(self.bank())
        self.assertEqual((len(base), len(all_events)), (1, 4))

    def test_base_only_old_revision_unfinished_or_truncated_evidence_is_red(self):
        for section, key, value in [('Probe', 'Protocol', '1'), ('BaseFinished', 'Done', '0'),
                                     ('Finished', 'Done', '0'), ('Finished', 'Events', '5'),
                                     ('Finished', 'BaseEvents', '2'), ('Event2', 'Supplement', '0'),
                                     ('Event4', 'Case', 'PrismDeath'), ('BaseFinished', 'Time', '30')]:
            with self.subTest(section=section, key=key):
                bank = self.bank()
                bank[section][key] = value
                with self.assertRaises(AssertionError):
                    validator.split_protocol_trace(bank)


if __name__ == '__main__':
    unittest.main()
