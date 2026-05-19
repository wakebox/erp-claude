# PRD｜物流管理 — 物流異動查詢作業

> 來源：逆向自 `kingmaker-module-pdm` 後端程式碼（`controller/admin/rawmateriallogistics/RawMaterialLogisticsController.java`、`service/rawmateriallogistics/RawMaterialLogisticsServiceImpl.java`、`dal/dataobject/rawmateriallogistics/`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。
>
> ⚠️ Excel 將「物流異動查詢」與「物流串接記錄」(#52) 列為兩個獨立功能，但**後端共用一套 CRUD**（`pdm_raw_material_logistics` 主表 + `_dtl` 子表）。本 PRD 聚焦於「**從明細視角查詢實際到店情況與物流異動**」。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **物流規劃人員 / 採購助理 / 倉儲主管**。配送車送到門市後，我需要追蹤每筆品號的**「實際到店數量」與「需求量」是否一致** — 異動指的是「**配送過程中的數量變化**」：

> 「PR-20260519100423 配送單明細：牛肉餅 LB-04 需求 50 公斤、實際到店 48 公斤；差 2 公斤需查原因（破損 / 短發 / 偷換）」

### 1.2 我要做什麼

- 取得物流單明細列表（依 parentId 查 dtl，含關聯資訊：品號名、廠商名等）
- 分頁查詢物流單頭
- 取得單筆物流單
- 編輯 / 刪除物流單（含明細）
- Excel 匯出

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 看「實際到店數量」 | 對應採購 / 預測量差異 |
| 追溯到需求預測 / 臨時需求 | 知道這筆配送源自哪張單 |
| 區域 / 門市過濾 | 多區域並行配送 |
| 異動原因記錄 | 短發 / 破損的後續處理 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 物流單 CRUD（單頭 + 明細） | 異動記錄 |
| 帶關聯資訊的明細查詢 | 一次拿到品號 / 廠商 / 門市完整資訊 |
| 分頁 / Excel 匯出 | 報表 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 物流異動查詢作業 |
| 所屬模組 | Excel 列「物流管理」、實作在 PDM `rawmateriallogistics` |
| 兄弟功能 | 物流行事曆 (#48)、規劃查詢 (#49)、配送查詢 (#50)、串接記錄 (#52) |
| 主要頁面 | 物流單列表頁、明細展開頁、Excel 匯出 |
| 簽核流程 | 無（純查詢） |
| 與 #50 關係 | #50 `/generateCsv` 寫入本表的資料；本功能負責檢視 |

---

## 2. 功能目的

物流異動查詢是「**配送後資料的檢視與調整入口**」：

1. **承接 #50 串接** — #50 寫入物流單，本功能讀取
2. **檢視異動** — 對照需求 vs 實際到店
3. **修正資料** — 若實際到店數量錯誤可編輯

---

## 3. 業務邏輯背景

### 3.1 兩張表

| 表 | 用途 |
|---|---|
| `pdm_raw_material_logistics`（單頭 / `RawMaterialLogisticsDO`） | 單據編號、配送模式、配送廠商代號、出貨日 |
| `pdm_raw_material_logistics_dtl`（明細 / `RawMaterialLogisticsDtlDO`） | parentId、配送模式、品號、漢堡王原料 ID、廠商代號、實際到店數量、訂單類別、門店編碼、門市 ID、區域 ID、需求 / 臨時單號、出貨日 |

### 3.2 與 #50 的關係

- #50 `/generateCsv` 每日跑：撈 MSS 配送 → CSV → SFTP → 寫入這兩張表
- 本功能 (#51) 負責「**事後檢視**」
- 共用 Controller，差別只是 UI 的查詢 / 操作目的

### 3.3 編輯刪舊插新

`updateRawMaterialLogistics`：刪除所有 dtl 再重新插入（同前述功能策略）

### 3.4 「異動」的真實意義不明

`RawMaterialLogisticsDtlDO` 上只有 `actualArrivalAmount`（實際到店數量），**沒有單獨欄位記錄「需求量」「異動原因」「短缺量」**。

⚠️ 推測「異動」是透過比對：
- 本表的 `actualArrivalAmount`
- vs `pdm_raw_material_demand_detail` 的 `demandAmount`
- 兩者差異 = 異動量

但程式碼中無此比對 SQL — 業務上的「異動原因」如何記錄需確認（見 §11）。

### 3.5 跨模組依賴

- 來源：#50 `/generateCsv` 寫入
- 對應：`pdm_raw_material_demand_detail`（#25 / #30）

---

## 4. 情境說明

### 4.1 正常流程 — 配送後檢視

物流規劃人員查詢昨日配送結果：

1. GET /pdm/raw-material-logistics/page
2. 看到 PR-20260518100423 等多筆單頭
3. 點某筆 → GET /raw-material-logistics-dtl/list-by-parent-id?parentId=
4. 看明細：牛肉餅實際到店 48 公斤

### 4.2 異常情境 — 異動記錄

若昨日有破損 / 短發：

- 編輯該明細 → PUT /update 修改 actualArrivalAmount
- 系統刪舊插新

⚠️ 修改後**沒有 audit trail** — 不記錄誰改、何時改的（除 BaseDO 的 updateTime 外無變更歷史）。

### 4.3 規則分流 — 匯出 Excel

匯出**只含單頭**，明細不在裡面（與 #34 類似但本功能 Excel 不為空）。

---

## 5. 操作流程

```
[使用者進入「物流異動查詢」]
  │
  ├─ 1. CRUD
  │    POST /create、PUT /update、DELETE /delete?id=、GET /get?id=
  │
  ├─ 2. 單頭分頁 GET /pdm/raw-material-logistics/page
  │
  ├─ 3. 明細展開 GET /pdm/raw-material-logistics/raw-material-logistics-dtl/list-by-parent-id?parentId=
  │    └─ 帶關聯資訊（品號名、廠商名等）
  │
  └─ 4. 匯出 Excel GET /export-excel
```

---

## 6. 欄位規格

### 6.1 單頭

| 欄位 | 中文業務語 |
|---|---|
| signCode | 單據編號（前綴 PR） |
| deliveryMode | 配送模式（delivery） |
| deliveryMfrId | 配送廠商代號（如 MSS） |
| shippingDate | 出貨日 |

### 6.2 明細

| 欄位 | 中文業務語 |
|---|---|
| prodCode | 品號 |
| materialProductId | 漢堡王原料 ID（中繼系統用） |
| mfrId | 廠商代號 |
| actualArrivalAmount | 實際到店數量 |
| materialType | 訂單類別（R） |
| storeCode / storeId | 門店 / 門市 |
| regionId | 區域 |
| demandRelationDoc / tempRelationDoc | 來源單號 |
| shippingDate | 出貨日 |

---

## 7. 商業邏輯

CRUD + 編輯刪舊插新

---

## 8. 使用角色與權限

| 角色 | 對應權限字串 |
|---|---|
| 物流規劃 / 倉儲主管 | `pdm:raw-material-logistics:create/update/delete/query/export` |

---

## 9. 畫面需求

建議：列表 + drill-down + 對應原始需求量的對比視圖

---

## 10. 功能範圍

包含：物流單 CRUD、明細含關聯查詢、Excel 匯出

不包含：CSV 產生（#50）、串接記錄（#52，邏輯重疊）、實際入庫（WHS #40）

---

## 11. 待確認事項

| 議題 | 證據 |
|---|---|
| 「異動」原因 / 短缺欄位未明確 — DO 上沒有 | DO 欄位 |
| 與需求量的差異對比邏輯未實作 | 無對應 SQL |
| 編輯無 audit trail | service line 50-61 |
| 與 #52 串接記錄 Excel 上分開為兩功能，但程式碼共用 | Controller 設計 |
| 編輯刪舊插新導致明細 id 變動 | service line 109-113 |
| 「實際到店數量」實務上是否來自門市回報？目前 #50 是用 `demandAmount` 作預設值 | #50 line 222 |
| 物流單頭很簡單（只有 signCode、deliveryMode、deliveryMfrId、shippingDate） — 缺整體狀態欄位（如「待配送 / 配送中 / 已完成」） | DO 欄位 |
| 無 BPM 流程整合 | service |
| 無使用者區域過濾 | service |
