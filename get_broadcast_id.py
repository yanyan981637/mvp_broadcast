#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.exceptions import TwoFactorRequired, ClientError

load_dotenv()
USERNAME     = os.getenv("INSTAGRAM_USERNAME", "").strip()
PASSWORD     = os.getenv("INSTAGRAM_PASSWORD", "").strip()
SESSION_FILE = "session.json"

if not USERNAME or not PASSWORD:
    sys.exit("錯誤：請先在 .env 填寫 INSTAGRAM_USERNAME 與 INSTAGRAM_PASSWORD。")

# -------------------------------------------------------------------
# 1. 登入並取得 cookies 與 user_agent
# -------------------------------------------------------------------
cl = Client()
try:
    cl.login(USERNAME, PASSWORD)
except TwoFactorRequired:
    code = input("📱 需要二次驗證 (2FA)。請輸入 TOTP 6 碼，或在手機按「允許」後直接按 Enter：").strip()
    try:
        if code:
            cl.login(USERNAME, PASSWORD, verification_code=code)
        else:
            cl.login(USERNAME, PASSWORD)
    except Exception as e:
        sys.exit(f"[{datetime.now():%Y-%m-%d %H:%M:%S'}] 二次驗證後登入失敗：{e}")
except ClientError as e:
    sys.exit(f"[{datetime.now():%Y-%m-%d %H:%M:%S'}] 登入失敗：{e}")

# 儲存 session.json 以便下次使用
try:
    cl.dump_settings(SESSION_FILE)
except Exception:
    pass

# 從 cl.cookie_dict 屬性取得 cookies
cookie_dict = cl.cookie_dict
sessionid  = cookie_dict.get("sessionid", "")
csrftoken  = cookie_dict.get("csrftoken", "")
mid        = cookie_dict.get("mid", "")

# 從 settings 中取得 Instagram App 的 UA
ua = cl.settings.get("user_agent") or cl.base_headers.get("User-Agent", "")

print("✔ 登入成功，取得以下參數：")
print(f"  sessionid = {sessionid}")
print(f"  csrftoken = {csrftoken}")
print(f"  mid       = {mid}")
print(f"  user_agent= {ua}")

# -------------------------------------------------------------------
# 2. 取得 numeric user_id
# -------------------------------------------------------------------
try:
    user_id = cl.user_id_from_username(USERNAME)
except Exception as e:
    sys.exit(f"[{datetime.now():%Y-%m-%d %H:%M:%S'}] 無法取得 user_id：{e}")

# -------------------------------------------------------------------
# 3. 印出等效 curl 命令
# -------------------------------------------------------------------
curl_cmd = f"""curl 'https://i.instagram.com/api/v1/live/{user_id}/info/' \\
  -H 'User-Agent: {ua}' \\
  -H 'Cookie: sessionid={sessionid}; csrftoken={csrftoken}; mid={mid}' \\
  --compressed"""
print("\n📋 等效 curl 命令：")
print(curl_cmd)

# -------------------------------------------------------------------
# 4. 直接呼叫私有 API 並顯示結果
# -------------------------------------------------------------------
endpoint = f"https://i.instagram.com/api/v1/live/{user_id}/info/"
print(f"\n⏳ 正在呼叫：{endpoint}")
resp = requests.get(
    endpoint,
    headers={"User-Agent": ua},
    cookies={"sessionid": sessionid, "csrftoken": csrftoken, "mid": mid},
)
try:
    data = resp.json()
except json.JSONDecodeError:
    sys.exit("❌ 回傳非 JSON，請確認 Cookie 與 User-Agent 是否正確。")

print("— 回傳的完整 JSON：")
print(json.dumps(data, indent=2, ensure_ascii=False))

# -------------------------------------------------------------------
# 5. 解析並顯示 broadcast_id
# -------------------------------------------------------------------
broadcast_id = data.get("broadcast_id") or data.get("broadcast", {}).get("broadcast_id")
if broadcast_id:
    print(f"\n✅ 成功取得 broadcast_id：{broadcast_id}")
else:
    print("\n❌ Broadcast is unavailable（尚未取得 broadcast_id）。")
