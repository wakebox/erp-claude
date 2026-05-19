# PRD｜物流管理 — 物流管理行事曆

> 來源：逆向自 `kingmaker-module-pdm` 後端程式碼（`controller/admin/rawmaterial1/RawMaterialDemandHeadController.java` 的 `/query-details-by-month` 與 `/query-details-by-ids` 端點、`service/rawmaterial1/RawMaterialDemandHeadOtherServiceImpl.java`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。
>
> ⚠️ Excel 將「物流管理」列為獨立模組，但**實作仍在 PDM `rawmaterial1`**（與 #25 / #30 共用 Controller）。本 PRD 聚焦於物流管理行事曆視角的「**月度檢視 + 多層分組**」。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **物流規劃人員 / 區經理 / 倉儲主管**。我需要從「日曆視角」掌握下個月每天每個門市的配送活動：

> 「2026-06 北一區行事曆：6/1（一）週配 12 筆、月配 0 筆；6/2（二）週配 8 筆、月配 3 筆；…」

這份行事曆讓我安排車輛、排路線、預估物流負擔。

### 1.2 我要做什麼

- 指定區域 + 查詢月份（必）+ 可選門店 + 可選配送模式 → 取得「日期 → 配送模式 → 明細」三層分組結果
- 依 ID 列表反查明細（給前端展開用）

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 按月查看 | 物流排程通常以月為單位 |
| 多層分組 | 同一天可能有週配 + 月配兩種模式 |
| 預計配送日為分組 key | 不是需求日，而是物流實際配送日 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 月度多層分組查詢 | 主畫面 |
| 依 ID 列表反查 | 前端展開 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 物流管理行事曆 |
| 所屬模組 | Excel 列「物流管理」、實作在 PDM `rawmaterial1` |
| 兄弟功能 | 物流規劃查詢 (#49)、物流配送查詢 (#50)、原料物需求行事曆 (#30) |
| 主要頁面 | 行事曆視圖（日曆 + 列表混合） |
| 簽核流程 | 無（純查詢） |
| 資料來源 | `pdm_raw_material_demand_detail` 由 #25 建立 |

---

## 2. 功能目的

物流行事曆是「**物流規劃的月度視圖**」：

1. **聚合視圖** — 把分散的明細按日期 + 配送模式聚合
2. **跨模組查詢** — 資料來自 #25 #30 #26（PMM 採購無關）
3. **唯讀** — 不寫入

---

## 3. 業務邏輯背景

### 3.1 三層分組結構

`queryRawMaterialDemandDetailsByMonthGrouped`：

```
DateGroups（按日期）
  └─ DeliveryModeGroups（按配送模式：週配 / 月配 / 直送）
       └─ details: List<RawMaterialDemandDetailQueryRespVO>
```

實作（`RawMaterialDemandHeadOtherServiceImpl.java:100-143`）：

```
1. 撈所有明細（按 expectDeliveryDate 排序）
2. 逐筆判斷 date / mode 是否變化
3. 變化時建立新分組
4. 加入明細
```

⚠️ **這個邏輯依賴 SQL 回傳順序**（需 `ORDER BY expectDeliveryDate, deliveryMode`）— xml 未確認。若順序不對，分組會失敗（見 §11）。

### 3.2 必填參數

- regionId 必填 → 否則拋 `RAW_MATERIAL_REGION_EMPTY`
- queryMonth 格式 `yyyy-MM` 必填 → 解析失敗拋 `RAW_MATERIAL_DATE_EMPTY`

### 3.3 過濾參數

- storeId（可選）：限該門市
- deliveryMode（可選）：限該配送模式

### 3.4 跨模組依賴

- `pdm_raw_material_demand_detail`：資料源（由 #25 寫入）

---

## 4. 情境說明

### 4.1 正常流程

物流規劃人員查 2026-06 北一區整月行事曆：

1. GET /pdm/raw-material-demand-head/query-details-by-month
   - regionId=3、queryMonth=2026-06、（storeId 不填、deliveryMode 不填）
2. 系統撈該月該區所有 detail，按日期 + 配送模式分組
3. 前端用日曆 widget 渲染

### 4.2 規則分流 — 過濾配送模式

只要看「月配」：

- 傳 deliveryMode=月
- 系統只回月配的記錄

### 4.3 異常情境 — queryMonth 格式錯誤

queryMonth=「2026/06」（用 `/` 而非 `-`）：

- `YearMonth.parse(...)` 拋例外
- service catch 後拋 `RAW_MATERIAL_DATE_EMPTY`（錯誤碼語意不對 — 不是「日期空」而是「日期格式錯」，見 §11）

---

## 5. 操作流程

```
[使用者進入「物流管理行事曆」]
  │
  ├─ 1. 月度分組查詢 GET /pdm/raw-material-demand-head/query-details-by-month
  │    參數：regionId（必）、queryMonth（必，yyyy-MM）、storeId、deliveryMode
  │    └─ 回 RawMaterialDemandDetailGroupedRespVO（三層分組）
  │
  └─ 2. 依 ID 反查 POST /pdm/raw-material-demand-head/query-details-by-ids
       body: List<Long> ids
       └─ 回 List<RawMaterialDemandDetailQueryRespVO>
```

---

## 6. 欄位規格

### 6.1 輸入

| 欄位 | 必填 |
|---|---|
| regionId | ✅ |
| queryMonth (yyyy-MM) | ✅ |
| storeId | 可選 |
| deliveryMode | 可選 |

### 6.2 回應結構

```
RawMaterialDemandDetailGroupedRespVO
  ├─ dateGroups: List<DateGroup>
       ├─ date
       └─ deliveryModeGroups: List<DeliveryModeGroup>
              ├─ deliveryMode
              └─ details: List<RawMaterialDemandDetailQueryRespVO>
```

---

## 7. 商業邏輯

依 SQL 回傳順序按 date / deliveryMode 分組。

---

## 8. 使用角色與權限

| 角色 | 對應權限字串 |
|---|---|
| 物流規劃人員 / 區經理 | `pdm:raw-material-demand-head:query` |

---

## 9. 畫面需求

建議：日曆視圖（月）+ 點某天彈出該日配送清單

---

## 10. 功能範圍

包含：月度多層分組查詢、依 ID 反查

不包含：建單（#25）、規劃查詢（#49）、配送查詢（#50）、串接記錄（#52）

---

## 11. 待確認事項

| 議題 | 證據 |
|---|---|
| 分組邏輯依賴 SQL 排序 — 若 ORDER BY 缺失會壞 | service line 119、129 |
| queryMonth 格式錯誤拋 `RAW_MATERIAL_DATE_EMPTY` — 語意不準 | service line 95 |
| 無使用者區域 / 門店自動過濾 | service line 80-97 無 SecurityFrameworkUtils |
| 無分頁 — 月度大區域可能回大量資料 | service 無分頁 |
| `deliveryMode` 字面值未字典化 | 跨模組 |
| 程式碼歸 PDM 但業務名「物流管理」 | 模組界線 |
