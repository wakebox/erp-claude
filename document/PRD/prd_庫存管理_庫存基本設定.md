# PRD｜庫存管理 — 庫存基本設定

> 來源：逆向自 `kingmaker-module-whs` 後端程式碼（`controller/admin/warehouse/WarehouseController.java`、`service/warehouse/`、`dal/dataobject/warehouse/WarehouseDO.java`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。
>
> ⚠️ Excel「庫存基本設定」業務名 → 對應後端 `WarehouseController`「倉儲設定」 — 兩者名稱不一致但程式碼註解明確是「倉庫主檔」。詳見 §11。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **倉儲主管 / 總部系統管理員**。我負責定義整個 ERP 內可用的「倉庫主檔」結構，包含五層：

> 「**區域 → 倉別 → 倉名 → 儲區 → 儲位**」
>
> 例：「北一區 → MSS（總部冷藏） → MSS01 → FZ（冷凍區） → A01」

下游所有需要「倉庫位置」的功能（入庫、出庫、調撥、盤點、安全存量、庫存查詢）都引用本表。

### 1.2 我要做什麼

- 維護倉庫主檔（CRUD）
- 提供多種「下拉選項」端點 — 依層級逐層篩選
  - 所有不重複的「區域」
  - 某區下所有「倉別」
  - 某區某倉別下所有「倉名」
  - 某區某倉別某倉名下所有「儲區」
  - 某區下所有「倉名」（跨倉別）
- 「層級查詢」`/hierarchy` 一次回傳指定條件下的所有倉位元素
- Excel 匯出

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 五層結構表達倉位 | 北一區的 MSS01 冷凍區的 A01 格 |
| 編輯下拉時逐層篩選 | 選了「北一區」後倉別下拉只顯示北一區的倉別 |
| 各層支援名稱與代碼分離 | 代碼系統用、名稱顯示用 |
| Excel 匯出 | 對倉儲規劃、稽核 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 倉庫主檔 CRUD | 維護 |
| 「層級查詢」 | 給規劃 / 報表 |
| 多個 distinct 下拉端點 | 給編輯頁逐層篩選 |
| Excel 匯出 | 規劃 / 稽核 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 庫存基本設定（業務名）／ 倉儲設定（程式碼 Tag） |
| 所屬模組 | WHS（庫存管理） |
| 兄弟功能 | 倉儲查詢 (#38)、安全存量設定 (#36/37)、入庫 (#40)、出庫 (#41)、調撥 (#42)、盤點 (#43+)、不良品 (#47) |
| 主要頁面 | 倉庫主檔分頁、編輯頁、Excel 匯出 |
| 簽核流程 | 無 |
| 相關 Controller | `WarehouseController`、`WarehouseNameController`（疑似另一倉名子集，未在本 PRD 詳查） |

---

## 2. 功能目的

倉庫主檔是「**WHS 模組的位置字典**」：

1. **整體位置結構** — 全公司所有倉位以五層樹狀表示
2. **下游引用** — 入出庫、調撥、盤點、安全存量都用 `warehouseId` 為 FK
3. **逐層下拉** — 編輯下游單據時，使用者依層級逐層選

---

## 3. 業務邏輯背景

### 3.1 一張表（`whs_warehouse`）

| 欄位 | 中文業務語 |
|---|---|
| id | 主鍵 |
| category | 類別代碼（疑似父層分類） |
| categoryName | 類別名稱 |
| warehouseType | 倉別代碼 |
| warehouseTypeName | 倉別名稱 |
| warehouse | 倉名代碼 |
| warehouseName | 倉名名稱 |
| zone | 儲區代碼 |
| zoneName | 儲區名稱 |
| binCode | 儲位代碼 |
| area | 區域 ID（Integer，與中繼 area_group_id 對應） |
| areaName | 區域名稱 |

⚠️ 注意：本表是**扁平化的「最小儲位」單筆**，沒有父子關係 — 同一個倉名會被複製到多筆（每筆 binCode 一筆）。

### 3.2 五層結構

```
區域（area, areaName）           ← 跨多筆共用
  └─ 倉別（warehouseType, name） ← 跨多筆共用
       └─ 倉名（warehouse, name） ← 跨多筆共用
            └─ 儲區（zone, name） ← 跨多筆共用
                 └─ 儲位（binCode） ← 每筆一個
```

實際儲存：

| id | area | warehouseType | warehouse | zone | binCode |
|---|---|---|---|---|---|
| 1 | 3 | MSS | MSS01 | FZ | A01 |
| 2 | 3 | MSS | MSS01 | FZ | A02 |
| 3 | 3 | MSS | MSS01 | RT | B01 |

distinct 端點就是對各層欄位 group by 抓不重複值。

### 3.3 五個 distinct 端點

| 端點 | 用途 |
|---|---|
| `/distinct-areas` | 所有區域 |
| `/distinct-warehouse-types?area=` | 某區下所有倉別 |
| `/distinct-warehouses?area=&warehouseType=` | 某區某倉別下所有倉名 |
| `/distinct-zones?area=&warehouseType=&warehouse=` | 某區某倉別某倉名下所有儲區 |
| `/distinct-area-warehouses?area=` | 某區下所有倉名（跨倉別） |

各端點要求參數逐層遞增，給前端搭配 cascade 下拉使用。

### 3.4 層級查詢 `/hierarchy`

5 個參數都 optional，可任意組合過濾。

### 3.5 跨模組依賴

- 被 #36 安全存量、#38 倉儲查詢、#40 入庫、#41 出庫、#42 調撥、#43+ 盤點、#47 不良品、PMM 報價維護等使用

### 3.6 與 WarehouseNameController 並存

另一 controller `WarehouseNameController`（103 行）疑似為「倉名」子集 — 提供更聚焦的倉名相關 API。本 PRD 未深入。

---

## 4. 情境說明

### 4.1 正常流程 — 編輯入庫單時逐層選倉位

倉儲人員小李為入庫單填倉位：

1. 區域下拉 → 打 /distinct-areas → 選「北一區」
2. 倉別下拉 → 打 /distinct-warehouse-types?area=3 → 選「MSS」
3. 倉名下拉 → 打 /distinct-warehouses?area=3&warehouseType=MSS → 選「MSS01」
4. 儲區下拉 → 打 /distinct-zones?area=3&warehouseType=MSS&warehouse=MSS01 → 選「FZ」
5. 儲位輸入或下拉 → A01

最終取得對應的 `warehouseId`（由 binCode 唯一確定）

### 4.2 典型業務 — 新增儲位

倉儲規劃新增「北二倉 RT 區 C01 儲位」：

1. POST /create
2. 填入：area=4、warehouseType=MSS、warehouse=MSS02、zone=RT、binCode=C01、各 name 欄位填中文
3. insert

### 4.3 規則分流 — 跨倉別取倉名

某需求「列出北一區所有倉名（不分倉別）」：

- 打 /distinct-area-warehouses?area=3
- 一次回傳該區所有倉名（合併不同 warehouseType）

---

## 5. 操作流程

```
[使用者進入「庫存基本設定」]
  │
  ├─ CRUD: /create、/update、/delete?id=、/get?id=、/page
  │
  ├─ 層級查詢: /hierarchy?area=&warehouseType=&warehouse=&zone=&binCode=
  │
  ├─ 各層 distinct:
  │  ├─ /distinct-areas
  │  ├─ /distinct-warehouse-types?area=
  │  ├─ /distinct-warehouses?area=&warehouseType=
  │  ├─ /distinct-zones?area=&warehouseType=&warehouse=
  │  └─ /distinct-area-warehouses?area=
  │
  └─ 匯出: /export-excel
```

---

## 6. 欄位規格

詳見 §3.1。

驗證規則：VO 無詳查；無顯著必填約束。

---

## 7. 商業邏輯

### 7.1 CRUD 一般化

無業務檢查（無唯一性、無關聯保護）

### 7.2 distinct 端點靠 SQL group by

xml 未讀。

---

## 8. 使用角色與權限

| 角色 | 可操作 | 對應權限字串 |
|---|---|---|
| 系統管理員 / 倉儲主管 | CRUD / 匯出 | `whs:warehouse:create`、`update`、`delete`、`query`、`export` |
| 所有下游模組 | 透過 distinct 端點取下拉 | `query` |

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節。建議：

### 9.1 編輯頁

- 各欄位手動填寫，或從上層 cascade 選擇
- 區域 / 倉別 / 倉名 / 儲區 應為下拉

### 9.2 分頁

- 條件：區域、倉別、倉名、儲區、儲位（多層篩選）
- 表格：區域、倉別、倉名、儲區、儲位、各對應名稱、操作

---

## 10. 功能範圍

### 10.1 包含的功能

- 倉庫主檔 CRUD
- 層級查詢
- 五個 distinct 下拉端點
- Excel 匯出

### 10.2 預留但尚未實作 / 缺陷

- **唯一性檢查**：應該 (area, warehouseType, warehouse, zone, binCode) 組合唯一，程式無檢查
- **跨表保護**：刪除被下游引用的倉位無檢查
- **VO 必填驗證**：未深查
- **與 `WarehouseNameController` 的關係不明**

### 10.3 不包含

- 庫存數量（屬於 #38 倉儲查詢 / 入出庫管理）
- 安全存量（#36/37）
- 倉名子集功能（疑似 `WarehouseNameController`，本 PRD 未涵蓋）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| Excel「庫存基本設定」對應後端「倉儲設定」 — 名稱不一致 | 業務 / 程式對照斷裂 | excel.md vs Controller Tag |
| `WarehouseNameController` 與本功能的關係 | 兩個 Controller 並存 | 同目錄 |
| 五層結構唯一性無檢查 | 同 binCode 可重複建 | service 無檢查 |
| 跨表保護無 | 刪除已被引用的倉位下游會孤兒 | service 無檢查 |
| `category` 與 `categoryName` 欄位用途未文件化 | 五層結構未含「類別」，是第六層？ | DO `category` |
| `area` 是 Integer，但其他層級代碼是 String | 一致性 | DO |
| distinct 端點對「停用 / 啟用」過濾否？ | 倉庫無啟用 / 停用欄位，應加 | DO 缺 status |
| 區域與中繼 areaGroupId 是否對齊？ | 跨模組 ID 對應 | DO `area` |
| 沒有「批次匯入」端點 | 上百個儲位手動建 | Controller |
| Excel 匯出未做使用者權限過濾 | 一致性 | line 94-104 |
