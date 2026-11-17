import copy
import csv
import math
import tempfile
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from openpyxl import Workbook
from openpyxl.utils.datetime import CALENDAR_MAC_1904, CALENDAR_WINDOWS_1900

from scripts.export_wind_issuance import SERIES, export_workbook, observation_date, read_workbook
from scripts.registry import DEFAULT_REGISTRY


class WindIssuanceExportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / 'input.xlsx'
        self.output = self.root / 'manual'
        self.registry = self.root / 'registry.csv'
        with DEFAULT_REGISTRY.open(encoding='utf-8-sig', newline='') as handle:
            self.registry_rows = list(csv.DictReader(handle))
        self.write_registry()
        # Reverse chronology, a real zero, a blank, and decimals are intentional.
        self.cells = {
            'A1': ('e', '#NAME?'), 'B1': ('inlineStr', 'Billions $'),
            'A2': ('s', '0'), 'B2': ('s', '1'), 'C2': ('s', '2'), 'D2': ('s', '3'),
            'A3': ('n', '46326'), 'B3': ('n', '1.25'), 'C3': ('n', '0'), 'D3': ('n', '2.500'),
            'A4': ('n', '46295'), 'B4': ('n', '1.125'), 'C4': ('n', '3'), 'D4': ('n', None),
        }

    def write_registry(self):
        with self.registry.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=self.registry_rows[0])
            writer.writeheader()
            writer.writerows(self.registry_rows)

    def workbook(self, *, date1904=False, formulas=None):
        # Real XLSX fixtures from openpyxl, independent of production source files.
        book = Workbook()
        sheet = book.active
        sheet.title = 'bond-issuance'
        if date1904:
            book.epoch = CALENDAR_MAC_1904
        raw_numbers = {}
        for address, (kind, value) in self.cells.items():
            if kind == 's':
                value = ('指标名称', *SERIES)[int(value)]
            elif kind == 'n' and value is not None:
                if math.isfinite(float(value)):
                    value = float(value)
                else:
                    raw_numbers[address] = value
                    value = 0
            elif kind == 'd':
                value = date.fromisoformat(value)
            elif kind == 'b':
                value = value == '1'
            sheet[address] = value
            if address in (formulas or {}) and value is None:
                sheet[address] = '=' + formulas[address]
            if address.startswith('A') and int(address[1:]) >= 3:
                sheet[address].number_format = 'yyyy-mm'
        book.save(self.source)
        book.close()
        # openpyxl cannot author formula caches or invalid non-finite numbers.
        # Patch only these test cases, so the reader faces actual stored errors.
        if formulas or raw_numbers:
            with ZipFile(self.source) as archive:
                files = {name: archive.read(name) for name in archive.namelist()}
            ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
            root = ET.fromstring(files['xl/worksheets/sheet1.xml'])
            for address in set(formulas or {}) | set(raw_numbers):
                cell = root.find(f'.//{ns}c[@r="{address}"]')
                if address in (formulas or {}):
                    formula = cell.find(ns + 'f')
                    if formula is None:
                        formula = ET.SubElement(cell, ns + 'f')
                    formula.text = formulas[address]
                if address in raw_numbers:
                    cell.find(ns + 'v').text = raw_numbers[address]
            files['xl/worksheets/sheet1.xml'] = ET.tostring(root)
            with ZipFile(self.source, 'w') as archive:
                for name, content in files.items():
                    archive.writestr(name, content)

    def export(self, **kwargs):
        return export_workbook(self.source, self.output, registry_path=self.registry, **kwargs)

    def test_export_sorted_values_without_changing_source_and_idempotent(self):
        self.workbook()
        original = self.source.read_bytes()
        self.export()
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual((self.output / 'bond-issuance.csv').read_text(),
                         'date,value\n2026-09-30,1.125\n2026-10-31,1.25\n')
        self.assertEqual((self.output / 'corporate-bond-issuance.csv').read_text(),
                         'date,value\n2026-09-30,\n2026-10-31,2.5\n')
        self.assertIn('2026-10-31,0\n', (self.output / 'treasury-bond-issuance.csv').read_text())
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.output.iterdir()}
        self.export()
        self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
                                  for p in self.output.iterdir()})

    def test_headers_control_mapping_and_check_does_not_write(self):
        self.cells['B2'], self.cells['D2'] = self.cells['D2'], self.cells['B2']
        self.workbook()
        series = self.export(check=True)
        self.assertEqual(series['corporate-bond-issuance'][-1][1], Decimal('1.25'))
        self.assertFalse(self.output.exists())

    def test_excel_1904_and_iso_dates_preserved(self):
        self.cells['A3'] = ('n', str((date(2024, 2, 29) - date(1904, 1, 1)).days))
        self.cells['A4'] = ('d', '2024-01-31')
        self.workbook(date1904=True)
        self.assertEqual([p[0] for p in read_workbook(self.source)['bond-issuance']],
                         ['2024-01-31', '2024-02-29'])
        for value in (60, 46326.5, datetime(2026, 10, 31, 12), '2026-10-30', '20261031'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                observation_date(value, CALENDAR_WINDOWS_1900)

    def test_invalid_workbook_preserves_all_previous_outputs(self):
        self.workbook()
        self.export()
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        valid = copy.deepcopy(self.cells)
        for address, invalid in [
            ('A4', ('n', '46326')),  # duplicate date
            ('A4', ('n', None)),  # values without a date
            ('B3', ('e', '#N/A')), ('B3', ('n', 'NaN')), ('B3', ('n', 'Infinity')),
            ('B3', ('b', '1')), ('B3', ('inlineStr', 'updating...')),
            ('B1', ('inlineStr', 'Millions $')), ('C2', ('s', '1')),
            ('D2', ('inlineStr', 'unknown-series')), ('E3', ('n', '1')),
        ]:
            self.cells = valid | {address: invalid}
            self.workbook()
            with self.subTest(address=address, invalid=invalid), self.assertRaises(ValueError):
                self.export()
            self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})

    def test_formula_cache_required_but_never_recalculated(self):
        self.workbook(formulas={'B3': '1+2'})
        self.assertEqual(self.export(check=True)['bond-issuance'][-1][1], Decimal('1.25'))
        self.cells['B3'] = ('n', None)
        self.workbook(formulas={'B3': '1+2'})
        with self.assertRaisesRegex(ValueError, 'no saved result'):
            self.export()
        self.assertFalse(self.output.exists())

    def test_empty_history_or_missing_sheet_rejected(self):
        self.cells = {key: value for key, value in self.cells.items() if key.endswith(('1', '2'))}
        self.workbook()
        with self.assertRaisesRegex(ValueError, 'no numeric observations'):
            self.export()
        with self.assertRaisesRegex(ValueError, 'worksheet'):
            self.export(sheet_name='wrong')

    def test_wrong_registry_ownership_units_frequency_rejected(self):
        self.workbook()
        entry = next(row for row in self.registry_rows if row['series_id'] == 'bond-issuance')
        original = entry.copy()
        for field, value in [('update_method', 'automatic'), ('source_unit', 'Trillion'),
                             ('native_frequency', 'daily')]:
            entry.update(original)
            entry[field] = value
            self.write_registry()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.export()
            self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
