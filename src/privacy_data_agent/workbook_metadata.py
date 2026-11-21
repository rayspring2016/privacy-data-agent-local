"""Text outside cells that must participate in masking and restoration."""


def _replace_chart_text(node, replace, visited):
    if id(node) in visited or not hasattr(node, '__elements__'):
        return
    visited.add(id(node))
    # Series and chart titles also store fields outside __elements__.
    for field in dict.fromkeys((*node.__attrs__, *node.__elements__, *vars(node))):
        if field.startswith('_'):
            continue
        value = getattr(node, field, None)
        if field == 'numCache' and value is not None:
            if any(replace(str(point.v)) != str(point.v) for point in value.pt):
                setattr(node, field, None)
                continue
        if field == 'f' and isinstance(value, str) and replace(value) != value:
            raise ValueError('待核验：图表引用名称含敏感信息，请先调整引用名称。')
        if field in {'t', 'v'} and isinstance(value, str):
            setattr(node, field, replace(value))
        elif field == 'v' and isinstance(value, (int, float)) and replace(str(value)) != str(value):
            raise ValueError('待核验：图表包含独立的敏感数值，请先改为引用工作表数据。')
        elif isinstance(value, (list, tuple)):
            for item in value:
                _replace_chart_text(item, replace, visited)
        else:
            _replace_chart_text(value, replace, visited)


def replace_workbook_metadata(book, replace, replace_chart=None):
    for field in book.properties.__elements__:
        value = getattr(book.properties, field)
        if isinstance(value, str):
            setattr(book.properties, field, replace(value))
    for prop in book.custom_doc_props:
        if isinstance(prop.value, str):
            prop.value = replace(prop.value)
    for sheet in book:
        for chart in sheet._charts:
            for part in chart._charts:
                _replace_chart_text(part, replace_chart or replace, set())
        for header in (sheet.oddHeader, sheet.evenHeader, sheet.firstHeader,
                       sheet.oddFooter, sheet.evenFooter, sheet.firstFooter):
            for part in (header.left, header.center, header.right):
                if part.text:
                    part.text = replace(part.text)
        for row in sheet:
            for cell in row:
                if cell.comment:
                    cell.comment.text = replace(cell.comment.text)
                    if cell.comment.author:
                        cell.comment.author = replace(cell.comment.author)
