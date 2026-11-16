"""Localize verified exact external lookups using only their saved cache cells."""
import re
from numbers import Number
from openpyxl.comments import Comment
from openpyxl.formula.tokenizer import Tokenizer
from openpyxl.utils.cell import coordinate_to_tuple, range_boundaries, get_column_letter, quote_sheetname
from privacy_data_agent.detectors import detect_column_entity_type, detect_optional_column_entity_type
from privacy_data_agent.models import EntityType
from privacy_data_agent.person_identity import IdentityReviewError
from privacy_data_agent.workbook_identifiers import lookup_arguments, local_range

HEADERS = {EntityType.EMPLOYEE_ID: '工号', EntityType.ID_NUMBER: '身份证号',
           EntityType.EMAIL: '邮箱', EntityType.BANK_ACCOUNT: '银行卡号',
           EntityType.DEPARTMENT: '部门', EntityType.CUSTOMER: '客户名称',
           EntityType.PHONE: '电话', EntityType.JOB_TITLE: '岗位', EntityType.SALARY: '金额'}


ATTRIBUTE_TYPES = set(HEADERS) - {EntityType.SALARY}
ATTRIBUTE_TYPES.update({EntityType.EMPLOYEE, EntityType.LICENSE_PLATE})


def _external_reference(value):
    return bool(re.search(r"\[[^\]]+\].*!", value))


def _external_names(book):
    return {name.name.casefold() for name in book.defined_names.values() if _external_reference(str(name.attr_text))}


def _has_external_formula(formula, names):
    return any(token.subtype == 'RANGE' and (_external_reference(token.value) or token.value.casefold() in names)
               for token in Tokenizer(formula).items)


def _clear_unused_links(book):
    names = _external_names(book)
    if not names and not any(_has_external_formula(cell.value, names) for sheet in book for row in sheet for cell in row
                             if cell.data_type == 'f' and isinstance(cell.value, str)):
        book._external_links.clear()


def freeze_external_attributes(book, cached, headers):
    converted = 0
    names = _external_names(book)
    for number, sheet in enumerate(book, 1):
        for row, saved_row in zip(sheet.iter_rows(), cached[sheet.title].iter_rows()):
            for cell, saved in zip(row, saved_row):
                if (cell.data_type != 'f' or not isinstance(cell.value, str)
                        or (detect_column_entity_type(headers[sheet.title].get(cell.column, ''))
                            or detect_optional_column_entity_type(headers[sheet.title].get(cell.column, ''))) not in ATTRIBUTE_TYPES
                        or not _has_external_formula(cell.value, names)):
                    continue
                position = f'第 {number} 张工作表 {cell.coordinate}'
                if saved.data_type == 'e':
                    raise IdentityReviewError(f'{position} 的外部人员属性原保存结果已报错，请修复原表来源、重新计算并保存后重试。')
                if saved.value is None and saved.data_type not in {'s', 'str', 'inlineStr'}:
                    raise IdentityReviewError(f'{position} 的外部人员属性缺少已保存结果，请在可访问来源的电脑上重新计算并保存，或补齐来源文件后重试。')
                cell.value = saved.value
                if isinstance(saved.value, str):
                    cell.data_type = 's'
                note = '外部人员属性已取原文件保存结果并按字段设置脱敏；该值是历史保存结果，最新性未经验证。'
                if cell.comment:
                    cell.comment.text += '\n' + note
                else:
                    cell.comment = Comment(note, 'Privacy Data Agent')
                converted += 1
    if converted:
        _clear_unused_links(book)
    return converted


def _cache_values(link, sheet_id):
    values = {}
    dataset = link.externalBook.sheetDataSet
    if dataset is None:
        return values
    for sheet in dataset.sheetData:
        if sheet.sheetId != sheet_id:
            continue
        for row in sheet.row:
            for cell in row.cell:
                value = cell.v
                if value is not None and cell.t not in {'str', 's', 'e'}:
                    try:
                        value = float(value)
                        if cell.t == 'b':
                            value = bool(value)
                        elif value.is_integer():
                            value = int(value)
                    except ValueError:
                        return {}
                if cell.r in values and values[cell.r] != (cell.t, value):
                    return {}
                values[cell.r] = (cell.t, value)
    return values


def localize_external_lookups(book, cached, headers):
    localized = 0
    snapshots = {}
    caches = {}
    originals = list(book.worksheets)
    for sheet in originals:
        for row in sheet.iter_rows():
            for cell in row:
                if cell.data_type != 'f' or not isinstance(cell.value, str) or '[' not in cell.value:
                    continue
                formula = Tokenizer(cell.value)
                calls = [t for t in formula.items if t.type == 'FUNC' and t.subtype == 'OPEN']
                args_list = list(lookup_arguments(cell.value))
                if len(calls) != 1 or calls[0].value.upper() != 'VLOOKUP(' or len(args_list) != 1:
                    continue
                args = [[t for t in arg if t.type != 'WHITE-SPACE'] for arg in args_list[0]]
                if len(args) != 4 or any(len(arg) != 1 for arg in args):
                    continue
                key_token, range_token, index_token, exact_token = [arg[0] for arg in args]
                if key_token.subtype != 'RANGE' or range_token.subtype != 'RANGE' or exact_token.value.upper() not in {'FALSE', '0'} or not index_token.value.isdigit():
                    continue
                title, bang, address = range_token.value.rpartition('!')
                if title.startswith("'") and title.endswith("'"):
                    title = title[1:-1].replace("''", "'")
                external = re.fullmatch(r'\[(\d+)\](.+)', title)
                key = local_range(book, sheet, key_token.value)
                if not external or not bang or not key or not re.fullmatch(r'\$?[A-Z]+(?:\$?\d+)?(?::\$?[A-Z]+(?:\$?\d+)?)?', address):
                    continue
                key_sheet, key_bounds = key
                if key_bounds[0] != key_bounds[2] or key_bounds[1] != key_bounds[3] or not key_bounds[1]:
                    continue
                link_index = int(external[1]) - 1
                if not 0 <= link_index < len(book._external_links):
                    continue
                link = book._external_links[link_index]
                names = link.externalBook.sheetNames
                if names is None or external[2] not in names.sheetName:
                    continue
                sheet_id = names.sheetName.index(external[2])
                cache_key = (link_index, sheet_id)
                if cache_key not in caches:
                    caches[cache_key] = _cache_values(link, sheet_id)
                values = caches[cache_key]
                left, top, right, bottom = range_boundaries(address)
                result_col = left + int(index_token.value) - 1
                if not left <= result_col <= right:
                    continue
                key_cell = cached[key_sheet.title].cell(key_bounds[1], key_bounds[0])
                saved = cached[sheet.title][cell.coordinate]
                key_kind = detect_column_entity_type(headers[key_sheet.title].get(key_bounds[0], ''))
                result_kind = detect_column_entity_type(headers[sheet.title].get(cell.column, ''))
                if key_kind not in HEADERS or result_kind not in HEADERS and not isinstance(saved.value, Number):
                    continue
                if key_cell.value is None or saved.data_type == 'e':
                    continue
                candidates = []
                for ref, (kind, value) in values.items():
                    row_number, column = coordinate_to_tuple(ref)
                    if column == left and (top or 1) <= row_number <= (bottom or 1048576) and kind != 'e' and value == key_cell.value:
                        candidates.append(row_number)
                if not candidates:
                    continue
                first = min(candidates)
                result_ref = f'{get_column_letter(result_col)}{first}'
                returned = values.get(result_ref)
                if first == 1 or returned is None or returned[0] == 'e' or returned[1] != saved.value:
                    continue
                snapshot_key = (*cache_key, address)
                if snapshot_key not in snapshots:
                    snap = book.create_sheet(f'_PDA_External_{len(snapshots) + 1:02d}')
                    snap.sheet_state = 'hidden'
                    snap['A1'] = '外部查找缓存快照：仅包含当前公式使用的数据，非外部原表的最新数据。'
                    snapshots[snapshot_key] = snap
                snap = snapshots[snapshot_key]
                snap.cell(1, left, HEADERS[key_kind])
                snap.cell(1, result_col, HEADERS.get(result_kind, '计算结果'))
                for column, value in ((left, key_cell.value), (result_col, returned[1])):
                    imported = snap.cell(first, column, value)
                    if isinstance(value, str):
                        imported.data_type = 's'

                old_reference = range_token.value
                for token in formula.items:
                    if token.subtype == 'RANGE' and token.value == old_reference:
                        token.value = quote_sheetname(snap.title) + '!' + address
                cell.value = formula.render()
                note = '外部查找已改为本地隐藏缓存快照；保留 VLOOKUP 逻辑。快照仅代表原文件保存时的结果，无法证明外部原表的最新数据。'
                if cell.comment:
                    cell.comment.text += '\n' + note
                else:
                    cell.comment = Comment(note, 'Privacy Data Agent')
                localized += 1
    if localized:
        _clear_unused_links(book)
    return localized
