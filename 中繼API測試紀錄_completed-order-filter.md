# BurgerKing 中繼 API 測試紀錄

> 端點：`/api/burgerking/admin/order/completed/filter`
> 整理日期：2026-06-11

---

## 一、需求

模擬 ERP 系統「呼叫中繼(Feign relay)」的方式，直接打上游 BurgerKing API：

| 需求 | 端點 | 參數 |
|------|------|------|
| 取得 4 月資料 | `/api/burgerking/admin/order/completed/filter` | `groupAreaId=3`、`2025-04-01` ~ `2025-04-30` |
| 再用 5 月測試 | 同上 | `groupAreaId=3`、`2025-05-01` ~ `2025-05-31` |
| 診斷 | — | 為何用 Postman 無法得到相同結果 |

---

## 二、系統架構摘要

ERP（Spring Boot / kingmaker）透過 **OpenFeign** 中繼呼叫上游 BurgerKing API：

- **Feign Client**：`BurgerKingStoreClient.java`
  - `@FeignClient(url = "http://61.218.209.215:80/api", configuration = BurgerKingFeignConfig.class)`
  - 目標方法：
    ```java
    @GetMapping("/api/burgerking/admin/order/completed/filter")
    CommonResult<List<StoreSalesStatisticsVO>> getCompletedOrdersFilter(
        @RequestParam @NotNull Integer groupAreaId,
        @RequestParam @NotNull @DateTimeFormat(pattern = "yyyy-MM-dd HH:mm:ss") LocalDateTime startTime,
        @RequestParam @NotNull @DateTimeFormat(pattern = "yyyy-MM-dd HH:mm:ss") LocalDateTime endTime,
        @RequestParam(required = false) Integer storeId);
    ```
- **認證注入**：`BurgerKingFeignConfig.java` 的 `RequestInterceptor` 一律注入上游 BK 的 `Authorization`（忽略本地請求 header，且不帶 tenant-id）。
- **Token 管理**：`BurgerKingTokenManager.java` 自動登入並在記憶體快取 token，從登入回應的 `data.token / data.accessToken / data.access_token` 取出，正規化為 `Bearer <token>`。
- **設定**（`application-dev.yaml` / `application-local.yaml`）：
  ```yaml
  burgerking:
    api:
      base-url: http://61.218.209.215:80
      login-path: /api/api/burgerking/admin/auth/login
    admin:
      username: admin
      password: newsoft
  ```

### ⚠️ 關鍵：雙 `/api` 路徑

因為 Feign 的 `url` 結尾是 `/api`，而 `@GetMapping` 又以 `/api/...` 開頭，串接後實際 URL 為**兩個 api**：

```
http://61.218.209.215:80/api/api/burgerking/admin/order/completed/filter
                          ↑↑↑ 兩個 api
```

登入端點同理：`http://61.218.209.215:80/api/api/burgerking/admin/auth/login`

---

## 三、測試結果

### 環境障礙與處置
- ERP 後端 `http://10.65.163.46/admin-api/system/auth/login` 回傳 **502 Bad Gateway**（Spring Boot 後端已停機）。
- **處置**：辨識出目標端點其實是「上游 BurgerKing API」，直接複製 Feign 的中繼邏輯打 `http://61.218.209.215:80`，繞過已停機的 ERP 後端。

### 登入取得 token
```
POST http://61.218.209.215:80/api/api/burgerking/admin/auth/login
Content-Type: application/json

{"username":"admin","password":"newsoft"}
```
→ token 在回應的 **`data.accessToken`**。

### 4 月（2025-04-01 ~ 2025-04-30）
- 參數：`groupAreaId=3`、`startTime=2025-04-01 00:00:00`、`endTime=2025-04-30 23:59:59`、帶 Bearer token
- 結果：**HTTP 200，`code:0` 成功取得門店銷售統計資料** ✓

### 5 月（2025-05-01 ~ 2025-05-31）
- 結果：**`code:0` 成功，但回傳 0 筆門店**。
- 結論：這是**資料面**狀況（groupAreaId=3 在 5 月確實沒有已完成訂單統計），**並非呼叫失敗**。

---

## 四、為何用 Postman 無法得到相同結果

針對「為何 Postman 拿不到相同結果」，實測重現 4 種情境（均打 `http://61.218.209.215:80`，使用快取 token）：

| # | 情境 | 結果 |
|---|------|------|
| A | **正確**：雙 `/api` + 正確時間格式 + Bearer token | **HTTP 200** ✓ |
| B | 單一 `/api`（`.../api/burgerking/...`） | `{"code":500,"message":"No static resource burgerking/admin/order/completed/filter."}` |
| C | 日期沒帶時分秒（`startTime=2025-04-01`） | `{"code":500,"message":"...Failed to convert ... to required type 'java.time.LocalDateTime'"}` |
| D | 沒帶 Authorization header | `{"code":401,"msg":"账号未登录"}` |

### 失敗主因（對應上表）

1. **路徑少了一個 `/api`（最常見）** → 對應 B
   必須是雙 `/api`：
   ```
   http://61.218.209.215:80/api/api/burgerking/admin/order/completed/filter
   ```

2. **時間格式必須是 `yyyy-MM-dd HH:mm:ss`** → 對應 C
   只給 `2025-04-01`（無時分秒）會轉型失敗；且中間空格要 URL encode 成 `%20`（`startTime=2025-04-01%2000:00:00`）。

3. **Token 來源錯／沒帶** → 對應 D
   - 必須用「上游 BK 登入」取得的 token，**不是 ERP 的 token，也不是程式裡寫死那串（早已過期）**。
   - 登入端點同樣是雙 api，token 在 `data.accessToken`。

### Postman 正確設定

| 項目 | 值 |
|------|-----|
| Method | GET |
| URL | `http://61.218.209.215:80/api/api/burgerking/admin/order/completed/filter` |
| Params: `groupAreaId` | `3` |
| Params: `startTime` | `2025-04-01 00:00:00` |
| Params: `endTime` | `2025-04-30 23:59:59` |
| Header: `Authorization` | `Bearer <上游登入拿的 accessToken>` |

> 注意：5 月回傳 0 筆是資料面問題，不是呼叫錯誤（仍為 `code:0` 成功）。若 Postman 連 4 月都拿到空或報錯，那就是上述 1~3 的設定問題。

---

## 五、相關檔案

| 用途 | 路徑 |
|------|------|
| Feign Client（上游 URL、方法簽章） | `kingmaker-module-pdm/.../client/BurgerKingStoreClient.java` |
| Feign 認證注入設定 | `kingmaker-module-pdm/.../framework/feign/config/BurgerKingFeignConfig.java` |
| Token 管理 | `kingmaker-module-pdm/.../client/token/BurgerKingTokenManager.java` |
| 測試 Controller（呼叫範例） | `kingmaker-module-pdm/.../controller/admin/PdmTestController.java` |
| 設定檔（credentials） | `kingmaker-server/src/main/resources/application-dev.yaml`、`application-local.yaml` |
