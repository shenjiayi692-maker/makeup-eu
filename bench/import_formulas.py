#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把供应商配方汇总 xlsx 转成 bench/formulas.json。

    python bench/import_formulas.py ~/Downloads/真实化妆品供应商配方汇总_百分数值_含驻留水基配方.xlsx

手抄九份配方、上百个成分必然出错，所以走脚本。每次改了源表重跑一次即可。
需要 openpyxl。
"""
import argparse
import json
import os
import re
import sys

try:
    import openpyxl
except ImportError:
    sys.exit("需要 openpyxl：pip install openpyxl")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'formulas.json')

# sheet -> 该表产出哪些配方。amount_col 是「投料量」在表里的列偏移（从 INCI 列算起）
SHEETS = {
    '卸妆油':            [('F1a', '配方 1'), ('F1b', '配方 2')],
    '透明除臭棒':        [('F2',  None)],
    '无水防晒油':        [('F3a', '2-1'), ('F3b', '2-2')],
    '抗痘洁面_III+V':    [('F4',  None)],
    '水杨酸洗发_III+V':  [('F5',  None)],
    '延缓老化面手霜_驻留': [('F6',  None)],
    'HappySkin面霜_驻留': [('F7',  None)],
}

PRODUCT_META = {
    'F1a': dict(category='cleansing oil', rinse_off=True, base='oil',
                body_parts=['face'], claims=['makeup removal']),
    'F1b': dict(category='cleansing oil', rinse_off=True, base='oil',
                body_parts=['face'], claims=['makeup removal']),
    'F2':  dict(category='deodorant stick', rinse_off=False, base='anhydrous',
                body_parts=['underarm'], claims=['deodorant']),
    'F3a': dict(category='sun care oil', rinse_off=False, base='anhydrous',
                body_parts=['face', 'body'], claims=['sun protection']),
    'F3b': dict(category='sun care oil', rinse_off=False, base='anhydrous',
                body_parts=['face', 'body'], claims=['sun protection']),
    'F4':  dict(category='face wash', rinse_off=True, base='aqueous',
                body_parts=['face'], claims=['anti-acne', 'mild cleansing']),
    'F5':  dict(category='shampoo', rinse_off=True, base='aqueous',
                body_parts=['scalp', 'hair'], claims=['scalp care']),
    'F6':  dict(category='face cream', rinse_off=False, base='aqueous',
                body_parts=['face', 'hands'], claims=['anti-ageing']),
    'F7':  dict(category='face cream', rinse_off=False, base='aqueous O/W emulsion',
                body_parts=['face'], claims=[]),
}

# 供应形态：从「商品名/供应形态」一列里解析出活性含量
FORM_PATTERNS = [
    (re.compile(r'(\d+(?:\.\d+)?)\s*%\s*(?:total\s+)?solids', re.I), 'solution'),
    (re.compile(r'(\d+(?:\.\d+)?)\s*%\s*active', re.I),             'solution'),
    (re.compile(r'(\d+(?:\.\d+)?)\s*%\s*(?:w/w\s*)?solution', re.I), 'solution'),
    (re.compile(r'(\d+(?:\.\d+)?)\s*%\s*dispersion', re.I),          'dispersion'),
    (re.compile(r'(\d+(?:\.\d+)?)\s*%\s*w/w', re.I),                 'solution'),
    (re.compile(r'^\s*(\d+(?:\.\d+)?)\s*%\s*$'),                     'solution'),
]
NEAT_HINTS = ('neat', '未注明稀释')

FUNCTION_MAP = {
    '防腐剂': 'preservative', '防腐体系': 'preservative',
    '皮肤调理/防腐增效': 'preservative booster',
    '抗氧化剂': 'antioxidant', '着色剂': 'colorant', '香精': 'fragrance',
    '紫外线过滤剂': 'uv filter', '表面活性剂': 'surfactant',
    '润肤剂': 'emollient', '保湿剂': 'humectant', '螯合剂': 'chelating agent',
    '流变改性剂': 'rheology modifier', '增稠剂': 'thickener',
    'pH 调节剂': 'ph adjuster', '乳化剂': 'emulsifier',
    '稀释剂': 'diluent', '载体': 'carrier',
}


def parse_supply_form(text):
    """-> (supply_form, 是否为已知稀释形态)"""
    t = str(text or '').strip()
    if not t or t == '—':
        return {"kind": "neat", "active_pct": 100}, False
    if any(h in t.lower() for h in NEAT_HINTS):
        return {"kind": "neat", "active_pct": 100}, False
    if 'q.s.' in t.lower():
        return {"kind": "neat", "active_pct": 100}, False
    for rx, kind in FORM_PATTERNS:
        m = rx.search(t)
        if m:
            return {"kind": kind, "active_pct": float(m.group(1)),
                    "as_supplied": t}, True
    return {"kind": "neat", "active_pct": 100}, False


def map_function(cn):
    cn = str(cn or '').strip()
    if cn in FUNCTION_MAP:
        return [FUNCTION_MAP[cn]]
    for k, v in FUNCTION_MAP.items():
        if k and k in cn:
            return [v]
    return [cn] if cn else []


def find_header(ws):
    for i, row in enumerate(ws.iter_rows(values_only=True), 1):
        cells = [str(c).strip() if c is not None else '' for c in row]
        if any(c.startswith('INCI') for c in cells):
            return i, cells
    return None, None


def cell(row, idx):
    if idx is None or idx >= len(row):
        return ''
    v = row[idx]
    if v is None:
        return ''
    return v if isinstance(v, (int, float)) else str(v).strip()


def sheet_meta(ws):
    """产品类型 / 使用部位 / 目标人群 / 来源 URL"""
    meta = {}
    for row in ws.iter_rows(min_row=1, max_row=12, values_only=True):
        cells = [str(c).strip() if c is not None else '' for c in row]
        for j, c in enumerate(cells):
            if c in ('产品类型', '使用部位', '目标人群') and j + 1 < len(cells):
                meta[c] = cells[j + 1]
            if c in ('来源 URL', '供应商页面') and j + 1 < len(cells):
                meta.setdefault('source_url', cells[j + 1])
    return meta


def parse_sheet(ws, targets):
    hdr_i, hdr = find_header(ws)
    if hdr_i is None:
        raise SystemExit("找不到表头: %s" % ws.title)
    inci_i = next(j for j, c in enumerate(hdr) if c.startswith('INCI'))
    def col(pred):
        return next((j for j, c in enumerate(hdr) if pred(c)), None)
    trade_i = col(lambda c: c.startswith('商品名'))
    func_i = col(lambda c: '功能' in c)
    note_i = col(lambda c: c == '备注')
    annex_i = col(lambda c: '附件标记' in c)

    out = {}
    for code, amount_label in targets:
        if amount_label:
            amt_i = col(lambda c, L=amount_label: c.startswith(L))
        else:
            amt_i = col(lambda c: '投料量' in c)
        if amt_i is None:
            raise SystemExit("%s: 找不到投料量列 (%s)" % (ws.title, amount_label))
        ings = []
        for row in ws.iter_rows(min_row=hdr_i + 1, values_only=True):
            # 成分表下面还跟着「合计」和供应商自己的初步核对表；这些行的标记
            # 不一定落在 INCI 那一列，所以整行扫
            flat = [str(c).strip() for c in row if c is not None]
            if any(x.startswith(('合计', '说明', '物质')) for x in flat):
                break
            name = cell(row, inci_i)
            if not name:
                continue
            amt = cell(row, amt_i)
            if amt == '' or amt is None:
                continue
            try:
                amt = float(amt)
            except (TypeError, ValueError):
                continue
            if amt == 0:                     # F3a 里硅石是 0，等于不存在
                continue
            trade = str(cell(row, trade_i) or '')
            form, diluted = parse_supply_form(trade)
            ing = {
                "name_as_written": str(name),
                "inci": str(name),
                "function": map_function(cell(row, func_i)),
                "input_pct": amt,
                "supply_form": form,
            }
            if trade and trade != '—':
                ing['trade_name'] = trade
            if diluted:
                ing['supplied_diluted'] = True
            if ',' in str(name):
                ing['kind'] = 'blend'
                ing['known_components'] = [s.strip() for s in str(name).split(',')]
                ing['composition_disclosed'] = False
            n = str(cell(row, note_i) or '')
            if n:
                ing['supplier_note'] = n
            a = str(cell(row, annex_i) or '')
            if a and a != '—':
                ing['supplier_annex_hint'] = a
            ings.append(ing)
        meta = sheet_meta(ws)
        product = dict(PRODUCT_META[code])
        product['name'] = str(ws.cell(1, 1).value or code)
        product['supplier_product_type'] = meta.get('产品类型', '')
        product['supplier_body_parts'] = meta.get('使用部位', '')
        product['target_population_note'] = meta.get('目标人群', '')
        out[code] = {
            "complete": True,
            "source": {"sheet": ws.title, "url": meta.get('source_url', '')},
            "product": product,
            "key_ingredients": [],
            "base_ingredients": ings,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xlsx')
    ap.add_argument('--out', default=OUT)
    a = ap.parse_args()
    wb = openpyxl.load_workbook(a.xlsx, data_only=True)

    data = {
        "_note": "由 import_formulas.py 从供应商配方汇总 xlsx 生成，不要手改。"
                 "改了源表就重跑：python bench/import_formulas.py <xlsx>",
        "_source_file": os.path.basename(a.xlsx),
        "_assessment_date": "2026-09-05",
        "_regulation_version": "02009R1223-20260518",
    }
    for name, targets in SHEETS.items():
        if name not in wb.sheetnames:
            sys.exit("源表里没有 sheet: %s" % name)
        data.update(parse_sheet(wb[name], targets))

    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    print("wrote %s" % a.out)
    for code in [c for c in data if not c.startswith('_')]:
        ings = data[code]['base_ingredients']
        total = sum(i['input_pct'] for i in ings)
        dil = sum(1 for i in ings if i.get('supplied_diluted'))
        blend = sum(1 for i in ings if i.get('kind') == 'blend')
        flag = '' if abs(total - 100) < 0.05 else '   <-- 合计不是 100'
        print("  %-4s %2d 个成分  合计 %6.2f%%  稀释供应 %d  复配 %d%s"
              % (code, len(ings), total, dil, blend, flag))


if __name__ == '__main__':
    main()
