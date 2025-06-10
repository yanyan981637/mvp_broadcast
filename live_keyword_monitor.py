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
load_dotenv()
IG_USERNAME    = os.getenv("INSTAGRAM_USERNAME", "").strip()
IG_PASSWORD    = os.getenv("INSTAGRAM_PASSWORD", "").strip()
MAX_COUNT_ENV  = os.getenv("MAX_COUNT", "").strip()
BROADCAST_ID   = os.getenv("BROADCAST_ID", "").strip()
SESSION_FILE   = "session.json"

if not IG_USERNAME or not IG_PASSWORD:
    sys.exit("錯誤：請先在 .env 填寫 INSTAGRAM_USERNAME 及 INSTAGRAM_PASSWORD。")
if not MAX_COUNT_ENV.isdigit():
    sys.exit("錯誤：請在 .env 中給定一個合法的整數 MAX_COUNT，例如 MAX_COUNT=10")
MAX_COUNT = int(MAX_COUNT_ENV)

# --------------------------------------------------------------------------
# 2. 建立正則，匹配「金額 + 數量」格式
# --------------------------------------------------------------------------
PATTERN = re.compile(r"""
    (?P<amount>\d+)
    [\s,]*
    \+
    (?P<count>\d+)
""", re.VERBOSE)

def match_keyword(text: str):
    m = PATTERN.search(text)
    if not m:
        return None
    amount = int(m.group("amount"))
    count  = int(m.group("count"))
    if count > MAX_COUNT:
        return None
    return amount, count

# --------------------------------------------------------------------------
# 3. 登入並管理 session
# --------------------------------------------------------------------------
def get_client() -> Client:
    cl = Client()
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 已載入 {SESSION_FILE}，嘗試使用既有 session。")
            cl.user_id_from_username(IG_USERNAME)
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Session 驗證成功，不需重新登入。")
            return cl
        except Exception:
            os.remove(SESSION_FILE)
    try:
        cl.login(IG_USERNAME, IG_PASSWORD)
        cl.dump_settings(SESSION_FILE)
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 已成功登入並儲存 session。")
        return cl
    except (LoginRequired, ClientError) as e:
        sys.exit(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 登入失敗：{e}")

# --------------------------------------------------------------------------
# 4. 自動偵測直播 broadcast_id
# --------------------------------------------------------------------------
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

# --------------------------------------------------------------------------
# 5. 透過 Private API 輪詢直播聊天室
# --------------------------------------------------------------------------
def fetch_live_comments_manual(client: Client, broadcast_id: str):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 開始監聽直播聊天室（broadcast_id={broadcast_id}）")
    seen = set()
    last_ts = 0
    while True:
        try:
            res = client.private_request(
                f'live/{broadcast_id}/get_comment/',
                params={'last_comment_ts': last_ts}
            )
            comments = res.get('comments', [])
            for c in comments:
                cid = c.get('pk') or c.get('id')
                if cid and cid not in seen:
                    seen.add(cid)
                    text = c.get('text', '')
                    result = match_keyword(text)
                    if result:
                        amount, count = result
                        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        print(f"[{ts}] 偵測到符合關鍵字 → user_id={c.get('user_id')}, amount={amount}, count={count}, text=\"{text}\"")
            if comments:
                last_ts = max(c.get('created_at', last_ts) for c in comments)
        except Exception as e:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 讀取留言錯誤：{e}")
        time.sleep(2)

# --------------------------------------------------------------------------
# 6. 主程式
# --------------------------------------------------------------------------
if __name__ == "__main__":
    client = get_client()
    if BROADCAST_ID:
        broadcast_id = BROADCAST_ID
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 使用 .env 設定的 broadcast_id：{broadcast_id}")
    else:
        broadcast_id = get_own_broadcast_id(client)
    fetch_live_comments_manual(client, broadcast_id)
