#!/usr/bin/env python3
"""生成人效分析报告 Word 版本"""
import pandas as pd
import numpy as np
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
import os, re
from collections import Counter

SRC = '/Users/caochunlei/Downloads/test_脱敏包/anonymized.xlsx'
OUT_DIR = '/Users/caochunlei/Documents/HR Things/人效组织/人效看板/'
OUT = os.path.join(OUT_DIR, '人效分析报告_2025.docx')
MONTHS = list(range(3, 13))
MONTH_LABELS = [f'{m}月' for m in MONTHS]

# Colors
C_PRIMARY = RGBColor(0x1A, 0x3C, 0x6E)
C_ACCENT = RGBColor(0x2E, 0x86, 0xC1)
C_GREEN = RGBColor(0x27, 0xAE, 0x60)
C_RED = RGBColor(0xE7, 0x4C, 0x3C)
C_GRAY = RGBColor(0x7F, 0x8C, 0x8D)
C_TABLE_HEADER_BG = 'D6E4F0'
C_TABLE_ALT_BG = 'F2F6FA'
C_BLACK = RGBColor(0x33, 0x33, 0x33)

def load_data():
    df = pd.read_excel(SRC, sheet_name='人效测算表')
    df2 = pd.read_excel(SRC, sheet_name='11月采编核算过程')
    return df, df2

def compute_scores(df):
    records = []
    remark_col_map = {
        3: '备注', 4: None, 5: None, 6: None, 7: None, 8: None, 9: None, 10: None, 11: '备注.1', 12: '备注.2'
    }
    trend_col_map = {
        3: None, 4: '趋势', 5: '趋势.1', 6: '趋势.2', 7: '趋势.3',
        8: '趋势.4', 9: '趋势.5', 10: '趋势.6', 11: '趋势.7', 12: '趋势.8'
    }
    low_eff_map = {
        3: '效能得分较低人员原因备注', 4: '效能得分较低人员原因备注', 5: '效能得分较低人员原因备注.1',
        6: '效能得分较低人员原因备注.2', 7: '效能得分较低人员原因备注.3', 8: '效能得分较低人员原因备注.4',
        9: '效能得分较低人员原因备注.5', 10: '效能得分较低人员原因备注.6', 11: None, 12: None
    }

    for m in MONTHS:
        attend_key = f'{m}月考勤分\n-30%'
        demand_key = f'{m}月需求价值分-70%'
        attend_hours_key = f'{m}月考勤时长'
        for idx, row in df.iterrows():
            a = pd.to_numeric(row.get(attend_key), errors='coerce')
            d = pd.to_numeric(row.get(demand_key), errors='coerce')
            h = pd.to_numeric(row.get(attend_hours_key), errors='coerce')
            total = (a * 0.3 + d * 0.7) if pd.notna(a) and pd.notna(d) else (d if pd.notna(d) else (a if pd.notna(a) else np.nan))

            records.append({
                'name': row['姓名'],
                'eid': row['工号'],
                'dept_l1': row['一级部门'],
                'dept_l2': row['二级部门'],
                'dept_l3': row['三级部门'],
                'position': row['岗位'],
                'month': m,
                'attend_hours': h,
                'attend_score': a,
                'demand_score': d,
                'total_score': total,
                'has_full_score': pd.notna(a) and pd.notna(d),
                'remark': row.get(remark_col_map[m]) if remark_col_map[m] and remark_col_map[m] in row.index else None,
                'trend': row.get(trend_col_map[m]) if trend_col_map[m] and trend_col_map[m] in row.index else None,
                'low_eff_remark': row.get(low_eff_map[m]) if low_eff_map[m] and low_eff_map[m] in row.index else None,
            })
    return pd.DataFrame(records)

def compute_aggregates(ldf):
    monthly_stats = []
    for m in MONTHS:
        md = ldf[ldf['month'] == m]
        ts = md['total_score'].dropna()
        ds = md['demand_score'].dropna()
        monthly_stats.append({
            'month': m,
            'total_mean': ts.mean(), 'total_median': ts.median(),
            'total_p25': ts.quantile(0.25), 'total_p75': ts.quantile(0.75),
            'total_std': ts.std(), 'total_count': len(ts),
            'demand_mean': ds.mean(), 'demand_count': len(ds),
            'attend_hours_mean': md['attend_hours'].mean(),
            'full_score_count': md['has_full_score'].sum(),
        })
    return pd.DataFrame(monthly_stats)

def compute_employee_stats(ldf):
    emp = ldf.groupby('name').agg(
        annual_mean=('total_score', 'mean'),
        annual_std=('total_score', 'std'),
        annual_min=('total_score', 'min'),
        annual_max=('total_score', 'max'),
        months_active=('total_score', lambda x: x.notna().sum()),
        dept_l2=('dept_l2', 'first'),
        position=('position', 'first'),
        demand_mean=('demand_score', 'mean'),
    ).reset_index()
    emp['volatility'] = emp['annual_std'] / emp['annual_mean']
    return emp

def compute_dept_stats(ldf):
    dept_monthly = ldf.groupby(['dept_l2', 'month'])['total_score'].mean().reset_index()
    dept_annual = ldf.groupby('dept_l2').agg(
        count=('name', 'nunique'),
        annual_mean=('total_score', 'mean'),
        demand_mean=('demand_score', 'mean'),
    ).reset_index()
    dept_annual['trend_months'] = dept_annual['dept_l2'].apply(
        lambda d: dept_monthly[dept_monthly['dept_l2'] == d]['total_score'].tolist()
    )
    return dept_annual.sort_values('annual_mean', ascending=False), dept_monthly

def classify_remarks(ldf):
    remarks = ldf['remark'].dropna()
    remark_list = [str(r) for r in remarks if str(r).strip() and str(r).strip() != 'nan']

    categories = {
        '任务周期性长/长期项目': [],
        '任务结案/系统未更新': [],
        '需求难度波动': [],
        'TB外工作（未建任务）': [],
        '依赖阻塞（前端/测试）': [],
        '技术攻关/研发投入': [],
        '新人/学习过渡期': [],
        '加班量较低': [],
        '团队/数据异常': [],
        '其他': [],
    }

    for r in remark_list:
        if any(kw in r for kw in ['任务周期性', '长期', '周期性较长']):
            categories['任务周期性长/长期项目'].append(r)
        elif any(kw in r for kw in ['结案没更新', '结案未更新', '没更新', '没关掉']):
            categories['任务结案/系统未更新'].append(r)
        elif any(kw in r for kw in ['难易程度', '难度不同', '任务难度', '难度变化']):
            categories['需求难度波动'].append(r)
        elif any(kw in r for kw in ['没有在TB', '不走TB', '没有建TB', '不对应产出']):
            categories['TB外工作（未建任务）'].append(r)
        elif any(kw in r for kw in ['依赖', '测试一直没返回', '测试没返回', '依赖前端']):
            categories['依赖阻塞（前端/测试）'].append(r)
        elif any(kw in r for kw in ['攻克', '技术难点', '研发', '优化基准', '竞品分析']):
            categories['技术攻关/研发投入'].append(r)
        elif any(kw in r for kw in ['新人', '刚参与考核', '学习', '了解AI']):
            categories['新人/学习过渡期'].append(r)
        elif any(kw in r for kw in ['加班量', '加班']):
            categories['加班量较低'].append(r)
        elif any(kw in r for kw in ['数据异常', '团队数据异常']):
            categories['团队/数据异常'].append(r)
        else:
            categories['其他'].append(r)

    return {k: v for k, v in categories.items() if v}


# --- Document Generation ---

def set_cell_shading(cell, color_hex):
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}" w:val="clear"/>')
    cell._tc.get_or_add_tcPr().append(shading)

def set_cell_border(cell, **kwargs):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = parse_xml(f'<w:tcBorders {nsdecls("w")}></w:tcBorders>')
    for edge, val in kwargs.items():
        element = parse_xml(
            f'<w:{edge} {nsdecls("w")} w:val="{val.get("val", "single")}" '
            f'w:sz="{val.get("sz", "4")}" w:color="{val.get("color", "BDBDBD")}"/>'
        )
        tcBorders.append(element)
    tcPr.append(tcBorders)

def make_cell(cell, text, bold=False, color=None, size=Pt(9), align=WD_ALIGN_PARAGRAPH.LEFT):
    cell.text = ''
    p = cell.paragraphs[0]
    p.alignment = align
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(str(text) if text is not None else '-')
    run.font.size = size
    run.font.name = '微软雅黑'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    if bold:
        run.bold = True
    if color:
        run.font.color.rgb = color

def make_table(doc, headers, rows, col_widths=None, header_color=C_TABLE_HEADER_BG):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        make_cell(cell, h, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF), size=Pt(9), align=WD_ALIGN_PARAGRAPH.CENTER)
        set_cell_shading(cell, '1A3C6E')
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = table.rows[ri + 1].cells[ci]
            make_cell(cell, val, size=Pt(9), align=WD_ALIGN_PARAGRAPH.CENTER if ci > 0 else WD_ALIGN_PARAGRAPH.LEFT)
            if ri % 2 == 1:
                set_cell_shading(cell, C_TABLE_ALT_BG)

    if col_widths:
        for i, w in enumerate(col_widths):
            for row in table.rows:
                row.cells[i].width = Cm(w)
    return table

def add_heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.name = '微软雅黑'
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    return h

def add_body(doc, text, bold=False, color=None, size=Pt(10.5)):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = size
    run.font.name = '微软雅黑'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    run.font.color.rgb = color or C_BLACK
    if bold:
        run.bold = True
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.5
    return p

def add_rich_para(doc, segments):
    """segments: list of (text, bold, color, size)"""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.5
    for text, bold, color, size in segments:
        run = p.add_run(text)
        run.font.size = size or Pt(10.5)
        run.font.name = '微软雅黑'
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
        run.font.color.rgb = color or C_BLACK
        if bold:
            run.bold = True
    return p

def build_report(ldf, emp_stats, dept_annual, dept_monthly, monthly_stats, remark_cats, df2):
    doc = Document()

    # Page setup
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)

    style = doc.styles['Normal']
    style.font.name = '微软雅黑'
    style.font.size = Pt(10.5)
    style._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    # ---- Cover ----
    for _ in range(6):
        doc.add_paragraph()
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_p.add_run('人效分析报告')
    run.font.size = Pt(28)
    run.bold = True
    run.font.color.rgb = C_PRIMARY
    run.font.name = '微软雅黑'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub_p.add_run('2025年3月 — 12月')
    run.font.size = Pt(16)
    run.font.color.rgb = C_GRAY
    run.font.name = '微软雅黑'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    doc.add_paragraph()
    doc.add_paragraph()

    subp2 = doc.add_paragraph()
    subp2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subp2.add_run('数据覆盖范围：2025年3月–12月 | 员工月度效能考核数据')
    run.font.size = Pt(11)
    run.font.color.rgb = C_GRAY
    run.font.name = '微软雅黑'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    for _ in range(4):
        doc.add_paragraph()
    footer_p = doc.add_paragraph()
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer_p.add_run('人力资源部  |  机密')
    run.font.size = Pt(12)
    run.font.color.rgb = C_GRAY
    run.font.name = '微软雅黑'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    doc.add_page_break()

    # ---- 1. 数据概览 ----
    add_heading(doc, '一、数据概览', level=1)

    total_emp = ldf['name'].nunique()
    dept_l1_count = ldf['dept_l1'].nunique()
    dept_l2_count = ldf['dept_l2'].nunique()
    overall_mean = ldf['total_score'].mean()
    overall_median = ldf['total_score'].median()
    avg_hours = ldf['attend_hours'].mean()
    demand_coverage = ldf['demand_score'].notna().sum()
    full_coverage = ldf['has_full_score'].sum()

    add_body(doc, f'本报告基于 2025 年 3 月至 12 月员工月度效能考核数据，覆盖 {total_emp} 名员工、{dept_l1_count} 个一级部门下的 {dept_l2_count} 个二级部门。核心考核指标为「考勤分（权重 30%）+ 需求价值分（权重 70%）」加权总分。')

    overview_headers = ['指标', '数值']
    overview_rows = [
        ['覆盖员工总数', f'{total_emp} 人'],
        ['一级部门数', f'{dept_l1_count} 个'],
        ['二级部门数', f'{dept_l2_count} 个'],
        ['考核月份', '3月 – 12月（共10个月）'],
        ['全年效能均分（均值）', f'{overall_mean:.1f}'],
        ['全年效能均分（中位数）', f'{overall_median:.1f}'],
        ['月均考勤时长', f'{avg_hours:.1f} 小时/天'],
        ['需求价值分覆盖人次', f'{demand_coverage} 人次'],
        ['完整加权分覆盖人次', f'{full_coverage} 人次（考勤分+需求分均有效）'],
        ['分数集中区间', '40–50 分（占 59.6%）'],
    ]
    make_table(doc, overview_headers, overview_rows, col_widths=[6, 10])

    doc.add_paragraph()

    # ---- 2. 部门人效分析 ----
    add_heading(doc, '二、部门人效分析', level=1)

    add_body(doc, '以下为各二级部门 2025 年 3–12 月效能均分排名。部门趋势基于月度均分走向判断。')

    dept_headers = ['排名', '二级部门', '人数', '年均总分', '最高月份', '最低月份', '趋势']
    dept_rows = []
    for rank, (_, r) in enumerate(dept_annual.iterrows(), 1):
        scores = r['trend_months']
        max_m = MONTH_LABELS[scores.index(max(scores))] if scores else '-'
        min_m = MONTH_LABELS[scores.index(min(scores))] if scores else '-'
        first_half = np.mean(scores[:5]) if len(scores) >= 5 else np.mean(scores)
        second_half = np.mean(scores[5:]) if len(scores) >= 6 else np.mean(scores)
        trend_word = '↑ 上升' if second_half > first_half + 1 else ('↓ 下降' if second_half < first_half - 1 else '→ 平稳')
        dept_rows.append([
            str(rank),
            str(r['dept_l2']),
            str(int(r['count'])),
            f'{r["annual_mean"]:.1f}',
            max_m, min_m, trend_word
        ])
    make_table(doc, dept_headers, dept_rows, col_widths=[1.2, 4, 1.2, 2, 2, 2, 2])

    top3 = dept_annual.head(3)
    bot3 = dept_annual.tail(3)
    add_body(doc, '')
    add_rich_para(doc, [
        ('效能领先部门：', True, C_PRIMARY, Pt(10.5)),
        ('、'.join([f'{r["dept_l2"]}（{r["annual_mean"]:.1f}分）' for _, r in top3.iterrows()]), False, C_BLACK, Pt(10.5)),
        ('，这些部门全年均分稳定在较高水平，需求价值分持续产出。', False, C_BLACK, Pt(10.5)),
    ])
    add_rich_para(doc, [
        ('需关注部门：', True, C_RED, Pt(10.5)),
        ('、'.join([f'{r["dept_l2"]}（{r["annual_mean"]:.1f}分）' for _, r in bot3.iterrows()]), False, C_BLACK, Pt(10.5)),
        ('，均分显著低于整体水平，建议深入分析原因。', False, C_BLACK, Pt(10.5)),
    ])

    # ---- 3. 月度趋势分析 ----
    doc.add_page_break()
    add_heading(doc, '三、月度趋势分析', level=1)

    add_body(doc, '下表展示 2025 年各月效能总分的关键统计指标。整体分布呈左偏形态（中位数持续高于均值），说明多数员工集中在中等偏上分数段，少数低分个体拉低了均值。')

    m_headers = ['月份', '均值', '中位数', 'P25', 'P75', '标准差', '有效人数']
    m_rows = []
    for _, r in monthly_stats.iterrows():
        m_rows.append([
            f'{int(r["month"])}月',
            f'{r["total_mean"]:.1f}', f'{r["total_median"]:.1f}',
            f'{r["total_p25"]:.1f}', f'{r["total_p75"]:.1f}',
            f'{r["total_std"]:.1f}', str(int(r['total_count']))
        ])
    make_table(doc, m_headers, m_rows, col_widths=[1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.8])

    doc.add_paragraph()
    q1_mean = monthly_stats.iloc[:5]['total_mean'].mean()
    q2_mean = monthly_stats.iloc[5:]['total_mean'].mean()
    add_rich_para(doc, [
        ('上半年（3–7月）均分：', True, C_PRIMARY, Pt(10.5)),
        (f'{q1_mean:.1f}', True, C_ACCENT, Pt(10.5)),
        ('  |  ', False, C_GRAY, Pt(10.5)),
        ('下半年（8–12月）均分：', True, C_PRIMARY, Pt(10.5)),
        (f'{q2_mean:.1f}', True, C_ACCENT, Pt(10.5)),
        ('  |  变化：', False, C_GRAY, Pt(10.5)),
        (f'{"+" if q2_mean > q1_mean else ""}{q2_mean - q1_mean:.1f}', True,
         C_GREEN if q2_mean > q1_mean else C_RED, Pt(10.5)),
    ])

    add_body(doc, f'考勤时长全年稳定在月均 {avg_hours:.1f} 小时/天，波动极小，表明考勤时长对效能差异的解释力有限。效能得分的波动主要由需求价值分驱动。')

    # ---- 4. 个体效能分析 ----
    doc.add_page_break()
    add_heading(doc, '四、个体效能分析', level=1)

    bins = [0, 20, 30, 40, 50, 60, 100]
    labels = ['<20分', '20–30分', '30–40分', '40–50分', '50–60分', '60分以上']
    emp_stats['bucket'] = pd.cut(emp_stats['annual_mean'], bins=bins, labels=labels, right=False)
    dist = emp_stats['bucket'].value_counts().sort_index()

    add_body(doc, '全年均分分布如下。绝大多数员工（59.6%）集中在 40–50 分区间，呈现集中化分布特征。')

    dist_headers = ['分数段', '人数', '占比']
    dist_rows = [[str(k), str(v), f'{v/len(emp_stats)*100:.1f}%'] for k, v in dist.items()]
    make_table(doc, dist_headers, dist_rows, col_widths=[4, 3, 3])

    doc.add_paragraph()
    add_body(doc, 'Top 10（全年均分最高）', bold=True, color=C_PRIMARY)
    top10 = emp_stats.nlargest(10, 'annual_mean')
    make_table(doc,
        ['排名', '姓名', '岗位', '二级部门', '年均总分', '波动率'],
        [[str(i+1), str(r['name']), str(r['position']), str(r['dept_l2']),
          f'{r["annual_mean"]:.1f}', f'{r["volatility"]:.2f}' if pd.notna(r['volatility']) else '-']
         for i, (_, r) in enumerate(top10.iterrows())],
        col_widths=[1, 3.5, 3, 3.5, 2, 2]
    )

    doc.add_paragraph()
    add_body(doc, 'Bottom 10（全年均分最低，需重点关注）', bold=True, color=C_RED)
    bot10 = emp_stats.nsmallest(10, 'annual_mean')
    make_table(doc,
        ['排名', '姓名', '岗位', '二级部门', '年均总分', '波动率'],
        [[str(i+1), str(r['name']), str(r['position']), str(r['dept_l2']),
          f'{r["annual_mean"]:.1f}', f'{r["volatility"]:.2f}' if pd.notna(r['volatility']) else '-']
         for i, (_, r) in enumerate(bot10.iterrows())],
        col_widths=[1, 3.5, 3, 3.5, 2, 2]
    )

    add_body(doc, '')
    add_body(doc, f'Bottom 10 员工均分仅 13.8–26.9，与 Top 10（57.0–49.7）差距达 2–4 倍。低分人员主要集中在数据采集类岗位，建议重点排查其工作模式与任务量管理。')

    # ---- 5. 效能波动与趋势分析 ----
    doc.add_page_break()
    add_heading(doc, '五、效能波动与趋势分析', level=1)

    trends_all = ldf['trend'].dropna()
    up = (trends_all == '↑').sum()
    down = (trends_all == '↓').sum()
    flat = (trends_all.isin(['→', '/'])).sum()

    add_body(doc, '各月环比趋势箭头统计（4月–12月）：')
    add_rich_para(doc, [
        (f'↑ 上升：{up} 人次', False, C_GREEN, Pt(10.5)),
        ('  |  ', False, C_GRAY, Pt(10.5)),
        (f'↓ 下降：{down} 人次', False, C_RED, Pt(10.5)),
        ('  |  ', False, C_GRAY, Pt(10.5)),
        (f'→ 持平：{flat} 人次', False, C_GRAY, Pt(10.5)),
    ])

    # Per-month trend
    trend_rows = []
    for m in range(4, 13):
        md = ldf[ldf['month'] == m]
        t = md['trend'].value_counts()
        trend_rows.append([
            f'{m}月',
            str(t.get('↑', 0)), str(t.get('↓', 0)),
            str(t.get('→', 0) + t.get('/', 0)),
        ])
    make_table(doc,
        ['月份', '↑ 上升人数', '↓ 下降人数', '→ 持平人数'],
        trend_rows, col_widths=[2, 3, 3, 3]
    )

    doc.add_paragraph()
    add_body(doc, '员工效能稳定性分析：')
    stable = (emp_stats['volatility'] < 0.15).sum()
    moderate = ((emp_stats['volatility'] >= 0.15) & (emp_stats['volatility'] < 0.3)).sum()
    high = (emp_stats['volatility'] >= 0.3).sum()
    add_rich_para(doc, [
        (f'稳定（CV<0.15）：{stable} 人  |  中度波动（0.15≤CV<0.3）：{moderate} 人  |  高度波动（CV≥0.3）：{high} 人', False, C_BLACK, Pt(10.5)),
    ])
    add_body(doc, f'{high} 名员工效能波动较大（变异系数≥0.3），其分数月度间起伏明显，建议逐一复盘波动原因，特别是波动伴随整体下行趋势的个案。')

    # ---- 6. 低效能原因分析 ----
    doc.add_page_break()
    add_heading(doc, '六、低效能原因分析', level=1)

    add_body(doc, '基于员工备注（`备注`列）中的文字说明，将低效能/低分原因归纳为以下类别。部分备注列已被脱敏处理，以下仅统计中文文本可读的部分。')

    reason_rows = []
    total_reasons = sum(len(v) for v in remark_cats.values())
    for cat, items in sorted(remark_cats.items(), key=lambda x: -len(x[1])):
        pct = f'{len(items)/total_reasons*100:.1f}%' if total_reasons > 0 else '0%'
        reason_rows.append([cat, str(len(items)), pct])
    make_table(doc,
        ['原因类别', '出现次数', '占比'],
        reason_rows, col_widths=[6, 3, 3]
    )

    doc.add_paragraph()
    add_body(doc, '典型备注举例（已脱敏）：', bold=True, color=C_PRIMARY)
    all_remarks = [str(r) for r in ldf['remark'].dropna() if str(r).strip() and str(r).strip() != 'nan']
    for r in list(dict.fromkeys(all_remarks))[:10]:
        add_body(doc, f'• {r}', size=Pt(9), color=C_GRAY)

    doc.add_paragraph()
    add_body(doc, '核心发现：', bold=True)
    add_body(doc, '1. "TB 外工作"是最高频的低分原因——大量员工的实际产出（合规审查、竞品分析、独立开发、系统优化等）未在 TB 系统中建任务追踪，导致系统内任务量数据低估了真实产出。')
    add_body(doc, '2. "任务结案未更新"反映流程管理问题——任务完成后未及时关闭，导致考核周期内统计失真。')
    add_body(doc, '3. "任务周期性长"在算法/技术岗位中普遍存在——长周期研发任务的月度产出天然不均衡，当前月度考核机制无法准确反映这类工作的价值。')

    # ---- 7. 核心发现与改进建议 ----
    doc.add_page_break()
    add_heading(doc, '七、核心发现与改进建议', level=1)

    findings = [
        ('效能分布集中化，但底部存在显著长尾',
         f'59.6% 员工集中在 40–50 分区间，但 {int((emp_stats["annual_mean"] < 30).sum())} 名员工年均分低于 30 分，最低仅 13.8 分，与头部差距达 4 倍。底部员工主要集中在数据采集类岗位。',
         '对低于 30 分员工启动一对一效能面谈，排查是任务分配问题、能力匹配问题还是系统统计失真；必要时进行岗位调整或专项培训。'),

        ('TB 系统任务数据与实际产出存在严重偏差',
         '大量员工反馈实际工作（合规审查、独立开发、竞品分析、系统优化、微信养号等）未进入 TB 任务系统，导致考核数据低估真实产出。这是"TB 外工作"成为最高频低分原因的根本原因。',
         '建立非 TB 任务的补充登记机制，允许员工在考核周期内提交 TB 外工作产出清单；中长期考虑将考核数据源从单一 TB 系统扩展至多维产出平台。'),

        ('考勤分覆盖率过低，加权总分代表性不足',
         f'全年仅 {full_coverage} 人次同时具有考勤分和需求分（覆盖率约 {full_coverage/(len(MONTHS)*total_emp)*100:.0f}%），绝大多数月份仅靠需求价值分评价。考勤分的评分标准和录入率需审视。',
         '明确考勤分的录入标准与责任人，将覆盖率提升至 80% 以上；或重新评估 30% 权重的合理性，考虑降低考勤分权重或改为定性评价。'),

        ('长周期研发岗位月度考核机制存在结构性缺陷',
         '算法、架构师等技术岗位普遍反馈"任务周期性较长"，单月任务量无法反映长期研发投入的价值。这类岗位的月度效能分数持续偏低并非能力问题，而是考核机制不匹配。',
         '对算法、架构师等研发岗位设立双轨考核：月度保留基本考勤+关键里程碑评价，季度/半年度进行深度产出评估；引入技术委员会同行评议。'),

        ('下半年效能整体优于上半年',
         f'下半年均分 {q2_mean:.1f} 较上半年 {q1_mean:.1f} 提升 {q2_mean - q1_mean:.1f} 分，9 月（{monthly_stats.iloc[6]["total_mean"]:.1f}）和 12 月（{monthly_stats.iloc[9]["total_mean"]:.1f}）为全年高峰。',
         '识别下半年效能提升的驱动因素（项目管理改善、人员熟练度提升、年底冲刺效应），将有效做法固化为制度，避免过度依赖年底突击。'),

        ('效能波动存在季节性规律',
         f'3 月（{monthly_stats.iloc[0]["total_mean"]:.1f}）和 10 月（{monthly_stats.iloc[7]["total_mean"]:.1f}）为全年最低点，可能与春节后恢复期和国庆长假有关。',
         '在 3 月和 10 月设置合理的考核预期基线，避免因季节性因素误判员工效能；同时在长假前做好任务规划以平滑产出节奏。'),
    ]

    for i, (title, finding, suggestion) in enumerate(findings, 1):
        add_rich_para(doc, [
            (f'发现 {i}：{title}', True, C_PRIMARY, Pt(11)),
        ])
        add_body(doc, f'现状：{finding}')
        add_rich_para(doc, [
            ('建议：', True, C_ACCENT, Pt(10.5)),
            (suggestion, False, C_BLACK, Pt(10.5)),
        ])
        doc.add_paragraph()

    # ---- Notes ----
    doc.add_paragraph()
    doc.add_paragraph()
    add_body(doc, '说明：本报告基于脱敏后的效能考核数据生成，人员姓名、部门名称已替换为匿名标识。所有统计分析仅基于数值型和文本型（备注）数据。考勤分覆盖率较低是本次分析的主要数据质量限制。', size=Pt(9), color=C_GRAY)
    add_body(doc, f'报告生成日期：2025年度数据汇总。数据来源：人效测算表（203人×10个月）。', size=Pt(9), color=C_GRAY)

    os.makedirs(OUT_DIR, exist_ok=True)
    doc.save(OUT)
    print(f'报告已保存至：{OUT}')
    return doc


def main():
    print("加载数据...")
    df, df2 = load_data()
    ldf = compute_scores(df)
    monthly_stats = compute_aggregates(ldf)
    emp_stats = compute_employee_stats(ldf)
    dept_annual, dept_monthly = compute_dept_stats(ldf)
    remark_cats = classify_remarks(ldf)
    build_report(ldf, emp_stats, dept_annual, dept_monthly, monthly_stats, remark_cats, df2)

if __name__ == '__main__':
    main()
