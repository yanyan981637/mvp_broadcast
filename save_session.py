from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired, ChallengeError, ClientError

import os
from dotenv import load_dotenv

load_dotenv()
IG_USERNAME = os.getenv("INSTAGRAM_USERNAME", "").strip()
IG_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "").strip()

def save_session():
    cl = Client()
    try:
        cl.login(IG_USERNAME, IG_PASSWORD)
        cl.dump_settings("session.json")
        print("✅ 登入並儲存 session 成功！")
    except TwoFactorRequired:
        print("⚠️ 需要二次驗證 (2FA)。")
    except ChallengeRequired as e:
        print("⚠️ Instagram 要求挑戰驗證 (Challenge)。")

        # 先嘗試從 e.error_response 或 e.response 拿
        data = None
        try:
            data = e.error_response
        except AttributeError:
            data = getattr(e, "response", None)

        if data:
            print(">>> e.error_response／e.response 內容：", data)
        else:
            print(">>> e.error_response／e.response 都是 None。")

        # 再從 cl.last_json 取出真正的 challenge payload
        challenge_payload = getattr(cl, "last_json", None)
        if challenge_payload:
            print(">>> cl.last_json：", challenge_payload)
            # 拿到裡面的 challenge 資料（通常是個 dict）
            challenge_info = challenge_payload.get("challenge")
            if challenge_info:
                print(">>> challenge 資訊：", challenge_info)
                # 有些版本是放在 'url'，有些是 'api_path'
                api_path = challenge_info.get("api_path") or challenge_info.get("url")
                if api_path:
                    challenge_url = f"https://www.instagram.com{api_path}"
                    print("請在瀏覽器打開以下網址完成驗證：")
                    print(challenge_url)
                else:
                    print("❌ challenge_info 裡沒有 'api_path' 或 'url' 欄位，請檢查上面印出的 challenge_info。")
            else:
                print("❌ cl.last_json 裡找不到 'challenge' key，請印出來確認 JSON 結構。")
        else:
            print("❌ 無法從 cl.last_json 取得任何資料。")

    except ChallengeError as e:
        print("❌ 挑戰驗證失敗：驗證碼不正確或已過期。", e)
    except ClientError as e:
        print("❌ 發生 ClientError：", e)
    except Exception as e:
        print("🚨 未預期錯誤：", e)

if __name__ == "__main__":
    print("▶︎ 程式讀到的 IG_USERNAME：", repr(IG_USERNAME))
    save_session()
