# PRD｜採購管理 — 請購計劃管理

> 來源：逆向自 `kingmaker-module-pdm` 後端程式碼（`controller/admin/demand/DemandForecastConfigController.java`、`service/demand/DemandForecastConfigServiceImpl.java`、`dal/dataobject/demand/DemandForecastConfigDO.java`、`DemandForecastConfigScopeDO.java`）。
>
> ⚠️ **重要**：序號 29「請購計劃管理」在 PMM 模組內**無對應實作**。經逆向比對，實作位於 PDM 模組的「需求預測配置（DemandForecastConfig）」，由排程驅動「自動跑需求預測」並落為已歸檔的需求預測單，**並非「自動產生請購單」**。本文件描述當前後端真實行為，並標註與「業務語意上的『請購計劃』」之差距。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **採購規劃主管 / 系統管理員**。我希望系統能自動定期幫每個區域 / 門店跑下週的需求預測，不要每週靠人工進入頁面點「試算 + 儲存」；同時希望排程結果能直接歸檔，作為採購活動的下一步依據。

> 注意：原 Excel 用「請購計劃管理」這個業務名，**期望可能**是「排程自動建立請購單」。但目前系統實際做的事情是「**排程自動建立需求預測單**」（PRD #24 的單頭），距離「自動產生請購單」（#31）還有一步 — 需求預測 → 請購單之間的自動轉換**尚未實作**（見 §11）。

### 1.2 我要做什麼

- 建立 / 編輯 / 停用 / 啟用「需求預測配置」
- 為配置設定「適用範圍」（區域 ID + 門店 ID）— 一個配置可掛多個範圍
- 設定 Quartz Cron 排程表達式（什麼時間自動跑）
- 設定預測模式、需求週數、銷售資料天數、預測加成 %
- 啟用時系統自動「互斥檢查」：與其他啟用中的配置若範圍重疊則拒絕啟用
- 加入新範圍前可「預檢互斥」
- 手動觸發某配置「立即執行」（不必等排程）
- 看配置列表與單筆詳情（含適用範圍）

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 系統自動定期跑需求預測 | 採購助理每週都要進去手動跑 7 個區 × N 個門店，太花時間 |
| 不同配置不能重疊 | 兩份配置同時跑「北一區」會建出重複的預測單 |
| 互斥檢查必須即時 | 加入範圍前就要知道會不會撞，不要儲存後才報錯 |
| 範圍可粗可細 | 北一區整區是一筆；北一區下單店也是一筆 |
| 排程失敗有斷點記錄 | 重啟服務時可從 `lastSuccessTime` 繼續 |
| 啟用後若被別人改範圍造成衝突，需提示 | 用 `conflictFlag` 標記 |
| 手動觸發 | 補跑昨天忘了跑的；測試新配置 |
| 自動產生的單據視為已定案（已歸檔） | 不需要再走簽核 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 配置 + 適用範圍的 CRUD | 維護排程 |
| 範圍互斥檢查（precheck） | 加入前預知衝突 |
| 啟用時掃衝突 + 標記 conflictFlag | 啟用瞬間最終把關 |
| 停用 | 暫停排程不刪資料 |
| 手動觸發 run-now | 補跑 / 測試 |
| 依配置與範圍自動生成「需求預測單」 | 取代人工試算 |
| 幂等保護（同 region+store+週期已存在則跳過） | 防止重跑造成重複 |
| 預測加成 % 從配置帶入 | 統一加成標準 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 請購計劃管理（業務語）／需求預測配置（實作語） |
| 所屬模組 | Excel 列為「採購管理」，**實作在 PDM 模組** |
| 兄弟功能 | 食材需求預測試算表 BOM（#24）— 配置是預測單的「自動產生器」 |
| 主要頁面 | 配置列表、配置編輯頁、互斥預檢提示、手動觸發 |
| 簽核流程 | 無 — 自動產生的需求預測單直接設為「已歸檔」 |
| Cron 引擎 | Quartz |

---

## 2. 功能目的

需求預測配置是「需求預測試算表（BOM）」的**自動化版本**。設計理念：

1. **以「範圍」為單位排程** — 一個配置可涵蓋多個（region + store）範圍，每個範圍獨立執行
2. **互斥規則保證唯一性** — 同範圍只能由一個啟用中的配置負責，避免重複生成
3. **配置與執行分離** — 配置存「規則」（cron、加成 %、週數），執行 (run-now / cron 觸發) 才產生實際的預測單
4. **執行即定案** — 自動產生的需求預測單直接設為「已歸檔」，跳過簽核
5. **幂等保護** — 同範圍同週期已存在預測單則跳過，可重跑不會重複建

**業務語意差距**：

- Excel 「請購計劃管理」期望可能是「排程自動產生請購單」
- 程式實作是「排程自動產生需求預測單」
- 從需求預測 → 請購單的轉換仍是手動（採購人員看預測結果，自行進 #31 建請購單）
- 完整「請購計劃」流程**尚未自動化**（見 §11）

---

## 3. 業務邏輯背景

### 3.1 兩張表

| 表 | 用途 |
|---|---|
| `crg_demand_forecast_config`（配置 / `DemandForecastConfigDO`） | 配置名、enabled、conflictFlag、forecastMode、cronExpression、demandWeeks、salesDays、dataLengthDays、forecastIncrementPercent、lastSuccessTime |
| `crg_demand_forecast_config_scope`（範圍 / `DemandForecastConfigScopeDO`） | configId、regionId、storeId（可空，空表示「區域全門店」） |

關係：一個配置對多個範圍（1:N）

### 3.2 範圍重疊規則

`isScopeOverlap(r1, s1, r2, s2)` 邏輯：

```
1. 任一 regionId 為 null → 不衝突（false）
2. regionId 不同 → 不衝突
3. 任一 storeId 為 null（區域全門店） → 衝突
4. storeId 相同 → 衝突
5. 否則 → 不衝突
```

來源：`DemandForecastConfigServiceImpl.java:410-421`。

**含義**：

- 「北一區全店」(regionId=3, storeId=null) 與「北一區 1 號店」(regionId=3, storeId=11) → **衝突**（因為前者涵蓋後者）
- 「北一區 1 號店」與「北一區 2 號店」(storeId=12) → **不衝突**
- 「北一區」與「北二區」(regionId=4) → **不衝突**

### 3.3 啟用 vs 停用 vs 衝突標記

| 欄位 | 值 | 行為 |
|---|---|---|
| `enabled` | 1 啟用 | 排程會跑 |
| `enabled` | 0 停用 | 排程不跑，資料保留 |
| `conflictFlag` | 1 有衝突 | 啟用時偵測到衝突 → 強制停用且標記，前端列表顯示橙色「衝突」標籤 |
| `conflictFlag` | 0 無衝突 | 正常 |

啟用流程：

```
enableConfig(id):
  1. 取配置
  2. 對其範圍跑 precheck（排除自己）
  3. 有衝突 → enabled=0, conflictFlag=1, 不啟用，回傳 hasConflict=true + 衝突配置清單
  4. 無衝突 → enabled=1, conflictFlag=0
```

### 3.4 儲存時的強檢查

`saveConfig`：

1. scopes 不可空 → `DEMAND_FORECAST_CONFIG_SCOPE_EMPTY`
2. cronExpression 必須是有效的 Quartz Cron → `DEMAND_FORECAST_CONFIG_CRON_INVALID`
3. 若 enabled=1，跑 precheck → 有衝突拋 `DEMAND_FORECAST_CONFIG_SCOPE_CONFLICT`

### 3.5 編輯範圍：刪舊插新

`saveConfig` 更新時：

1. updateById 主配置
2. `scopeMapper.deleteByConfigId` 刪所有舊範圍
3. 批次插入新範圍

子表 ID 變動。

### 3.6 手動觸發 `runNow`

```
1. 取配置與範圍
2. 對每個範圍：
   - 呼叫 demandForecastService.getProductRecipeAnalysis(regionId, storeId, salesStart, salesEnd, weekStart, weekEnd, forecastIncrementPercent)
   - 對回傳的每個門店：
     - 檢查 existsDemandForecast(regionId, storeId, weekStart, weekEnd) → 已存在則跳過（幂等）
     - 否則 createDemandForecastFromAnalysis：建立單頭 + 明細
       - processStatus = 「已歸檔」（直接定案，不走簽核）
       - documentDate = today
       - signCode = generateSignCode("需求預測試算表")
       - subject = 配置名稱
3. 更新 lastSuccessTime = now
4. 回傳建立的 headerId 清單
```

來源：`DemandForecastConfigServiceImpl.java:283-337`。

### 3.7 排程觸發

未在程式中明顯看到排程入口，但 cronExpression 由 `CronUtils.isValid` 驗證，推測有 Quartz 任務定期讀 enabled=1 的配置並呼叫 runNow（具體 Job 在 infra 模組 / quartz 子系統）。

### 3.8 幂等保護

`existsDemandForecast(regionId, storeId, weekStart, weekEnd)` 查 `crg_demand_forecast` 是否有相同四欄位的記錄。若有 → 跳過。

注意：

- 用 `weekStartDate + weekEndDate` 等值比對，**不考慮預測模式 / 資料長度等差異**
- 同範圍同週的兩種不同配置會視為同一筆（其中一個會被擋）
- 若手動先建過 + 後來配置自動跑也會被擋

### 3.9 與 #24 的關係

- #24 是「人工試算 + 簽核」版本：使用者進入頁面跑試算、編輯、儲存、走簽核
- #29 是「自動執行版本」：配置好排程，系統自動建單頭，狀態直接「已歸檔」
- **同一張 `crg_demand_forecast` 表，兩個來源共用**

---

## 4. 情境說明

### 4.1 正常流程 — 建立週度全區排程

採購規劃主管小王要設定「每週日 23:00 自動跑下週北一、北二、桃竹三區的需求預測」：

1. 進入配置維護頁，新增配置：
   - 配置名：每週全區預測
   - 預測模式：區域-週
   - Cron：`0 0 23 ? * SUN`
   - 需求週數：1
   - 銷售資料天數：28
   - 資料長度天數：28
   - 預測加成 %：1.05（+5%）
   - 啟用：1
   - 範圍：[(regionId=3, storeId=null), (regionId=4, storeId=null), (regionId=5, storeId=null)]
2. POST /save
3. 系統：
   - scopes 非空 ✓
   - Cron 有效 ✓
   - 因 enabled=1，跑 precheck（排除自己） → 假設無衝突
   - insert 主配置 → configId
   - batch insert 3 個範圍
4. 每週日 23:00 系統自動跑：
   - 對每個範圍呼叫 getProductRecipeAnalysis 拉預測結果
   - 對每店每個產品每個食材建立明細
   - 寫入 crg_demand_forecast（已歸檔）
   - 更新 lastSuccessTime

### 4.2 異常情境 — 範圍重疊

小王想再加一個「北一區 1 號店每日加跑」配置（細粒度）。但「每週全區預測」已包含北一區全店：

- precheck：incoming (regionId=3, storeId=11) 與 existing (regionId=3, storeId=null) → isScopeOverlap → 衝突
- 回傳 hasConflict=true、message = "加入此範圍將與 [每週全區預測] 配置產生衝突"
- 前端顯示提示，小王要不選別的範圍、要不停用前者

### 4.3 規則分流 — 啟用瞬間衝突

某使用者編輯了既有配置 A 的範圍，與配置 B 重疊。儲存時若 A 是停用狀態，**不會檢查衝突**（saveConfig 只在 enabled=1 時 precheck）。後來 A 點啟用：

- enableConfig 偵測衝突 → enabled=0, conflictFlag=1, 不啟用
- 回傳 hasConflict=true + B 的清單
- 前端列表顯示橙色「衝突」標籤

### 4.4 規則分流 — 手動觸發 + 幂等

小王發現上週日排程失敗。他選配置「每週全區預測」點「手動執行」，填入：
- startCompletedTime / endCompletedTime：上週銷售區間
- demandWeekStartTime / demandWeekEndTime：上週的預測週

系統執行：

- 對每個範圍跑 analysis
- 對每店檢查 existsDemandForecast(上週) → 上週的某些店已建（手動或其他配置） → 跳過
- 其他店建立
- 回傳 createdHeaderIds

### 4.5 異常情境 — Cron 表達式無效

小王手滑寫了 `0 0 23 SUN`（少欄位）：

- `CronUtils.isValid` 回 false → 拋 `DEMAND_FORECAST_CONFIG_CRON_INVALID`

### 4.6 與「請購單」的距離

主管查看：

- 排程跑出 100 張預測單（已歸檔）
- 採購助理進入請購單管理（#31），看著預測結果，**手動**選品、填數量建請購單

> 「請購計劃」的完整自動化（預測 → 自動產生請購單）**目前無實作**。

---

## 5. 操作流程

```
[配置維護人員進入「需求預測配置」]
  │
  ├─ 1. 列表 GET /pdm/demand-forecast-config/list
  │
  ├─ 2. 單筆 GET /pdm/demand-forecast-config/get?id=
  │
  ├─ 3. 預檢 POST /pdm/demand-forecast-config/precheck
  │    └─ 給前端加入範圍前的即時提示
  │
  ├─ 4. 儲存 POST /pdm/demand-forecast-config/save
  │    ├─ scopes 非空
  │    ├─ Cron 有效
  │    ├─ enabled=1 強檢查無衝突
  │    └─ insert 或 updateById + 範圍刪舊插新
  │
  ├─ 5. 停用 PUT /pdm/demand-forecast-config/disable?id=
  │    └─ enabled=0
  │
  ├─ 6. 啟用 PUT /pdm/demand-forecast-config/enable?id=
  │    ├─ 跑 precheck
  │    ├─ 有衝突 → enabled=0, conflictFlag=1, 回 hasConflict=true
  │    └─ 無衝突 → enabled=1, conflictFlag=0
  │
  └─ 7. 手動執行 POST /pdm/demand-forecast-config/run-now
       ├─ 對每範圍跑 getProductRecipeAnalysis
       ├─ 對每店幂等檢查
       ├─ 建立 crg_demand_forecast 單頭（已歸檔）+ 明細
       └─ 更新 lastSuccessTime，回 createdHeaderIds

[Quartz 排程引擎]
  └─ 定期掃 enabled=1 的配置 → 對符合 cron 的配置呼叫 runNow（推測）
```

---

## 6. 欄位規格

### 6.1 配置（`crg_demand_forecast_config`）

| 欄位 | 中文業務語 | 型別 |
|---|---|---|
| id | 配置 ID | Long |
| name | 配置名 | 字串 |
| enabled | 啟用旗標 | Integer（0/1） |
| conflictFlag | 衝突旗標 | Integer（0/1） |
| forecastMode | 預測模式 | 字串 |
| cronExpression | Quartz Cron 表達式 | 字串 |
| demandWeeks | 需求週數 | Integer |
| salesDays | 銷售資料天數 | Integer |
| dataLengthDays | 資料長度天數 | Integer |
| forecastIncrementPercent | 預測加成倍率 | BigDecimal（如 1.05） |
| lastSuccessTime | 上次成功執行時間 | LocalDateTime |

### 6.2 範圍（`crg_demand_forecast_config_scope`）

| 欄位 | 中文業務語 |
|---|---|
| id | 範圍 ID |
| configId | 配置 ID |
| regionId | 區域 ID |
| storeId | 門店 ID（可空，空=區域全店） |

### 6.3 互斥規則摘要

| 範圍 1 | 範圍 2 | 是否衝突 |
|---|---|---|
| (3, null) | (3, null) | ✅ 是 |
| (3, null) | (3, 11) | ✅ 是（前者涵蓋後者） |
| (3, 11) | (3, null) | ✅ 是 |
| (3, 11) | (3, 11) | ✅ 是 |
| (3, 11) | (3, 12) | ❌ 否 |
| (3, null) | (4, null) | ❌ 否 |
| (null, *) | (*, *) | ❌ 否（null region 視為無效輸入） |

### 6.4 驗證規則

- scopes 不可空
- cronExpression 必須是有效 Quartz Cron
- enabled=1 儲存時必須無衝突

---

## 7. 商業邏輯

### 7.1 儲存

略，詳見 §3.4 + §3.5。

### 7.2 啟用

略，詳見 §3.3。

### 7.3 手動觸發

略，詳見 §3.6。

### 7.4 幂等保護

`existsDemandForecast(regionId, storeId, weekStart, weekEnd)` 等值比對四欄位。

### 7.5 自動產生需求預測單

- documentDate = today
- processStatus = 「已歸檔」（**跳過簽核**）
- signCode = generateSignCode("需求預測試算表")（**共用 #24 的 signCode 規則**）
- subject = 配置名
- 預測加成 % 從配置帶入
- 明細從 `getProductRecipeAnalysis` 的結果展開

---

## 8. 使用角色與權限

| 角色 | 可操作 | 對應權限字串 |
|---|---|---|
| 採購規劃主管 / 系統管理員 | 全部 | `pdm:demand-forecast:query`、`create`、`update`（與 #24 共用） |

> 注意：**權限字串與 #24 共用** `pdm:demand-forecast:*` — 角色設定難以分離「能跑試算」與「能設定排程」（見 §11）。

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節。建議：

### 9.1 列表

- 表格：配置名、啟用狀態（switch）、衝突標籤（橙色顯示）、Cron 表達式、上次執行時間、操作（編輯 / 停用 / 啟用 / 手動執行）

### 9.2 編輯頁

- 主配置段：配置名、預測模式（下拉）、Cron 表達式（含格式提示與 quick picker）、需求週數、銷售天數、資料長度、加成 %
- 範圍段：加 / 刪範圍（每行：區域下拉 + 門店下拉，門店可空=全店）
- 預檢按鈕（加入範圍前的提示）
- 儲存按鈕

### 9.3 手動執行對話框

- 銷售區間 / 預測週區間（必填）
- 執行按鈕 → 顯示 createdHeaderIds

---

## 10. 功能範圍

### 10.1 包含的功能

- 配置 + 適用範圍的 CRUD
- 範圍互斥（precheck / saveConfig / enableConfig 三處）
- 啟用 / 停用
- 手動觸發
- Cron 表達式驗證
- 自動產生需求預測單（已歸檔）
- 幂等保護
- lastSuccessTime 斷點

### 10.2 預留但尚未實作

- **自動轉請購單**：預測結果產生後，仍需人工開啟 #31 請購單管理建單
- **排程失敗的補償 / 通知**：lastSuccessTime 只記成功，失敗無記錄
- **跨配置「優先級」**：兩個配置同範圍只能擇一，但無「override」概念
- **時區 / 跨時段處理**：cronExpression 預設使用伺服器時區
- **執行歷史記錄**：每次 runNow 只回 headerIds，無詳細執行 log

### 10.3 不包含

- 需求預測試算本身（屬於 #24，本功能只是其自動化前端）
- 請購單建立（屬於 #31）
- 採購單建立（屬於 #33）
- 報表 / 排程監控（屬於 infra / quartz 模組）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| 業務語意上「請購計劃管理」期待的是「自動產生請購單」嗎？ | 程式實作只到「自動產生需求預測單」，距離請購單還需手動一步 | 模組命名與程式碼差異 |
| 是否要實作「需求預測 → 自動產生請購單」？ | 真正的「請購計劃」自動化 | 程式無此邏輯 |
| 程式碼放在 PDM 而非 PMM，Excel 卻歸類 PMM | 模組界線需重新討論 | 跨模組設計 |
| 權限字串與 #24 共用 `pdm:demand-forecast:*` | 無法分離「跑試算」與「設定排程」權限 | Controller `@PreAuthorize` |
| 互斥規則：(3, null) 與 (3, 11) 是衝突，但有時可能想要「全店一份 + 重點店加強」 | 規則太嚴 | `isScopeOverlap` |
| 「啟用瞬間掃衝突」與「儲存時 enabled=1 強檢查」邏輯部分重複 | 兩處都做 precheck，可能不一致 | saveConfig vs enableConfig |
| 自動產生的單據直接「已歸檔」跳過簽核 | 是否符合內控？人工試算需簽核但排程不需，標準不一 | `createDemandForecastFromAnalysis` |
| 排程 Job 在哪？ | 未在程式碼明確列出 cron-triggered entry point | infra/quartz 模組 |
| 排程失敗如何處理？ | 無 lastFailureTime、無重試 | DO 欄位 |
| 預測週 / 銷售區間如何由 Cron 自動推算？ | runNow 接受時間參數，但定時觸發時的時間從何而來？ | RunReqVO 接受參數但 cron 觸發未說明 |
| 表前綴 `crg_` 與 #24 / #25 / #26 一致，但與其他 PDM 不同 | 命名混亂 | 多檔案 |
| 幂等條件用 `weekStartDate + weekEndDate` 等值，是否該包含 forecastMode？ | 同範圍同週但不同模式視為同一筆，可能會擋掉合法情況 | `existsDemandForecast` |
| `forecastIncrementPercent` 為「乘數」(1.05) 還是「百分比」(5)? | 程式碼顯示是乘數，但欄位名稱有 percent 字眼 | `getProductRecipeAnalysis` 用法 |
| Cron 是否要 UI 提供視覺化編輯 | 純字串難用 | 前端 UX |
| 預測模式（forecastMode）合法值？ | 字面字串，無 enum 化 | DO |
| 範圍重疊規則對「全公司無區域限制」的情況？ | regionId=null 被視為「不衝突」，可能造成漏網範圍 | `isScopeOverlap:411` |
| 「lastSuccessTime」何時記錄 — 整批跑完？單範圍跑完？ | 程式只在最後更新一次 | runNow 末尾 |
| 自動產生的需求預測單能否被人工編輯 | 已歸檔保護（同 #24）會阻擋編輯 | #24 §7.4 |
| run-now 是否該有並發鎖？ | 兩人同時觸發同配置可能重複建單（雖有幂等） | 程式邏輯無鎖 |
