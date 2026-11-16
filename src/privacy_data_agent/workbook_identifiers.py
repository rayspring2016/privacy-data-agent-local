"""Propagate identifier types across explicit local Excel lookup/reference links."""
import re
from openpyxl.formula.tokenizer import Tokenizer
from openpyxl.utils.cell import range_boundaries
from privacy_data_agent.detectors import detect_column_entity_type
from privacy_data_agent.models import EntityType

LINKED_TYPES = {EntityType.EMPLOYEE_ID, EntityType.ID_NUMBER, EntityType.EMAIL, EntityType.BANK_ACCOUNT, EntityType.DEPARTMENT, EntityType.CUSTOMER}


def lookup_arguments(formula):
    """Yield VLOOKUP arguments while respecting nested calls and separators."""
    stack = []
    for token in Tokenizer(formula).items:
        if token.type == 'FUNC' and token.subtype == 'OPEN':
            if stack:
                stack[-1][1][-1].append(token)
            stack.append((token.value.upper(), [[]]))
        elif token.type == 'FUNC' and token.subtype == 'CLOSE':
            name, args = stack.pop()
            if name == 'VLOOKUP(':
                yield args
            if stack:
                stack[-1][1][-1].append(token)
        elif token.type == 'SEP' and token.subtype == 'ARG' and stack:
            stack[-1][1].append([])
        elif stack:
            stack[-1][1][-1].append(token)


def local_range(book, sheet, value):
    title, bang, address = value.rpartition('!')
    title = title[1:-1].replace("''", "'") if title.startswith("'") and title.endswith("'") else title
    if bang:
        if title not in book.sheetnames:
            return None
        sheet = book[title]
    else:
        address = value
    if not re.fullmatch(r'\$?[A-Z]+(?:\$?\d+)?(?::\$?[A-Z]+(?:\$?\d+)?)?', address):
        return None
    try:
        bounds = range_boundaries(address)
    except ValueError:
        return None
    return sheet, bounds


def linked_identifier_cells(book, formulas, header_row, pivots):
    # Import here to keep the workbook module's header logic in one place.
    from privacy_data_agent.workbook_anonymizer import _detect_xlsx_header_row, _header_by_column
    kinds = {}
    headers = {}
    for sheet in book:
        headers[sheet.title] = _header_by_column(sheet, header_row or _detect_xlsx_header_row(sheet))
        for col, label in headers[sheet.title].items():
            kinds[sheet.title, col] = detect_column_entity_type(label)
        for left, _, _, _, _, labels in pivots[sheet.title]:
            for col, label in enumerate(labels, left):
                kinds[sheet.title, col] = detect_column_entity_type(label)
    links = set()
    max_rows = {sheet.title: sheet.max_row for sheet in book}

    def endpoint(sheet, bounds, col=None):
        return (sheet.title, col or bounds[0], bounds[1] or 1, min(bounds[3] or max_rows[sheet.title], max_rows[sheet.title]))

    for title, cells in formulas.items():
        sheet = book[title]
        for address, formula in cells.items():
            tokens = [t for t in Tokenizer(formula).items if t.type != 'WHITE-SPACE']
            if len(tokens) == 1 and tokens[0].subtype == 'RANGE':
                source = local_range(book, sheet, tokens[0].value)
                if source and source[1][0] == source[1][2] and source[1][1] == source[1][3] and source[1][1]:
                    links.add((endpoint(sheet, (sheet[address].column, sheet[address].row, sheet[address].column, sheet[address].row)), endpoint(*source)))
            for args in lookup_arguments(formula):
                if len(args) != 4:
                    continue
                args = [[t for t in arg if t.type != 'WHITE-SPACE'] for arg in args]
                if any(len(args[i]) != 1 for i in (0, 1, 3)) or args[3][0].value.upper() not in {'FALSE', '0'}:
                    continue
                if args[0][0].subtype != 'RANGE' or args[1][0].subtype != 'RANGE':
                    continue
                key = local_range(book, sheet, args[0][0].value)
                table = local_range(book, sheet, args[1][0].value)
                if key and table and key[1][0] == key[1][2] and key[1][1] == key[1][3] and key[1][1]:
                    links.add((endpoint(*key), endpoint(*table)))
                    if len(args[2]) == 1 and args[2][0].subtype == 'NUMBER' and args[2][0].value.isdigit():
                        result_col = table[1][0] + int(args[2][0].value) - 1
                        if table[1][0] <= result_col <= table[1][2]:
                            links.add((endpoint(sheet, (sheet[address].column, sheet[address].row, sheet[address].column, sheet[address].row)), endpoint(*table, col=result_col)))
    inferred = {}
    inferred_by_column = {}

    def field_kind(node):
        title, col, first, last = node
        explicit = kinds.get((title, col))
        if explicit is not None:
            return explicit
        if node in inferred:
            return inferred[node]
        for start, end, kind in inferred_by_column.get((title, col), ()):
            if start <= first <= last <= end:
                return kind
        return None

    changed = True
    while changed:
        changed = False
        for a, b in links:
            for source, target in ((a, b), (b, a)):
                kind = field_kind(source)
                if kind in LINKED_TYPES and field_kind(target) is None:
                    inferred[target] = kind
                    inferred_by_column.setdefault(target[:2], []).append((*target[2:], kind))
                    changed = True
    cells = {}
    for (title, col, first, last), kind in inferred.items():
        for row in range(first, last + 1):
            cells[title, row, col] = kind
    return cells
