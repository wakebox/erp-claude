# PRD｜物流管理 — 物流配送查詢作業

> 來源：逆向自 `kingmaker-module-pdm` 後端程式碼（`controller/admin/rawmaterial1/RawMaterialDemandHeadController.java` 的 `/query-details-by-delivery-date` 與 `/generateCsv` 端點、`service/rawmaterial1/RawMaterialDemandHeadOtherServiceImpl.java`）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **物流配送人員 / 倉儲人員**。當某個預計配送日到來，我需要：

> 「2026-05-26 北一區當天要配送什麼？對應到哪張需求預測單號 / 臨時需求單號？我可以下載 CSV 給 MSS 倉做配送串接」

### 1.2 我要做什麼

- **依配送日 + 來源單號查明細**：傳入 regionId、預計配送日（timestamp）、可選 demandRelationDoc / tempRelationDoc / storeId → 回明細清單
- **產生當日 MSS 配送 CSV**：把當前日期所有由 MSS 倉配送的明細打包成 CSV，**上傳到 SFTP**（rocky@61.185.224.68:8422），並寫一筆 `pdm_raw_material_logistics` + 多筆 `_dtl` 表

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 看某天要送什麼 | 配送車上掛清單 |
| 跨單號彙整 | 同一天有預測 + 臨時 |
| CSV 給 MSS | 串接外部物流系統 |
| SFTP 上傳 | 自動化串接 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 依配送日 + 單號查明細 | 主畫面 |
| 日 MSS CSV 產生 + SFTP 上傳 | 外部串接 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 物流配送查詢作業 |
| 所屬模組 | Excel 列「物流管理」、實作在 PDM `rawmaterial1` |
| 兄弟功能 | 行事曆 (#48)、規劃查詢 (#49)、異動查詢 (#51)、串接記錄 (#52) |
| 主要頁面 | 配送明細查詢、CSV 產生按鈕 |
| 簽核流程 | 無 |
| 外部串接 | SFTP（rocky@61.185.224.68:8422） |
| 持久化表 | `pdm_raw_material_logistics`（單頭）/ `pdm_raw_material_logistics_dtl`（明細） |

---

## 2. 功能目的

物流配送查詢承擔兩個任務：

1. **「某天要送什麼」明細查詢**（單純 SQL）
2. **MSS CSV 自動串接**：每日產生由 MSS 倉配送的清單 → CSV → 上傳 SFTP → 寫入物流串接表（與 #52 相關）

---

## 3. 業務邏輯背景

### 3.1 兩個端點

| 端點 | 用途 |
|---|---|
| GET `/query-details-by-delivery-date` | 依配送日 + 單號查明細 |
| POST `/generateCsv` | 產生當日 MSS 配送 CSV + SFTP 上傳 |

### 3.2 配送日明細查詢

`queryDetailsByDeliveryDateAndDoc`：

```java
// 將逗號分隔字串轉為 List
List<String> demandRelationDocList = demandRelationDoc.split(",");
List<String> tempRelationDocList = tempRelationDoc.split(",");
return mapper.selectDetailsByDeliveryDateAndDoc(
    regionId, expectDeliveryDate, demandRelationDocList, tempRelationDocList, storeId);
```

來源：`RawMaterialDemandHeadOtherServiceImpl.java:158-179`。

注意：

- `expectDeliveryDate` 透過 Controller 從 **timestamp（毫秒）轉 LocalDateTime**（`Instant.ofEpochMilli` + 系統時區）
- 多單號用逗號分隔，service 端 split

### 3.3 MSS CSV 產生 + SFTP

`generateEveryDayAllMSSDelivery`：

```
1. 產生 signCode = "PR" + yyyyMMddHHmmss
2. 撈當日由 MSS 倉配送的明細
3. 為空 → 結束
4. 組裝 CSV：UTF-8 BOM + Windows 換行
   表頭：出貨日、品號、數量、訂單類別、店號、餐廳採購單號
5. 連 SFTP（rocky@61.185.224.68:8422）→ 上傳 /home/rocky/HAVI/FSTP/{signCode}.csv
6. insert `pdm_raw_material_logistics`：
   - signCode、deliveryMode="delivery"、deliveryMfrId="MSS"、shippingDate=now
7. insert `pdm_raw_material_logistics_dtl`（每明細一筆）：
   - parentId、deliveryMode、actualArrivalAmount=demandAmount、materialType="R"、shippingDate
```

來源：`RawMaterialDemandHeadOtherServiceImpl.java:181-238`。

⚠️ **嚴重安全問題**：

- **SFTP 連線資訊硬編在程式碼**：`new SftpUtil("rocky", "newsoft@1234", "61.185.224.68", 8422)` （line 203）— 密碼明碼
- **與 @Value 注入的 sftpUsername/sftpPassword 不一致**：程式有設定檔注入這四個變數但**沒用**，直接 hardcode
- **錯誤訊息打 log 的是設定檔的值**（`127.0.0.1`），與實際連線 IP 不符（line 229）

詳見 §11。

### 3.4 Controller 端點 `/generateCsv` 無權限保護

```java
@PostMapping("/generateCsv")
@Operation(summary = "生成当前日期的由MSS仓配送的数据，生成csv")
public void generateEveryDayAllMSSDelivery() {
```

**沒有 `@PreAuthorize`** — 任何登入使用者甚至匿名都可能觸發（依 SpringSecurity 全域設定而定）。詳見 §11。

### 3.5 跨模組依賴

- SFTP 外部服務
- `pdm_raw_material_logistics` 表（與 #52 物流串接記錄相關）
- 中繼 API 無

---

## 4. 情境說明

### 4.1 正常流程 — 查某天配送明細

物流人員 5/25 早上要排車：

1. GET /pdm/raw-material-demand-head/query-details-by-delivery-date
   - regionId=3、expectDeliveryDate=2026-05-25 的 timestamp、demandRelationDoc=「D-001,D-002」
2. 系統撈該日對應這兩張預測單的明細
3. 回 List<RawMaterialDemandDetailQueryRespVO>

### 4.2 規則分流 — 每日 MSS CSV 自動產生

排程或人工觸發 `/generateCsv`（推測由 cron 觸發）：

1. 撈當日 MSS 倉配送的明細
2. 產 CSV + UTF-8 BOM
3. SFTP 上傳到 MSS 倉的 `/home/rocky/HAVI/FSTP/`
4. 寫入物流串接記錄
5. log 紀錄各步驟成敗

### 4.3 異常情境 — SFTP 失敗

連線失敗 → log error + e.printStackTrace()，**不拋例外**（catch IOException 後沒 throw）。

- 結果：上層拿不到失敗訊號，物流串接表也沒寫入
- **但 service 已執行到 try 內第一個 sftp.uploadFile** — 若失敗發生在後續寫表前，CSV 上傳了但 DB 沒記錄；反之亦然
- 詳見 §11

---

## 5. 操作流程

```
[使用者進入「物流配送查詢」]
  │
  ├─ 1. 配送日明細 GET /pdm/raw-material-demand-head/query-details-by-delivery-date
  │    參數：regionId（必）、expectDeliveryDate timestamp（必）、demandRelationDoc、tempRelationDoc、storeId
  │
  └─ 2. MSS CSV 產生 POST /pdm/raw-material-demand-head/generateCsv
       └─ ⚠️ 無權限保護
       └─ 步驟：
           ├─ 撈當日 MSS 配送資料
           ├─ 組 CSV（UTF-8 BOM）
           ├─ SFTP 上傳（硬編密碼）
           ├─ insert raw_material_logistics 單頭
           └─ batch insert dtl
```

---

## 6. 欄位規格

### 6.1 配送日查詢輸入

| 欄位 | 必填 |
|---|---|
| regionId | ✅ |
| expectDeliveryDate (timestamp) | ✅ |
| demandRelationDoc (逗號分隔) | 可選 |
| tempRelationDoc (逗號分隔) | 可選 |
| storeId | 可選 |

### 6.2 CSV 表頭

```
出貨日 | 品號 | 數量 | 訂單類別 | 店號 | 餐廳採購單號
```

訂單類別硬編 `R`。

### 6.3 物流串接表（`pdm_raw_material_logistics` 單頭）

| 欄位 | 中文業務語 |
|---|---|
| signCode | 單據編號（PR + yyyyMMddHHmmss） |
| deliveryMode | 配送模式（"delivery"） |
| deliveryMfrId | 配送廠商代號（"MSS"） |
| shippingDate | 出貨日期 |

---

## 7. 商業邏輯

### 7.1 配送日明細查詢

純 SQL，service 只負責 split 字串。

### 7.2 MSS CSV 串接

略，見 §3.3。

---

## 8. 使用角色與權限

| 角色 | 對應權限字串 |
|---|---|
| 物流配送人員 | （配送日查詢）`pdm:raw-material-demand-head:query` |
| `/generateCsv` | **無權限保護** ⚠️ |

---

## 9. 畫面需求

建議：

### 9.1 配送日查詢頁

- 條件：區域、配送日（日曆 picker）、預測單號（多選）、臨時單號（多選）、門店
- 表格：明細列表
- 列印 / 匯出按鈕

### 9.2 CSV 產生

通常由排程觸發，不開放 UI。若要 UI，應加權限保護。

---

## 10. 功能範圍

包含：配送日明細查詢、MSS CSV + SFTP 串接

不包含：行事曆 (#48)、規劃查詢 (#49)、實際異動追蹤 (#51)、串接歷史 (#52)

---

## 11. 待確認事項

| 議題 | 證據 |
|---|---|
| **SFTP 密碼明碼硬編** — 嚴重安全問題 | line 203 |
| `@Value` 注入的設定檔變數未使用 | line 61-71 vs line 203 |
| log error 的 IP（127.0.0.1）與實際連線 IP（61.185.224.68）不同 | line 229 |
| `/generateCsv` 無 `@PreAuthorize` | Controller line 175-179 |
| SFTP 失敗只 log 不拋例外 | line 228-230 |
| CSV 寫上傳前 / 後與 DB 寫入的順序未在 transaction 內 — 部分成功部分失敗風險 | line 197-227 |
| 「店號」storeCode 來源未明（VO 上有但寫入時機未驗證） | line 291 |
| `materialType="R"` 字面值硬編 | line 223 |
| `signCode` 前綴 "PR" 含義未文件化 | line 186 |
| 中文表頭「出貨日 / 品號 / 數量」與 MSS 外部系統的格式需確認對接 | line 281 |
| `selectCurrentDayMssDeliveryDate` SQL「當前日期」依賴 server timezone | line 189 |
| 大量明細時 CSV byte[] in-memory 占記憶體 | 設計 |
| `pdm_raw_material_logistics_dtl.actualArrivalAmount` 設為 `demandAmount` — 名稱誤導（實際到貨 vs 需求） | line 222 |
| 若同日多次呼叫 `/generateCsv` 會建多張單 — 無幂等 | line 186（用時間戳避免撞號但仍重複） |
