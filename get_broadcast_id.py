#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.exceptions import ClientError, LoginRequired

def get_broadcast_id(client: Client, username: str) -> str:
    """
    嘗試透過 private_request 呼叫 live/{user_id}/info/ 端點，
    如果該帳號正在直播，就回傳 broadcast_id。
    否則結束程式並顯示錯誤訊息。
    """
    try:
        user_id = client.user_id_from_username(username)
    except Exception as e:
        sys.exit(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 無法取得 user_id：{e}")

    endpoint = f"live/{user_id}/info/"

    try:
        data = client.private_request(endpoint)
    except ClientError as e:
        sys.exit(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 抓取直播資訊失敗：{e}")
    except Exception as e:
        sys.exit(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 取得直播資訊例外：{e}")

    # JSON 格式可能為：
    # {
    #   "broadcast_id": "12345678901234567",
    #   "status": "ok",
    #   ...
    # }
    broadcast_id = data.get("broadcast_id") or data.get("broadcast", {}).get("broadcast_id")
    if not broadcast_id:
        sys.exit(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 目前帳號沒有正在直播，無法取得 broadcast_id。")

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 偵測到正在直播，broadcast_id = {broadcast_id}")
    return str(broadcast_id)

def main():
    # 讀取 .env
    load_dotenv()
    IG_USERNAME = os.getenv("INSTAGRAM_USERNAME", "").strip()
    IG_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "").strip()
    SESSION_FILE = "session.json"

    if not IG_USERNAME or not IG_PASSWORD:
        sys.exit("錯誤：請先在 .env 填寫 INSTAGRAM_USERNAME 及 INSTAGRAM_PASSWORD。")

    # 建立 Client
    cl = Client()

    # 嘗試以 session.json 登入
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已載入 {SESSION_FILE}，嘗試使用既有 session 登入…")
            cl.user_id_from_username(IG_USERNAME)  # 驗證 session 是否有效
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Session 驗證成功。")
        except Exception:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] session.json 失效，改用帳密重新登入。")
            try:
                os.remove(SESSION_FILE)
            except OSError:
                pass
            try:
                cl.login(IG_USERNAME, IG_PASSWORD)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已成功登入 Instagram：{IG_USERNAME}")
                cl.dump_settings(SESSION_FILE)
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已將新的 session 寫入 {SESSION_FILE}。")
            except (LoginRequired, ClientError) as e:
                sys.exit(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 登入失敗：{e}")
    else:
        # 若沒有 session.json，就用帳密登入
        try:
            cl.login(IG_USERNAME, IG_PASSWORD)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已成功登入 Instagram：{IG_USERNAME}")
            cl.dump_settings(SESSION_FILE)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已將 session 寫入 {SESSION_FILE}。")
        except (LoginRequired, ClientError) as e:
            sys.exit(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 登入失敗：{e}")

    # 呼叫自訂函式取得 broadcast_id
    get_broadcast_id(cl, IG_USERNAME)

if __name__ == "__main__":
    main()
