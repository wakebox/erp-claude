#!/usr/bin/env python3
"""
gen-stock-docs.py
從 stock-api-docs.md 生成 stock-api-docs.html

使用方式:
  python3 gen-stock-docs.py

編輯 stock-api-docs.md 中的 [x] / [ ] 來控制 OA 實作狀態，
執行此腳本即可重新生成 HTML。
"""

import re
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 模組靜態 ID 對應（依 Markdown 出現順序）
MODULE_IDS = [
    'safety-stock',
    'warehouse',
    'stock-query',
    'stock-in',
    'stock-out',
    'transfer',
    'bad-product',
    'day-check',
    'check-plan',
    'check-exec',
    'pdm-related',
]

# 模組優先級 tag 樣式
PRIORITY_CLASS = {
    'P1': 'orange',
    'P2': 'blue',
    'P3': 'green',
}

# ── 額外的靜態 HTML 內容（TypeScript 介面、流程說明等）──────────────────────

EXTRAS = {
    'safety-stock': """
    <h3>TypeScript 介面定義</h3>
    <pre><span class="kw">export namespace</span> <span class="tp">StockSafeApi</span> {
  <span class="kw">export interface</span> <span class="tp">StockSafeDetail</span> {
    recipeId?: <span class="tp">number</span>;
    productName?: <span class="tp">string</span>;
    dailySaleNum?: <span class="tp">number</span>;
    ingredientName?: <span class="tp">string</span>;
    ingredientId?: <span class="tp">number</span>;
    standardAmount?: <span class="tp">number</span>;
    amountUnit?: <span class="tp">string</span>;
    standardQuantity?: <span class="tp">number</span>;
    quantityUnit?: <span class="tp">string</span>;
    safeAmount?: <span class="tp">number</span>;
    safeQuantity?: <span class="tp">number</span>;
    safeStock?: <span class="tp">number</span>;
  }
  <span class="kw">export interface</span> <span class="tp">StockSafe</span> {
    id?: <span class="tp">number</span>;
    signCode?: <span class="tp">string</span>;
    applyDept?: <span class="tp">string</span>;
    subject?: <span class="tp">string</span>;
    weightDay?: <span class="tp">string</span>;
    warehouse?: <span class="tp">string</span>;
    processStatus?: <span class="tp">string</span>;
    stockSafeDetailReqVOList?: <span class="tp">StockSafeDetail</span>[];
  }
}</pre>
    <h3>計算邏輯說明</h3>
    <div class="alert info">
      <strong>安全存量計算公式：</strong><br>
      <code>safeStock = dailySaleNum × standardAmount × weightDay</code><br>
      系統先呼叫 <code>getAllProductDaySales(weightDay)</code> 取得各產品每日銷售量，再依食譜配方中的 standardAmount 計算每種食材的安全存量。
    </div>
""",

    'warehouse': """
    <h3>倉庫層級結構</h3>
    <div class="flow">
      <div class="flow-box">區域<br><small>area</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">倉別<br><small>warehouseType</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">倉名<br><small>warehouse</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">儲區<br><small>zone</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">儲位<br><small>binCode</small></div>
    </div>
""",

    'stock-query': """
    <h3>StockVO 回傳欄位</h3>
    <pre><span class="kw">interface</span> <span class="tp">StockVO</span> {
  warehouseId?: <span class="tp">number</span>;
  prodCode?: <span class="tp">string</span>;
  ingredientName?: <span class="tp">string</span>;
  warehouseTypeName?: <span class="tp">string</span>;
  warehouseName?: <span class="tp">string</span>;
  zoneName?: <span class="tp">string</span>;
  binCode?: <span class="tp">string</span>;
  standardAmount?: <span class="tp">number</span>;
  standardQuantity?: <span class="tp">number</span>;
  safeStock?: <span class="tp">number</span>;   <span class="cm">// 用於高亮警示</span>
}</pre>
""",

    'stock-in': """
    <h3>批量處理請求結構</h3>
    <pre><span class="kw">interface</span> <span class="tp">BatchProcessStockRecordParams</span> {
  id?: <span class="tp">number</span>;
  formCode?: <span class="tp">string</span>;
  processStatus?: <span class="tp">string</span>;
  stockType: <span class="tp">number</span>;         <span class="cm">// 0=出庫, 1=入庫（必填）</span>
  stockReason?: <span class="tp">string</span>;
  sourceSignCode?: <span class="tp">string</span>;
  area?: <span class="tp">number</span>;
  warehouseType?: <span class="tp">string</span>;
  warehouse?: <span class="tp">string</span>;
  warehouseId?: <span class="tp">number</span>;
  inboundTime?: <span class="tp">number</span>;
  approvalComments?: <span class="tp">string</span>;
  stockRecordList?: <span class="tp">Array</span>&lt;{
    id?: <span class="tp">number</span>;
    prodCode?: <span class="tp">string</span>;
    warehouseId?: <span class="tp">number</span>;
    invNumChange?: <span class="tp">number</span>;
    standardAmount?: <span class="tp">number</span>;
    standardQuantity?: <span class="tp">number</span>;
    stockType?: <span class="tp">number</span>;
    recordId?: <span class="tp">number</span>;
  }&gt;;
}</pre>
    <div class="alert warning">
      <strong>⚠️ 注意：</strong> 入庫與出庫共用 <code>/whs/stock-record-head</code> 和 <code>/whs/stock-record</code>，以 <code>stockType</code> 區分（0=出庫，1=入庫）。
    </div>
""",

    'stock-out': """
    <div class="alert info">
      <strong>💡 共用端點：</strong> 出庫與入庫共用相同的底層 API，差異在於參數 <code>stockType=0</code>。更新流程狀態時仍使用 <code>/whs/stock-in/update-process-status</code> 路徑。
    </div>
""",

    'transfer': """
    <h3>調撥計算庫存請求</h3>
    <pre><span class="kw">interface</span> <span class="tp">ComputeAreaInventoryParams</span> {
  area: <span class="tp">number</span>;
  outWarehouse?: <span class="tp">string</span>;
  inWarehouse?: <span class="tp">string</span>;
  prodCode: <span class="tp">string</span>[];
}
<span class="kw">interface</span> <span class="tp">InventoryQuantity</span> {
  prodCode: <span class="tp">string</span>;
  areaInvNum?: <span class="tp">number</span>;    <span class="cm">// 出庫倉庫存數量</span>
  inAreaInvNum?: <span class="tp">number</span>;   <span class="cm">// 入庫倉庫存數量</span>
}</pre>
""",

    'bad-product': "",

    'day-check': "",

    'check-plan': "",

    'check-exec': """
    <h3>盤點差異計算欄位</h3>
    <pre><span class="kw">interface</span> <span class="tp">CheckRecordItem</span> {
  accountQuantity?: <span class="tp">number</span>;  <span class="cm">// 帳面數量（系統計算）</span>
  checkQuantity?: <span class="tp">number</span>;    <span class="cm">// 盤點數量（實際清點）</span>
  auditQuantity?: <span class="tp">number</span>;    <span class="cm">// 審核數量 = checkQuantity - accountQuantity</span>
  zone?: <span class="tp">string</span>;
  binCode?: <span class="tp">string</span>;
  stockReason?: <span class="tp">string</span>;     <span class="cm">// SW03=盤點</span>
}</pre>
""",

    'pdm-related': """
    <div class="alert success">
      <strong>✅ 已實作的 PDM 端點：</strong> 食材規格（pdm/ingredient-specs）、食譜（pdm/recipe）等均已在後端實作，可直接被 Stock 模組使用。
    </div>
""",
}

# ── Markdown 解析 ────────────────────────────────────────────────────────────

def parse_markdown(path):
    with open(path, encoding='utf-8') as f:
        text = f.read()

    modules = []
    # 以 ## 分段（不含 ###）
    raw_sections = re.split(r'\n(?=## )', text)

    for idx, section in enumerate(raw_sections):
        if not section.startswith('## '):
            continue
        lines = section.split('\n')
        header = lines[0]

        # 解析 header：## 一、🛡️ 安全存量設定 (Safety Stock) 或 （相依模組）
        hm = re.match(r'^##\s+(?:\S+、)?\s*(.+?)\s*[（(](.+?)[）)]', header)
        if not hm:
            continue

        name_raw = hm.group(1).strip()
        name_en = hm.group(2).strip()

        # 擷取 emoji icon（第一個非 ASCII 字元）
        emoji_m = re.search(r'[\U0001F300-\U0001FAFF☀-➿]', name_raw)
        icon = emoji_m.group(0) if emoji_m else ''
        name = re.sub(r'^[\U0001F300-\U0001FAFF☀-➿\s]+', '', name_raw).strip()

        # section id（依順序對應）
        section_idx = len(modules)
        section_id = MODULE_IDS[section_idx] if section_idx < len(MODULE_IDS) else name_en.lower().replace(' ', '-')

        # 解析 metadata 行
        route = ''
        api_file = ''
        priority = ''
        for line in lines[1:10]:
            rm = re.search(r'\*\*路由\*\*[：:]\s*`([^`]+)`', line)
            if rm:
                route = rm.group(1)
            fm = re.search(r'\*\*(?:API\s*)?檔案\*\*[：:]\s*`([^`]+)`', line)
            if fm:
                api_file = fm.group(1)
            pm = re.search(r'\*\*優先級\*\*[：:]\s*`([^`]+)`', line)
            if pm:
                priority = pm.group(1)

        # 解析 API 表格
        apis = []
        in_table = False
        for line in lines:
            if re.match(r'^\|[\s:]-', line):  # separator row
                in_table = True
                continue
            if in_table and line.startswith('|'):
                cols = [c.strip() for c in line.split('|')[1:-1]]
                if len(cols) >= 5:
                    method = re.sub(r'[`*]', '', cols[0]).strip()
                    endpoint = re.sub(r'[`]', '', cols[1]).strip()
                    function = cols[2].strip()
                    description = cols[3].strip()
                    oa_col = cols[4]
                    oa = '[x]' in oa_col
                    if method.upper() in ('GET', 'POST', 'PUT', 'DELETE', 'PATCH'):
                        apis.append({
                            'method': method.upper(),
                            'endpoint': endpoint,
                            'function': function,
                            'description': description,
                            'oa': oa,
                        })
            elif in_table and line.strip() and not line.startswith('|') and not line.startswith('>'):
                in_table = False

        modules.append({
            'id': section_id,
            'icon': icon,
            'name': name,
            'name_en': name_en,
            'route': route,
            'api_file': api_file,
            'priority': priority,
            'apis': apis,
        })

    return modules

# ── HTML 生成輔助函式 ─────────────────────────────────────────────────────────

CSS = """
  :root {
    --primary: #d4380d;
    --primary-light: #fff2e8;
    --success: #389e0d;
    --success-bg: #f6ffed;
    --danger: #cf1322;
    --danger-bg: #fff1f0;
    --warning: #d48806;
    --warning-bg: #fffbe6;
    --info: #096dd9;
    --info-bg: #e6f7ff;
    --border: #d9d9d9;
    --text: #262626;
    --text-secondary: #595959;
    --bg: #f5f5f5;
    --code-bg: #1e1e2e;
    --radius: 8px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }
  .sidebar { position: fixed; left: 0; top: 0; width: 260px; height: 100vh; background: #141414; color: #ccc; overflow-y: auto; z-index: 100; padding: 16px 0; }
  .sidebar h2 { color: #fff; padding: 12px 20px; font-size: 14px; border-bottom: 1px solid #333; margin-bottom: 8px; }
  .sidebar a { display: block; padding: 6px 20px; color: #aaa; text-decoration: none; font-size: 13px; transition: all 0.2s; }
  .sidebar a:hover { color: #fff; background: #333; }
  .sidebar .group { font-size: 11px; color: #666; padding: 10px 20px 4px; text-transform: uppercase; letter-spacing: 1px; }
  .sidebar .badge { display: inline-block; font-size: 10px; padding: 1px 6px; border-radius: 10px; margin-left: 4px; }
  .sidebar .badge.no { background: var(--danger); color: #fff; }
  .sidebar .badge.yes { background: var(--success); color: #fff; }
  .sidebar .badge.partial { background: var(--warning); color: #fff; }
  .main { margin-left: 260px; padding: 24px; }
  .header { background: linear-gradient(135deg, #d4380d, #fa541c); color: #fff; padding: 40px; border-radius: var(--radius); margin-bottom: 28px; }
  .header h1 { font-size: 28px; margin-bottom: 8px; }
  .header p { opacity: 0.85; font-size: 15px; }
  .header .stats { display: flex; gap: 24px; margin-top: 20px; }
  .header .stat { background: rgba(255,255,255,0.15); padding: 12px 20px; border-radius: var(--radius); text-align: center; }
  .header .stat .num { font-size: 28px; font-weight: 700; }
  .header .stat .label { font-size: 12px; opacity: 0.8; }
  .section { background: #fff; border-radius: var(--radius); padding: 28px; margin-bottom: 24px; border: 1px solid var(--border); }
  .section-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 2px solid var(--bg); }
  .section-header h2 { font-size: 20px; }
  .section-header .icon { font-size: 24px; }
  .impl-badge { padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
  .impl-badge.no { background: var(--danger-bg); color: var(--danger); border: 1px solid #ffa39e; }
  .impl-badge.yes { background: var(--success-bg); color: var(--success); border: 1px solid #b7eb8f; }
  .impl-badge.partial { background: var(--warning-bg); color: var(--warning); border: 1px solid #ffe58f; }
  .overview-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; margin-bottom: 28px; }
  .module-card { border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; cursor: pointer; transition: all 0.2s; }
  .module-card:hover { border-color: var(--primary); box-shadow: 0 4px 12px rgba(212,56,13,0.15); transform: translateY(-2px); }
  .module-card .title { font-weight: 600; margin-bottom: 4px; }
  .module-card .path { font-size: 12px; color: var(--primary); font-family: monospace; margin-bottom: 8px; }
  .module-card .count { font-size: 12px; color: var(--text-secondary); }
  .module-card .status { margin-top: 10px; }
  .api-table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px; }
  .api-table th { background: #fafafa; padding: 10px 12px; text-align: left; border-bottom: 2px solid var(--border); font-weight: 600; color: var(--text-secondary); }
  .api-table td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
  .api-table tr:hover td { background: #fafafa; }
  .method { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; font-family: monospace; min-width: 50px; text-align: center; }
  .method.GET { background: #e6f7ff; color: #096dd9; }
  .method.POST { background: #f6ffed; color: #389e0d; }
  .method.PUT { background: #fff7e6; color: #d48806; }
  .method.DELETE { background: #fff1f0; color: #cf1322; }
  .endpoint { font-family: monospace; font-size: 12px; color: #531dab; background: #f9f0ff; padding: 2px 8px; border-radius: 4px; }
  .oa-yes { color: var(--success); font-weight: 600; }
  .oa-no { color: var(--danger); font-weight: 600; }
  pre { background: var(--code-bg); color: #cdd6f4; padding: 20px; border-radius: var(--radius); overflow-x: auto; font-size: 12px; line-height: 1.7; margin: 12px 0; }
  pre .kw { color: #cba6f7; }
  pre .str { color: #a6e3a1; }
  pre .cm { color: #6c7086; font-style: italic; }
  pre .tp { color: #89dceb; }
  pre .num { color: #fab387; }
  pre .fn { color: #89b4fa; }
  .flow { display: flex; align-items: center; flex-wrap: wrap; gap: 0; margin: 16px 0; }
  .flow-box { background: var(--info-bg); border: 1px solid #91caff; padding: 10px 16px; border-radius: 6px; font-size: 13px; text-align: center; min-width: 110px; }
  .flow-box.start { background: var(--success-bg); border-color: #b7eb8f; }
  .flow-box.end { background: #f9f0ff; border-color: #d3adf7; }
  .flow-box.decision { background: var(--warning-bg); border-color: #ffe58f; }
  .flow-arrow { padding: 0 8px; color: #999; font-size: 18px; }
  .alert { padding: 12px 16px; border-radius: var(--radius); margin: 12px 0; border-left: 4px solid; font-size: 13px; }
  .alert.info { background: var(--info-bg); border-color: var(--info); }
  .alert.warning { background: var(--warning-bg); border-color: var(--warning); }
  .alert.danger { background: var(--danger-bg); border-color: var(--danger); }
  .alert.success { background: var(--success-bg); border-color: var(--success); }
  .sidebar a.active { color: #fff; background: #1a1a3e; border-left: 3px solid var(--primary); }
  h3 { font-size: 16px; margin: 20px 0 12px; color: var(--text); }
  h4 { font-size: 14px; margin: 16px 0 8px; color: var(--text-secondary); }
  p { font-size: 14px; color: var(--text-secondary); margin-bottom: 10px; }
  ul { padding-left: 20px; font-size: 14px; color: var(--text-secondary); }
  li { margin-bottom: 4px; }
  .tag { display: inline-block; padding: 1px 8px; border-radius: 4px; font-size: 11px; margin: 2px; }
  .tag.blue { background: var(--info-bg); color: var(--info); border: 1px solid #91caff; }
  .tag.green { background: var(--success-bg); color: var(--success); border: 1px solid #b7eb8f; }
  .tag.orange { background: var(--primary-light); color: var(--primary); border: 1px solid #ffbb96; }
  .model-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
  .model-box { border: 2px solid #d3adf7; border-radius: var(--radius); overflow: hidden; }
  .model-box .model-title { background: #722ed1; color: #fff; padding: 10px 16px; font-weight: 700; font-size: 14px; }
  .model-box table { width: 100%; font-size: 12px; }
  .model-box table th { background: #f9f0ff; padding: 6px 12px; border-bottom: 1px solid #d3adf7; color: #531dab; }
  .model-box table td { padding: 5px 12px; border-bottom: 1px solid #f0f0f0; font-family: monospace; }
  .field-key { color: var(--primary); font-weight: 600; }
  .field-type { color: #096dd9; }
  .field-desc { color: var(--text-secondary); font-family: sans-serif; font-size: 11px; }
"""

JS = """
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const parent = tab.closest('.tabs').parentElement;
    parent.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    parent.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    const target = parent.querySelector('#' + tab.dataset.target);
    if (target) target.classList.add('active');
  });
});
const sections = document.querySelectorAll('[id]');
const navLinks = document.querySelectorAll('.sidebar a');
window.addEventListener('scroll', () => {
  let current = '';
  sections.forEach(s => { if (window.scrollY >= s.offsetTop - 100) current = s.id; });
  navLinks.forEach(a => {
    a.classList.remove('active');
    if (a.getAttribute('href') === '#' + current) a.classList.add('active');
  });
});
"""

def oa_badge_class(oa_count, total):
    if total == 0:
        return 'no'
    if oa_count == total:
        return 'yes'
    if oa_count == 0:
        return 'no'
    return 'partial'

def oa_badge_text(oa_count, total):
    if oa_count == total and total > 0:
        return 'OA 已實作'
    if oa_count == 0:
        return 'OA 未實作'
    return f'OA 部分實作 ({oa_count}/{total})'

def sidebar_badge_class(oa_count, total):
    if total == 0 or oa_count == 0:
        return 'no'
    if oa_count == total:
        return 'yes'
    return 'partial'

def sidebar_badge_text(oa_count, total):
    if oa_count == total and total > 0:
        return '已實作'
    if oa_count == 0:
        return '未實作'
    return f'{oa_count}/{total}'

def gen_sidebar(modules):
    html = '<nav class="sidebar">\n'
    html += '  <h2>🍔 Stock 模組 API 文件</h2>\n'
    html += '  <div class="group">概覽</div>\n'
    html += '  <a href="#overview">系統架構總覽</a>\n'
    html += '  <a href="#flow-overview">業務流程圖</a>\n'
    html += '  <a href="#model-overview">資料模型圖</a>\n'
    html += '  <div class="group">庫存管理模組</div>\n'

    for m in modules:
        if m['id'] == 'pdm-related':
            continue
        total = len(m['apis'])
        oa_count = sum(1 for a in m['apis'] if a['oa'])
        bc = sidebar_badge_class(oa_count, total)
        bt = sidebar_badge_text(oa_count, total)
        html += f'  <a href="#{m["id"]}">{m["icon"]} {m["name"]} <span class="badge {bc}">{bt}</span></a>\n'

    html += '  <div class="group">相關模組</div>\n'
    for m in modules:
        if m['id'] == 'pdm-related':
            total = len(m['apis'])
            oa_count = sum(1 for a in m['apis'] if a['oa'])
            bc = sidebar_badge_class(oa_count, total)
            bt = sidebar_badge_text(oa_count, total)
            html += f'  <a href="#pdm-related">PDM 相關 API <span class="badge {bc}">{bt}</span></a>\n'

    html += '  <a href="#impl-summary">實作建議</a>\n'
    html += '</nav>\n'
    return html

def gen_overview_cards(modules):
    html = '<div class="overview-grid">\n'
    for m in modules:
        if m['id'] == 'pdm-related':
            continue
        total = len(m['apis'])
        oa_count = sum(1 for a in m['apis'] if a['oa'])
        bc = oa_badge_class(oa_count, total)
        bt = oa_badge_text(oa_count, total)
        html += f'''  <div class="module-card" onclick="location.href='#{m["id"]}'">
    <div class="title">{m["icon"]} {m["name"]}</div>
    <div class="path">{m["route"]}</div>
    <div class="count">{total} 個 API 端點</div>
    <div class="status"><span class="impl-badge {bc}">{bt}</span></div>
  </div>\n'''
    html += '</div>\n'
    return html

def gen_api_table(module, show_priority=False):
    html = '<table class="api-table">\n'
    html += '  <tr><th>方法</th><th>端點</th><th>功能</th><th>說明</th><th>OA 實作</th></tr>\n'
    for api in module['apis']:
        oa_class = 'oa-yes' if api['oa'] else 'oa-no'
        oa_text = '✅ 已實作' if api['oa'] else '❌ 未實作'
        desc = api['description'] if api['description'] else '—'
        html += f'''  <tr>
    <td><span class="method {api["method"]}">{api["method"]}</span></td>
    <td><span class="endpoint">{api["endpoint"]}</span></td>
    <td>{api["function"]}</td>
    <td>{desc}</td>
    <td class="{oa_class}">{oa_text}</td>
  </tr>\n'''
    html += '</table>\n'
    return html

def gen_section(module):
    total = len(module['apis'])
    oa_count = sum(1 for a in module['apis'] if a['oa'])
    bc = oa_badge_class(oa_count, total)
    bt = oa_badge_text(oa_count, total)

    meta_parts = []
    if module['route']:
        meta_parts.append(f'<strong>前端路由：</strong> <code>{module["route"]}</code>')
    if module['api_file']:
        meta_parts.append(f'<strong>API 檔案：</strong> <code>{module["api_file"]}</code>')

    meta_line = ' &nbsp; '.join(meta_parts)

    html = f'''
  <div id="{module["id"]}" class="section">
    <div class="section-header">
      <span class="icon">{module["icon"]}</span>
      <h2>{module["name"]} ({module["name_en"]})</h2>
      <span class="impl-badge {bc}">{bt}</span>
    </div>
'''
    if meta_line:
        html += f'    <p>{meta_line}</p>\n'

    html += gen_api_table(module)
    html += EXTRAS.get(module['id'], '')
    html += '  </div>\n'
    return html

def gen_summary_table(modules):
    html = '<table class="api-table">\n'
    html += '  <tr><th>模組</th><th>前綴路由</th><th>API 數</th><th>OA 實作</th><th>優先級</th></tr>\n'

    priority_map = {
        'P1': ('<span class="tag orange">P1 最高</span>', 'orange'),
        'P2': ('<span class="tag blue">P2 高</span>', 'blue'),
        'P3': ('<span class="tag green">P3 中</span>', 'green'),
    }

    for m in modules:
        if m['id'] == 'pdm-related':
            continue
        total = len(m['apis'])
        oa_count = sum(1 for a in m['apis'] if a['oa'])
        oa_class = 'oa-yes' if oa_count == total else 'oa-no'
        priority_key = m['priority'].split()[0] if m['priority'] else 'P3'
        ptag = priority_map.get(priority_key, ('<span class="tag green">—</span>', 'green'))[0]
        # 前綴路由（從第一個 API 端點推斷）
        prefix = ''
        if m['apis']:
            ep = m['apis'][0]['endpoint']
            parts = ep.split('/')
            if len(parts) >= 3:
                prefix = '/' + '/'.join(parts[1:3])

        html += f'''  <tr>
    <td>{m["icon"]} {m["name"]}</td>
    <td><code>{prefix}</code></td>
    <td>{total}</td>
    <td class="{oa_class}">{oa_count} / {total}</td>
    <td>{ptag}</td>
  </tr>\n'''

    html += '</table>\n'
    return html

# ── 靜態 HTML 區塊 ────────────────────────────────────────────────────────────

FLOW_SECTION = """
  <div id="flow-overview" class="section">
    <div class="section-header">
      <span class="icon">🔀</span>
      <h2>業務流程圖</h2>
    </div>
    <h3>庫存異動主流程</h3>
    <div class="flow">
      <div class="flow-box start">食材需求預測<br><small>(PDM)</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">物流管理日曆<br><small>(gatherReq)</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box decision">觸發入庫<br><small>create-stock-in</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">入庫作業<br><small>/whs/stock-record-head</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">倉庫庫存<br><small>/whs/stock</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box end">倉儲查詢<br><small>/whs/stock/currentPage</small></div>
    </div>
    <h3>調撥作業流程</h3>
    <div class="flow">
      <div class="flow-box start">申請調撥<br><small>新增調撥單</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">計算庫存<br><small>compute-area-inventory</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">提交簽核<br><small>batch-process</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box decision">流程審核<br><small>todo-page</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">出庫記錄<br><small>stockType=0</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box end">入庫記錄<br><small>stockType=1</small></div>
    </div>
    <h3>盤點作業流程</h3>
    <div class="flow">
      <div class="flow-box start">制定盤點計劃<br><small>/whs/check-plan</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">執行盤點任務<br><small>/whs/check-plan-detail</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">盤點品項<br><small>check-plan-item</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box decision">帳面 vs 實際<br><small>差異計算</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">庫存調整<br><small>入/出庫</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box end">庫存更新<br><small>stock record</small></div>
    </div>
    <h3>簽核流程（所有異動單據）</h3>
    <div class="flow">
      <div class="flow-box start">建立單據<br><small>processStatus: draft</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">暫存<br><small>batch-process</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">提交<br><small>processStatus: pending</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box decision">審核<br><small>todo-page</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box end">核准/退回<br><small>update-process-status</small></div>
    </div>
    <div class="alert info">
      <strong>💡 流程說明：</strong> 所有異動類單據均支援簽核流程。前端透過 <code>isTodo</code> 參數自動切換 <code>/page</code>（無簽核）或 <code>/todo-page</code>（簽核待辦）模式。
    </div>
  </div>
"""

MODEL_SECTION = """
  <div id="model-overview" class="section">
    <div class="section-header">
      <span class="icon">🗄️</span>
      <h2>資料模型關聯圖</h2>
    </div>
    <div class="alert info">資料表命名規則：<code>whs_</code> 前綴，全部使用 snake_case</div>
    <h3>核心資料表關係</h3>
    <pre>
whs_warehouse (倉庫主檔)
  ├── id, category, warehouse_type, warehouse, zone, bin_code, area
  ├──◀ whs_stock (當前庫存)
  │     └── warehouse_id, prod_code, standard_amount, standard_quantity, safe_stock
  ├──◀ whs_stock_record (庫存異動記錄)
  │     └── warehouse_id, prod_code, inv_num_change, stock_type, stock_reason
  └──◀ whs_stock_safe_detail (安全存量明細)

whs_stock_record_head (庫存異動表頭)
  ├── form_code, stock_type(0=出/1=入), stock_reason, process_status
  └──▶ whs_stock_record[]

whs_stock_transfer (調撥單主表)
  └──▶ whs_stock_transfer_detail[]

whs_bad_product (不良品主表)
  └──▶ whs_bad_product_detail[]

whs_daily_inventory (每日盤點主表)
  └──▶ whs_daily_inventory_detail[]

whs_check_plan (盤點計劃主表)
  └──▶ whs_check_plan_detail[]
        └──▶ whs_check_plan_item[]
              └── prod_code, account_quantity, check_quantity, audit_quantity</pre>
    <h3>主要 Model 欄位</h3>
    <div class="model-grid">
      <div class="model-box">
        <div class="model-title">whs_warehouse（倉庫主檔）</div>
        <table><tr><th>欄位</th><th>類型</th><th>說明</th></tr>
          <tr><td class="field-key">id</td><td class="field-type">bigint PK</td><td class="field-desc">自增主鍵</td></tr>
          <tr><td>category</td><td class="field-type">varchar</td><td class="field-desc">類別代碼</td></tr>
          <tr><td>warehouse_type</td><td class="field-type">varchar</td><td class="field-desc">倉別代碼</td></tr>
          <tr><td>warehouse</td><td class="field-type">varchar</td><td class="field-desc">倉名代碼</td></tr>
          <tr><td>zone</td><td class="field-type">varchar</td><td class="field-desc">儲區代碼</td></tr>
          <tr><td>bin_code</td><td class="field-type">varchar</td><td class="field-desc">儲位代碼</td></tr>
          <tr><td>area</td><td class="field-type">int</td><td class="field-desc">區域ID</td></tr>
        </table>
      </div>
      <div class="model-box">
        <div class="model-title">whs_stock（當前庫存）</div>
        <table><tr><th>欄位</th><th>類型</th><th>說明</th></tr>
          <tr><td class="field-key">id</td><td class="field-type">bigint PK</td><td class="field-desc">自增主鍵</td></tr>
          <tr><td class="field-key">warehouse_id</td><td class="field-type">bigint FK</td><td class="field-desc">→ whs_warehouse</td></tr>
          <tr><td>prod_code</td><td class="field-type">varchar</td><td class="field-desc">品號</td></tr>
          <tr><td>standard_amount</td><td class="field-type">decimal</td><td class="field-desc">庫存計量</td></tr>
          <tr><td>standard_quantity</td><td class="field-type">decimal</td><td class="field-desc">庫存計數</td></tr>
          <tr><td>safe_stock</td><td class="field-type">decimal</td><td class="field-desc">安全存量</td></tr>
        </table>
      </div>
      <div class="model-box">
        <div class="model-title">whs_stock_record_head（異動表頭）</div>
        <table><tr><th>欄位</th><th>類型</th><th>說明</th></tr>
          <tr><td class="field-key">id</td><td class="field-type">bigint PK</td><td class="field-desc">自增主鍵</td></tr>
          <tr><td>form_code</td><td class="field-type">varchar</td><td class="field-desc">單據編號</td></tr>
          <tr><td>stock_type</td><td class="field-type">tinyint</td><td class="field-desc">0=出庫, 1=入庫</td></tr>
          <tr><td>stock_reason</td><td class="field-type">varchar</td><td class="field-desc">異動事由</td></tr>
          <tr><td class="field-key">warehouse_id</td><td class="field-type">bigint FK</td><td class="field-desc">→ whs_warehouse</td></tr>
          <tr><td>process_status</td><td class="field-type">varchar</td><td class="field-desc">流程狀態</td></tr>
          <tr><td>inbound_time</td><td class="field-type">bigint</td><td class="field-desc">入/出庫時間戳</td></tr>
        </table>
      </div>
      <div class="model-box">
        <div class="model-title">whs_check_plan（盤點計劃）</div>
        <table><tr><th>欄位</th><th>類型</th><th>說明</th></tr>
          <tr><td class="field-key">id</td><td class="field-type">bigint PK</td><td class="field-desc">自增主鍵</td></tr>
          <tr><td>sign_code</td><td class="field-type">varchar</td><td class="field-desc">單據編號</td></tr>
          <tr><td>area</td><td class="field-type">int</td><td class="field-desc">區域ID</td></tr>
          <tr><td>plan_date_st</td><td class="field-type">datetime</td><td class="field-desc">計劃開始日</td></tr>
          <tr><td>plan_date_ed</td><td class="field-type">datetime</td><td class="field-desc">計劃結束日</td></tr>
          <tr><td>periodicity</td><td class="field-type">varchar</td><td class="field-desc">每月/每季/每年</td></tr>
          <tr><td>process_status</td><td class="field-type">varchar</td><td class="field-desc">流程狀態</td></tr>
        </table>
      </div>
    </div>
  </div>
"""

def gen_html(modules):
    total_apis = sum(len(m['apis']) for m in modules)
    total_oa = sum(sum(1 for a in m['apis'] if a['oa']) for m in modules)
    total_pending = total_apis - total_oa
    total_modules = sum(1 for m in modules if m['id'] != 'pdm-related')

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock 模組 API 文件 - Burger King ERP</title>
<style>
{CSS}
</style>
</head>
<body>

{gen_sidebar(modules)}

<div class="main">

  <div class="header">
    <h1>📦 Stock 模組 API 完整文件</h1>
    <p>基於前端 <code>/stock/</code> 目錄分析，整理所有 WHS (Warehouse) 相關 API 端點、資料模型與業務流程</p>
    <div class="stats">
      <div class="stat"><div class="num">{total_modules}</div><div class="label">功能模組</div></div>
      <div class="stat"><div class="num">{total_apis}</div><div class="label">API 端點</div></div>
      <div class="stat"><div class="num">{total_oa}</div><div class="label">OA 已實作</div></div>
      <div class="stat"><div class="num">{total_pending}</div><div class="label">待實作</div></div>
    </div>
  </div>

"""

    if total_oa == 0:
        html += """  <div class="alert danger">
    <strong>⚠️ 重要：</strong> 後端 (<code>/data/newprooa</code>) 目前 <strong>完全未實作</strong> 任何 <code>/whs/*</code> 端點。前端已完整定義所有 API 介面與資料型別，後端需從零開始建立 WHS 模組。
  </div>\n"""
    elif total_oa < total_apis:
        html += f"""  <div class="alert warning">
    <strong>⚠️ 實作進度：</strong> 共 {total_apis} 個 API 端點，已實作 {total_oa} 個，尚有 {total_pending} 個待實作。
  </div>\n"""
    else:
        html += """  <div class="alert success">
    <strong>✅ 全部完成：</strong> 所有 API 端點均已實作。
  </div>\n"""

    # 概覽 section
    html += """
  <div id="overview" class="section">
    <div class="section-header">
      <span class="icon">🗺️</span>
      <h2>系統架構總覽</h2>
    </div>
    <h3>模組清單</h3>
"""
    html += gen_overview_cards(modules)
    html += """
    <h3>前端檔案位置</h3>
    <table class="api-table">
      <tr><th>模組</th><th>API 檔案</th><th>View 檔案</th></tr>
      <tr><td>安全存量</td><td><code>src/api/stock/safetyStock/index.ts</code></td><td><code>src/views/stock/safetyStock/</code></td></tr>
      <tr><td>倉庫設定</td><td><code>src/api/stock/stockBasic/index.ts</code></td><td><code>src/views/stock/stockBasic/</code></td></tr>
      <tr><td>倉儲查詢</td><td><code>src/api/stock/stockQuery/index.ts</code></td><td><code>src/views/stock/storageQuery/</code></td></tr>
      <tr><td>入庫管理</td><td><code>src/api/stock/in/index.ts</code></td><td><code>src/views/stock/in/</code></td></tr>
      <tr><td>出庫管理</td><td><code>src/api/stock/out/index.ts</code></td><td><code>src/views/stock/out/</code></td></tr>
      <tr><td>調撥管理</td><td><code>src/api/stock/transfer/index.ts</code></td><td><code>src/views/stock/transfer/</code></td></tr>
      <tr><td>不良品</td><td><code>src/api/stock/badProduct/index.ts</code></td><td><code>src/views/stock/badProduct/</code></td></tr>
      <tr><td>每日盤點</td><td><code>src/api/stock/dayCheck/index.ts</code></td><td><code>src/views/stock/dayCheck/</code></td></tr>
      <tr><td>盤點計劃</td><td><code>src/api/stock/check/plan/index.ts</code></td><td><code>src/views/stock/check/plan/</code></td></tr>
      <tr><td>盤點執行</td><td><code>src/api/stock/check/execution/index.ts</code></td><td><code>src/views/stock/check/execution/</code></td></tr>
    </table>
  </div>
"""

    html += FLOW_SECTION
    html += MODEL_SECTION

    # 各模組 section
    for m in modules:
        html += gen_section(m)

    # 實作建議 section
    html += f"""
  <div id="impl-summary" class="section">
    <div class="section-header">
      <span class="icon">📊</span>
      <h2>實作狀態總覽與建議</h2>
    </div>
    <h3>全部 API 端點統計</h3>
{gen_summary_table(modules)}
    <h3>建議實作順序</h3>
    <div class="flow">
      <div class="flow-box start">Phase 1<br><small>倉庫基礎設定</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">Phase 2<br><small>入出庫作業</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box">Phase 3<br><small>調撥+安全存量</small></div>
      <div class="flow-arrow">→</div>
      <div class="flow-box end">Phase 4<br><small>盤點+不良品</small></div>
    </div>
    <h3>共用設計模式</h3>
    <div class="alert info">
      <strong>所有異動單據均遵循相同模式：</strong>
      <ul style="margin-top:8px;">
        <li><strong>List API：</strong> <code>GET /page</code>（無簽核）或 <code>GET /todo-page</code>（簽核待辦）</li>
        <li><strong>Detail API：</strong> <code>GET /get?id=X</code> 或 <code>GET /get-with-details?xId=X</code></li>
        <li><strong>Create/Submit：</strong> <code>POST /batch-process</code>（含表頭與明細）</li>
        <li><strong>Update：</strong> <code>PUT /edit-with-head</code>（含表頭與明細）</li>
        <li><strong>Status：</strong> <code>PUT /update-process-status</code>（簽核流程）</li>
        <li><strong>Delete：</strong> <code>DELETE /delete?id=X</code></li>
      </ul>
    </div>
    <h3>stockReason 代碼說明</h3>
    <table class="api-table">
      <tr><th>代碼</th><th>用途</th><th>來源模組</th></tr>
      <tr><td><code>SW01</code></td><td>一般入/出庫</td><td>入庫/出庫作業</td></tr>
      <tr><td><code>SW02</code></td><td>調撥</td><td>門市調撥管理</td></tr>
      <tr><td><code>SW03</code></td><td>盤點差異調整</td><td>盤點計劃執行</td></tr>
      <tr><td><em>其他</em></td><td>待確認</td><td>不良品管理、每日盤點</td></tr>
    </table>
  </div>

</div>

<script>
{JS}
</script>
</body>
</html>"""

    return html

# ── 主程式 ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    md_path = os.path.join(SCRIPT_DIR, 'stock-api-docs.md')
    out_path = os.path.join(SCRIPT_DIR, 'stock-api-docs.html')

    print(f'讀取 {md_path} ...')
    modules = parse_markdown(md_path)

    total_apis = sum(len(m['apis']) for m in modules)
    total_oa = sum(sum(1 for a in m['apis'] if a['oa']) for m in modules)
    print(f'解析完成：{len(modules)} 個模組，{total_apis} 個 API，{total_oa} 個已實作')

    html = gen_html(modules)

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'已生成 {out_path}')
