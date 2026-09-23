import os
import requests
from dotenv import load_dotenv, set_key

load_dotenv()

ENV_FILE = ".env"

CLIENT_ID = os.getenv("WHOOP_CLIENT_ID")
CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("WHOOP_REFRESH_TOKEN")

TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
RECOVERY_URL = "https://api.prod.whoop.com/developer/v2/recovery"


def refresh_access_token():
    data = {
        "grant_type": "refresh_token",
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "offline",
    }

    response = requests.post(TOKEN_URL, data=data)

    print("Статус обновления токена:", response.status_code)

    if response.status_code != 200:
        print("Ошибка обновления токена:")
        print(response.text)
        return None

    token_data = response.json()

    new_access_token = token_data["access_token"]
    new_refresh_token = token_data.get("refresh_token")

    # Сохраняем новый Access Token в .env
    set_key(
        ENV_FILE,
        "WHOOP_ACCESS_TOKEN",
        new_access_token
    )

    # Если WHOOP прислал новый Refresh Token — тоже сохраняем
    if new_refresh_token:
        set_key(
            ENV_FILE,
            "WHOOP_REFRESH_TOKEN",
            new_refresh_token
        )

    print("🎉 Токены обновлены и сохранены!")

    return new_access_token


def get_recovery(access_token):
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(
        RECOVERY_URL,
        headers=headers
    )

    print("Статус WHOOP:", response.status_code)

    if response.status_code != 200:
        print("Ошибка WHOOP:")
        print(response.text)
        return

    whoop_data = response.json()
    records = whoop_data["records"]

    if not records:
        print("WHOOP пока не вернул данные Recovery.")
        return

    latest = records[0]
    score = latest["score"]

    recovery = score["recovery_score"]
    resting_hr = score["resting_heart_rate"]
    hrv = score["hrv_rmssd_milli"]
    spo2 = score["spo2_percentage"]
    skin_temp = score["skin_temp_celsius"]

    print()
    print("📊 WHOOP сегодня")
    print(f"💚 Восстановление: {recovery}%")
    print(f"❤️ Пульс в покое: {resting_hr:.0f} уд/мин")
    print(f"💓 HRV: {hrv:.2f} мс")
    print(f"🫁 SpO₂: {spo2}%")
    print(f"🌡 Температура кожи: {skin_temp:.2f} °C")


access_token = refresh_access_token()

if access_token:
    get_recovery(access_token)