# PRD｜PDM — 編碼原則維護

> 來源：逆向自 `kingmaker-module-pdm` 之編碼結構（code-structure）相關後端程式碼（含 `controller/admin/codestructure/CodeStructureController.java`、`controller/admin/codestructure/CodeStructureDetailController.java`、`service/codestructure/CodeStructureServiceImpl.java`、`service/codestructure/CodeStructureDetailServiceImpl.java`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

> **本 PRD 範圍**：本程式內部命名為「編碼結構」（code-structure），業務語意上對應「編碼原則」。本 PRD 以「編碼原則」為主稱呼。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王 PDM 的**編碼體系維護人員**。
我已經建好了「編碼類別」（食材大類、食材中類、食材小類…），又在底下填了「編碼項目」（肉類、蔬果類…）。現在我要規劃**編碼怎麼拼接**：例如「食材編號」是不是該由「食材大類 2 碼 + 食材中類 4 碼 + 食材小類 6 碼 + 流水」組合而成。本功能負責定義這些「拼接原則」。

### 1.2 我要做什麼

- **新增編碼原則**：定義一個原則（例如「食材編碼原則」）、它的階層、它由哪些編碼類別依序拼接組成。
- **修改編碼原則**：調整名稱、階層、組成。
- **新增／修改／刪除原則明細**：每筆明細是「序號 + 哪個編碼類別代碼」的組合，表示拼接的順序。
- **批量刪除原則**：清理過時原則（連同其明細子表）。
- **查詢**：依名稱、階層、建立人員、時間區間篩選。

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 一個編碼原則可以包含多個編碼類別 | 編號是由多個元素組成 |
| 明細要有「序號」決定排列順序 | 「食材大類 + 食材中類」 vs「食材中類 + 食材大類」是不同編號 |
| 一個原則對應一個「階層」深度 | 業務概念區分（食材有多階層、單品可能較少） |
| 刪除原則時連動刪除明細 | 避免孤兒明細 |
| 對應業務模組（如食材維護作業）能呼叫此原則決定組編號 | 自動編號 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 新增編碼原則（主檔） | 建立新原則 |
| 修改編碼原則 | 調整定義 |
| 批量刪除編碼原則（連動刪明細） | 清理 |
| 條件分頁查詢 | 維運盤點 |
| 取得單一編碼原則 | 編輯前回填 |
| 取得單一原則之明細清單／分頁 | 編輯子表 |
| 明細的新增、修改、刪除 | 管理拼接順序 |
| 匯出 Excel | 盤點佐證 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 編碼原則維護 |
| 所屬模組 | PDM |
| 兄弟功能 | 編碼類別維護、編碼項目維護、食材維護作業、單品維護作業、包材維護作業 |
| 主要頁面 | 編碼原則列表頁、編碼原則新增／編輯彈窗、原則明細管理彈窗 |
| 簽核流程 | 無 |

---

## 2. 功能目的

提供漢堡王 PDM 編碼體系的**第三層拼接規則**定義。每筆「編碼原則」描述「某種編號由哪些編碼類別依序組合而成」。例如：

```
編碼原則「食材編碼原則」(id=5, level=4)
├── 序號 1: 編碼類別代碼=01 (食材大類)
├── 序號 2: 編碼類別代碼=02 (食材中類)
├── 序號 3: 編碼類別代碼=03 (食材小類)
└── 序號 4: 編碼類別代碼=04 (原型食材)
```

下游：

- **食材維護作業**：主檔的 `structure` 欄位（寫死 = 5）就是引用此原則
- **單品維護作業**：主檔的 `structure` 欄位由使用者選

---

## 3. 業務邏輯背景

### 3.1 「主檔 + 一張子表」結構

```
編碼原則主檔（pdm_code_structure）
  └── 1:N 編碼原則明細（pdm_code_structure_detail）
```

子表的 `parentId` 指回主檔 ID。每筆明細記「序號 + 編碼類別代碼」。

### 3.2 主檔欄位（極簡）

- ID
- 編碼結構名稱（name）
- 階層（level，Short 型態）
- 樂觀鎖（revision）

### 3.3 子表欄位

- ID
- 序號（serialNo，整數）
- 主表 ID（parentId）
- 編碼類別代碼（categoryCode）
- 樂觀鎖（revision）

### 3.4 **兩支 Controller 並存**

本模組有**兩支 Controller** 各自提供子表 CRUD 端點：

| Controller | 路徑 | 子表 CRUD |
|---|---|---|
| `CodeStructureController` | `/pdm/code-structure/code-structure-detail/*` | 提供 page、create、update、delete、get |
| `CodeStructureDetailController` | `/pdm/code-structure-detail/*` | 提供 page、create、update、delete、get、export-excel |

兩支 Controller 對同一張子表進行操作，端點略有不同：

- 第一支用主檔 Service 處理，前端會帶 `parentId` 作分頁過濾
- 第二支用獨立的 Detail Service 處理
- 第二支多了一個「含 storageType 的匯出 Excel」端點（LEFT JOIN `pdm_ingredient_subcategory_type`）

設計上存在重疊與不一致，列入 §11。

### 3.5 主檔的新增、修改**沒有任何驗證**

- 新增主檔：直接 insert，不檢查名稱重複、不檢查階層合理性
- 修改主檔：僅驗證存在
- 修改後也不檢查是否被下游引用

### 3.6 主檔刪除採物理刪除 + 連動子表清理

刪除主檔時：

1. 驗證存在
2. 物理刪除主檔
3. 依 parentId 刪除所有子表記錄
4. 包在 `@Transactional` 中

### 3.7 批量刪除無交易

`/delete` 端點接受 `ids` 清單，迭代呼叫單筆刪除。**整批的迴圈外無 `@Transactional`**（但單筆刪除自身有 `@Transactional`，所以單筆是原子的，批次整體不是）。中途失敗會殘留已刪部分。列入 §11。

### 3.8 子表新增、修改**也沒有任何驗證**

- 新增：直接 insert，不檢查序號唯一性、不檢查 parentId 存在性、不檢查 categoryCode 存在於「編碼類別維護」
- 修改：僅驗證子表自身存在
- 不檢查序號順序合理性
- 不檢查同一原則下同一序號是否重複

### 3.9 子表更新時清空 updater 與 updateTime

`CodeStructureServiceImpl.updateCodeStructureDetail` 中：

```java
codeStructureDetail.setUpdater(null).setUpdateTime(null);
```

意義是「讓框架自動填值」（避免前端帶錯）。但 `CodeStructureDetailServiceImpl.updateCodeStructureDetail` **沒有這個處理**。兩支 Service 的行為不一致，列入 §11。

### 3.10 子表的「含 storageType 匯出」

第二支 `CodeStructureDetailController` 提供獨有的 `/export-excel` 端點，呼叫 `selectWithStorageTypeByParentId`，LEFT JOIN `pdm_ingredient_subcategory_type` 取出儲存類型。意義推論為：當原則的明細指向食材小類時，連帶帶出該小類的儲存類型，供下游參考。

### 3.11 樂觀鎖欄位 revision 存在但未使用（同其他編碼模組）

DO 有 `revision` 欄位但 Service 端未啟用樂觀鎖。

### 3.12 主檔的匯出端點 `@Hidden`

`CodeStructureController.exportCodeStructureExcel` 標註 `@Hidden`，Swagger 不顯示。

---

## 4. 情境說明

### 4.1 正常流程 — 新增一個編碼原則

PDM 維護員小華要建立「食材編碼原則」：

**主檔**：
- 編碼結構名稱：`食材編碼原則`
- 階層：4

送出後系統：

1. 直接 insert（無唯一性檢查）
2. 回傳新主檔 ID

接著小華逐筆新增明細：

- 序號 1，編碼類別代碼 `01`（食材大類）
- 序號 2，編碼類別代碼 `02`（食材中類）
- 序號 3，編碼類別代碼 `03`（食材小類）
- 序號 4，編碼類別代碼 `04`（原型食材）

每筆 insert 不檢查任何唯一性、不檢查 parentId 存在、不檢查 categoryCode 是否真的對應到一個編碼類別。

### 4.2 異常情境 — 名稱重複

小華手滑新增第二筆同名的「食材編碼原則」：系統**不擋**，兩筆並存。列入 §11。

### 4.3 異常情境 — 子表序號重複

小華手滑同一個原則下新增兩筆「序號 2」的明細：系統**不擋**。後續業務邏輯如何決定哪一筆生效，未定義。列入 §11。

### 4.4 異常情境 — 子表 categoryCode 指向不存在的編碼類別

小華手滑填了 `categoryCode = 999`（不存在）：系統**不擋**。列入 §11。

### 4.5 異常情境 — 子表 parentId 指向不存在的主檔

小華手滑填了 `parentId = 99999`（不存在）：系統**不擋**。寫入孤兒明細。列入 §11。

### 4.6 正常流程 — 刪除一個編碼原則

小華刪除「食材編碼原則」（id=5）：

1. 驗證主檔存在
2. 物理刪除主檔
3. 依 `parentId=5` 刪除所有明細
4. 整段包在 `@Transactional`

> **但**：系統**不檢查**「食材維護作業」中是否有食材主檔的 `structure` 欄位指向此原則。刪除後食材維護作業的編號規則可能失效（食材主檔 structure=5 但對應主檔已不存在）。列入 §11。

### 4.7 業務規則分流情境 — 子表更新時 updater 處理不一致

阿凱用第一支 Controller 修改明細：updater 被清空、由框架自動填。
小華用第二支 Controller 修改明細：updater 不被清空、前端可帶任意值。

兩支 Service 行為不一致，可能導致 updater 欄位的可信度有疑問。列入 §11。

### 4.8 業務規則分流情境 — 含 storageType 的匯出

小華匯出「食材編碼原則」的明細：

- 走第二支 `CodeStructureDetailController.exportCodeStructureDetailExcel`
- 系統 LEFT JOIN `pdm_ingredient_subcategory_type`
- 對於指向食材小類項目的明細，帶出該項目的儲存類型
- 對於非食材小類的明細，storageType 為 null

> **註**：此匯出端點接受 `parentId` 參數但**不分頁**，固定取全部。資料量大時可能 OOM（推論，列入 §11）。

---

## 5. 操作流程

### 5.1 新增編碼原則（主檔）

```
[填寫表單]
  │
  ▼
[權限檢查：是否具備「PDM-編碼原則-新增」]
  │
  ▼
[直接 insert（無唯一性檢查）]
  │
  ▼
[回傳新 ID]
```

### 5.2 修改編碼原則（主檔）

```
[編輯表單，送出]
  │
  ▼
[權限檢查：是否具備「PDM-編碼原則-修改」]
  │
  ▼
[驗證存在]
  │
  ▼
[直接覆寫]
```

### 5.3 批量刪除編碼原則

```
[輸入 IDs 清單]
  │
  ▼
[權限檢查：是否具備「PDM-編碼原則-刪除」]
  │
  ▼
[迭代呼叫單筆刪除]
  ├─ 驗證存在
  ├─ 物理刪除主檔
  └─ 依 parentId 刪除所有明細
  │
  ▼
[（單筆有 @Transactional，整批迴圈外無）]
```

### 5.4 取得單一主檔

```
[輸入 ID]
  │
  ▼
[權限檢查：是否具備「PDM-編碼原則-查詢」]
  │
  ▼
[查主檔回傳]
```

### 5.5 分頁查詢主檔

```
[輸入查詢條件]
  │
  ▼
[權限檢查：是否具備「PDM-編碼原則-查詢」]
  │
  ▼
[依條件分頁]
  │
  ▼
[回傳]
```

### 5.6 取得單一原則的明細分頁

```
[輸入 parentId]
  │
  ▼
[權限檢查：是否具備「PDM-編碼原則-查詢」]
  │
  ▼
[依 parentId 分頁查子表]
  │
  ▼
[回傳]
```

### 5.7 新增／修改／刪除明細（兩支 Controller 並存）

兩支 Controller 各自提供同一張子表的 CRUD。Service 行為略有差異（updater 處理）。

### 5.8 匯出含 storageType 的明細

```
[輸入 parentId]
  │
  ▼
[權限檢查：是否具備「PDM-編碼原則明細-匯出」]
  │
  ▼
[呼叫 selectWithStorageTypeByParentId（LEFT JOIN）]
  │
  ▼
[輸出 Excel：編碼結構維護子類.xls]
```

---

## 6. 欄位規格

### 6.1 編碼原則主檔欄位

| 欄位（業務名） | 型別 | 必填 | 規則 | 備註 |
|---|---|---|---|---|
| 編碼結構 ID | 數字 | 系統產生 | 全系統唯一 | — |
| 編碼結構名稱 | 文字 | 否（推論） | **無唯一性檢查** | — |
| 階層 | Short | 否 | — | 業務意義待確認 |
| 樂觀鎖 | 數字 | 系統寫入 | **未使用** | dead column |
| 建立人員、建立時間、修改人員、修改時間 | BaseDO | 系統寫入 | — | — |

> 來源：`CodeStructureDO.java`、`CodeStructureSaveReqVO.java`

### 6.2 編碼原則明細子表欄位

| 欄位 | 型別 | 必填 | 規則 | 備註 |
|---|---|---|---|---|
| 明細 ID | 數字 | 系統產生 | 全系統唯一 | — |
| 序號 | 整數 | 否（推論） | **無唯一性檢查（同原則下可重複）** | 拼接順序 |
| 主表 ID（parentId） | 數字 | 否（推論） | **無存在性檢查** | — |
| 編碼類別代碼 | 文字 | 否（推論） | **無存在性檢查** | 指向「編碼類別維護」 |
| 樂觀鎖 | 數字 | 系統寫入 | **未使用** | dead column |

> 來源：`CodeStructureDetailDO.java`

### 6.3 查詢輸入欄位

| 欄位 | 規則 |
|---|---|
| 名稱、階層、樂觀鎖、建立人員、建立時間、修改人員、修改時間 | （行為待確認） |

---

## 7. 商業邏輯

### 7.1 主檔幾乎不做任何驗證

新增無唯一性檢查、修改僅驗證存在、刪除僅驗證存在。

### 7.2 主檔刪除連動清子表（有 `@Transactional`）

唯一的「業務邏輯」部分。

### 7.3 批量刪除整體無交易（單筆有）

中途失敗會殘留已刪部分。

### 7.4 子表幾乎不做任何驗證

新增不檢查 parentId、序號、categoryCode 的合理性。修改僅驗證子表自身存在。

### 7.5 兩支 Controller 的差異

| 項目 | 第一支（在主 Controller 內） | 第二支（獨立 Controller） |
|---|---|---|
| URL | `/pdm/code-structure/code-structure-detail/*` | `/pdm/code-structure-detail/*` |
| Service | `CodeStructureServiceImpl` | `CodeStructureDetailServiceImpl` |
| 更新時 updater 處理 | 清空（由框架自動填） | **不清空**（前端帶任意值） |
| 匯出 Excel | 無 | 有（含 storageType） |
| 權限字串 | `pdm:code-structure:*` | `pdm:code-structure-detail:*` |

---

## 8. 使用角色與權限

| 角色 | 可看資料 | 可操作 |
|---|---|---|
| **PDM 編碼維護員（具備兩組權限字串）** | 全部編碼原則與明細 | 全部操作 |
| **僅具備查詢權限者** | 全部資料 | 僅瀏覽 |

---

## 9. 畫面需求／視覺規範

無 UI 細節可從後端反推。待前端對照。

預期應提供：

- 編碼原則列表頁
- 編碼原則新增／編輯彈窗（含名稱、階層）
- 明細管理彈窗（含序號、編碼類別代碼）
- 匯出按鈕（含 storageType 版）

---

## 10. 功能範圍

### 10.1 包含的功能

- 編碼原則主檔之新增、修改、批量刪除（含連動刪明細）
- 編碼原則明細之新增、修改、刪除（兩支 Controller）
- 條件分頁查詢
- 取得單一主檔／明細
- 取得明細分頁（依 parentId）
- 匯出 Excel（主檔 `@Hidden`；明細含 storageType）

### 10.2 預留但尚未實作

- **任何業務驗證**：名稱唯一性、序號唯一性、parentId 存在性、categoryCode 存在性
- **下游引用檢查**：刪除主檔時不檢查食材／單品引用
- **批量刪除的整體 `@Transactional`**
- **兩支 Controller 的行為一致性**
- **樂觀鎖實際使用**

### 10.3 不包含

- 編碼類別本身的維護（在「編碼類別維護」）
- 編碼項目本身的維護（在「編碼項目維護」）
- 編碼原則被引用的食材／單品主檔

---

## 11. 待確認事項

| # | 議題 | 為何要確認 | 證據／來源 |
|---|---|---|---|
| 1 | **存在兩支 Controller** 同時管理同一張子表，行為略有不一致（updater 處理、提供的端點）。是否要統一為一支？ | 維護成本與行為一致性 | `CodeStructureController.java`、`CodeStructureDetailController.java` |
| 2 | 主檔的新增、修改**無任何業務驗證**（名稱重複、階層合理性）。是否要補？ | 資料正確性 | `CodeStructureServiceImpl.java:37-52` |
| 3 | 子表的新增、修改**無任何業務驗證**（序號唯一性、parentId 存在、categoryCode 存在）。是否要補？ | 資料正確性 | `CodeStructureServiceImpl.java:92-105`、`CodeStructureDetailServiceImpl.java:26-37` |
| 4 | 「序號」可以重複，後續業務邏輯如何決定哪一筆生效？是否要強制唯一？ | 編碼正確性 | `CodeStructureDetailDO.java:33` |
| 5 | 刪除主檔時**不檢查下游引用**（食材／單品的 `structure` 欄位）。刪除後可能造成食材／單品的編碼規則失效。 | 資料完整性 | `CodeStructureServiceImpl.java:54-64` |
| 6 | 批量刪除迴圈外無 `@Transactional`，中途失敗會殘留已刪部分。 | 資料一致性 | `CodeStructureController.java:60-67` |
| 7 | 樂觀鎖欄位 revision 存在但未使用（同其他編碼模組）。 | 欄位語意 | `CodeStructureDO.java:41`、`CodeStructureDetailDO.java:45` |
| 8 | 兩支 Service 更新時 updater 處理不一致（一支清空、一支不清空）。哪個是正確行為？ | 資料正確性 | `CodeStructureServiceImpl.java:103`、`CodeStructureDetailServiceImpl.java:35` |
| 9 | 含 storageType 的匯出端點**不分頁**，固定取全部。資料量大時可能 OOM。 | 系統穩定性 | `CodeStructureDetailController.java:85-94` |
| 10 | 「階層」的業務意義？跟「明細子表的筆數」有沒有強制關係？ | 業務理解 | `CodeStructureDO.java:37` |
| 11 | 主檔匯出端點 `@Hidden`（Swagger 不顯示），但子表匯出有 `@Hidden`／有沒有不一致？需確認。 | API 可發現性 | `CodeStructureController.java:89` |
| 12 | 食材維護作業的 `structure=5` 寫死值對應到本模組哪筆主檔？對應關係穩定嗎？ | 跨模組依賴 | `IngredientServiceImpl.java:67-68` |
