# Instagram 直播關鍵字留言監控

本工具可即時監控你的 Instagram 直播聊天室留言，自動偵測符合格式的關鍵字（如「1000+2」），
並將符合條件的留言資訊寫入指定的 CSV 檔案。支援自訂檔名、Session 快速登入、支援多平台（Windows/Mac/Linux）。

---

## 📦 特色功能

* **直播即時監控**：自動輪詢抓取 IG 直播留言，支持高頻率留言。
* **關鍵字自訂格式**：例如「1000+2」可拆分為金額+數量。
* **偵測到關鍵字自動寫入 CSV**：所有資料寫入同一份檔案，直到程式關閉。
* **帳號 session 智慧管理**：Session 檔自動驗證帳號正確與否，無效或異帳號時自動重登。
* **支援自訂 CSV 檔名**：檔案自動加上日期時間+自訂名稱。
* **跨平台**：Windows（雙擊 .bat）、Mac/Linux（.sh/.command）。

---

## 🚀 快速開始

### 1. 安裝環境

**建議先用 Python 3.9+ 建立虛擬環境再安裝：**

```bash
python -m venv venv
source venv/bin/activate  # Windows 請用 venv\Scripts\activate
pip install instagrapi python-dotenv
```

---

### 2. 設定 IG 帳號資訊

在同目錄下建立 `.env` 檔案，內容如下：

```
INSTAGRAM_USERNAME=你的帳號
INSTAGRAM_PASSWORD=你的密碼
BROADCAST_ID=你的直播 broadcast_id
```

---

### 3. 執行程式

#### **互動模式（推薦給新手）：**

```bash
python live_broadcast_keyword.py
```

* 啟動後，依序輸入：最大數量、最多抓幾筆、要寫入的檔案名稱。

#### **或用參數直接啟動：**

```bash
python live_broadcast_keyword.py --max-count 5 --limit 10 --filename 拍賣場次
```

* `--max-count 5`  指留言格式裡數量最大值，例如「1000+5」
* `--limit 10`     表示只抓 10 筆後自動結束，0 則無限制
* `--filename 拍賣場次` 最後會產生如 `20240614_1433_拍賣場次.csv`

---

### 4. **Windows/Mac/Linux 一鍵雙擊啟動**

* **Windows：**
  編輯並儲存下列內容為 `run_live_keyword.bat`

  ```bat
  @echo off
  cd /d %~dp0
  chcp 65001 >nul
  python live_broadcast_keyword.py
  pause
  ```

  然後**雙擊執行即可**。

* **Mac/Linux：**
  編輯並儲存下列內容為 `run_live_keyword.sh`

  ```sh
  #!/bin/bash
  cd "$(dirname "$0")"
  python3 live_broadcast_keyword.py
  read -n 1 -s -r -p "Press any key to continue"
  echo
  ```

  然後在終端機執行 `chmod +x run_live_keyword.sh`，之後**雙擊或用終端機執行**。

* **Mac 專用（推薦）：**
  編輯並儲存為 `run_live_keyword.command`，內容同上。加上執行權限後直接雙擊。

---

### 5. 輸出結果

* 偵測到的關鍵字留言，會自動寫入 `order_information/` 目錄下，檔名格式如：
  `20240614_1433_你的自訂名稱.csv`

---

## 📝 參數說明

| 參數             | 說明                        | 範例              |
| -------------- | ------------------------- | --------------- |
| --max-count    | 關鍵字最大數量，例如 `1000+5` 的 `5` | --max-count 5   |
| --limit        | 最多抓幾筆後自動結束，0 表示無限制        | --limit 10      |
| --filename     | 檔案名稱（會加在日期時間之後）           | --filename 拍賣場次 |
| --mode session | 只驗證登入與取得 session，不進行監控    | --mode session  |

---

## 🔒 session 安全與自動重登

* 程式會自動檢查 session.json 是否對應你的帳號，如不是/過期會自動重登並更新 session。
* 若你更換帳號，建議手動刪除 session.json。

---

## 💡 Q\&A

* **Q: 為什麼會被 IG 登出或 session 過期？**
  A: IG 會定期檢查帳號安全，或跨裝置/異地會自動登出，屬於正常情況。

* **Q: 支援多帳號嗎？**
  A: 預設設計一份 session.json 一個帳號。

* **Q: 監控不到留言怎麼辦？**
  A: 檢查 IG 帳號登入狀態、權限、是否開直播，以及 sleep 間隔是否太長（高頻直播建議 1 秒一次）。
