# PRD｜PDM — 門市分群維護表

> 來源：逆向自 `kingmaker-module-pdm` 後端程式碼。**本功能在 ERP 內無對應的維護端點與資料表** — 主資料來自漢堡王中繼系統，ERP 透過 FeignClient 拉取 (`client/BurgerKingStoreClient.java`、`client/vo/AreaGroupHierarchyVO.java`、`PdmTestController.java`)。本文件為 PM 對齊需求、SA 拆 task、QA 寫測試案例之工作文件。

---

## 1. 功能概覽

### 1.1 我是誰

我是漢堡王台灣總部的 **PDM／需求預測／採購／庫存等任何使用門市清單的人員**。每當我要做「全台北分公司的銷量預測」「桃園區的調撥計畫」「南部六家門市的安全存量套用」這類動作，我需要知道：

- 哪些門市屬於同一個「區域群組」（例：北一區、北二區、桃竹區…）
- 區域群組之上還有一層「組別」（例：直營區、加盟區、CTM 區）
- 每個門市現在屬於哪個區、哪個組

### 1.2 我要做什麼

從 ERP 使用者的角度，我「要做的事」其實是：

- **檢視**目前漢堡王中繼系統內的門市分群層級（組 → 區 → 店）
- 在需求預測、調撥、報表等模組中，把「分群」當成過濾／統計維度
- **接受** 我無法直接在 ERP 內新增 / 修改 / 刪除分群 — 那是中繼系統的權責

> ⚠️ **這個功能在 ERP 內不是「維護」性質，而是「消費」性質**。Excel 把它列在 PDM 模組是因為它與其他 PDM 字典（單位、餐食類型、營養成分…）有相同的「主檔」地位，但實作上它是**唯讀映射層**。

### 1.3 我有什麼需求

| 我的需求 | 背後的問題 |
|---|---|
| 看到一份「永遠跟中繼系統一致」的門市分群清單 | 若 ERP 自己存一份，就會跟中繼漂移；門市開關店、調區是中繼那邊發生的事 |
| 由分群下鑽到門市清單 | 報表、調撥、預測都需要「某區下的所有門市 ID」 |
| 用「分群區域 ID」當作 API 的過濾條件 | 需求預測（試算 BOM 用量）與門市銷售統計都用 `groupAreaId` 篩 |
| 不會誤以為 ERP 可以改分群 | 避免採購／預測同事去問「為何 ERP 內看不到新分群？」其實是中繼還沒同步 |

### 1.4 因此，需要以下功能

| 功能 | 解決的問題 |
|---|---|
| 透過 FeignClient 取得「組 → 區 → 店」三層階層 | 提供整份分群結構給前端展示／其他模組消費 |
| 取得「未含城市縣市」的精簡版本 | 給只關心 ID 與名稱的下游模組節省傳輸量 |
| 依 `groupId`（區域 ID）查該區下所有門市 | 給「某區的調撥／預測」場景使用 |
| 依 `groupName + id` 查單一區域的門店 | 給「單一區域明細」場景 |
| 與漢堡王中繼共用同一份 token（55 分鐘自動續期） | 不需 ERP 端各自處理身分驗證 |

### 1.5 功能基本資訊

| 項目 | 內容 |
|---|---|
| 功能中文名 | 門市分群維護表（實際語意為「門市分群檢視 / 消費」） |
| 所屬模組 | PDM（但資料**不在** PDM 資料庫內） |
| 兄弟功能 | 編碼類別維護、編碼項目維護、編碼原則維護、營養成分定義維護表、餐食類型維護表、單位定義維護表、單位轉換維護表、物流類型維護表 |
| 主要頁面 | 暫無正式維護頁；目前僅以 `PdmTestController` 提供測試用端點 |
| 簽核流程 | 無 |
| **資料來源** | 漢堡王中繼 API `http://61.218.209.215:80/api` — FeignClient `BurgerKingStoreClient` |

---

## 2. 功能目的

「門市分群」是漢堡王台灣組織結構的基礎主檔，被用於：

1. **報表彙整維度**：銷量統計、訂單統計、商品銷售統計可依「組／區／店」三層彙整
2. **需求預測的範圍切割**：需求預測試算（PRD #24 食材 BOM、#25 物料非 BOM）會用 `groupAreaId` 把某區的銷售歷史拉進計算
3. **調撥／補貨的範圍**：門市間調撥（PRD #42）以同區內為主
4. **權限的潛在範圍**：未來「店長只能看自己門市」「區經理可看整區」等資料權限可能會以分群為依據

**核心設計理念**：

- **單一事實來源在中繼**：漢堡王中繼系統（推測即「Laravel OA」或其延伸）是門市與分群的權責方；ERP 是消費者
- **不在本地落 DB**：ERP 不存「分群表」也不存「門市表」；每次查詢都即時呼叫 FeignClient（必要時搭配快取，見 §10.2）
- **以 token 共用維持身分**：`BurgerKingTokenManager` 統一管理 55 分鐘 token，所有呼叫共用

---

## 3. 業務邏輯背景

### 3.1 三層階層

```
組（Area Group, id + groupName）
  └─ 區（Area, id + groupName，注意這裡欄位也叫 groupName）
       └─ 店（Store, id + storeName）
```

- 「組」例：直營組、加盟組
- 「區」例：北一區、北二區、桃竹區、中區、南區
- 「店」例：BK 信義店、BK 板橋店

來源：`AreaGroupHierarchyVO` 含 `id`、`groupName`、`areas`（List）；`AreaInfo` 含 `id`、`groupName`（這裡實為「區」名）、`stores`（List）；`StoreInfo` 含 `id`、`storeName`。

> ⚠️ **欄位命名陷阱**：「組」與「區」的名稱欄位都叫 `groupName`，前端取值要小心層級。

### 3.2 主要的中繼 API 端點

| FeignClient 方法 | 中繼路徑 | 用途 |
|---|---|---|
| `getGroupWithStores(auth, tenantId)` | `/api/burgerking/admin/store/all-with-location` ⚠️ 註解寫的是 `group-with-stores` 但實際路徑指向 `all-with-location` | 完整門市資訊（含城市縣市），回傳 raw JSON 字串 |
| `getGroupWithStoresInnerRaw()` | `/api/burgerking/admin/store/group-with-stores/inner` | 精簡版（不含城市縣市），回傳 raw JSON 字串 |
| `getGroupWithStoresInner()` | 同上 | 同精簡版，但回傳強型別 `List<GroupWithStoresInnerVO>` |
| `getGroupWithStoresInnerByGroupId(groupId)` | `/api/burgerking/admin/store/group-with-stores/inner/group-id` | 查某「區」下的所有門市 |
| `getAllAreasWithStores()` | `/api/burgerking/admin/area-group/all-areas-with-stores` | 完整三層階層 `List<AreaGroupHierarchyVO>` |
| `getOneAreasWithStores(groupName, id)` | `/api/burgerking/admin/area-group/one-areas-with-stores` | 單一區域下的門店 |

來源：`BurgerKingStoreClient.java:46-110`。

### 3.3 認證

呼叫中繼 API 必須帶 `Authorization` header（中繼系統用 JWT）。ERP 端的處理：

1. `BurgerKingTokenManager` 維護一份遠端 token（55 分鐘有效期，自動續期）
2. `BurgerKingFeignConfig` 攔截 Feign 請求並注入 token
3. 部分方法支援前端傳入 Authorization header 覆寫（如 `getGroupWithStores`）

### 3.4 目前的呼叫入口

PDM 模組內**沒有**為「門市分群」設計正式的 Admin Controller。目前呼叫此 API 的地方：

1. **`PdmTestController`**（測試用，路徑 `/pdm/test/*`） — 包含 `group-with-stores`、`group-with-stores-feign`、`completed-orders-filter-service2/3`、`product-sales-test04` 等測試端點
2. **`DemandForecastService`**（需求預測，PRD #24/#25） — 內部呼叫以取得分群下的門市
3. **`RawMaterialDemandHeadServiceImpl`**（原料物需求預測） — 同上

來源：Grep 結果顯示這些檔案使用 `getAllAreasWithStores` / `getGroupWithStoresInner`。

> **結論**：目前 ERP 內**沒有給最終使用者「直接看到 / 操作門市分群」的頁面**。它純粹作為其他功能的「資料供應」存在。若 PM 想做「門市分群檢視頁」，需新建一個正式的 Controller。

### 3.5 為何「不在 PDM 內建表」

漢堡王中繼系統管理開關店、區劃調整、組織變動等業務，是門市分群的權責方。若 ERP 也建一份本地表：

- 必須處理同步策略（cron / webhook / on-demand）
- 必須處理同步失敗的補償
- 必須處理 ERP 改了本地、但中繼是事實來源時的衝突

成本高且收益低 — 因為 ERP 不會用「分群」做任何寫入動作（只做檢視 / 過濾）。**保持唯讀消費是正確設計**。

---

## 4. 情境說明

### 4.1 典型業務 — 需求預測按區試算

採購人員小張要為「北一區」下週的食材用量做需求預測（PRD #24）。她在前端選擇「北一區」，系統內部：

1. 從 `getAllAreasWithStores()` 拉到所有分群結構，找到「北一區」對應的 `groupId`
2. 用 `getGroupWithStoresInnerByGroupId(groupId)` 取得該區所有門店 ID 清單
3. 用門店 ID 清單去打中繼 API 拉每店過去 28 天的銷售歷史
4. 跑預測演算法、回傳食材需求量

小張不需理解中繼 API 細節，她只看到「北一區」這個選項。

### 4.2 典型業務 — 報表中看門市清單下拉

調撥管理（PRD #42）的調出方／調入方下拉，需要顯示「組 → 區 → 店」三層樹狀。前端打 `/pdm/test/api/burgerking/admin/order/daily/product-sales-test04` 拿 `List<AreaGroupHierarchyVO>`，渲染成樹狀下拉。

### 4.3 異常情境 — 中繼 API 不可用

中繼系統正在升級，所有 Feign 呼叫都會逾時或回 5xx。後果：

- 需求預測整個跑不動
- 調撥下拉空白
- 報表彙整失敗

目前 ERP 端**沒有 fallback** — 呼叫失敗直接拋例外給上層（雖然 `PdmTestController` 內部分端點有 try-catch，但業務 Service 沒有）。**屬於高耦合風險**（見 §11）。

### 4.4 異常情境 — Token 過期但續期失敗

`BurgerKingTokenManager` 通常自動續期，但若中繼登入服務本身掛掉，token 拿不到，所有呼叫 401。同 §4.3。

### 4.5 規則分流 — 完整版 vs 精簡版

需求預測只需要 ID 與名稱：用 `getGroupWithStoresInner()`（精簡）
要顯示地址、城市縣市的後台地圖頁：用 `getGroupWithStores()`（完整）

兩個方法都打中繼，但回傳資料量差異大；前端應依場景選擇對應方法。

---

## 5. 操作流程

```
[ERP 任何模組需要分群資訊]
  │
  ├─ 想取完整三層階層
  │    └─ BurgerKingStoreClient.getAllAreasWithStores()
  │        └─ GET 中繼 /api/burgerking/admin/area-group/all-areas-with-stores
  │            ├─ Token 由 BurgerKingFeignConfig 自動注入
  │            └─ 回傳 List<AreaGroupHierarchyVO> = 組 → 區 → 店
  │
  ├─ 想取「某區」下的門市
  │    └─ BurgerKingStoreClient.getGroupWithStoresInnerByGroupId(groupId)
  │        └─ GET .../group-with-stores/inner/group-id?groupId=
  │            └─ 回傳 List<GroupAndStoreVO>
  │
  ├─ 想取完整門市資訊（含縣市）
  │    └─ BurgerKingStoreClient.getGroupWithStores(auth, tenantId)
  │        └─ GET .../store/all-with-location（注意：方法名是 group-with-stores 但 URL 路徑是 all-with-location）
  │
  └─ 想取精簡門市資訊
       └─ BurgerKingStoreClient.getGroupWithStoresInner()
           └─ 回傳 List<GroupWithStoresInnerVO>

[Token 自動管理]
  ├─ BurgerKingTokenManager 每次呼叫前確認 token 是否在 55 分鐘有效期內
  ├─ 過期 → 自動打中繼登入 API 取新 token
  └─ 用 bk-username / bk-password 設定（記在系統設定）

[ERP 端目前沒有正式 Controller]
  └─ 測試端點僅在 PdmTestController：
      /pdm/test/group-with-stores
      /pdm/test/group-with-stores-feign
      /pdm/test/completed-orders-filter-service2
      /pdm/test/completed-orders-filter-service3
      /pdm/test/api/burgerking/admin/order/daily/product-sales-test04
      ⚠️ 這些是測試用，不應給最終使用者
```

---

## 6. 欄位規格

### 6.1 階層資料結構（`AreaGroupHierarchyVO`，三層）

| 層級 | 欄位 | 型別 | 說明 |
|---|---|---|---|
| 組 | id | Integer | 區域組 ID |
| 組 | groupName | String | 組名（例：直營組） |
| 組 | areas | List&lt;AreaInfo&gt; | 區清單 |
| 區 | id | Integer | 區 ID |
| 區 | groupName | String | 區名（例：北一區）⚠️ 與組同名欄位 |
| 區 | stores | List&lt;StoreInfo&gt; | 門店清單 |
| 店 | id | Integer | 門店 ID |
| 店 | storeName | String | 門店名稱（例：BK 信義店） |

### 6.2 精簡版（`GroupWithStoresInnerVO`、`GroupAndStoreVO`）

未直接讀檔，但從用法推測為「區與門店」兩層結構，無縣市資訊。詳細欄位需查對應 VO 檔案。

### 6.3 完整版（`getGroupWithStores` 回傳）

raw JSON 字串，由前端或下游自行解析；中繼 API 回傳結構文件需另外取得。

### 6.4 ERP 端不存任何欄位

無 `pdm_store_group` / `pdm_area_group` 之類的表。

---

## 7. 商業邏輯

### 7.1 ERP 端的「邏輯」非常薄

本功能在 ERP 端的程式邏輯幾乎只有兩件事：

1. 呼叫 Feign，把結果傳給呼叫者
2. 失敗時拋例外或回傳 CommonResult.error

**沒有的邏輯**：

- 沒有快取（每次都打中繼，潛在效能風險）
- 沒有 fallback / 降級
- 沒有重試機制
- 沒有資料一致性檢查

### 7.2 Token 邏輯（在 `BurgerKingTokenManager`）

雖然不在本功能範圍，但這是門市分群能正常運作的前提：

1. 第一次呼叫 → 用 `bk-username / bk-password` 打中繼登入 API
2. 拿到 token + 過期時間，存進記憶體
3. 後續呼叫前先檢查 token 是否還在 55 分鐘有效期內
4. 不在 → 自動續期

### 7.3 沒有 Service 層

不像其他 PDM 功能有 `Service` 介面與 `ServiceImpl`，本「功能」沒有獨立的 `StoreGroupService`。所有呼叫都直接從業務 Service（如 `DemandForecastServiceImpl`）打 FeignClient。

**建議**：若未來要正式化，應建立 `StoreGroupService` 統一封裝這些 Feign 呼叫，並加上快取（見 §10.2、§11）。

---

## 8. 使用角色與權限

| 角色 | 可看資料 | 可操作 | 對應權限字串 |
|---|---|---|---|
| 任何登入使用者 | 透過下游功能間接看到分群結構 | 僅檢視 | — |
| PDM 維護人員 | 同上 | 無法在 ERP 內維護分群 | — |
| 中繼系統管理員 | 全部 | 可在中繼系統內增刪改 | （在中繼系統內，非 ERP） |

> 目前 `PdmTestController` 的測試端點**沒有任何 `@PreAuthorize`**，技術上所有登入使用者都能呼叫。若正式發布需加上權限保護（見 §11）。

---

## 9. 畫面需求 / 視覺規範

**目前 ERP 內無正式 UI**。建議規劃時的最小頁面組成：

- 樹狀檢視：左側展開「組 → 區 → 店」
- 列表檢視：可切換為平面 grid，顯示「組 / 區 / 店 / 門店 ID」
- 同步狀態提示：右上角顯示「資料來源：漢堡王中繼，最後同步：xxx」
- 重新整理按鈕：強制重新呼叫中繼 API（繞過快取）
- 唯讀提示：頁面顯眼處標示「此資料來自漢堡王中繼，請至中繼系統維護」

### 在其他功能的引用

- 需求預測（#24/#25）：分群下拉
- 調撥管理（#42）：來源 / 目的門市下拉
- 報表彙整：以分群為彙整維度
- 安全存量（#36 庫存）：可選擇「整區套用同一套安全存量」

---

## 10. 功能範圍

### 10.1 包含的功能

- 透過 FeignClient 取得門市分群階層
- Token 自動續期（共用 `BurgerKingTokenManager`）
- 多個查詢入口（完整／精簡／單區／單組）

### 10.2 預留但尚未實作

- **正式的 Admin Controller** — 目前僅 `PdmTestController` 內有測試端點
- **快取層** — 每次呼叫都打中繼，未利用 `@Cacheable`（VO 註解中只看到 `@Cacheable` import，未實際套用）
- **資料一致性提示** — 若中繼與 ERP 內部其他資料（如門店銷量）有時間差，目前無提示
- **降級 / 重試** — 中繼掛掉就整個流程斷掉
- **權限保護** — 測試端點未保護

### 10.3 不包含

- 門市分群的新增 / 修改 / 刪除（屬於漢堡王中繼系統）
- 門市基本資料的維護（屬於漢堡王中繼系統）
- 銷售統計、訂單統計（雖然 FeignClient 內含相關方法，屬於需求預測 / 報表模組的範疇）

---

## 11. 待確認事項

| 議題 | 為何要確認 | 證據來源 |
|---|---|---|
| 是否需要為「門市分群」建立正式 Admin Controller？ | 目前僅測試端點，若 PM 要做檢視頁需新建 | 無正式 Controller |
| 是否需要本地快取？ | 每次呼叫中繼可能造成需求預測等高頻場景慢 | `getAllAreasWithStores` 等都無 `@Cacheable` |
| 中繼系統不可用時，ERP 是否要降級？ | 目前完全斷掉；至少需 fallback 到「快取的上次結果」 | 業務 Service 無 try-catch |
| `getGroupWithStores` 的路徑是 `all-with-location` 但方法名仍叫 `group-with-stores`，是否要重新命名？ | 程式碼註解保留原路徑，現在改指其他端點，可能造成維護混淆 | `BurgerKingStoreClient.java:46` |
| `AreaGroupHierarchyVO` 的「組」與「區」都用 `groupName` 欄位名，是否要區分？ | 前端取值容易混淆層級 | `AreaGroupHierarchyVO.java:18、35` |
| 是否需做「快照表」以便歷史報表能比對「過去某時點分群」？ | 中繼若調整分群，歷史報表的「北一區銷量」會與當下定義對不上 | 無快照表 |
| 「組」與「區」的英文 ID 命名（`groupId` vs `areaGroupId` vs `groupAreaId`）混用是否需統一？ | 不同方法傳入名稱不同 | `BurgerKingStoreClient.java:67、78、95` |
| `PdmTestController` 內的測試端點是否該移除或加上權限？ | 含硬編 access_token、test 路徑，不應上 prod | `PdmTestController.java:68-69` |
| 是否需要 `StoreGroupService` 統一封裝？ | 目前各業務 Service 直接打 FeignClient，重複程式碼 | 多檔案 grep |
| 中繼 API 失敗時的錯誤碼 / 訊息規格 | 前端要顯示什麼提示？目前是通用 500 | `PdmTestController.java:93-97` |
| 是否需支援「分群權限」（店長只看自己門市）？ | 未來資料權限可能依此切割，需確認設計 | 目前無 |
| 中繼 `/api` 路徑硬編在 FeignClient（`http://61.218.209.215:80/api`），是否要改為設定檔？ | 環境變動（測試／正式）難切換 | `BurgerKingStoreClient.java:35` |
| OA 整合長期規劃下，本功能會如何演變？ | 依專案決策（2026-05-16）使用者體系將以 OA 為事實來源；門市分群是否也會搬到 OA？ | `MEMORY.md` `[[project_user_integration_decision]]` |
