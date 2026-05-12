# 漢堡王 ERP — AI Agent 工作手冊

> 這份文件是 Claude Code 每次啟動時的主要參考。請先讀完這份，再讀 `document/` 下的詳細文件。

## 專案身份

- **系統名稱**：漢堡王 ERP（Kingmaker ERP）
- **目的**：供漢堡王台灣內部使用的 ERP 系統，涵蓋需求預測、採購、庫存、BPM 審批流
- **狀態**：開發中，尚未上線
- **後端 Repo**：`erp-spring`（參考程式碼位於 `../erp-spring`，本 repo 為 AI 工作目錄 `erp-claude`）
- **前端 Repo**：獨立 repo（Vue 3 + Ant Design Vue），不在本 repo 內

---

## 工作目錄說明

- **AI 工作目錄**（本 repo）：`d:\tdd\erp-claude` — 文件、設定、AI 輸出都在這裡
- **後端原始碼**（參考）：`d:\tdd\erp-spring` — 實際 Java/Spring Boot 程式碼，讀取時使用此路徑

當需要查看或修改後端程式碼，請讀取 `../erp-spring/` 下的對應路徑。

## 快速啟動

```bash
# 環境需求
# - JDK 17
# - PostgreSQL 15（192.168.29.113:5432，資料庫名：bk）
# - Redis（本地或遠端）

# 切到後端程式碼目錄
cd d:\tdd\erp-spring

# 編譯
mvn clean install -DskipTests

# 啟動（使用 local profile）
cd kingmaker-server
mvn spring-boot:run -Dspring-boot.run.profiles=local

# API 文件（Swagger UI）
# http://localhost:48080/doc.html
```

> **注意**：`application-local.yaml` 中的資料庫 IP `192.168.29.113` 是開發環境 PostgreSQL。請確認可連線，或修改為本地 DB。

---

## 架構一覽

> 以下路徑皆相對於 `d:\tdd\erp-spring\`

```
kingmaker-dependencies/          # 全域依賴 BOM
kingmaker-framework/             # 框架層（14 個 Starter + common）
  ├── kingmaker-common/          # 公共工具、例外、POJO
  ├── kingmaker-spring-boot-starter-security/   # JWT 認證
  ├── kingmaker-spring-boot-starter-mybatis/    # MyBatis Plus
  ├── kingmaker-spring-boot-starter-redis/      # Redisson
  └── ... (共 14 個 starter)
kingmaker-module-system/         # 系統模組：用戶、角色、權限、選單
kingmaker-module-infra/          # 基礎設施：檔案、程式碼生成器、排程任務
kingmaker-module-bpm/            # 工作流：Flowable 審批流
kingmaker-module-pdm/            # PDM：食材、BOM、需求預測
kingmaker-module-whs/            # WHS：庫存管理
kingmaker-module-pmm/            # PMM：採購管理（廠商→請購→採購→驗收）
kingmaker-module-bhm/            # BHM：漢堡王基礎資料（凍結，暫不開發）
kingmaker-server/                # 主應用啟動模組（port 48080）
```

每個業務模組分為 `-api`（對外介面定義）和 `-biz`（業務實作）兩層。

---

## 標準模組結構（每個 `-biz` 模組）

```
controller/admin/{feature}/
  {Feature}Controller.java         # REST 端點
  vo/
    {Feature}PageReqVO.java        # 分頁查詢請求
    {Feature}SaveReqVO.java        # 新增/更新請求
    {Feature}RespVO.java           # 回應 VO
dal/
  dataobject/{feature}/
    {Feature}DO.java               # 資料庫實體（繼承 BaseDO）
  mysql/{feature}/
    {Feature}Mapper.java           # MyBatis Plus Mapper
service/{feature}/
  {Feature}Service.java            # Service 介面
  {Feature}ServiceImpl.java        # Service 實作
convert/{feature}/
  {Feature}Convert.java            # MapStruct 轉換（部分模組有）
```

---

## 關鍵開發規範

### 1. 錯誤處理
```java
// 正確：使用框架的 ServiceExceptionUtil
import static com.newsoft.kingmaker.framework.common.exception.util.ServiceExceptionUtil.exception;
throw exception(ErrorCodeConstants.XXX_NOT_EXISTS);

// 錯誤：不要用 Java 原生例外
throw new IllegalArgumentException("...");  // 不符合框架規範
throw new RuntimeException("...");          // 不符合框架規範
```

### 2. 統一回應格式
```java
// 所有 Controller 方法回傳 CommonResult<T>
return success(data);
return CommonResult.error(errorCode);
```

### 3. BPM 流程綁定
需要審批流的單據，Service 中需呼叫 `MenuFlowProcessInstanceHelper` 判斷選單是否綁定流程，再決定是否發起 Flowable 流程。

### 4. 分頁查詢
```java
// 分頁請求繼承 PageParam
public class XxxPageReqVO extends PageParam { ... }

// 回傳 PageResult<T>
PageResult<XxxDO> pageResult = mapper.selectPage(pageReqVO);
```

### 5. 使用者身份
```java
import static com.newsoft.kingmaker.framework.security.core.util.SecurityFrameworkUtils.getLoginUserId;
Long userId = getLoginUserId();
```

---

## 外部系統整合

| 系統 | 說明 |
|---|---|
| 漢堡王中繼 API | `http://61.218.209.215:80/api`，FeignClient：`BurgerKingStoreClient` |
| Token 管理 | `BurgerKingTokenManager` 自動維護，有效期 55 分鐘，自動更新 |

---

## Git 分支規範

| 分支 | 用途 |
|---|---|
| `master` | 穩定版本 |
| `dev` / `dev-tw` | 主要開發分支 |
| `feature/{人名}/{功能}` | 個人功能分支 |

目前本地分支為 `dev-wilson`。

---

## 重要提醒（AI Agent 必讀）

1. **有些功能規格未知** — 遇到 `UNKNOWNS.md` 列出的項目，**不要自行假設規格**，必須先詢問
2. **BizContract 整個被註解** — `kingmaker-server/controller/contract/` 的程式碼全部在 `/* */` 中，用途未知，不要解除註解
3. **BHM 模組凍結** — `kingmaker-module-bhm` 暫時不修改
4. **測試** — 目前無自動化測試，靠手動 Swagger UI 驗證
5. **資料庫 schema** — 使用手動 `.sql` 檔，無 Flyway/Liquibase 版本控制

---

## 詳細文件索引

| 文件 | 內容 |
|---|---|
| [`document/CONTEXT.md`](document/CONTEXT.md) | 技術棧詳細說明、模組架構、外部整合 |
| [`document/STATUS.md`](document/STATUS.md) | 各模組各功能完成度 |
| [`document/UNKNOWNS.md`](document/UNKNOWNS.md) | 待釐清事項（AI 不要自行假設） |
| [`document/BACKLOG.md`](document/BACKLOG.md) | 待辦功能清單（程式碼 TODO 整理） |
| [`document/MODULES.md`](document/MODULES.md) | 各模組業務流程規格 |
| [`document/DEV_GUIDE.md`](document/DEV_GUIDE.md) | 新功能開發步驟指南 |
| [`document/RECOMMENDATIONS.md`](document/RECOMMENDATIONS.md) | 穩定性改善建議 |
