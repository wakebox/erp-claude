# PRD｜庫存管理 — 盤點作業管理

> 來源：逆向自 `kingmaker-module-whs` 後端程式碼（`controller/admin/checktake/CheckTakeController.java`、`service/checktake/`、`dal/dataobject/checktake/`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **倉儲人員 / 店長**。當某倉庫週期性盤點時，我建立「盤點單（CheckTake）」記錄實際盤點的結果：

> 「2026-05-25 信義店冷凍倉盤點：牛肉餅 LB-04 系統庫存 10 公斤、實盤 9 公斤 → 盤虧 1 公斤；起司 PKG-CHEESE 系統 5 包 / 實盤 5 包 → 一致」
>
> 盤點單歸檔後，差異透過 #40/#41 出入庫機制調整 `whs_stock` 庫存值。

### 1.2 我要做什麼

- 建立 / 編輯盤點單（單頭 + 明細）
- 走簽核流程
- **盤盈 → 入庫**（呼叫 #40，stockType=1）
- **盤虧 → 出庫**（呼叫 #41，stockType=0）
- 信號編號前綴 `CE` → 由 batchProcessStockRecords 觸發回寫
- 分頁查詢、待簽分頁、Excel 匯出
- 兩個輔助端點：
  - `/get-by-opposite-stock-type` — 出入庫互查
  - `/get-stock-record-batch-by-sign-code` — 依 signCode 反查 StockRecord 批次

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 對倉庫的實際存量做正式記錄 | 系統庫存 vs 實盤差異需可追溯 |
| 盤盈 / 盤虧自動調整庫存 | 不要再手動建出入庫單 |
| 簽核 | 庫存差異需審核（涉及損益） |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 盤點單 CRUD | 建單據 |
| signCode 前綴 CE 與 #40/#41 串接 | 自動調整庫存 |
| BPM 簽核流程 | 內控 |
| 出入庫互查、StockRecord 批次反查 | 跨單據查詢 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 盤點作業管理 |
| 所屬模組 | WHS（庫存管理） |
| 兄弟功能 | 盤點計劃製定 (#44)、盤點計劃執行 (#45)、每日盤點 (#46)、入出庫 (#40/#41) |
| 主要頁面 | 盤點單編輯頁、單頭分頁、Excel 匯出 |
| 簽核流程 | 有（推測），但程式碼中 `CheckTakeController` 無 `/todo-page` 端點，看似還沒做完 |
| 與 #40/#41 串接 | signCode 前綴 `CE`，由 batchProcessStockRecords 觸發 updateCheckTakeStatus 回寫 |
| 程式碼 Tag | 「盘点单_计划执行_单头」— 表示本功能是「計劃的執行端」 |

---

## 2. 功能目的

盤點作業是「**庫存差異記錄 + 調整入口**」：

1. **承接 #44/#45** — 計劃製定後執行盤點
2. **差異調整** — 盤盈 / 盤虧透過 #40/#41 寫回 `whs_stock`
3. **簽核** — 損益確認

---

## 3. 業務邏輯背景

### 3.1 兩張表

| 表 | 用途 |
|---|---|
| `whs_check_take`（單頭 / `CheckTakeDO`） | 單據編號、processStatus、區域、倉別、執行日期（takeTime） |
| `whs_check_take_detail`（明細 / `CheckTakeDetailDO`） | 品號、系統庫存、實盤數量、差異等 |

⚠️ **DO 上 `KeySequence` 名稱寫成 `whs_stock_take_id_seq`** 而非 `whs_check_take_id_seq` — 命名歷史殘留（見 §11）。

### 3.2 與 #45 計劃執行的關係

CheckPlanDetail（#45）負責「**規劃哪些品項要盤、由誰盤**」。CheckTake（#43）負責「**實際盤點當下的記錄**」。實務上 #43 的 signCode 通常從 #45 衍生。

### 3.3 signCode 前綴 `CE`

由 #40/#41 `batchProcessStockRecords` 的 `updateSourceDocumentStatus` 偵測 → 呼叫 `updateCheckTakeStatus(signCode, stockType)` 回寫 `whs_check_plan_detail` 的 stockType（注意是 #45 表，非 #43 表）。

> ⚠️ **跨表回寫**：CE 前綴回寫的是 `whs_check_plan_detail`，不是 `whs_check_take`（來源：#40 `updateCheckTakeStatus` line 245-259，撈 `CheckPlanDetailDO`）— 命名混亂（見 §11）。

### 3.4 跨模組依賴

- BPM：表單路徑（未明確列出）
- #40/#41：盤盈盤虧調整

---

## 4. 情境說明

### 4.1 正常流程

倉儲執行 #45 計劃 → 建立本功能盤點單 → 填實盤數量 → 提交簽核 → 歸檔 → 系統根據差異自動觸發 #40/#41 → `whs_stock` 同步調整。

### 4.2 規則分流 — 盤盈 / 盤虧

| 差異 | 動作 |
|---|---|
| 實盤 > 系統 | 盤盈 → 入庫（stockType=1） |
| 實盤 < 系統 | 盤虧 → 出庫（stockType=0） |
| 實盤 = 系統 | 無動作 |

---

## 5. 操作流程

```
[執行盤點]
  │
  ├─ POST /whs/check-take/create
  ├─ PUT /whs/check-take/update
  ├─ DELETE /whs/check-take/delete?id=
  ├─ GET /whs/check-take/get?id=（CheckTakeAndDetailVO）
  ├─ GET /whs/check-take/page、export-excel
  ├─ POST /whs/check-take/get-by-opposite-stock-type
  ├─ GET /whs/check-take/check-take-detail/list-by-check-take-id?checkTakeId=
  └─ GET /whs/check-take/get-stock-record-batch-by-sign-code?signCode=
       └─ 給 #40/#41 反查使用

[簽核歸檔]
  └─ 觸發 #40/#41 batchProcessStockRecords → updateCheckTakeStatus
```

---

## 6. 欄位規格

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| signCode | 單據編號（前綴 CE） |
| processStatus | 流程狀態 |
| area / areaName / warehouseType / warehouseTypeName | 倉位 |
| takeTime | 執行日期 |
| ... | （明細 DO 未深查） |

---

## 7. 商業邏輯

詳見 §3.3 跨表回寫。

---

## 8. 使用角色與權限

| 角色 | 對應權限字串 |
|---|---|
| 倉儲人員 | `whs:check-take:create/update/delete/query/export` |

---

## 9. 畫面需求

建議：列表 + 編輯頁，編輯頁顯示「系統庫存」與「實盤」並計算差異。

---

## 10. 功能範圍

- 包含：CRUD、跨模組串接
- 不包含：盤點計劃製定（#44）、計劃執行（#45）、每日盤點（#46）

---

## 11. 待確認事項

| 議題 | 證據 |
|---|---|
| `KeySequence` 命名與 TableName 不一致（whs_stock_take_id_seq vs whs_check_take） | DO 註解 |
| CE 前綴實際回寫到 `whs_check_plan_detail` 而非本表 | #40 `updateCheckTakeStatus` line 245-259 |
| 本 Controller 無 `/todo-page` — 是否表示尚未整合簽核分頁？ | Controller 缺端點 |
| CheckTake 與 CheckPlanDetail（#45）的對應關係未明確 | 跨表設計 |
| 明細 DO 未深查 — 含哪些欄位（實盤數量 / 差異） | 需後續釐清 |
