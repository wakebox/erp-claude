# 系統全覽（CONTEXT）

> 完整技術棧說明、模組架構、外部系統整合。
> 面向新加入的開發者和 AI Agent。

---

## 一、專案背景

| 項目 | 說明 |
|---|---|
| 系統名稱 | 漢堡王 ERP（Kingmaker ERP） |
| 客戶 | 漢堡王台灣 |
| 目的 | 整合需求預測、採購管理、庫存管理、BPM 審批流的內部 ERP 系統 |
| 現況 | 開發中，尚未上線 |
| 前端 | 獨立 repo（Vue 3 + Ant Design Vue），不在本 repo |

---

## 二、技術棧

### 後端

| 層級 | 技術 | 版本 |
|---|---|---|
| 語言 | Java | 17 |
| 框架 | Spring Boot | 3.4.1 |
| 基礎腳手架 | 芋道框架（Ruoyi-Vue-Pro fork） | 2.4.2 |
| ORM | MyBatis Plus | 3.5.9 |
| 工作流引擎 | Flowable | 7.0.1 |
| 遠端調用 | Spring Cloud OpenFeign | 2024.0.1 |
| 安全認證 | Spring Security + JWT | — |
| 資料庫 | PostgreSQL | 15（port 5432，DB: bk） |
| 連接池 | Druid | 1.2.24 |
| 快取 | Redis + Redisson | 3.41.0，DB 0，TTL 預設 1 小時 |
| 定時任務 | Quartz | — |
| API 文件 | SpringDoc + Knife4j | 2.7.0 + 4.6.0 |
| 工具庫 | Hutool | 5.8.35 |
| 應用埠 | — | 48080 |

### 前端

| 層級 | 技術 | 版本 |
|---|---|---|
| 核心框架 | Vue | 3.5.17 |
| 路由 | Vue Router | 4.5.1 |
| 狀態管理 | Pinia | 3.0.3 |
| UI 元件庫 | Ant Design Vue | 4.2.6 |
| 建置工具 | Vite | 7.1.2 |
| 語言 | TypeScript | 5.8.3 |
| CSS | Tailwind CSS | 3.4.17 |
| HTTP 客戶端 | @vben/request（基於 axios） | 1.10.0 |
| 工程形態 | pnpm Monorepo（apps/packages/internal） | — |
| 基礎模板 | vue-vben-admin（@vben/burger-king） | — |

---

## 三、Maven 模組架構

```
erp-spring/
├── kingmaker-dependencies/                # 全域依賴 BOM（版本管理）
├── kingmaker-framework/                   # 框架層
│   ├── kingmaker-common/                  # 公共工具、常量、例外、POJO
│   ├── kingmaker-spring-boot-starter-web/
│   ├── kingmaker-spring-boot-starter-security/   # JWT 認證鑑權
│   ├── kingmaker-spring-boot-starter-mybatis/    # ORM
│   ├── kingmaker-spring-boot-starter-redis/      # Redis
│   ├── kingmaker-spring-boot-starter-biz-tenant/ # 多租戶
│   ├── kingmaker-spring-boot-starter-biz-data-permission/
│   ├── kingmaker-spring-boot-starter-excel/
│   ├── kingmaker-spring-boot-starter-job/        # 定時任務
│   ├── kingmaker-spring-boot-starter-monitor/
│   ├── kingmaker-spring-boot-starter-mq/
│   ├── kingmaker-spring-boot-starter-protection/
│   ├── kingmaker-spring-boot-starter-biz-ip/
│   └── kingmaker-spring-boot-starter-websocket/
├── kingmaker-module-system/               # 系統模組（用戶/角色/權限/選單）
│   ├── kingmaker-module-system-api/
│   └── kingmaker-module-system-biz/
├── kingmaker-module-infra/                # 基礎設施模組
│   ├── kingmaker-module-infra-api/
│   └── kingmaker-module-infra-biz/
├── kingmaker-module-bpm/                  # 工作流模組（Flowable）
│   ├── kingmaker-module-bpm-api/
│   └── kingmaker-module-bpm-biz/
├── kingmaker-module-pdm/                  # PDM + 需求預測模組
│   ├── kingmaker-module-pdm-api/
│   └── kingmaker-module-pdm-biz/
├── kingmaker-module-whs/                  # 庫存管理模組
│   ├── kingmaker-module-whs-api/
│   └── kingmaker-module-whs-biz/
├── kingmaker-module-pmm/                  # 採購管理模組
│   ├── kingmaker-module-pmm-api/
│   └── kingmaker-module-pmm-biz/
├── kingmaker-module-bhm/                  # 漢堡王基礎資料（凍結）
│   ├── kingmaker-module-bhm-api/
│   └── kingmaker-module-bhm-biz/
└── kingmaker-server/                      # 主應用啟動模組（port 48080）
```

每個業務模組分為：
- `-api`：對外暴露的介面定義（DTO、枚舉、API 介面），供其他模組依賴
- `-biz`：業務實作（Controller、Service、Mapper、資料庫操作）

---

## 四、外部系統整合

### 漢堡王中繼 API（上游資料來源）

```
位置：kingmaker-module-pdm-biz
FeignClient 類：BurgerKingStoreClient
基礎 URL：http://61.218.209.215:80/api
認證方式：JWT Token（有效期 55 分鐘，自動更新）
Token 管理：BurgerKingTokenManager（自動刷新，調用方無需處理）
```

| API 路徑 | 方法 | 用途 |
|---|---|---|
| `/api/burgerking/admin/order/completed/filter` | GET | 已完成訂單統計 |
| `/api/burgerking/admin/order/daily/product-sales` | GET | 日維度商品銷量 |
| `/api/burgerking/admin/area-group/all-areas-with-stores` | GET | 區域組及門店（層級結構） |

**資料流向**：
```
漢堡王門店系統
  ↓ FeignClient 拉取銷售資料（DemandForecastServiceImpl）
需求預測計算
  ↓ 計算各門店各品項需求量
需求預測單（DemandForecast）
  ↓ BPM 審批
歸檔（⚠️ 後續邏輯待實作）
  ↓ 展開 BOM → 計算原料需求
原物料需求明細（RawMaterialDemand）
  ↓ 觸發
PMM 採購流程
```

---

## 五、標準模組內部結構

每個 `-biz` 模組遵循相同結構：

```
controller/
  admin/{feature}/              # 管理後台 API
    {Feature}Controller.java
    vo/
      {Feature}PageReqVO.java   # 分頁查詢請求（繼承 PageParam）
      {Feature}SaveReqVO.java   # 新增/更新請求
      {Feature}RespVO.java      # 回應 VO
  app/{feature}/               # App 端 API（部分模組有）
dal/
  dataobject/{feature}/
    {Feature}DO.java            # 資料庫實體（繼承 BaseDO）
  mysql/{feature}/
    {Feature}Mapper.java        # MyBatis Plus Mapper（繼承 BaseMapperX）
service/{feature}/
  {Feature}Service.java         # Service 介面
  {Feature}ServiceImpl.java     # Service 實作
convert/{feature}/             # MapStruct 轉換（部分模組有）
enums/                         # 業務枚舉
framework/                     # 模組級配置
```

---

## 六、認證鑑權機制

### JWT 認證流程

```
POST /system/auth/login { username, password, captchaVerification }
  ↓
驗證帳密 + 人機驗證
  ↓
回傳 { accessToken, refreshToken, userId, ... }

後續 API 請求：
Header: Authorization: Bearer {accessToken}
  ↓
JwtAuthenticationTokenFilter 解析
  ↓
注入 SecurityContextHolder
  ↓
@PreAuthorize("@ss.hasPermission('module:resource:action')") 驗證
```

### 取得當前登入用戶

```java
import static com.newsoft.kingmaker.framework.security.core.util.SecurityFrameworkUtils.getLoginUserId;

Long userId = getLoginUserId();
```

---

## 七、資料庫

- **類型**：PostgreSQL 15
- **連接**：`192.168.29.113:5432`，資料庫 `bk`
- **使用者**：`postgres`
- **Schema 管理**：手動 SQL 檔（`sql/` 目錄），尚未導入 Flyway/Liquibase
- **ORM**：MyBatis Plus，Mapper 繼承 `BaseMapperX`

### 主要 SQL 檔案

| 檔案 | 說明 |
|---|---|
| `sql/kingmaker.sql` | 主要 schema（約 810KB） |
| `sql/quartz.sql` | Quartz 排程器所需表 |
| `sql/basic-table-structure/public.sql` | 基礎表結構 |
| `sql/add_flow_process_instance_id_columns.sql` | 補充 BPM 流程 ID 欄位 |
| `sql/add_ingredient_subcategory_type.sql` | 食材小類型資料 |

---

## 八、Git 分支規範

| 分支 | 說明 |
|---|---|
| `master` | 穩定版本，對應 origin/master |
| `dev` / `dev-tw` | 主要開發分支（台灣開發團隊使用 `dev-tw`） |
| `dev-wilson` | 當前本地工作分支 |
| `feature/{人名}/{功能}` | 功能開發分支（如 `feature/carl/import-excel`） |

**建議工作流**：
1. 從 `dev-tw` 建立 feature branch
2. 開發完成後 PR 回 `dev-tw`
3. 測試通過後合併至 `master`

---

## 九、開發環境設定

### 本地環境需求

- JDK 17（推薦 Eclipse Temurin 或 Azul Zulu）
- Maven 3.8+
- PostgreSQL 15（或可連至 `192.168.29.113:5432`）
- Redis（本地啟動或連至開發環境）

### 配置檔說明

| 檔案 | 用途 |
|---|---|
| `application.yaml` | 通用設定 |
| `application-dev.yaml` | 開發環境設定 |
| `application-local.yaml` | 本地開發設定（優先使用） |

### 啟動指令

```bash
# 編譯（跳過測試）
mvn clean install -DskipTests

# 啟動（使用 local profile）
cd kingmaker-server
mvn spring-boot:run -Dspring-boot.run.profiles=local

# Swagger UI
http://localhost:48080/doc.html
```
