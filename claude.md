
# 產生程式碼，參考以下相關的路徑


參考以下路徑

# OA Source code path

/data/newprooa

# ERP backend code path
/data/burgerking/erp-spring

# ERP frontend code path
/data/burgerking/erp-kingmaker

# myclaude 
/data/erp-claude

# seeder 來源資料庫
10.65.163.46
postgres
account: postgres
password: Newsoft_0255



# laravel PHP 遵守原則
採用 clean architecture 原則，遵循 SOLID 原則，確保程式碼可維護性與可擴展性。

使用 Laravel 的 Eloquent ORM 來處理資料庫操作，確保資料庫交互的簡潔和高效。

商業邏輯分離 實做於 servce ,使用 model , repository 處理資料庫

model 用中文解釋欄位名稱，確保程式碼的可讀性和易於理解。

model 用中文解釋欄位名稱，確保程式碼的可讀性和易於理解。
使用最少的程式達成功能，決不額外寫不需要的程式

controller 是否有遵守 MVC 原則，controller 絕不處理資料庫，商業邏輯