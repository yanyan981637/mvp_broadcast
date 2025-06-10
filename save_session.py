#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.mixins.challenge import ChallengeChoice
from instagrapi.exceptions import ClientError

# 載入環境變數
load_dotenv()
IG_USERNAME = os.getenv("INSTAGRAM_USERNAME", "").strip()
IG_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "").strip()
SESSION_FILE = "session.json"

# 確認必要的環境變數已設置
if not IG_USERNAME or not IG_PASSWORD:
    sys.exit("錯誤：請先在 .env 填寫 INSTAGRAM_USERNAME 及 INSTAGRAM_PASSWORD。")

# 挑戰碼處理函式
def challenge_code_handler(username: str, choice: ChallengeChoice) -> str:
    if choice == ChallengeChoice.TWO_FACTOR:
        return input("📱 請輸入 Google Authenticator 6 位數 2FA 驗證碼：").strip()
    elif choice == ChallengeChoice.EMAIL:
        return input("📧 請輸入寄到 Email 的 6 位數驗證碼：").strip()
    elif choice == ChallengeChoice.SMS:
        return input("📲 請輸入手機簡訊的 6 位數驗證碼：").strip()
    return False

# 主流程：使用 Mobile API 登入，注入到 Public Session，再抓取 cookies

def save_session():
    cl = Client()
    cl.challenge_code_handler = challenge_code_handler

    try:
        cl.login(IG_USERNAME, IG_PASSWORD)
    except ClientError as e:
        sys.exit(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 登入失敗：{e}")

    # 持久化設定，包括開發者設定 (Authorization header), 但不含 Web cookies
    cl.dump_settings(SESSION_FILE)
    print("✅ 登入並儲存 session 成功！\n")

    # 把 Private Session 的 sessionid 注入到 Public Session (使 Public Session 擁有 cookies) ([subzeroid.github.io](https://subzeroid.github.io/instagrapi/usage-guide/interactions.html?utm_source=chatgpt.com))
    cl.inject_sessionid_to_public()

    # 掃描 Client 物件所有屬性，搜尋 .cookies 款並取得有效 cookies
    cookie_dict = {}
    for name in dir(cl):
        try:
            attr = getattr(cl, name)
        except Exception:
            continue
        # 找到含 cookies 屬性
        if hasattr(attr, 'cookies'):
            jar = attr.cookies
            if hasattr(jar, 'get_dict'):
                cookies = jar.get_dict()
            else:
                try:
                    cookies = {c.name: c.value for c in jar}
                except Exception:
                    continue
            if cookies:
                print(f"🍪 從屬性 {name}.cookies 擷取到 cookies：")
                cookie_dict = cookies
                break

    if not cookie_dict:
        print("⚠️ 無法在任何屬性中找到有效 cookies！可能因為使用 Authorization header 而非傳統 cookie 方式登入。")
    else:
        print(json.dumps(cookie_dict, indent=2, ensure_ascii=False))
        print("\n📋 關鍵欄位：")
        print(f"  sessionid = {cookie_dict.get('sessionid', '<missing>')}")
        print(f"  csrftoken = {cookie_dict.get('csrftoken', '<missing>')}")
        print(f"  mid       = {cookie_dict.get('mid', '<missing>')}")

    # 顯示 user_agent
    ua = cl.settings.get('user_agent', '<missing UA>')
    print(f"\n🔖 user_agent = {ua}")

if __name__ == '__main__':
    save_session()
