#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.exceptions import ClientError, LoginRequired

# --------------------------------------------------------------------------
# 1. 讀取 .env
# --------------------------------------------------------------------------
load_dotenv()  # 從當前路徑的 .env 讀環境變數到 os.environ

IG_USERNAME    = os.getenv("INSTAGRAM_USERNAME", "").strip()
IG_PASSWORD    = os.getenv("INSTAGRAM_PASSWORD", "").strip()
MAX_COUNT_ENV  = os.getenv("MAX_COUNT", "").strip()
SESSION_FILE   = "session.json"  # session 檔案名稱

if not IG_USERNAME or not IG_PASSWORD:
    sys.exit("錯誤：請先在 .env 填寫 INSTAGRAM_USERNAME 及 INSTAGRAM_PASSWORD。")

if not MAX_COUNT_ENV.isdigit():
    sys.exit("錯誤：請在 .env 中給定一個合法的整數 MAX_COUNT，例如 MAX_COUNT=10")
MAX_COUNT = int(MAX_COUNT_ENV)

# --------------------------------------------------------------------------
# 2. 建立正則，匹配「金額 + 數量」格式
# --------------------------------------------------------------------------
PATTERN = re.compile(r"""
    (?P<amount>\d+)       # 前面一串數字，代表「金額」
    [\s,]*                # 中間允許有 0 個或多個空白、逗號
    \+                    # 必須有一個加號 '+'
    (?P<count>\d+)        # 後面一串數字，代表「數量」
""", re.VERBOSE)

def match_keyword(text: str):
    """
    如果 text 裡面含有符合 PATTERN 的片段，就回傳 (amount: int, count: int, match_obj)；
    若 count > MAX_COUNT 或沒匹配就回傳 None。
    """
    m = PATTERN.search(text)
    if not m:
        return None
    amount = int(m.group("amount"))
    count  = int(m.group("count"))
    if count > MAX_COUNT:
        return None
    return amount, count, m

# --------------------------------------------------------------------------
# 3. 取得一個已登入狀態的 Client（自動判定 session.json 或重新登入）
# --------------------------------------------------------------------------
def get_client() -> Client:
    """
    如果當前目錄有 session.json，就嘗試載入；否則用帳密登入並將 session 寫入 session.json。
    """
    cl = Client()

    # 1) 若存在 session.json，先嘗試載入
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已載入 {SESSION_FILE}，嘗試使用既有 session 登入…")
            # 用載入的 session 嘗試呼叫一個 API，以驗證 session 是否仍有效
            cl.user_id_from_username(IG_USERNAME)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Session 驗證成功，不需重新登入。")
            return cl
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 載入 session 失敗或 session 過期：{e}")
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 將刪除舊的 {SESSION_FILE} 並重新登入。")
            try:
                os.remove(SESSION_FILE)
            except OSError:
                pass  # 若刪除失敗，繼續嘗試登入即可

    # 2) 必須重新登入，使用帳號密碼
    try:
        cl.login(IG_USERNAME, IG_PASSWORD)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已成功登入 Instagram：{IG_USERNAME}")
        # 登入成功後，將 session 寫入檔案
        cl.dump_settings(SESSION_FILE)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 已將 session 寫入 {SESSION_FILE}。")
        return cl
    except LoginRequired as e:
        sys.exit(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 登入失敗 (LoginRequired)：{e}")
    except ClientError as e:
        sys.exit(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 登入時發生 ClientError：{e}")

# --------------------------------------------------------------------------
# 4. 自動取得自己帳號目前正在直播的 broadcast_id (解法二：透過 user_reels_media)
# --------------------------------------------------------------------------
def get_own_broadcast_id(client: Client) -> str:
    """
    1) 用 client.user_id_from_username(IG_USERNAME) 取得自己的 user_id
    2) 呼叫 client.user_reels_media(user_id) 取得 reels/story 列表
    3) 遍歷這些 media 物件，若某個物件具有 live_broadcast_id 或 broadcast_id，就回傳
    若找不到代表沒有直播，程式結束。
    """
    try:
        user_id = client.user_id_from_username(IG_USERNAME)
    except Exception as e:
        sys.exit(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 無法取得 user_id：{e}")

    try:
        reels = client.user_reels_media(user_id)
    except ClientError as e:
        sys.exit(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 抓取 reels（可能包含 live）失敗：{e}")
    except Exception as e:
        sys.exit(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 取得 reels 失敗：{e}")

    # reels 是一個 dict，key 為 media_id, value 為 Media 物件
    for media in reels.values():
        # 嘗試先取得 live_broadcast_id，有些版本名稱可能為 broadcast_id
        broadcast_id = getattr(media, "live_broadcast_id", None) or getattr(media, "broadcast_id", None)
        if broadcast_id:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 偵測到正在直播，broadcast_id = {broadcast_id}")
            return str(broadcast_id)

    # 如果沒有任何 media 含 live_broadcast_id，就代表目前沒有直播
    sys.exit(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 目前帳號沒有正在直播，請先開直播後再執行程式。")

# --------------------------------------------------------------------------
# 5. 持續從直播聊天室抓留言，並偵測關鍵字
# --------------------------------------------------------------------------
def fetch_live_comments(client: Client, broadcast_id: str):
    """
    不斷地從直播聊天室拉取最新留言（instagrapi live_comments generator），
    每抓到一則 comment，就用 match_keyword() 檢查是否符合「金額 + 數量」格式，
    並且 count <= MAX_COUNT。若符合，就印出時間戳、使用者、金額與數量等資訊。
    """
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 開始監聽直播聊天室（broadcast_id={broadcast_id}）")
    seen_comments = set()  # 紀錄已處理過的 comment_id，避免重複

    try:
        # live_comments() 會 yield「新的留言 dict」，直到直播結束或程式中斷
        for comment in client.live_comments(broadcast_id):
            comment_id = comment.get("id")
            if not comment_id or comment_id in seen_comments:
                continue
            seen_comments.add(comment_id)

            text = comment.get("text", "")
            if not text:
                continue

            result = match_keyword(text)
            if result:
                amount, count, _ = result
                user_id = comment.get("user_id")
                ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"[{ts}] 偵測到符合關鍵字 → user_id={user_id}, amount={amount}, count={count}, text=\"{text}\"")

    except ClientError as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 讀取留言時發生 ClientError：{e}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 未知錯誤：{e}")

# --------------------------------------------------------------------------
# 6. 主程式入口
# --------------------------------------------------------------------------
if __name__ == "__main__":
    # 取得已登入狀態的 client（自動判斷 session.json 或帳密登入）
    client = get_client()

    # 自動查詢自己目前的直播 broadcast_id
    broadcast_id = get_own_broadcast_id(client)

    # 開始監聽並篩選留言
    fetch_live_comments(client, broadcast_id)
