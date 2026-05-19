# PRD｜庫存管理 — 每日盤點作業

> 來源：逆向自 `kingmaker-module-whs` 後端程式碼（`controller/admin/dailyinventory/DailyInventoryController.java`、`service/dailyinventory/`、`dal/dataobject/dailyinventory/`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **店長 / 倉儲員**。每天營業結束後，我需要對門市冰箱 / 冷凍倉做「快速盤點」 — 不是月度 / 季度的正式大盤，而是「**每日固定品項的快速核對**」：

> 「2026-05-19 信義店打烊後：牛肉餅剩 8 公斤、起司剩 30 包、生菜剩 5 包、麵包剩 25 個」
>
> 比月度盤點頻繁、簡化、結合每日銷量試算「應有庫存」。

### 1.2 我要做什麼

- 建立 / 編輯每日盤點單（單頭 + 明細）
- 走簽核流程
- 從中繼拉「每日商品銷量 + 食材」資訊（`getDailyProductSalesWithIngredients`）
- 取食材下拉清單（`getIngredientOptions`，依區域 / 倉庫 / 品號 / 食材名稱過濾）
- 分頁查詢、待簽分頁、Excel 匯出

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 快速盤點 | 月度大盤太累 |
| 結合每日銷量試算 | 「昨天賣了 50 個華堡，應該用掉 5 公斤牛肉餅，今天該還有多少？」 |
| 食材下拉自動帶倉庫 | 不要每次手動選 |
| 走簽核 | 差異需審核 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 每日盤點單 CRUD | 主要建單 |
| 中繼銷量試算 API | 給編輯頁參考 |
| 食材下拉 API | 編輯頁選食材 |
| BPM 簽核 | 內控 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 每日盤點作業 |
| 所屬模組 | WHS（庫存管理） |
| 兄弟功能 | 月度盤點作業 (#43)、計劃製定 (#44)、計劃執行 (#45) |
| 主要頁面 | 每日盤點編輯頁（含每日銷量試算）、單頭分頁、待簽分頁 |
| 簽核流程 | 有：`/todo-page` 存在 |
| 中繼依賴 | `getDailyProductSales` 從中繼拉每日銷量 |

---

## 2. 功能目的

每日盤點是「**高頻、輕量的盤點機制**」：

1. **每日執行** — 與月度盤點互補
2. **結合銷量試算** — 從中繼拉每日商品銷量、展開食材
3. **快速差異發現** — 隔天就能發現問題（食材消耗異常、被偷、損壞）

---

## 3. 業務邏輯背景

### 3.1 兩張表

| 表 | 用途 |
|---|---|
| `whs_daily_inventory`（單頭 / `DailyInventoryDO`） | 單據編號、processStatus、區域、倉庫、盤點日期等 |
| `whs_daily_inventory_detail`（明細 / `DailyInventoryDetailDO`） | 品號、實盤數量、（推測還有理論用量 / 差異等） |

### 3.2 中繼銷量試算

`/daily-product-sales`：

- 輸入：groupAreaId、storeId（可選）、date
- 內部呼叫中繼 API（推測為 `getDailyProductSales`）
- 對每產品撈食材
- 計算每食材的理論用量

實際邏輯未深查。

### 3.3 食材下拉

`/ingredient-options`：

- 輸入：area（必）、warehouse（必）、prodCode / ingredientName（過濾）
- 撈該倉庫的食材清單

### 3.4 與 #43–#45 的差異

| 比較 | #43–#45（月 / 季盤點） | #46（每日盤點） |
|---|---|---|
| 頻率 | 月 / 季 | 每日 |
| 範圍 | 全倉或大範圍 | 重點品項 |
| 計劃 | 需 #44 規劃 | 直接每日做 |
| 與庫存 | 簽核後調整 | 推測也會調整（未明確） |

### 3.5 跨模組依賴

- 中繼 API（每日銷量）
- PDM 食譜（食材展開）
- BPM 簽核

---

## 4. 情境說明

### 4.1 正常流程 — 店長下班前盤點

店長小李 22:00 關店後：

1. 進入每日盤點編輯頁
2. 選區域 + 門店 + 日期
3. 點「載入今日銷量」→ `/daily-product-sales` → 顯示每食材的「理論消耗量」
4. 走進冷凍倉實盤 → 填「實盤數量」
5. 系統顯示差異
6. 提交簽核 → 店長下班

### 4.2 異常情境 — 差異過大

若實盤 vs（昨日庫存 - 今日理論消耗）差距大：

- 系統應警示（推測，未實作）
- 簽核者可決定接受 / 退回重盤

---

## 5. 操作流程

```
[店長 / 倉儲員進入「每日盤點作業」]
  │
  ├─ 1. 載入今日銷量試算
  │    GET /whs/daily-inventory/daily-product-sales?groupAreaId=&storeId=&date=
  │
  ├─ 2. 食材下拉
  │    GET /whs/daily-inventory/ingredient-options?area=&warehouse=&prodCode=&ingredientName=
  │
  ├─ 3. CRUD
  │    POST /create、PUT /update、DELETE /delete?id=、GET /get?id=
  │
  ├─ 4. 分頁 / 待簽 / 匯出
  │    GET /page、/todo-page、/export-excel
  │
  └─ 5. 明細查詢
       GET /daily-inventory-detail/list-by-daily-inventory-id?dailyInventoryId=
```

---

## 6. 欄位規格

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| signCode | 單據編號 |
| processStatus | 流程狀態 |
| 其他 | 區域 / 倉庫 / 盤點日期 / 明細欄位（DO 未深查） |

---

## 7. 商業邏輯

CRUD + BPM + 中繼銷量整合

---

## 8. 使用角色與權限

| 角色 | 對應權限字串 |
|---|---|
| 店長 / 倉儲員 | `whs:daily-inventory:create/update/delete/query/export` |

---

## 9. 畫面需求

建議：每日盤點專用 UI，含試算載入按鈕與快速輸入

---

## 10. 功能範圍

包含：每日盤點 CRUD、中繼銷量試算、食材下拉、BPM

不包含：月度 / 季度盤點（#43–#45）、入出庫（#40/#41）、庫存查詢（#38）

---

## 11. 待確認事項

| 議題 | 證據 |
|---|---|
| 是否會自動調整 `whs_stock`？ | 程式未明確 |
| 「差異閾值警示」未實作 | 業務需求 |
| `storeId` 為 String（與其他模組 Integer 不一致） | Controller line 121 |
| 與 #43–#45 三層的差異 / 統一 | 設計層面 |
| 「每日盤點」是否該強制每店每日一筆？目前無唯一性檢查 | 設計 |
| 食材下拉的權限過濾（店長只能看自己店）— 未在 controller 看到自動套用 | service 邏輯需確認 |
| 與 PMM 銷量資料的對應 | 跨模組 |
| DailyInventoryDetailRespVO 內容未深查 | DO |
