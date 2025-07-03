#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import time
import csv
import random
import argparse
import platform
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from instagrapi import Client
from instagrapi.exceptions import TwoFactorRequired, LoginRequired
from PIL import Image, ImageDraw, ImageFont, ImageWin

# =======================
# 裝置資料池
# =======================
DEVICE_POOL = [
    {
        "app_version": "290.0.0.28.109",
        "android_version": 30,
        "android_release": "11",
        "dpi": "420dpi",
        "resolution": "1080x2136",
        "manufacturer": "samsung",
        "device": "y2q",
        "model": "SM-G9810",
        "cpu": "qcom",
        "version_code": "465350279",
        "user_agent": "Instagram 290.0.0.28.109 Android (30/11; 420dpi; 1080x2136; samsung; SM-G9810; y2q; qcom; zh_TW; 465350279)"
    },
    {
        "app_version": "286.0.0.15.69",
        "android_version": 30,
        "android_release": "11",
        "dpi": "480dpi",
        "resolution": "1080x2400",
        "manufacturer": "Xiaomi",
        "device": "umi",
        "model": "Mi 10",
        "cpu": "qcom",
        "version_code": "398737262",
        "user_agent": "Instagram 286.0.0.15.69 Android (30/11; 480dpi; 1080x2400; Xiaomi; Mi 10; umi; qcom; zh_CN; 398737262)"
    },
    {
        "app_version": "275.0.0.27.100",
        "android_version": 29,
        "android_release": "10",
        "dpi": "440dpi",
        "resolution": "1080x2340",
        "manufacturer": "HUAWEI",
        "device": "HWEL29",
        "model": "ELE-L29",
        "cpu": "kirin980",
        "version_code": "285739473",
        "user_agent": "Instagram 275.0.0.27.100 Android (29/10; 440dpi; 1080x2340; HUAWEI; ELE-L29; HWEL29; kirin980; zh_CN; 285739473)"
    },
    {
        "app_version": "253.0.0.16.119",
        "android_version": 30,
        "android_release": "10",
        "dpi": "420dpi",
        "resolution": "1080x2220",
        "manufacturer": "samsung",
        "device": "starlte",
        "model": "SM-G960F",
        "cpu": "exynos9810",
        "version_code": "215757342",
        "user_agent": "Instagram 253.0.0.16.119 Android (30/10; 420dpi; 1080x2220; samsung; SM-G960F; starlte; exynos9810; zh_TW; 215757342)"
    }
]

# =======================
# Windows printing modules
# =======================
if platform.system().lower() == "windows":
    try:
        import win32print
        import win32ui
        import win32con
    except ImportError:
        print("請先安裝 pywin32：pip install pywin32")
        sys.exit(1)

def get_font(size):
    paths = [
        r"C:\Windows\Fonts\msjh.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    ]
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def generate_print_image(username, text, img_path):
    dpi = 300
    w_cm, h_cm = 5, 3
    w_px, h_px = int(w_cm * dpi / 2.54), int(h_cm * dpi / 2.54)
    img = Image.new('RGB', (w_px, h_px), 'white')
    draw = ImageDraw.Draw(img)

    def text_size(txt, font):
        bbox = draw.textbbox((0, 0), txt, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    def fit_font(txt, max_w, max_s):
        s = max_s
        font = get_font(s)
        w, _ = text_size(txt, font)
        while w > max_w and s > 10:
            s -= 1
            font = get_font(s)
            w, _ = text_size(txt, font)
        return font

    f1 = fit_font(username, w_px * 0.9, 70)
    f2 = fit_font(text, w_px * 0.9, 55)
    w1, _ = text_size(username, f1)
    w2, _ = text_size(text, f2)
    x1, x2 = (w_px - w1) // 2, (w_px - w2) // 2
    y1, y2 = int(h_px * 0.18), int(h_px * 0.56)

    draw.text((x1, y1), username, 'black', font=f1)
    draw.text((x2, y2), text, 'black', font=f2)
    img.save(img_path, dpi=(dpi, dpi))
    return img_path

def print_image_auto(img_path):
    landscape = platform.system().lower() == 'windows'
    img = Image.open(img_path).rotate(90, expand=True)
    if not landscape:
        tmp = img_path.replace('.png', '_rotated.png')
        img.save(tmp)
        os.system(f'lp "{tmp}"')
        print(f"已發送至非Windows印表機：{tmp}")
        return
    printer = win32print.GetDefaultPrinter()
    dc = win32ui.CreateDC()
    dc.CreatePrinterDC(printer)
    dc.StartDoc(Path(img_path).name)
    dc.StartPage()
    dib = ImageWin.Dib(img)
    w_res = dc.GetDeviceCaps(win32con.HORZRES)
    h_res = dc.GetDeviceCaps(win32con.VERTRES)
    dib.draw(dc.GetHandleOutput(), (0, 0, w_res, h_res))
    dc.EndPage()
    dc.EndDoc()
    print(f"已發送列印：{img_path}")

load_dotenv()
USER = os.getenv('INSTAGRAM_USERNAME', '').strip()
PASS = os.getenv('INSTAGRAM_PASSWORD', '').strip()
BID = os.getenv('BROADCAST_ID', '').strip()
SESSION_FILE = 'session.json'
if not USER or not PASS:
    sys.exit('請設定 .env INSTAGRAM_USERNAME 和 INSTAGRAM_PASSWORD')

PAT = re.compile(r'([A-L])(1[0-2]|[1-9])\s*\+([1-9]\d{0,4})')
skip = {'patrician_jewelry', 'anita.lee0918'}

def match_keyword(txt):
    return [(int(m.group(3)), m.group(1), int(m.group(2))) for m in PAT.finditer(txt)] or None

def challenge_code_handler(username, choice):
    prompt = '驗證碼: '
    if 'app' in str(choice).lower(): prompt = 'OTP: '
    if 'email' in str(choice).lower(): prompt = 'Email code: '
    if 'sms' in str(choice).lower(): prompt = 'SMS code: '
    return input(prompt)

def get_client():
    device = random.choice(DEVICE_POOL)
    cl = Client()
    cl.set_user_agent(device["user_agent"])
    cl.device_settings = {
        "app_version": device["app_version"],
        "android_version": device["android_version"],
        "android_release": device["android_release"],
        "dpi": device["dpi"],
        "resolution": device["resolution"],
        "manufacturer": device["manufacturer"],
        "device": device["device"],
        "model": device["model"],
        "cpu": device["cpu"],
        "version_code": device["version_code"]
    }

    cl.challenge_code_handler = challenge_code_handler
    if Path(SESSION_FILE).exists():
        cl.load_settings(SESSION_FILE)
        print(f"已載入 session，使用 UA: {cl.user_agent}")
        return cl
    try:
        cl.login(USER, PASS)
        print(f"首次登入，使用 UA: {cl.user_agent}")
    except TwoFactorRequired as e:
        code = challenge_code_handler(USER, e)
        cl.login(USER, PASS, verification_code=code)
        print(f"二階段驗證登入，使用 UA: {cl.user_agent}")
    cl.dump_settings(SESSION_FILE)
    return cl

def save_csv(fp, row):
    new = not fp.exists()
    with open(fp, 'a', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        if new:
            w.writerow(['timestamp', 'number', 'group_letter', 'group_number', 'user_id', 'username', 'text'])
        w.writerow(row)

def advanced_private_request(cli, url, params):
    # 進階 header 強化仿真
    headers = {
        "X-IG-Capabilities": "3brTvw==",
        "X-IG-Connection-Type": "WIFI",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive"
    }
    return cli.private_request(url, params=params, headers=headers)

def fetch_comments_dynamic(cli, bid, limit, fname):
    seen, last, cnt = set(), 0, 0
    fail_count = 0
    max_fail = 3
    idle_count = 0
    min_interval = 5
    max_interval = 30
    idle_step = 5
    od, idr = Path('order_information'), Path('images')
    od.mkdir(exist_ok=True)
    idr.mkdir(exist_ok=True)
    fp = None

    while True:
        try:
            cur_interval = min(min_interval + idle_count * idle_step, max_interval)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 正在請求留言資料 ... (輪詢間隔 {cur_interval} 秒)")
            res = advanced_private_request(cli, f'live/{bid}/get_comment/', params={'last_comment_ts': last})
            comments = res.get('comments', [])
            print(f"本輪共取得 {len(comments)} 則留言。")
            fail_count = 0
        except LoginRequired:
            fail_count += 1
            print(f"[警告] Session 過期，正在第 {fail_count} 次嘗試重新登入...")
            if fail_count >= max_fail:
                print('連續登入失敗，腳本自動結束！請人工處理 IG 驗證。')
                break
            cli = get_client()
            sleep_time = random.uniform(min_interval, min(10, max_interval))
            print(f"Session 過期等待 {sleep_time:.1f} 秒再重試 ...")
            time.sleep(sleep_time)
            continue
        except Exception as e:
            print('取得評論失敗：', e)
            sleep_time = random.uniform(min_interval, min(10, max_interval))
            print(f"發生錯誤，暫停 {sleep_time:.1f} 秒")
            time.sleep(sleep_time)
            continue

        got_new = False
        for c in comments:
            cid = c.get('pk') or c.get('id')
            if not cid or cid in seen: continue
            seen.add(cid)
            un = c.get('user', {}).get('username', '<unk>')
            if un in skip: continue
            txt = c.get('text', '')
            kws = match_keyword(txt)
            if not kws: continue
            got_new = True
            if not fp:
                ts = datetime.now().strftime('%Y%m%d_%H%M')
                fp = od / f"{ts}_{fname}.csv"
            for num, let, grp in kws:
                row = [datetime.now().strftime('%Y-%m-%d %H:%M:%S'), num, let, grp, c.get('user_id'), un, txt]
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 抓到資料：{row}")
                save_csv(fp, row)
                print(f"資料已存入: {fp}")
                imgf = idr / f"print_{un}_{let}{grp}_{num}_{int(time.time())}.png"
                generate_print_image(un, txt, str(imgf))
                print(f"已產生列印圖片: {imgf}")
                print_image_auto(str(imgf))
                cnt += 1
                if limit and cnt >= limit:
                    print("已達到設定的留言數上限，結束任務。")
                    return
        if comments:
            last = max(c.get('created_at', last) for c in comments)

        if got_new:
            idle_count = 0
        else:
            idle_count += 1
        interval = min(min_interval + idle_count * idle_step, max_interval)
        interval = random.uniform(interval, interval+2)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 輪詢休息 {interval:.1f} 秒 ...\n")
        time.sleep(interval)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['session', 'monitor'], default='monitor')
    p.add_argument('--limit', type=int)
    p.add_argument('--filename', type=str)
    a = p.parse_args()
    lim = a.limit if a.limit is not None else int(input('最多偵測幾筆 (0 無限): ').strip() or 0)
    fn = a.filename if a.filename else input('輸入檔名: ').strip()
    if not fn: sys.exit('需提供檔名')
    cli = get_client()
    if a.mode == 'session':
        cli.inject_sessionid_to_public()
        print(cli.settings.get('user_agent'))
    else:
        if not BID: sys.exit('需設定 BROADCAST_ID')
        fetch_comments_dynamic(cli, BID, lim, fn)
