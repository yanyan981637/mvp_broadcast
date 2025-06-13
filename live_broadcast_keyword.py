#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import time
import json
import csv
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.mixins.challenge import ChallengeChoice
from instagrapi.exceptions import ClientError, LoginRequired

# 1. 讀取 .env
load_dotenv()
IG_USERNAME = os.getenv("INSTAGRAM_USERNAME", "").strip()
IG_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "").strip()
BROADCAST_ID = os.getenv("BROADCAST_ID", "").strip()
SESSION_FILE = "session.json"

if not IG_USERNAME or not IG_PASSWORD:
    sys.exit("錯誤：請先在 .env 填寫 INSTAGRAM_USERNAME 及 INSTAGRAM_PASSWORD。")

# 2. 挑戰驗證處理（2FA、Email、SMS）
def challenge_code_handler(username: str, choice):
    print("⚠️ IG 檢測到這次登入需要進行驗證，請依照下方提示輸入驗證碼。")
    c = str(choice).lower()
    if "two" in c or "totp" in c or "app" in c:
        return input("📱 請輸入 Google Authenticator 6 位數 2FA 驗證碼：").strip()
    elif "email" in c:
        return input("📧 請輸入寄到 Email 的 6 位數驗證碼：").strip()
    elif "sms" in c or "phone" in c:
        return input("📲 請輸入手機簡訊的 6 位數驗證碼：").strip()
    else:
        print(f"收到未知的驗證方式 {choice}，請查看 instagrapi 文件或升級。")
        return input("請手動輸入收到的驗證碼：").strip()

# 3. 關鍵字正則
PATTERN = re.compile(r"""
    (?P<amount>\d+)
    [\s,]*\+
    (?P<count>\d+)
""", re.VERBOSE)

def match_keyword(text: str, max_count: int):
    m = PATTERN.search(text)
    if not m:
        return None
    amount = int(m.group("amount"))
    count = int(m.group("count"))
    if count > max_count:
        return None
    return amount, count

# 4. 判斷 session.json 是否為目前帳號
def is_session_for_username(session_file, ig_username):
    if not os.path.exists(session_file):
        return False
    with open(session_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    ds_user_id = data.get("authorization_data", {}).get("ds_user_id")
    if not ds_user_id:
        return False
    # 拿 username 對應的 user_id（需連網）
    try:
        temp_cl = Client()
        user_id = temp_cl.user_id_from_username(ig_username)
    except Exception as e:
        print(f"查詢 username 對應 user_id 失敗：{e}")
        return False
    return str(ds_user_id) == str(user_id)

# 5. 登入並管理 session
def get_client():
    cl = Client()
    cl.challenge_code_handler = challenge_code_handler

    # 判斷 session.json 是否正確帳號
    if is_session_for_username(SESSION_FILE, IG_USERNAME):
        try:
            cl.load_settings(SESSION_FILE)
            cl.user_id_from_username(IG_USERNAME)
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 已載入 {SESSION_FILE}，session 有效且帳號正確。")
            return cl
        except Exception:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Session 檔案無效或過期，將重新登入。")
            os.remove(SESSION_FILE)

    # 登入並存新 session
    try:
        cl.login(IG_USERNAME, IG_PASSWORD)
        cl.dump_settings(SESSION_FILE)
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 使用帳密重新登入，並儲存 session。")
        return cl
    except (LoginRequired, ClientError) as e:
        sys.exit(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 登入失敗：{e}")

# 6. 自動取得直播 broadcast_id
def get_own_broadcast_id(client: Client) -> str:
    try:
        user_id = client.user_id_from_username(IG_USERNAME)
        reels = client.user_reels_media(user_id)
    except Exception as e:
        sys.exit(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 取得 reels 失敗：{e}")
    for media in reels.values():
        bid = getattr(media, "live_broadcast_id", None) or getattr(media, "broadcast_id", None)
        if bid:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 偵測到直播，broadcast_id={bid}")
            return str(bid)
    sys.exit(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 目前無正在直播，請先開直播。")

# 7. 偵測到關鍵字時，寫入指定csv
def save_order_info(file_path, amount, count, user_id, username, text):
    ts = datetime.now()
    header = ["timestamp", "amount", "count", "user_id", "username", "text"]
    row = [ts.strftime("%Y-%m-%d %H:%M:%S"), amount, count, user_id, username, text]
    write_header = not file_path.exists()
    with open(file_path, "a", encoding="utf-8", newline='') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(header)
        writer.writerow(row)

# 8. 直播聊天室監聽
def fetch_live_comments(client: Client, broadcast_id: str, max_count: int, limit: int, custom_filename: str):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 監聽直播聊天室（broadcast_id={broadcast_id}）")
    seen = set()
    last_ts = 0
    found_count = 0
    API_LIMIT = 50  # IG API 單次返回留言最大數量預設為 50

    folder = Path("order_information")
    folder.mkdir(exist_ok=True)
    file_path = None   # 首次偵測關鍵字時才產生

    while True:
        try:
            res = client.private_request(
                f'live/{broadcast_id}/get_comment/',
                params={'last_comment_ts': last_ts}
            )
            comments = res.get('comments', [])
            if len(comments) >= API_LIMIT:
                print(f"[警告] 本次取得 {len(comments)} 筆留言，已達單次API返回上限（{API_LIMIT}），建議減少 sleep 間隔或檢查是否有留言被遺漏！")
            for c in comments:
                cid = c.get('pk') or c.get('id')
                # print(json.dumps(c, indent=2, ensure_ascii=False))
                if cid and cid not in seen:
                    seen.add(cid)
                    text = c.get('text', '')
                    result = match_keyword(text, max_count)
                    if result:
                        amount, count = result
                        ts_now = datetime.now()
                        ts = ts_now.strftime('%Y-%m-%d %H:%M:%S')
                        user_info = c.get('user', {})
                        username = user_info.get('username', '<unknown>')
                        print(f"[{ts}] 偵測到關鍵字 → user_id={c.get('user_id')}, username={username}, amount={amount}, count={count}, text=\"{text}\"")
                        # --- 首次偵測才建立 file_path ---
                        if file_path is None:
                            prefix = ts_now.strftime("%Y%m%d_%H%M")
                            safe_custom_name = custom_filename.replace(' ', '_')
                            filename = f"{prefix}_{safe_custom_name}.csv"
                            file_path = folder / filename
                        save_order_info(file_path, amount, count, c.get('user_id'), username, text)
                        found_count += 1
                        if limit > 0 and found_count >= limit:
                            print(f"\n已達指定偵測數量 {limit}，自動停止。")
                            return
            if comments:
                last_ts = max(c.get('created_at', last_ts) for c in comments)
        except Exception as e:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 讀取留言錯誤：{e}")
        time.sleep(2)

# 9. 主程式：CLI 參數
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['session', 'monitor'], default='monitor',
                        help='session: 僅儲存/驗證 session | monitor: 啟動直播監聽')
    parser.add_argument('--max-count', type=int, help='關鍵字最大數量（不輸入則啟動時詢問）')
    parser.add_argument('--limit', type=int, help='最多偵測幾筆符合關鍵字的留言後停止（0為無限制）')
    parser.add_argument('--filename', type=str, help='自訂檔案名稱（會加在自動產生的日期時間後）')
    args = parser.parse_args()

    # max_count
    if args.max_count is not None:
        max_count = args.max_count
    else:
        try:
            max_count = int(input('請輸入關鍵字最大數量（MAX_COUNT）：').strip())
        except Exception:
            sys.exit('MAX_COUNT 輸入格式錯誤，請輸入整數。')

    # limit
    if args.limit is not None:
        limit = args.limit
    else:
        try:
            limit = int(input('請輸入最多偵測到幾筆符合關鍵字即停止（0 表示無限制）：').strip() or "0")
        except Exception:
            limit = 0

    # filename
    if args.filename:
        custom_filename = args.filename
    else:
        custom_filename = input('請輸入自訂檔案名稱：').strip()
        if not custom_filename:
            print("錯誤：請必須填入檔案名稱")
            sys.exit(1)

    client = get_client()

    if args.mode == 'session':
        # session模式只驗證並印出 session cookies 和 UA
        cl = client
        cl.inject_sessionid_to_public()
        cookie_dict = {}
        for name in dir(cl):
            try:
                attr = getattr(cl, name)
            except Exception:
                continue
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
        if cookie_dict:
            print(json.dumps(cookie_dict, indent=2, ensure_ascii=False))
            print("\n📋 關鍵欄位：")
            print(f"  sessionid = {cookie_dict.get('sessionid', '<missing>')}")
            print(f"  csrftoken = {cookie_dict.get('csrftoken', '<missing>')}")
            print(f"  mid       = {cookie_dict.get('mid', '<missing>')}")
        else:
            print("⚠️ 無法找到有效 cookies！")
        ua = cl.settings.get('user_agent', '<missing UA>')
        print(f"\n🔖 user_agent = {ua}")
        return

    # monitor
    if BROADCAST_ID:
        broadcast_id = BROADCAST_ID
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 使用 .env 設定的 broadcast_id：{broadcast_id}")
    else:
        broadcast_id = get_own_broadcast_id(client)
    fetch_live_comments(client, broadcast_id, max_count, limit, custom_filename)

if __name__ == '__main__':
    main()
