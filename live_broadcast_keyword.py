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
from PIL import Image, ImageDraw, ImageFont
import platform

if platform.system().lower() == "windows":
    try:
        import win32print
        import win32api
    except ImportError:
        print("請先安裝 pywin32：pip install pywin32")
        sys.exit(1)

# ========== 字體自動選擇 ==========
def get_font(font_size):
    # Windows
    font_path = r"C:\Windows\Fonts\msjh.ttc"
    if os.path.exists(font_path):
        return ImageFont.truetype(font_path, font_size)
    # macOS
    font_path_mac = "/System/Library/Fonts/STHeiti Light.ttc"
    if os.path.exists(font_path_mac):
        return ImageFont.truetype(font_path_mac, font_size)
    # Linux: Noto Sans CJK
    font_path_noto = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    if os.path.exists(font_path_noto):
        return ImageFont.truetype(font_path_noto, font_size)
    print("⚠️ 沒找到中文字體，將用預設，中文可能無法顯示。")
    return ImageFont.load_default()

# ========== 圖片產生 ==========
def generate_print_image(username, text, img_path):
    dpi = 300
    width_cm, height_cm = 5, 3
    width_px = int(width_cm * dpi / 2.54)
    height_px = int(height_cm * dpi / 2.54)
    img = Image.new('RGB', (width_px, height_px), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    big_font = get_font(70)
    med_font = get_font(55)

    def get_text_size(draw, text, font):
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        except Exception:
            w, h = draw.textsize(text, font=font)
        return w, h

    w1, h1 = get_text_size(draw, username, big_font)
    w2, h2 = get_text_size(draw, text, med_font)
    x1 = (width_px - w1) // 2
    x2 = (width_px - w2) // 2
    y1 = int(height_px * 0.18)
    y2 = int(height_px * 0.56)

    draw.text((x1, y1), username, fill=(0, 0, 0), font=big_font)
    draw.text((x2, y2), text, fill=(0, 0, 0), font=med_font)

    img.save(img_path, dpi=(dpi, dpi))
    print(f"已存檔: {img_path}")
    # img.show() # 若需即時預覽內容可開啟這行
    return img_path

# ========== 列印 ==========
def print_image_auto(img_path):
    system = platform.system().lower()
    try:
        if system == 'windows':
            printer_name = win32print.GetDefaultPrinter()
            win32api.ShellExecute(
                0,
                "print",
                img_path,
                None,
                ".",
                0
            )
            print(f"已自動發送列印（Windows）：{img_path}")
        elif system in ['linux', 'darwin']:
            os.system(f'lp "{img_path}"')
            print(f"已自動發送列印（lp）：{img_path}")
        else:
            print("⚠️ 不支援的作業系統，請手動列印。")
    except Exception as e:
        print(f"發送列印失敗：{e}")

# ========== IG 關鍵字擷取主程式 ==========

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

# 3. 關鍵字正則 (A-L)(1-12) + 1~99999
PATTERN = re.compile(r'([A-L])(1[0-2]|[1-9])\s*\+([1-9]\d{0,4})')

def match_keyword(text: str):
    matches = []
    for m in PATTERN.finditer(text):
        group_letter = m.group(1)
        group_number = int(m.group(2))
        number = int(m.group(3))
        matches.append((number, group_letter, group_number))
    return matches if matches else None

# 4. 判斷 session.json 是否為目前帳號
def is_session_for_username(session_file, ig_username):
    if not os.path.exists(session_file):
        return False
    with open(session_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    ds_user_id = data.get("authorization_data", {}).get("ds_user_id")
    if not ds_user_id:
        return False
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
    if is_session_for_username(SESSION_FILE, IG_USERNAME):
        try:
            cl.load_settings(SESSION_FILE)
            cl.user_id_from_username(IG_USERNAME)
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 已載入 {SESSION_FILE}，session 有效且帳號正確。")
            return cl
        except Exception:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Session 檔案無效或過期，將重新登入。")
            os.remove(SESSION_FILE)
    try:
        cl.login(IG_USERNAME, IG_PASSWORD)
        cl.dump_settings(SESSION_FILE)
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 使用帳密重新登入，並儲存 session。")
        return cl
    except (LoginRequired, ClientError) as e:
        sys.exit(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 登入失敗：{e}")

# 6. 偵測到關鍵字時，寫入指定csv
def save_order_info(file_path, number, group_letter, group_number, user_id, username, text):
    ts = datetime.now()
    header = ["timestamp", "number", "group_letter", "group_number", "user_id", "username", "text"]
    row = [ts.strftime("%Y-%m-%d %H:%M:%S"), number, group_letter, group_number, user_id, username, text]
    write_header = not file_path.exists()
    with open(file_path, "a", encoding="utf-8-sig", newline='') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(header)
        writer.writerow(row)

# 7. 直播聊天室監聽
def fetch_live_comments(client: Client, broadcast_id: str, limit: int, custom_filename: str):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 監聽直播聊天室（broadcast_id={broadcast_id}）")
    seen = set()
    last_ts = 0
    found_count = 0
    API_LIMIT = 50

    folder = Path("order_information")
    folder.mkdir(exist_ok=True)
    file_path = None

    images_dir = Path("images")
    images_dir.mkdir(exist_ok=True)

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
                if cid and cid not in seen:
                    seen.add(cid)
                    text = c.get('text', '')
                    results = match_keyword(text)
                    if results:
                        ts_now = datetime.now()
                        ts = ts_now.strftime('%Y-%m-%d %H:%M:%S')
                        user_info = c.get('user', {})
                        username = user_info.get('username', '<unknown>')
                        for number, group_letter, group_number in results:
                            print(f"[{ts}] 偵測到關鍵字 → user_id={c.get('user_id')}, username={username}, number={number}, group_letter={group_letter}, group_number={group_number}, text=\"{text}\"")
                            # 儲存 CSV
                            if file_path is None:
                                prefix = ts_now.strftime("%Y%m%d_%H%M")
                                safe_custom_name = custom_filename.replace(' ', '_')
                                filename = f"{prefix}_{safe_custom_name}.csv"
                                file_path = folder / filename
                            save_order_info(file_path, number, group_letter, group_number, c.get('user_id'), username, text)
                            # 產生小票圖片到 images
                            img_filename = f"print_{username}_{group_letter}{group_number}_{number}_{int(time.time())}.png"
                            img_path = str(images_dir / img_filename)
                            generate_print_image(username, text, img_path)
                            print_image_auto(img_path)
                            # ====== 確認內容正確再啟用刪除 ======
                            # try:
                            #     os.remove(img_path)
                            # except Exception as e:
                            #     print(f"⚠️ 刪除圖片失敗：{e}")
                            found_count += 1
                            if limit > 0 and found_count >= limit:
                                print(f"\n已達指定偵測數量 {limit}，自動停止。")
                                return
            if comments:
                last_ts = max(c.get('created_at', last_ts) for c in comments)
        except Exception as e:
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 讀取留言錯誤：{e}")
        time.sleep(2)

# 8. 主程式：CLI 參數
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['session', 'monitor'], default='monitor',
                        help='session: 僅儲存/驗證 session | monitor: 啟動直播監聽')
    parser.add_argument('--limit', type=int, help='最多偵測幾筆符合關鍵字的留言後停止（0為無限制）')
    parser.add_argument('--filename', type=str, help='自訂檔案名稱（會加在自動產生的日期時間後）')
    args = parser.parse_args()

    if args.limit is not None:
        limit = args.limit
    else:
        try:
            limit = int(input('請輸入最多偵測到幾筆符合關鍵字即停止（0 表示無限制）：').strip() or "0")
        except Exception:
            limit = 0

    if args.filename:
        custom_filename = args.filename
    else:
        custom_filename = input('請輸入自訂檔案名稱：').strip()
        if not custom_filename:
            print("錯誤：請必須填入檔案名稱")
            sys.exit(1)

    client = get_client()

    if args.mode == 'session':
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
    if not BROADCAST_ID:
        print("錯誤：.env 檔案未設定 BROADCAST_ID，請手動填寫。")
        sys.exit(1)
    broadcast_id = BROADCAST_ID
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 使用 .env 設定的 broadcast_id：{broadcast_id}")
    fetch_live_comments(client, broadcast_id, limit, custom_filename)

if __name__ == '__main__':
    main()
