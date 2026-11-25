"""Export saved Wind issuance and market values to manual date,value CSVs.

Reads Excel files with openpyxl. Does not execute formulas, refresh Wind,
modify the workbook, or assemble/publish a production snapshot.
"""
import argparse
import calendar
import csv
import io
import math
import re
import tempfile
from contextlib import ExitStack, closing
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.datetime import CALENDAR_WINDOWS_1900, from_excel
from openpyxl.utils.exceptions import InvalidFileException

if __package__:
    from .registry import DEFAULT_REGISTRY, load_registry
else:
    from registry import DEFAULT_REGISTRY, load_registry

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / 'data/sources/wind/Wind-data.xlsx'
DEFAULT_OUTPUT = ROOT / 'data/manual'
SERIES = ('bond-issuance', 'treasury-bond-issuance', 'corporate-bond-issuance')
MARKET_HEADERS = {'MOVE': 'move', 'USDX': 'dollar-index'}


def saved_value(cell, formula_cell, *, allow_na=False):
    """Keep empty observations distinct from Excel errors and uncached formulas."""
    value = cell.value
    if allow_na and cell.data_type == 'e' and value == '#N/A':
        return None
    if cell.data_type == 'e':
        raise ValueError(f'{cell.coordinate}: Excel error {value}; refresh Wind and save in Excel')
    if formula_cell.data_type == 'f' and value is None:
        raise ValueError(f'{cell.coordinate}: formula has no saved result; refresh Wind and save in Excel')
    if isinstance(value, bool):
        raise ValueError(f'{cell.coordinate}: boolean is not an observation')
    if isinstance(value, (int, float)) and not math.isfinite(value):
        raise ValueError(f'{cell.coordinate}: expected a finite number')
    return None if value == '' else value


def observation_date(value, epoch, *, month_end=True):
    """Use openpyxl's Excel date conversion; preserve source month-end dates."""
    try:
        if type(value) in (int, float):
            if not math.isfinite(value) or value < 0 or value != int(value):
                raise ValueError
            if epoch == CALENDAR_WINDOWS_1900 and value == 60:
                raise ValueError  # Excel's fictitious 1900-02-29
            value = from_excel(value, epoch)
        if isinstance(value, datetime):
            if value.time() != time() or value.tzinfo is not None:
                raise ValueError
            value = value.date()
        if isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            value = date.fromisoformat(value)
        if not isinstance(value, date):
            raise ValueError
    except (ValueError, OverflowError):
        raise ValueError(f'Invalid observation date: {value!r}') from None
    if month_end and value.day != calendar.monthrange(value.year, value.month)[1]:
        raise ValueError(f'{value}: expected a month-end observation date; dates are not shifted')
    return value.isoformat()


def read_workbook(path, sheet_name='bond-issuance'):
    """Read saved values and formula presence separately; never save either view."""
    with ExitStack() as stack:
        # Both views read the same bytes, even if Excel saves the source meanwhile.
        content = Path(path).read_bytes()
        try:
            cached = stack.enter_context(closing(load_workbook(io.BytesIO(content), data_only=True,
                                                               keep_links=False)))
            formulas = stack.enter_context(closing(load_workbook(io.BytesIO(content), data_only=False,
                                                                 keep_links=False)))
        except (BadZipFile, InvalidFileException, KeyError, ValueError) as error:
            raise ValueError(f'Invalid XLSX workbook: {error}') from error
        result = read_sheet(cached, formulas, sheet_name, market=False)
        result.update(read_sheet(cached, formulas, 'market', market=True))
        return result


def read_sheet(cached, formulas, sheet_name, *, market):
    if sheet_name not in cached.sheetnames:
        raise ValueError(f'Expected worksheet {sheet_name!r}')
    sheet, formula_sheet = cached[sheet_name], formulas[sheet_name]

    def value_at(row, column, *, allow_na=False):
        return saved_value(sheet.cell(row, column), formula_sheet.cell(row, column),
                           allow_na=allow_na)

    # A1's Wind control formula is not an observation and is never inspected.
    if not market and value_at(1, 2) != 'Billions $':
        raise ValueError('B1 must declare "Billions $"; source units cannot be inferred')
    mapping = MARKET_HEADERS if market else {key: key for key in SERIES}
    columns = range(1, sheet.max_column + 1)
    headers = {column: value_at(2, column) for column in range(2, sheet.max_column + 1)
               if value_at(2, column) is not None}
    if len(headers) != len(mapping) or set(headers.values()) != set(mapping):
        raise ValueError(f'Row 2 must contain each series ID exactly once: {", ".join(mapping)}')
    if value_at(2, 1) not in ('指标名称', 'date'):
        raise ValueError('A2 must be 指标名称 or date')
    result = {identifier: [] for identifier in mapping.values()}
    seen = set()
    for row in range(3, sheet.max_row + 1):
        populated = {column: value_at(row, column, allow_na=market and column in headers)
                     for column in columns}
        populated = {column: value for column, value in populated.items() if value is not None}
        if not populated:
            continue
        if set(populated) - {1, *headers}:
            raise ValueError(f'Row {row}: data outside the date/series columns')
        when = observation_date(populated.get(1), cached.epoch, month_end=not market)
        if when in seen:
            raise ValueError(f'Row {row}: duplicate observation date {when}')
        seen.add(when)
        for column, identifier in headers.items():
            value = populated.get(column)
            if value is not None and type(value) not in (int, float):
                raise ValueError(f'{sheet.cell(row, column).coordinate}: expected numeric value or blank, got {value!r}')
            # Keep numeric precision, without rounding to the cell's display
            # format. Decimal renders float's round-trip representation plainly.
            result[mapping[identifier]].append((when, None if value is None else Decimal(str(value))))
    for identifier, points in result.items():
        if not any(value is not None for _, value in points):
            raise ValueError(f'{identifier}: no numeric observations; refresh Wind and save in Excel')
        points.sort()
    return result


def export_workbook(source=DEFAULT_INPUT, output_dir=DEFAULT_OUTPUT, *,
                    registry_path=DEFAULT_REGISTRY, sheet_name='bond-issuance', check=False):
    registry = load_registry(registry_path)['series']
    for identifier in (*SERIES, *MARKET_HEADERS.values()):
        frequency = 'monthly' if identifier in SERIES else 'daily'
        unit = 'billions' if identifier in SERIES else 'none'
        entry = registry.get(identifier, {})
        if entry.get('update_method') != 'manual' or entry.get('native_frequency') != frequency:
            raise ValueError(f'{identifier}: requires manual ownership and {frequency} frequency')
        if (entry.get('source_unit') or '').lower() != unit:
            raise ValueError(f'{identifier}: registry source_unit must match workbook {unit}')
    series = read_workbook(source, sheet_name)
    payloads = {}
    for identifier, points in series.items():
        buffer = io.StringIO(newline='')
        writer = csv.writer(buffer, lineterminator='\n')
        writer.writerow(('date', 'value'))
        writer.writerows((when, '' if value is None else format(value, 'f')) for when, value in points)
        payloads[identifier] = buffer.getvalue()
    if not check:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        # Validate all inputs before writing; stage all files on the same
        # filesystem, then replace each CSV atomically. Unchanged CSVs stay intact.
        with tempfile.TemporaryDirectory(prefix='.wind-issuance-', dir=output_dir) as directory:
            staged = []
            for identifier, payload in payloads.items():
                destination = output_dir / f'{identifier}.csv'
                if destination.is_file() and destination.read_text(encoding='utf-8') == payload:
                    continue
                temporary = Path(directory) / destination.name
                temporary.write_text(payload, encoding='utf-8')
                staged.append((temporary, destination))
            for temporary, destination in staged:
                temporary.replace(destination)
    return series


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--registry', type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument('--sheet', default='bond-issuance')
    parser.add_argument('--check', action='store_true', help='Validate saved data without writing CSVs')
    args = parser.parse_args()
    try:
        series = export_workbook(args.input, args.output_dir, registry_path=args.registry,
                                 sheet_name=args.sheet, check=args.check)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Wind export failed: {error}\n')
    for identifier, points in series.items():
        missing = sum(value is None for _, value in points)
        print(f'{identifier}: {len(points)} rows, {points[0][0]} to {points[-1][0]}, {missing} missing')
    print('Validated saved workbook values.' if args.check else f'Exported CSVs to {args.output_dir}')
    print('Wind was not refreshed. Source review and production activation remain separate steps.')


if __name__ == '__main__':
    main()
