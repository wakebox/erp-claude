# PRD：系統管理模組（逆向規格分析）

> 本文件透過逆向分析 `erp-spring/kingmaker-module-system` 程式碼，還原系統管理模組的完整業務規格、資料表設計、ER Model 與功能清單。對應 `excel.md` 中序號 1-11 的 11 個子功能。

---

## Problem Statement

漢堡王 ERP 系統管理模組（系統的基礎建設層）目前缺乏正式規格文件。雖然程式碼已大部分實作，但：

- 11 個子功能（使用者、角色、權限、選單、部門、公告、日誌等）的規格散落在程式碼中
- RBAC（角色基礎存取控制）模型未有完整書面說明
- 資料權限（Data Scope）的 5 種模式運作邏輯未明
- 公告/行銷活動推播的目標對象擴展規則未明
- 操作日誌的自動記錄機制（@ApiAccessLog 攔截器）未文件化
- 新進開發人員或 AI Agent 必須從程式碼逆推所有規則

---

## Solution

產出本 PRD 作為系統管理模組的**權威規格文件**，涵蓋：
1. 完整 ER Model（12 張資料表，含關聯）
2. 每張資料表的欄位清單與說明
3. RBAC 三層權限模型（使用者—角色—選單/資料權限）
4. 5 種 DataScope 資料權限模式
5. 公告推播機制（含 WebSocket 即時推播與部門遞迴展開）
6. 操作日誌的 AOP 攔截原理
7. 所有 API 端點清單與權限碼

---

## User Stories

### 使用者管理（使用者管理）

1. 作為**系統管理員**，我想建立新的使用者帳號，填寫帳號、暱稱、所屬部門、職位、Email、手機、性別、頭像
2. 作為**系統管理員**，我想為新使用者設定初始密碼，系統需以 BCrypt 加密儲存
3. 作為**系統管理員**，我想更新使用者基本資料，但帳號（username）不可更改
4. 作為**系統管理員**，我想刪除使用者（軟刪除），系統需同步清理其 UserRole 關聯
5. 作為**系統管理員**，我想重設使用者密碼，無需知道原密碼
6. 作為**系統管理員**，我想啟用或停用使用者，停用後該帳號不可登入
7. 作為**系統管理員**，我想分頁查詢使用者，按帳號、暱稱、部門、狀態篩選
8. 作為**任何已登入使用者**，我想取得啟用中的使用者簡單清單（`/list-all-simple`），無需查詢權限，用於下拉選單
9. 作為**系統管理員**，我想匯出使用者清單為 Excel
10. 作為**系統管理員**，我想下載匯入範本（`/get-import-template`）
11. 作為**系統管理員**，我想批次匯入使用者，並選擇是否覆蓋既有資料
12. 作為**使用者**，我想更新自己的個人資料（暱稱、Email、手機、頭像）
13. 作為**使用者**，我想修改自己的密碼，需驗證原密碼

### 角色管理（角色匯出）

14. 作為**系統管理員**，我想建立角色，填寫名稱、代碼、排序、狀態、備註
15. 作為**系統管理員**，我想區分**系統內建角色（SYSTEM）**與**自訂角色（CUSTOM）**，內建角色不可刪除
16. 作為**系統管理員**，我想更新角色，但其代碼（code）需保持唯一
17. 作為**系統管理員**，我想刪除角色，系統需同步清理 RoleMenu、UserRole 關聯
18. 作為**系統管理員**，我想分頁查詢角色，按名稱、代碼、狀態篩選
19. 作為**系統管理員**，我想匯出角色清單為 Excel，並透過 `@ApiAccessLog(EXPORT)` 自動記錄稽核軌跡
20. 作為**任何已登入使用者**，我想取得啟用中的角色簡單清單，用於設定使用者角色

### 設定角色選單權限（設定角色選單權限）

21. 作為**系統管理員**，我想查詢某個角色已綁定的選單 ID 清單（`/list-role-menus`）
22. 作為**系統管理員**，我想將一組選單指派給某個角色（`/assign-role-menu`），系統需先清除舊綁定再批次新增
23. 作為**系統管理員**，我想看到指派完成後快取（`MENU_ROLE_ID_LIST`、`PERMISSION_MENU_ID_LIST`）自動失效
24. 作為**使用者**，我想登入後透過 `/system/auth/get-permission-info` 取得我可見的選單樹

### 設定角色資料權限（設定角色資料權限）

25. 作為**系統管理員**，我想為角色設定五種**資料權限範圍（DataScope）**之一：
    - `ALL=1` 全部資料
    - `DEPT_CUSTOM=2` 指定部門資料
    - `DEPT_ONLY=3` 本部門資料
    - `DEPT_AND_CHILD=4` 本部門及子部門
    - `SELF=5` 僅本人資料
26. 作為**系統管理員**，當選擇 `DEPT_CUSTOM` 時，我想額外指定 `dataScopeDeptIds` 部門清單
27. 作為**系統**，當使用者查詢資料時，需依其角色的 DataScope 自動加上 WHERE 條件過濾

### 設定使用者角色（設定使用者角色）

28. 作為**系統管理員**，我想查詢某個使用者已綁定的角色 ID 清單（`/list-user-roles`）
29. 作為**系統管理員**，我想將一組角色指派給某個使用者（`/assign-user-role`），系統需先清除舊綁定再批次新增
30. 作為**系統管理員**，我想看到指派完成後使用者的角色快取自動失效，下次查詢時即時生效

### 選單管理（選單管理）

31. 作為**系統管理員**，我想建立**目錄（DIR=1）**選單，作為父節點
32. 作為**系統管理員**，我想建立**選單（MENU=2）**，綁定到目錄下，填寫 path、component、icon
33. 作為**系統管理員**，我想建立**按鈕（BUTTON=3）**，綁定到選單下，填寫 permission 字串（格式：`module:resource:action`）
34. 作為**系統管理員**，我想設定選單的 `visible`、`keepAlive`、`alwaysShow` 等前端顯示行為
35. 作為**系統管理員**，我想為選單設定**單號生成規則**：`signCodePrefix`（前綴）+ `format`（日期格式）+ `serialNumberLength`（流水號長度）
36. 作為**系統管理員**，我想為選單**綁定 BPM 工作流**（`flowIsOpen`、`flowKey`），業務 Service 會據此判斷是否發起 Flowable 流程
37. 作為**系統**，我想透過 `/get-by-flow-key` 反查綁定某 flowKey 的選單，用於 BPM 監聽器
38. 作為**業務模組**，我想透過 `/get-generateSignCode?functionName=xxx` 取得下一個業務單號

### 部門管理（部門管理）

39. 作為**系統管理員**，我想建立部門，填寫名稱、父部門、部門主管、電話、Email、排序、狀態
40. 作為**系統管理員**，我想構建**部門樹**，以 `parentId=0` 為根，遞迴展開
41. 作為**系統管理員**，我想為部門指派**主管使用者（leaderUserId）**
42. 作為**系統管理員**，我想刪除部門，系統需檢查：
    - 該部門無子部門
    - 該部門無使用者
43. 作為**系統**，我想透過快取機制（`getChildDeptIdListFromCache`）取得某部門及所有子部門的 ID 清單，供 DataScope 過濾使用

### 公告維護（公告維護）

44. 作為**系統管理員**，我想建立公告，分為 3 種類型：
    - `NOTICE=1` 一般公告
    - `ANNOUNCEMENT=2` 通知
    - `MARKETING=3` 行銷活動公告
45. 作為**系統管理員**，我想填寫公告標題（≤50 字）、內容、狀態
46. 作為**系統管理員**，我想分頁查詢公告，按標題、類型、狀態篩選
47. 作為**系統管理員**，我想透過 `/push` 端點將公告**透過 WebSocket 即時推播**給所有當前在線使用者
48. 作為**使用者**，我想透過 `/my-page` 端點查詢屬於我的公告清單
49. 作為**訪客**，我想透過 `/page-Nosec`、`/get-Nosec` 取得公告清單，不需要權限

### 行銷活動公告（行銷活動公告）

50. 作為**行銷人員**，我想建立 `type=MARKETING` 的公告，並指定收件人：
    - `deptIds`：發送給指定部門的所有使用者（會遞迴展開子部門）
    - `userIds`：直接發送給指定使用者
    - 兩者可同時使用（聯集）
51. 作為**系統**，當行銷公告儲存時，需將每個收件人寫入 `system_notice_user` 表，含 `readStatus=0`（未讀）
52. 作為**使用者**，我想在 `/my-page` 看到：
    - 所有 `非 MARKETING` 類型的公告（全員可見）
    - 加上 `MARKETING` 類型且 `NoticeUser` 表中有我的記錄的公告
53. 作為**系統**，當行銷公告被更新時，需先刪除舊的 `NoticeUser` 記錄，再依新的 `deptIds`、`userIds` 重新建立

### 操作日誌（操作日誌）

54. 作為**稽核人員**，我想分頁查詢操作日誌，按使用者、模組、名稱、操作類型、狀態、時間區間篩選
55. 作為**稽核人員**，我想看到每筆日誌的：使用者、IP、瀏覽器、HTTP 方法、URL、請求參數、回應、執行時間（ms）、狀態（成功/失敗）、錯誤訊息
56. 作為**稽核人員**，我想匯出操作日誌為 Excel
57. 作為**系統**，我想透過 `@ApiAccessLog` 註解 + AOP 攔截器**自動記錄**所有 Controller 方法的操作：
    - 模組名稱從 `@Tag` 取
    - 操作名稱從 `@Operation.summary` 取
    - 操作類型由 `@ApiAccessLog(operateType=EXPORT/CREATE/UPDATE/DELETE/QUERY/LOGIN)` 指定
58. 作為**系統**，我想透過 `sanitizeKeys` 屏蔽敏感欄位（如密碼、token）
59. 作為**系統**，當 Controller 拋出例外時，需將 `status=1`、`errorMsg` 寫入日誌

### 登入日誌（登入日誌）

60. 作為**稽核人員**，我想分頁查詢登入日誌，按使用者、帳號、IP、狀態、時間區間篩選
61. 作為**稽核人員**，我想看到每筆日誌的：帳號、IP、登入地點、瀏覽器、作業系統、登入結果、訊息、登入/登出時間、停留時長
62. 作為**稽核人員**，我想看到登入失敗原因：
    - `SUCCESS=0` 成功
    - `BAD_CREDENTIALS=10` 帳密錯誤
    - `USER_DISABLED=20` 使用者已停用
    - `CAPTCHA_NOT_FOUND=30` 驗證碼不存在
    - `CAPTCHA_CODE_ERROR=31` 驗證碼錯誤
63. 作為**稽核人員**，我想匯出登入日誌為 Excel
64. 作為**系統**，當 `/system/auth/login` 被呼叫時，需自動記錄 `LOGIN_USERNAME=100` 或 `LOGIN_SMS=104` 等類型
65. 作為**系統**，當 `/system/auth/logout` 被呼叫時，需記錄 `LOGOUT_SELF=200`；管理員強制登出記錄 `LOGOUT_DELETE=202`

### 認證與授權

66. 作為**訪客**，我想透過 `/system/auth/login` 以帳號密碼登入，取得 accessToken 與 refreshToken
67. 作為**訪客**，我想透過 `/system/auth/sms-login` 以手機 + 簡訊碼登入
68. 作為**訪客**，我想透過 `/system/auth/social-login` 以社交帳號（OAuth）登入
69. 作為**使用者**，我想透過 `/system/auth/refresh-token` 在 accessToken 過期前以 refreshToken 續期
70. 作為**已登入使用者**，我想透過 `/system/auth/get-permission-info` 取得：
    - 我的基本資料（id、暱稱、頭像、部門、區域、門市）
    - 我的角色代碼清單
    - 我的權限碼清單（如 `system:user:create`）
    - 我可見的選單樹（含 path、component、icon 等）
71. 作為**訪客**，我想透過 `/system/auth/reset-password` 以簡訊驗證重設密碼

---

## Implementation Decisions

### 模組架構

採用 **kingmaker-module-system** 模組（`-api` 與 `-biz` 兩層）：
- `-api`：對外介面、DTO、Enum（給其他模組依賴）
- `-biz`：DO、Controller、Service、Mapper

### 資料表清單（12 張）

| 序號 | 資料表 | 對應功能 |
|------|--------|---------|
| 1 | `system_users` | 使用者主檔（AdminUserDO） |
| 2 | `system_role` | 角色主檔（RoleDO） |
| 3 | `system_menu` | 選單主檔（MenuDO） |
| 4 | `system_dept` | 部門主檔（DeptDO） |
| 5 | `system_post` | 職位主檔（PostDO） |
| 6 | `system_user_role` | 使用者—角色關聯（UserRoleDO） |
| 7 | `system_role_menu` | 角色—選單關聯（RoleMenuDO） |
| 8 | `system_user_post` | 使用者—職位關聯（UserPostDO） |
| 9 | `system_user_store` | 使用者—門市關聯（UserStoreDO） |
| 10 | `system_notice` | 公告主檔（NoticeDO） |
| 11 | `system_notice_user` | 公告—收件人關聯（NoticeUserDO） |
| 12 | `system_operate_log` | 操作日誌（OperateLogDO） |
| 13 | `system_login_log` | 登入日誌（LoginLogDO） |

---

### ER Model（文字描述）

```
RBAC 核心三角關係：
  AdminUserDO (1) ──< UserRoleDO >── (1) RoleDO
  RoleDO (1) ──< RoleMenuDO >── (1) MenuDO
  ⇒ 使用者透過角色取得選單與權限

組織結構：
  DeptDO (1) ──parentId─< DeptDO (自參考，樹狀)
  DeptDO (1) ──< AdminUserDO (deptId FK)
  DeptDO (1) ──leaderUserId─> AdminUserDO (1)

職位關聯：
  AdminUserDO (1) ──< UserPostDO >── (1) PostDO

門市資料權限：
  AdminUserDO (1) ──< UserStoreDO >── (1) StoreDO (外部)

選單階層：
  MenuDO (1) ──parentId─< MenuDO (自參考，樹狀)
  MenuDO (1) ── flowKey ─> BPM 流程定義（邏輯關聯）

資料權限（內嵌於 RoleDO）：
  RoleDO.dataScope (Integer)
  RoleDO.dataScopeDeptIds (Set<Long>, JSON 欄位)
  ⇒ 透過 @DataPermission AOP + MyBatis 攔截器注入 WHERE 條件

公告與推播：
  NoticeDO (1) ──< NoticeUserDO >── (1) AdminUserDO
  ⇒ 僅 MARKETING 類型需要 NoticeUserDO 記錄
  ⇒ 一般公告全員可見，不需 NoticeUserDO

日誌獨立表（無 FK）：
  OperateLogDO.userId 邏輯指向 AdminUserDO.id
  LoginLogDO.userId 邏輯指向 AdminUserDO.id
```

---

### 資料表詳細規格

#### 1. `system_users`（使用者主檔）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵（序列 `system_users_seq`） |
| username | VARCHAR | 帳號（唯一） |
| password | VARCHAR | 密碼（BCrypt 加密） |
| nickname | VARCHAR | 暱稱 |
| remark | VARCHAR | 備註 |
| dept_id | BIGINT FK→system_dept | 所屬部門 |
| post_ids | JSON | 職位 ID 集合（`@JacksonTypeHandler`） |
| email | VARCHAR | 電子郵件 |
| mobile | VARCHAR | 手機 |
| sex | INT | 性別（SexEnum：1=男、2=女、0=未知） |
| avatar | VARCHAR | 頭像 URL |
| status | INT | 狀態（0=啟用、1=停用） |
| login_ip | VARCHAR | 最後登入 IP |
| login_date | TIMESTAMP | 最後登入時間 |
| + TenantBaseDO 欄位 | | tenant_id, deleted, creator, create_time, updater, update_time |

#### 2. `system_role`（角色主檔）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| name | VARCHAR | 角色名稱 |
| code | VARCHAR | 角色代碼（唯一） |
| sort | INT | 排序 |
| status | INT | 狀態（CommonStatusEnum） |
| type | INT | 類型（RoleTypeEnum：1=系統、2=自訂） |
| remark | VARCHAR | 備註 |
| data_scope | INT | 資料權限（DataScopeEnum：1-5） |
| data_scope_dept_ids | JSON | 自訂部門 ID 集合 |
| + TenantBaseDO 欄位 | | |

#### 3. `system_menu`（選單主檔）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵（根節點 = 0L） |
| name | VARCHAR | 選單名稱 |
| permission | VARCHAR | 權限碼（如 `system:user:create`） |
| type | INT | 類型（MenuTypeEnum：1=目錄、2=選單、3=按鈕） |
| sort | INT | 排序 |
| parent_id | BIGINT FK→self | 父選單 ID |
| path | VARCHAR | 路由路徑（可為外部 URL） |
| icon | VARCHAR | 圖示 |
| component | VARCHAR | 元件路徑 |
| component_name | VARCHAR | 元件名稱 |
| status | INT | 狀態（CommonStatusEnum） |
| visible | BOOLEAN | 側邊欄是否顯示 |
| keep_alive | BOOLEAN | Vue route keep-alive |
| always_show | BOOLEAN | 只有單一子節點時是否仍顯示為目錄 |
| page_url | VARCHAR | 清單頁 URL |
| sign_code_prefix | VARCHAR | 單號前綴 |
| current_sign_code | VARCHAR | 當前單號 |
| format | VARCHAR | 日期格式（如 "yyMMdd"） |
| serial_number_length | INT | 流水號長度 |
| flow_is_open | INT | 工作流啟用旗標 |
| flow_key | VARCHAR | Flowable 流程 Key |
| + BaseDO 欄位 | | |

#### 4. `system_dept`（部門主檔）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵（根 = 0L） |
| name | VARCHAR | 部門名稱 |
| parent_id | BIGINT FK→self | 父部門 |
| sort | INT | 排序 |
| leader_user_id | BIGINT FK→system_users | 部門主管 |
| phone | VARCHAR | 電話 |
| email | VARCHAR | Email |
| status | INT | 狀態 |
| + TenantBaseDO 欄位 | | |

#### 5. `system_post`（職位主檔）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| name | VARCHAR | 職位名稱 |
| code | VARCHAR | 職位代碼 |
| sort | INT | 排序 |
| status | INT | 狀態 |
| remark | VARCHAR | 備註 |

#### 6. `system_user_role`（使用者—角色關聯）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| user_id | BIGINT FK→system_users | 使用者 ID |
| role_id | BIGINT FK→system_role | 角色 ID |

#### 7. `system_role_menu`（角色—選單關聯）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| role_id | BIGINT FK→system_role | 角色 ID |
| menu_id | BIGINT FK→system_menu | 選單 ID |
| + TenantBaseDO 欄位 | | |

#### 8. `system_user_post`（使用者—職位關聯）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| user_id | BIGINT FK→system_users | 使用者 ID |
| post_id | BIGINT FK→system_post | 職位 ID |

#### 9. `system_user_store`（使用者—門市關聯）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| user_id | BIGINT FK→system_users | 使用者 ID |
| store_id | BIGINT | 門市 ID（外部系統） |

#### 10. `system_notice`（公告主檔）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| title | VARCHAR(50) | 標題 |
| type | INT | 類型（NoticeTypeEnum：1=公告、2=通知、3=行銷） |
| content | TEXT | 內容 |
| status | INT | 狀態 |
| + BaseDO 欄位 | | |

#### 11. `system_notice_user`（公告—收件人關聯）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| notice_id | BIGINT FK→system_notice | 公告 ID |
| user_id | BIGINT FK→system_users | 收件人 ID |
| read_status | BOOLEAN | 0=未讀、1=已讀 |

#### 12. `system_operate_log`（操作日誌）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| trace_id | VARCHAR | 分散式追蹤 ID |
| user_id | BIGINT | 操作者 ID（邏輯 FK） |
| user_type | INT | 使用者類型（UserTypeEnum） |
| type | VARCHAR | 操作模組類型 |
| sub_type | VARCHAR | 操作名稱 |
| biz_id | BIGINT | 業務物件 ID |
| action | TEXT | 詳細操作描述（人類可讀） |
| extra | TEXT | 擴充欄位（JSON） |
| request_method | VARCHAR | HTTP 方法 |
| request_url | VARCHAR | URL |
| user_ip | VARCHAR | IP |
| user_agent | VARCHAR | 瀏覽器 UA |

#### 13. `system_login_log`（登入日誌）
| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGINT PK | 主鍵 |
| log_type | INT | 類型（LoginLogTypeEnum：100/101/103/104/200/202） |
| trace_id | VARCHAR | 分散式追蹤 ID |
| user_id | BIGINT | 使用者 ID |
| user_type | INT | 使用者類型 |
| username | VARCHAR | 帳號（冗餘儲存，因 username 可改） |
| result | INT | 結果（LoginResultEnum：0/10/20/30/31） |
| user_ip | VARCHAR | IP |
| user_agent | VARCHAR | UA |

---

### 枚舉清單

| 枚舉 | 值 | 用途 |
|------|------|------|
| `CommonStatusEnum` | ENABLE=0、DISABLE=1 | 通用狀態 |
| `SexEnum` | MALE=1、FEMALE=2、UNKNOWN=0 | 性別 |
| `MenuTypeEnum` | DIR=1、MENU=2、BUTTON=3 | 選單類型 |
| `RoleTypeEnum` | SYSTEM=1、CUSTOM=2 | 角色類型 |
| `DataScopeEnum` | ALL=1、DEPT_CUSTOM=2、DEPT_ONLY=3、DEPT_AND_CHILD=4、SELF=5 | 資料權限範圍 |
| `NoticeTypeEnum` | NOTICE=1、ANNOUNCEMENT=2、MARKETING=3 | 公告類型 |
| `LoginLogTypeEnum` | LOGIN_USERNAME=100、LOGIN_SOCIAL=101、LOGIN_MOBILE=103、LOGIN_SMS=104、LOGOUT_SELF=200、LOGOUT_DELETE=202 | 登入日誌類型 |
| `LoginResultEnum` | SUCCESS=0、BAD_CREDENTIALS=10、USER_DISABLED=20、CAPTCHA_NOT_FOUND=30、CAPTCHA_CODE_ERROR=31 | 登入結果 |

---

### API 端點清單

| 控制器 | 方法 | 路徑 | 權限碼 |
|--------|------|------|--------|
| **UserController** | POST | /system/user/create | system:user:create |
| | PUT | /system/user/update | system:user:update |
| | DELETE | /system/user/delete | system:user:delete |
| | PUT | /system/user/update-password | system:user:update-password |
| | PUT | /system/user/update-status | system:user:update |
| | GET | /system/user/page | system:user:query |
| | GET | /system/user/list-all-simple | 公開 |
| | GET | /system/user/get | system:user:query |
| | GET | /system/user/export | system:user:export |
| | GET | /system/user/get-import-template | 公開 |
| | POST | /system/user/import | system:user:import |
| **RoleController** | POST | /system/role/create | system:role:create |
| | PUT | /system/role/update | system:role:update |
| | DELETE | /system/role/delete | system:role:delete |
| | GET | /system/role/get | system:role:query |
| | GET | /system/role/page | system:role:query |
| | GET | /system/role/list-all-simple | 公開 |
| | GET | /system/role/export-excel | system:role:export |
| **PermissionController** | GET | /system/permission/list-role-menus | system:permission:assign-role-menu |
| | POST | /system/permission/assign-role-menu | system:permission:assign-role-menu |
| | POST | /system/permission/assign-role-data-scope | system:permission:assign-role-data-scope |
| | GET | /system/permission/list-user-roles | system:permission:assign-user-role |
| | POST | /system/permission/assign-user-role | system:permission:assign-user-role |
| **MenuController** | POST | /system/menu/create | system:menu:create |
| | PUT | /system/menu/update | system:menu:update |
| | PUT | /system/menu/update-flow | system:menu:update |
| | DELETE | /system/menu/delete | system:menu:delete |
| | GET | /system/menu/list | system:menu:query |
| | GET | /system/menu/list-all-simple | 公開 |
| | GET | /system/menu/get | system:menu:query |
| | GET | /system/menu/get-by-flow-key | 公開 |
| | GET | /system/menu/get-generateSignCode | 公開 |
| **DeptController** | POST | /system/dept/create | system:dept:create |
| | PUT | /system/dept/update | system:dept:update |
| | DELETE | /system/dept/delete | system:dept:delete |
| | GET | /system/dept/list | system:dept:query |
| | GET | /system/dept/list-all-simple | 公開 |
| | GET | /system/dept/get | system:dept:query |
| **NoticeController** | POST | /system/notice/create | system:notice:create |
| | PUT | /system/notice/update | system:notice:update |
| | DELETE | /system/notice/delete | system:notice:delete |
| | GET | /system/notice/page | system:notice:query |
| | GET | /system/notice/get | system:notice:query |
| | POST | /system/notice/push | system:notice:update |
| | GET | /system/notice/page-Nosec | 公開 |
| | GET | /system/notice/get-Nosec | 公開 |
| | GET | /system/notice/my-page | 公開 |
| **OperateLogController** | GET | /system/operate-log/page | system:operate-log:query |
| | GET | /system/operate-log/export | system:operate-log:export |
| **LoginLogController** | GET | /system/login-log/page | system:login-log:query |
| | GET | /system/login-log/export | system:login-log:export |
| **AuthController** | POST | /system/auth/login | 公開 |
| | POST | /system/auth/logout | 公開 |
| | POST | /system/auth/refresh-token | 公開 |
| | GET | /system/auth/get-permission-info | 已登入 |
| | POST | /system/auth/register | 公開 |
| | POST | /system/auth/sms-login | 公開 |
| | POST | /system/auth/send-sms-code | 公開 |
| | POST | /system/auth/reset-password | 公開 |
| | GET | /system/auth/social-auth-redirect | 公開 |
| | POST | /system/auth/social-login | 公開 |

---

### 核心機制設計

#### A. 權限檢查機制（@PreAuthorize）

```
@PreAuthorize("@ss.hasPermission('system:user:create')")
            │
            ▼ Spring Security SpEL 求值
@ss 是 PermissionService 的 Bean 別名
            │
            ▼ PermissionService.hasAnyPermissions(userId, permission)
1. 取使用者啟用中的角色清單（從快取）
2. 取權限對應的選單 ID 清單（MenuService.getMenuIdListByPermissionFromCache）
3. 取每個選單對應的角色 ID 清單（PermissionService.getMenuRoleIdListByMenuIdFromCache）
4. 取交集 → 有交集則授權
5. 額外檢查：若使用者是超級管理員（RoleService.hasAnySuperAdmin）→ 直接授權
```

#### B. 資料權限機制（@DataPermission）

```
@DataPermission(enable = true, includeRules = {DeptDataPermissionRule.class})
public List<XxxDO> getList(...) { ... }
            │
            ▼ DataPermissionAnnotationInterceptor (AOP)
1. 將註解推入 DataPermissionContextHolder 堆疊
2. 呼叫業務方法
            │
            ▼ MyBatis 攔截器（Query Plugin）
1. 偵測到當前堆疊有 @DataPermission
2. 取使用者目前角色的 dataScope + dataScopeDeptIds
3. 依 DataScopeEnum 動態組裝 WHERE 子句：
   - ALL：不加條件
   - DEPT_CUSTOM：WHERE dept_id IN (dataScopeDeptIds)
   - DEPT_ONLY：WHERE dept_id = user.deptId
   - DEPT_AND_CHILD：WHERE dept_id IN (user.deptId + 所有子部門)
   - SELF：WHERE creator = user.id
4. 注入原始 SQL，執行
```

#### C. 操作日誌自動記錄

```
Controller 方法上加註解：
@GetMapping("/export")
@ApiAccessLog(operateType = EXPORT, sanitizeKeys = {"password"})
public void exportUserList(...) { ... }
            │
            ▼ ApiAccessLogFilter (Filter)
1. 攔截 request，啟動 StopWatch
2. 從 HandlerMethod 讀取 @ApiAccessLog
3. 從類別 @Tag 取 module，從方法 @Operation.summary 取 name
4. 執行 Controller 方法
5. 若拋例外，捕捉 errorMsg，status=1；否則 status=0
6. 組裝 OperateLogCreateReqDTO（含 sanitize 過的請求參數）
7. 呼叫 OperateLogService.createOperateLog(dto) → 寫入 system_operate_log
```

#### D. 公告推播機制

```
管理員建立 MARKETING 公告（含 deptIds + userIds）
            │
            ▼ NoticeServiceImpl.createNotice
1. 寫入 system_notice
2. 若 type = MARKETING，呼叫 saveNoticeUsers(noticeId, deptIds, userIds)
            │
            ▼ saveNoticeUsers
1. 遞迴展開 deptIds → 取所有子部門 ID
2. 透過 AdminUserService.getUserListByDeptIds 取得使用者
3. 加上明確指定的 userIds（聯集去重）
4. 批次寫入 system_notice_user (每筆 read_status=0)

管理員按下「推播」按鈕：
            │
            ▼ NoticeController.push
1. webSocketSenderApi.sendObject(ADMIN, "notice-push", notice)
2. WebSocket Server 廣播給目前所有在線連線
3. 前端收到 notice-push 訊息，彈出公告

使用者查詢 /my-page：
1. 查 system_notice WHERE type != MARKETING (全員可見公告)
2. UNION 查 system_notice WHERE id IN (
     SELECT notice_id FROM system_notice_user WHERE user_id = me
   )
3. 依 createTime DESC 排序、分頁
```

---

### 取得登入後權限資訊的演算法

```
GET /system/auth/get-permission-info
            │
            ▼ AuthController.getPermissionInfo
1. AdminUserService.getUser(userId) → 取使用者資料
2. PermissionService.getUserRoleIdListByUserId(userId) → 取角色 ID
3. RoleService.getRoleList(roleIds) → 取角色物件，過濾停用
4. 收集 roles[] (角色代碼清單)
5. PermissionService.getRoleMenuListByRoleId(activeRoleIds) → 取選單 ID
6. MenuService.getMenuList(menuIds) → 取選單物件
7. MenuService.filterDisableMenus(menus) → 遞迴過濾停用選單
8. 拆分 permissions[]（型別=BUTTON 的 permission 欄位）
9. 構建 menus[]（型別=DIR/MENU，依 parentId 樹狀化）
10. UserStoreMapper.getUserStoreByUserId → 取門市資料
11. 回傳：{ user, roles, permissions, menus }
```

---

## Testing Decisions

**好的測試定義：** 只驗證外部行為（API 回應、權限決策結果），不測試 AOP 攔截器內部實作細節。

**目前測試方式：** 無自動化測試，依賴 Swagger UI 與前端整合測試手動驗證。

**建議優先測試模組（若加入自動化測試）：**

1. **PermissionService.hasAnyPermissions（最關鍵）**
   - 輸入：使用者 ID、權限碼
   - 期望：依角色—選單對應正確回傳 true/false
   - 涵蓋場景：未授權、單一角色授權、多角色授權、超級管理員、停用角色
   - 理由：所有 API 安全皆依賴此方法

2. **DataPermissionRule 5 種模式**
   - 各模式（ALL/DEPT_CUSTOM/DEPT_ONLY/DEPT_AND_CHILD/SELF）皆需驗證注入的 WHERE 條件
   - 理由：資料外洩風險最高的層

3. **NoticeService.saveNoticeUsers**
   - 驗證部門遞迴展開正確
   - 驗證 userIds 與 deptIds 使用者去重
   - 理由：行銷活動範圍若錯誤會誤發/漏發

4. **AdminAuthService.login**
   - 驗證 BAD_CREDENTIALS、USER_DISABLED、CAPTCHA_CODE_ERROR 路徑皆寫入正確 LoginLog
   - 理由：稽核合規必備

5. **MenuService.filterDisableMenus**
   - 驗證停用父選單後子選單也被過濾
   - 理由：影響使用者登入後可見功能

---

## Out of Scope

1. **BHM 模組**：凍結，不在本 PRD 範圍
2. **租戶管理（Tenant）**：屬於框架層 starter（kingmaker-spring-boot-starter-biz-tenant），非系統管理模組功能
3. **前端 UI 實作細節**：本 PRD 僅規範後端 API 合約
4. **驗證碼產生機制**：屬於 infra 模組
5. **檔案上傳（avatar 等）**：屬於 infra 模組
6. **WebSocket Server 設定細節**：屬於框架層

---

## Further Notes

### 與其他模組的整合

- **BPM 模組**：MenuDO 的 `flowKey` 欄位連結 Flowable 流程定義；業務模組透過 `MenuFlowProcessInstanceHelper.createProcessInstanceIfFlowOpen(userId, menu.getFlowpath(), recordId)` 啟動流程
- **業務模組（PDM/WHS/PMM）**：透過 `MenuService.generateSignCode(functionName)` 取得業務單號
- **API Module（system-api）**：對外暴露 `AdminUserApi`、`DeptApi`、`PermissionApi` 等介面供其他 module 依賴

### 多租戶與軟刪除

- 所有資料表均支援軟刪除（`deleted` 欄位 + `@TableLogic`）
- 部分資料表支援多租戶（`tenant_id`，自動由 MyBatis Plus 注入）
- 例外：`MenuDO`、`PostDO`、`OperateLogDO`、`LoginLogDO` 為 BaseDO（無 tenant_id）

### 快取設計

PermissionService 使用 Spring Cache：
- `@Cacheable(MENU_ROLE_ID_LIST)`：選單→角色 IDs（用於權限檢查）
- `@Cacheable(PERMISSION_MENU_ID_LIST)`：權限碼→選單 IDs
- `@Cacheable(USER_ROLE_ID_LIST)`：使用者→角色 IDs
- 任何 RoleMenu、UserRole 變更皆透過 `@CacheEvict` 即時失效

DeptService 使用 `@Cacheable(DEPT_CHILDREN_ID_LIST)` 快取子部門遞迴結果。

### 命名規範觀察

- 表名前綴一律 `system_`
- DTO 命名：請求 `XxxReqVO` / `XxxReqDTO`、回應 `XxxRespVO` / `XxxRespDTO`
- 簡單查詢用 `XxxSimpleRespVO`（資料量小，僅供下拉選單）
- 權限碼三段式：`${module}:${resource}:${action}`，如 `system:user:export`

### 已知限制

- 操作日誌（system_operate_log）不分租戶，所有租戶共用，可能造成查詢效能下降
- 公告推播（WebSocket）只能送到「目前在線」的使用者，離線者無法收到即時推送（仍可在 `/my-page` 看到）
- DataScope 僅支援部門維度，無法依「門市」或「區域」過濾（門市維度透過 `system_user_store` 另行管理）
