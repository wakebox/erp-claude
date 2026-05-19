# PRD｜物流管理 — 物流規劃查詢作業

> 來源：逆向自 `kingmaker-module-pdm` 後端程式碼（`controller/admin/rawmaterial1/RawMaterialDemandHeadController.java` 的 `/query-group-by-delivery-date` 端點、`service/rawmaterial1/RawMaterialDemandHeadOtherServiceImpl.queryGroupByDeliveryDate`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **物流規劃人員 / 採購助理**。我需要從「預計配送日」視角規劃車輛與路線：

> 「下週要送的料件以日為單位彙整，每天會出幾次車、多少品項、需求量總和」

### 1.2 我要做什麼

- 指定區域（必）+ 可選門店 + 可選日期區間 → 取得依「預計配送日」分組的清單
- 每筆回傳該日所有相關的「需求預測單號 + 臨時需求單號 + 預估銷售量」

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 按預計配送日分組 | 排車要看「哪天要出車」 |
| 區域 / 門店過濾 | 不同物流路線分開 |
| 看每天的源頭單號 | 知道是來自需求預測還是臨時需求 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 按預計配送日分組查詢 | 主畫面 |
| 多選過濾 | 路線規劃 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 物流規劃查詢作業 |
| 所屬模組 | Excel 列「物流管理」、實作在 PDM `rawmaterial1` |
| 兄弟功能 | 物流行事曆 (#48)、物流配送查詢 (#50) |
| 主要頁面 | 規劃查詢頁（按配送日分組） |
| 簽核流程 | 無（純查詢） |

---

## 2. 功能目的

物流規劃查詢與 #48 行事曆的差別：

- **#48 行事曆**：月度多層分組（日期 → 配送模式 → 明細）
- **#49 規劃查詢**：依配送日分組（單層，每組對應一筆 RawMaterialDemandDateListVO）

兩個功能服務不同視角；#49 更聚焦於「**每天的源頭單號彙整**」。

---

## 3. 業務邏輯背景

### 3.1 服務邏輯

`queryGroupByDeliveryDate` 非常簡單：

```java
return rawMaterialDemandDetailMapper.selectGroupByDeliveryDate(
    regionId, storeId, startDate, endDate);
```

純 SQL group by；service 端無業務邏輯（line 153-156）。

### 3.2 過濾條件

- regionId 必填
- storeId / startDate / endDate 可選

### 3.3 與 #48 的取捨

兩者都用 `pdm_raw_material_demand_detail`，但聚合粒度不同：

| 對比 | #48 | #49 |
|---|---|---|
| 必填區間 | 月（yyyy-MM） | 起訖日期（可不填） |
| 分組層數 | 三層（日期 → 模式 → 明細） | 一層（按 expect_delivery_date） |
| 回應結構 | `RawMaterialDemandDetailGroupedRespVO` | `List<RawMaterialDemandDateListVO>` |

---

## 4. 情境說明

### 4.1 正常流程

物流規劃人員查 5/25–5/31 北一區的配送日分組：

1. GET /pdm/raw-material-demand-head/query-group-by-delivery-date
   - regionId=3、storeId 不填、startDate=2026-05-25、endDate=2026-05-31
2. 系統 SQL group by expect_delivery_date
3. 回傳 List<RawMaterialDemandDateListVO>，每天一筆

---

## 5. 操作流程

```
[使用者進入「物流規劃查詢」]
  │
  └─ GET /pdm/raw-material-demand-head/query-group-by-delivery-date
     參數：regionId（必）、storeId、startDate (yyyy-MM-dd)、endDate
     └─ 回 List<RawMaterialDemandDateListVO>
```

---

## 6. 欄位規格

### 6.1 輸入

| 欄位 | 必填 |
|---|---|
| regionId | ✅ |
| storeId | 可選 |
| startDate / endDate (yyyy-MM-dd) | 可選 |

### 6.2 回應（`RawMaterialDemandDateListVO`）

同 #30 §6.2 — 含需求日、門市、預測單號、臨時需求單號、預估銷售量、預計配送日。

---

## 7. 商業邏輯

純 SQL group by，無 service 邏輯。

---

## 8. 使用角色與權限

| 角色 | 對應權限字串 |
|---|---|
| 物流規劃人員 | `pdm:raw-material-demand-head:query` |

---

## 9. 畫面需求

建議：列表 + 日期區間選擇器 + 區域 / 門店 cascade 下拉

---

## 10. 功能範圍

包含：依配送日的分組查詢

不包含：月度行事曆（#48）、配送明細（#50）、實際配送追蹤（#51）、串接記錄（#52）

---

## 11. 待確認事項

| 議題 | 證據 |
|---|---|
| service 層 0 邏輯 — 完全依賴 SQL | line 153-156 |
| 無使用者區域 / 門店自動過濾 | service 同上 |
| 無分頁 — 大區域大區間可能回大量資料 | service |
| `RawMaterialDemandDateListVO` 結構與 #30 共用 — 設計重用是否最佳？ | VO 跨模組共用 |
| 與 #48 行事曆功能重疊大 — 是否該合併？ | 設計 |
