# PRD｜需求集合 — 臨時需求審核

> 來源：逆向自 `kingmaker-module-pdm` 後端程式碼（`controller/admin/tempreq/`、`service/tempreq/`、`dal/dataobject/tempreq/`、相關 DTO 與 Mapper）。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣 **行銷企劃 / 各門店店長 / 區經理**。系統已經跑出下週的需求預測（PRD #24 食材 BOM 試算），但生意常常有臨時變數：

> 「下週六我們在板橋店辦『買一送一』活動，預計多賣 200 個華堡」
> 「東區下週開職員工旅行，會包場 80 個套餐」
> 「桃園機場店要應付週末包機團，多備 50 公斤雞塊」

這些**非常規、臨時性的加單需求**就由我建立「臨時需求審核單」送出簽核，核准後會被下游的「物料需求預測試算表（非 BOM）」（PRD #25）自動帶入，加到原本的預測量上。

### 1.2 我要做什麼

- 建立一張臨時需求單，標註：申請單位、門市區域 / 門店、需求週起訖、主旨
- 在明細列出我要加碼的「單品」與「臨時需求量」（單品而非食材）
- 系統會自動補上每單品對應的食材清單與用量試算（用每個食材的標準用量 × 申請數量）
- 送出後進入 BPM 簽核流程（待處理 → 待簽核 → 已歸檔）
- 在「待簽分頁」看到分派給自己的單據
- 編輯（已歸檔的不可改）
- 匯出 Excel 給管理層或行銷對照

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 用「單品」而非「食材」來提需求 | 行銷講「多做 200 個華堡」、不講「多用 200 片牛肉餅 + 200 個麵包」 |
| 系統自動展開食材試算 | 簽核者要看「加 200 個華堡會多耗多少牛肉、生菜、起司」決定能否核准 |
| 一張單可同時加多個單品 | 活動可能涵蓋多種餐點 |
| 走簽核 | 額外需求要主管確認，避免店長 / 行銷自由加單 |
| 已歸檔的不能改 | 否則簽核紀錄與下游採購會錯亂 |
| 申請單位欄位記錄誰提的 | 行銷部、店長都可能是來源 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 建立臨時需求單（單頭 + 單品明細） | 一次提交一個活動 / 事件的加單 |
| 編輯（含明細） | 修改人員、活動細節調整 |
| 刪除 | 廢棄誤建單 |
| 取得單頭 + 自動展開的食材試算 | 簽核者看到完整影響範圍 |
| 分頁查詢、待簽分頁 | 找回過去的單、看自己要處理的單 |
| Excel 匯出 | 對外提供報表 |
| BPM 流程整合 | 簽核流程驅動狀態變更 |
| 與物料需求（#25）對接 | 核准後被 #25 自動納入合併 |
| 與食材需求（#24）對接 | Mapper 提供 `selectTempIngredientDetailList1` 等查詢方法給 #25 用 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 臨時需求審核 |
| 所屬模組 | 需求集合（程式碼路徑 `pdm/tempreq`，資料表前綴 `crg_temp_req`） |
| 兄弟功能 | 食材需求預測試算表（BOM）（#24）、物料需求預測試算表（非 BOM）（#25） |
| 主要頁面 | 臨時需求單編輯頁、單頭分頁、待簽分頁、Excel 匯出 |
| 簽核流程 | 有：透過 `MenuFlowProcessInstanceHelper` 綁定 BPM；表單路徑 `FormPathUniqueEnum.TEMP_REQ` |
| 與框架的偏離 | 權限字串前綴用 `crg:` 不是 `pdm:`（與其他 PDM 功能不一致） |

---

## 2. 功能目的

「臨時需求審核」是漢堡王 ERP 在「常規需求預測」之外的**例外通道**：

1. **正規預測（#24）** 處理「依歷史銷量推估的常態需求」
2. **臨時需求審核（#26）** 處理「歷史銷量推不出來的事件性需求」（活動、包場、特殊客群）
3. **物料需求行事曆（#25）** 把兩者合併，輸出給採購使用

設計理念：

- **以「單品」為單位** — 行銷的業務語彙
- **系統自動展開食材試算** — 給簽核者看影響
- **簽核流程必須** — 避免被濫用
- **已歸檔保護** — 一旦定案不可改
- **資料權限自動過濾** — 店長只看自己門店的單

---

## 3. 業務邏輯背景

### 3.1 兩張表

| 表 | 用途 |
|---|---|
| `crg_temp_req`（單頭 / `TempReqDO`） | 申請單位、單據編號、簽核單號、門市區域、需求門市、區域 ID、門店 ID、需求週起訖、主旨、流程狀態、流程實例 ID |
| `crg_temp_req_detail`（明細 / `TempReqDetailDO`） | parentId、單品 ID、申請臨時需求量、臨時需求計數、臨時需求最終數量、品號、食材 ID、食材品號 |

> 表前綴 `crg_` 與 #24 一致，與其他 PDM 功能不同（推測為 Cross Region Group 或某內部代號）。

### 3.2 「申請數量」與「自動展開」

使用者在前端只填**單品** + 數量（如：華堡 200 個）。

進入 `getTempReq(id)`（取單筆詳情）時，系統會：

1. 從 `selectSingleProductInf` 取該單頭下所有單品的基本資訊
2. 從 `selectIngredientInfo(productIds)` 撈所有單品對應的食材
3. 對每個食材計算：
   - `tempReqQuantity` = `standardQuantity × appliTempNum`（標準數量 × 申請數量，scale=2 HALF_UP）
   - `tempReqFinalNum` = `tempReqUnit > 0 ? tempReqUnit : tempReqQuantity`（先取計量、否則取計數）
4. 組裝 `TempReqDetailRecipeDTO`（單品 → 食材清單）回傳

> 注意：`tempReqUnit`（臨時需求計量）的賦值邏輯在程式碼中被**註解掉**（`TempReqServiceImpl.java:170-174`） — 目前只算 `tempReqQuantity` 而不算 `tempReqUnit`，因此 `tempReqFinalNum` 永遠等於 `tempReqQuantity`。詳見 §11。

### 3.3 建立 / 更新時的食材品號補強

`createTempReqDetailList` 在建立明細時：

1. 撈所有食譜（recipe）的 ID → productCode 對照表
2. 撈所有食材規格的 ID → prodCode 對照表
3. 對每筆明細：
   - 找不到 productCode → 跳過（不寫入）⚠️
   - 找到 productCode → 寫入 `prodCode`
   - 找不到 ingProdCode → 跳過（不寫入）⚠️
   - 找到 → 寫入 `ingProdCode`
4. batch insert 通過檢查的明細

**問題點**：

- 整批 in-memory 對照（每次建立都全表掃 recipe 與 ingredient specs）— 大資料量時效能差
- `continue` 跳過的記錄**靜默丟失**，使用者不會收到任何提示
- 程式邏輯為 `if (productCode == null) continue;` 然後 `temp.setProdCode(productCode)`，但接著仍會處理 `ingProdCode` — 注意控制流（程式邏輯難讀）

詳見 §11。

### 3.4 更新採「刪舊插新」

`updateTempReqDetailList`：

1. 用 parentId 刪掉所有舊明細
2. 清空每筆 id / updater / updateTime（避免 id 衝突與 updateTime 不更新）
3. 重新跑 `createTempReqDetailList` 邏輯

問題：刪舊插新會丟失明細的歷史軌跡（如建立時間 / 建立者），且明細 ID 變動，外部若有引用會壞。

### 3.5 已歸檔保護（與 #24 不同的判斷）

`validateTempReqExists` 不只檢查存在，還檢查歸檔：

```java
if (StrUtil.isEmpty(tempReqDO.getProcessInstanceId())
    && ARCHIVED.equals(tempReqDO.getProcessStatus())) {
    throw exception(TEMP_REQ_ARCHIVED_CANNOT_UPDATE);
}
```

**注意條件是「沒有流程實例 ID **且** 已歸檔」** — 這個邏輯有點怪：

- 若有 processInstanceId 且已歸檔 → **不**會被擋
- 沒 processInstanceId 但已歸檔 → 被擋

詳見 §11。

### 3.6 BPM 流程

- 表單路徑：`FormPathUniqueEnum.TEMP_REQ.getPath()`
- 流程狀態：建立時設「待處理」
- 啟動流程：`menuFlowProcessInstanceHelper.createProcessInstanceIfFlowOpen(userId, formPath, tempReqId.longValue())` — 若選單綁定流程才啟動
- 待簽分頁：`listProcessInstanceIdsForAssigneeTodoPage` 取分派給自己的 processInstanceIds，套用統一查詢

### 3.7 資料權限自動過濾

`getTempReqPage`：

- 登入者有區域權限且請求未指定 → 自動加 regionId
- 登入者有門店權限且請求未指定 → 自動加 storeId

與 #24、#25 一致的設計。

### 3.8 給下游使用的 Mapper 方法

`TempReqMapper` / `TempReqDetailMapper` 提供：

- `selectRawMaterialDemandOneStore(materialDemandTitleVO)` — 給 #25 查某店某天的臨時需求單號
- `selectTempIngredientDetailList1(tempRelationDocList)` — 給 #25 撈臨時需求對應的食材清單

這些方法的設計與 #24 相對應的 Mapper 方法呼應，讓 #25 可以「需求預測 + 臨時需求」並列處理。

### 3.9 與框架慣例的偏離

| 項目 | 偏離點 |
|---|---|
| 權限字串前綴 | `crg:temp-req:*`，其他 PDM 都用 `pdm:*` |
| `id` 型別 | `Integer`，其他 DO 多用 `Long` |
| 表前綴 `crg_` | 與 PDM 其他功能不一致 |

---

## 4. 情境說明

### 4.1 正常流程 — 行銷建立臨時需求

行銷企劃 Cindy 計畫 5/30（六）在板橋店辦「華堡買一送一」活動，預計多賣 200 個華堡。

1. 進入「需求集合 → 臨時需求審核」，點「新增」
2. 填入：
   - 申請單位：行銷部
   - 區域：北一區（regionId=3）
   - 門店：板橋店（storeId=12）
   - 需求週起訖：5/25–5/31
   - 主旨：5/30 板橋店華堡買一送一
3. 明細：加一行「華堡（productId=801） 申請臨時需求量 200」
4. POST /create
5. 系統：
   - signCode = generateSignCode("臨時需求審核")
   - processStatus = 「待處理」
   - insert 單頭，拿到 id=1234
   - createTempReqDetailList：撈 recipe / ingredient 對照表，把華堡的 productCode 寫入明細
   - 啟動 BPM 流程（板橋店店長為簽核者）→ 回填 processInstanceId
6. 板橋店店長看到「待簽分頁」有這筆

### 4.2 典型業務 — 簽核者看到食材展開

板橋店店長進入 /get?id=1234 查看：

- 單頭資訊
- `TempReqDetailRecipeDTO[]`：
  - 華堡（appliTempNum=200）
    - 牛肉餅（recipeId=801, standardQuantity=1, tempReqQuantity=200）
    - 麵包（standardQuantity=1, tempReqQuantity=200）
    - 生菜（standardQuantity=0.05 kg, tempReqQuantity=10.00）
    - 起司（standardQuantity=1, tempReqQuantity=200）

店長看完評估「值得做」，在簽核流程上通過 → processStatus → 待簽核 → 已歸檔

### 4.3 異常情境 — 編輯已歸檔的單

某使用者試圖編輯一張已歸檔的單：

- `validateTempReqExists` 取出 DO
- 看 processInstanceId 為空且 processStatus = 「已歸檔」 → 拋 `TEMP_REQ_ARCHIVED_CANNOT_UPDATE`
- 若 processInstanceId 非空且已歸檔 → 不會被擋（此判斷邏輯有問題，見 §11）

### 4.4 異常情境 — 建立明細時 productCode / ingProdCode 對照不到

行銷選了一個剛建立、尚未維護完整的單品（productCode 還沒寫好）。系統 in-memory 對照後找不到，**那筆明細靜默被跳過**，不寫入。使用者送出後看到單頭存在但明細少了該品，沒有任何錯誤訊息。

### 4.5 規則分流 — 待簽分頁

簽核者 / 主管進入「待簽分頁」：

1. 透過 BPM 取得自己作為 assignee 的所有 processInstanceIds
2. 無任何 ID → 空頁
3. 套用統一分頁查詢 + taskIds 過濾
4. 顯示待我處理的單據

### 4.6 規則分流 — 跨模組查詢

當 #25 物料需求行事曆建立時，會打 `selectRawMaterialDemandOneStore` 找出對應日期該店的「已核可的臨時需求」（推測語意；實際 SQL 邏輯需另外讀 mapper.xml）。**「已核可」的判斷是否在 SQL 內就過濾掉「未歸檔」的單？需確認**（見 §11）。

### 4.7 匯出 Excel

主管要做行銷活動彙整：

1. 進入分頁，填條件
2. 點「匯出 Excel」
3. 系統不分頁、全量寫出檔名「臨時需求審核.xls」
4. 僅匯出單頭欄位（不含明細展開的食材試算）

### 4.8 使用者鍵入錯誤 — VO 完全沒驗證

`TempReqSaveReqVO` 上**沒有任何 `@NotNull` / `@NotEmpty`**（來源：`TempReqSaveReqVO.java`）。完全可以送出全空白的單頭。後端只在更新 / 刪除時檢查 ID 存在。

---

## 5. 操作流程

```
[使用者進入「臨時需求審核」]
  │
  ├─ 1. 建立 POST /pdm/temp-req/create
  │    ├─ 權限：crg:temp-req:create
  │    ├─ signCode = generateSignCode("臨時需求審核")
  │    ├─ processStatus = 「待處理」
  │    ├─ insert 單頭，取 tempReqId
  │    ├─ 若 details 不為空 → createTempReqDetailList
  │    │    ├─ 撈 recipe.id→productCode 對照表
  │    │    ├─ 撈 ingredient_specs.id→prodCode 對照表
  │    │    ├─ 對每筆明細：productCode / ingProdCode 找不到就跳過（靜默）
  │    │    └─ batch insert
  │    └─ 啟動 BPM 流程（若選單綁定）→ 寫回 processInstanceId
  │
  ├─ 2. 更新 PUT /pdm/temp-req/update
  │    ├─ 權限：crg:temp-req:update
  │    ├─ validateTempReqExists：
  │    │    ├─ ID 不存在 → 拋 TEMP_REQ_NOT_EXISTS
  │    │    └─ processInstanceId 空 且 processStatus = 已歸檔 → 拋 TEMP_REQ_ARCHIVED_CANNOT_UPDATE
  │    ├─ 若 details 不為空 → updateTempReqDetailList（刪舊插新）
  │    └─ updateById 單頭
  │
  ├─ 3. 刪除 DELETE /pdm/temp-req/delete?id=
  │    ├─ 權限：crg:temp-req:delete
  │    ├─ validateTempReqExists
  │    ├─ deleteById 單頭
  │    └─ deleteByParentId 明細
  │
  ├─ 4. 取得單筆 GET /pdm/temp-req/get?id=
  │    ├─ 權限：crg:temp-req:query
  │    ├─ 撈單頭
  │    ├─ 撈單品基本資訊
  │    ├─ 對應每單品撈食材
  │    ├─ 計算每食材的 tempReqQuantity（standardQuantity × appliTempNum）
  │    └─ 組裝 TempReqDetailRecipeDTO 回傳
  │
  ├─ 5. 分頁查詢 GET /pdm/temp-req/page
  │    ├─ 權限：crg:temp-req:query
  │    ├─ 過濾：申請單位、單據編號、區域、門市、週起訖、流程狀態、建立時間
  │    └─ 套登入者 areaId/storeId 自動過濾
  │
  ├─ 6. 待簽分頁 GET /pdm/temp-req/todo-page
  │    ├─ 取分派給我的 processInstanceIds
  │    └─ 套用統一查詢
  │
  ├─ 7. 匯出 Excel GET /pdm/temp-req/export-excel
  │    ├─ 權限：crg:temp-req:export
  │    ├─ 套相同查詢條件，全量
  │    └─ 寫出 Excel（單頭欄位）
  │
  └─ 8. 取得單筆明細 GET /pdm/temp-req/temp-req-detail/list-by-parent-id?parentId=
       └─ 權限：crg:temp-req:query
```

---

## 6. 欄位規格

### 6.1 單頭（`crg_temp_req` / `TempReqDO`）

| 欄位 | 中文業務語 | 型別 | 必填 |
|---|---|---|---|
| id | 單頭 ID | Integer | 系統 |
| applyUnit | 申請單位 | 字串 | （建議必填） |
| documentCode | 單據編號 | 字串 | ✕ |
| signCode | 簽核單號 | 字串 | 系統 |
| storeRegion | 門市區域名稱 | 字串 | ✕ |
| demandStore | 需求門市名稱 | 字串 | ✕ |
| regionId | 區域 ID | Integer | （建議必填） |
| storeId | 門店 ID | Integer | （建議必填） |
| weekStartDate | 需求週別開始 | LocalDateTime | （建議必填） |
| weekEndDate | 需求週別結束 | LocalDateTime | （建議必填） |
| subject | 主旨 | 字串 | （建議必填） |
| processStatus | 流程狀態 | 字串 | 系統 |
| processInstanceId | 流程實例 ID | 字串 | BPM 系統 |

> ⚠️ VO 上**無任何 `@NotNull` / `@NotEmpty`** — 全靠前端把關。

### 6.2 明細（`crg_temp_req_detail` / `TempReqDetailDO`）

| 欄位 | 中文業務語 |
|---|---|
| id | 明細 ID |
| parentId | 關聯單頭 ID |
| productId | 單品 ID（對應 `pdm_recipe.id`） |
| appliTempNum | 申請臨時需求量 |
| tempReqQuantity | 臨時需求計數（standardQuantity × appliTempNum） |
| tempReqFinalNum | 臨時需求最終數量 |
| prodCode | 單品品號（系統補） |
| ingredientId | 食材 ID |
| ingProdCode | 食材品號（系統補） |

> 注意：`appliTempNum` 是 `Integer`、`tempReqQuantity` 是 `Integer` — 與 #24 / #25 用 `BigDecimal` 不一致（見 §11）。

### 6.3 取單回應（`TempReqRespVO` 三層結構）

```
TempReqRespVO（單頭）
  └─ tempReqDetailRecipeDTOS: List<TempReqDetailRecipeDTO>
      ├─ productId / appliTempNum / name（單品名稱）
      └─ tempReqRespVOList: List<TempReqDetailDTO>
          ├─ recipeId / ingredientId / ingredientName
          ├─ standardQuantity
          ├─ tempReqQuantity = standardQuantity × appliTempNum
          ├─ tempReqUnit（**目前不算**，註解掉）
          └─ tempReqFinalNum = tempReqUnit > 0 ? tempReqUnit : tempReqQuantity
```

### 6.4 查詢條件（`TempReqPageReqVO`）

| 條件 | 比對 |
|---|---|
| 申請單位 / 單據編號 / 門市區域 / 需求門市 / 主旨 | 等於 |
| regionId / storeId | 等於（自動套登入者過濾） |
| weekStartDate / weekEndDate | 等於 |
| createTime | 等於 |
| processStatus | 等於 |
| processInstanceStatus | 流程實例狀態 |
| taskIds | 系統內部用（待簽分頁） |

---

## 7. 商業邏輯

### 7.1 建立

1. signCode = generateSignCode("臨時需求審核")
2. processStatus = 「待處理」
3. insert 單頭
4. 若 details 不為空 → createTempReqDetailList（productCode / ingProdCode 對照不到則靜默跳過）
5. 啟動 BPM 流程（選單綁定時）

### 7.2 更新

1. 檢查存在 + 已歸檔
2. 若 details 不為空 → updateTempReqDetailList（刪舊插新）
3. updateById 單頭

### 7.3 刪除

1. 檢查存在
2. deleteById 單頭
3. deleteByParentId 明細

### 7.4 取單筆（自動展開食材）

`getTempReq(id)` 的回應包含：

- 單頭 DO 轉 RespVO
- 對每單品計算食材試算（`standardQuantity × appliTempNum`）
- 組裝 `TempReqDetailRecipeDTO` 三層

### 7.5 BPM 整合

同 #24：`createProcessInstanceIfFlowOpen` 啟動、`listProcessInstanceIdsForAssigneeTodoPage` 找待簽。

### 7.6 資料權限自動過濾

`getTempReqPage` 套用登入者區域 / 門店。

---

## 8. 使用角色與權限

| 角色 | 可看資料 | 可操作 | 對應權限字串 |
|---|---|---|---|
| 行銷 / 店長 / 區經理（申請者） | 限自己權限範圍 | 建立、編輯、查詢、刪除 | `crg:temp-req:create`、`update`、`delete`、`query` |
| 簽核主管 | 待簽分頁看到分派的單 | 透過 BPM 簽核（核准 / 退回） | `crg:temp-req:query` + BPM 角色 |
| 採購（檢視 + 匯出） | 全部 | 查詢、匯出 | `crg:temp-req:query`、`export` |

> ⚠️ 權限前綴用 `crg:` 而非 PDM 慣例的 `pdm:` — 角色設定容易遺漏（見 §11）。

---

## 9. 畫面需求 / 視覺規範

後端無 UI 細節，**待前端對照**。建議：

### 9.1 編輯頁（建立 / 修改）

- 上方：申請單位 / 區域（必）/ 門店（必）/ 需求週起訖（必）/ 主旨（必）
- 中間：明細表格
  - 加單品按鈕（從 recipe 下拉）
  - 每行：單品名稱 / 申請臨時需求量
  - 即時試算：展開該單品的食材清單與用量（前端 mock 或呼叫 /get）
- 底部：儲存 / 取消

### 9.2 分頁查詢

- 條件：申請單位、單據編號、區域、門市、週起訖、流程狀態、建立時間
- 表格：單據編號、簽核單號、申請單位、區域、門市、需求週、主旨、流程狀態、建立人、建立時間、操作

### 9.3 待簽分頁

- 與分頁類似，但只顯示我作為 assignee 的單
- 操作按鈕：核准 / 退回 / 改派

### 9.4 詳情頁

- 顯示單頭 + 三層結構：單品 → 食材 → 用量試算
- 簽核者重點看：每食材的 `tempReqQuantity` 與「目前庫存」的對比（庫存需另查）

---

## 10. 功能範圍

### 10.1 包含的功能

- 臨時需求單的 CRUD（含明細）
- 自動展開單品 → 食材 → 用量試算
- BPM 流程整合
- 已歸檔保護（部分條件下）
- 資料權限自動過濾
- 分頁查詢、待簽分頁
- Excel 匯出
- 給下游 #25 使用的查詢方法

### 10.2 預留但尚未實作

- **`tempReqUnit` 計量**：程式碼註解掉，目前只算 `tempReqQuantity` 計數
- **VO 必填驗證**：完全靠前端
- **productCode / ingProdCode 對照失敗的提示**：靜默跳過
- **「同單品重複」檢查**：可在同一張單建多筆同產品
- **跨單衝突檢查**：同活動可能被重複建立

### 10.3 不包含

- 食材本身的維護（屬於 [PDM > 食材維護作業]）
- 單品 / 食譜本身的維護（屬於 [PDM > 單品維護作業]）
- 採購單建立（屬於 [採購管理]）
- 入庫 / 出庫管理（屬於 [庫存管理]）
- 庫存的即時影響（本單只是預測加碼，實際扣庫需透過 #25 → #33 採購）
- 與 #24 的合併試算（屬於 #25）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| `tempReqUnit`（臨時需求計量）的計算邏輯被註解，是否該啟用？ | 目前 `tempReqFinalNum` 永遠等於 `tempReqQuantity`，計量分支永遠 false | `TempReqServiceImpl.java:170-174` |
| productCode / ingProdCode 對照失敗的明細靜默跳過 | 使用者沒被通知，造成「明細缺少行」 | `TempReqServiceImpl.java:245-251` |
| 已歸檔保護的條件：為什麼是「沒 processInstanceId **且** 已歸檔」？ | 有 processInstanceId 且歸檔的情況反而不被擋？邏輯似乎反 | `TempReqServiceImpl.java:129-131` |
| 權限前綴用 `crg:` 不是 `pdm:` | 與 PDM 其他功能不一致，角色設定容易遺漏 | Controller `@PreAuthorize` |
| 表前綴 `crg_` 是什麼？ | 與其他 PDM `pdm_` 表不一致，未文件化 | `TempReqDO.java:15` |
| `id` 用 `Integer` 而非 `Long` 是否會限制資料量？ | Integer 最大 21 億，正常使用無虞但與 #24 不一致 | `TempReqDO.java:29` |
| `appliTempNum` 為 Integer，無法表達 0.5 個套餐這類小數情境 | 業務若有「半份」需求會無法填 | `TempReqDetailDO.java:44` |
| 「申請單位」是否需字典化？ | 目前純字串，可能出現「行銷部 / 行銷 / 行銷企劃」三種寫法 | `TempReqDO.java:33` |
| 同一張單可新增重複的單品（同 productId 多筆） | 未檢查，可能造成數量重複計算 | createTempReqDetailList 邏輯 |
| 更新採「刪舊插新」會丟失明細歷史軌跡 | 明細 id 變動，外部引用會壞 | `TempReqServiceImpl.java:257-261` |
| createTempReqDetailList 每次撈全表的 recipe / ingredient_specs，效能 | 資料量大時 in-memory 對照緩慢 | `TempReqServiceImpl.java:231-238` |
| 是否需要新增時的「同主旨 / 同活動」重複建立檢查？ | 同活動可能被重建多次，下游 #25 會重複計算 | 無檢查 |
| 必填欄位（申請單位、區域、門市、週起訖、主旨）後端無驗證 | 易產生髒資料 | `TempReqSaveReqVO.java` 無 @NotNull |
| `selectRawMaterialDemandOneStore` SQL 是否過濾「已歸檔」單？ | 若不過濾，未核可的臨時需求會被 #25 拉去做物料試算 | mapper.xml 未讀 |
| 簽核流程具體節點與分派規則？ | 由 BPM 配置決定，需與 PM 對齊（誰是簽核者、退回流程） | 程式碼僅啟動流程，節點規格在 BPM |
| 流程狀態的合法值（待處理 / 待簽核 / 已歸檔）是否需固化為 enum？ | 目前是字面字串，未字典化 | `TempReqServiceImpl.java:73、122` |
| 「需求週起訖」是否要與單頭的需求預測（#24）的週起訖對齊驗證？ | 跨週的臨時需求合併到 #25 時可能對不上 | 無驗證 |
| 一張臨時需求單能涉及多個門店嗎？ | 目前 storeId 是單頭欄位，看似只能一個門店；若行銷活動跨店要分開建？ | DO 設計 |
| 「臨時需求最終數量」(`tempReqFinalNum`) 寫到 DB 嗎？還是只在取單時計算？ | 看程式邏輯像是只在 `getTempReq` 內 in-memory 計算，DB 上的欄位可能永遠空 | `TempReqDetailDO.java:54` vs `TempReqServiceImpl.java:180-184` |
| Excel 匯出只含單頭，使用者若要包含明細怎麼辦？ | 採購可能想要含明細 | Controller 只匯出單頭 |
| 待簽分頁的 processInstanceStatus 業務語意 | 「待處理 / 待簽核 / 待歸檔」三個值如何對應 BPM 任務狀態？ | `TempReqPageReqVO.java:53` |
