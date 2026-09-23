import os
import requests
from dotenv import load_dotenv, set_key
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

ENV_FILE = ".env"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

WHOOP_CLIENT_ID = os.getenv("WHOOP_CLIENT_ID")
WHOOP_CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET")

TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
RECOVERY_URL = "https://api.prod.whoop.com/developer/v2/recovery"
CYCLE_URL = "https://api.prod.whoop.com/developer/v2/cycle"
SLEEP_URL = "https://api.prod.whoop.com/developer/v2/activity/sleep"


def refresh_whoop_token():
    current_refresh_token = os.getenv("WHOOP_REFRESH_TOKEN")

    data = {
        "grant_type": "refresh_token",
        "refresh_token": current_refresh_token,
        "client_id": WHOOP_CLIENT_ID,
        "client_secret": WHOOP_CLIENT_SECRET,
        "scope": "offline",
    }

    response = requests.post(TOKEN_URL, data=data, timeout=30)

    if response.status_code != 200:
        print("Ошибка обновления токена:", response.text)
        return None

    token_data = response.json()

    new_access_token = token_data["access_token"]
    new_refresh_token = token_data.get("refresh_token")

    set_key(
        ENV_FILE,
        "WHOOP_ACCESS_TOKEN",
        new_access_token
    )

    if new_refresh_token:
        set_key(
            ENV_FILE,
            "WHOOP_REFRESH_TOKEN",
            new_refresh_token
        )

        os.environ["WHOOP_REFRESH_TOKEN"] = new_refresh_token

    return new_access_token


def format_hours(milliseconds):
    hours = milliseconds // 3600000
    minutes = (milliseconds % 3600000) // 60000

    return f"{hours} ч {minutes} мин"


def recovery_comment(recovery):
    if recovery >= 67:
        return "🟢 Хорошее восстановление. Организм сегодня восстановлен хорошо."

    if recovery >= 34:
        return "🟡 Среднее восстановление. Нагрузка сегодня лучше умеренная."

    return "🔴 Низкое восстановление. Сегодня стоит уделить больше внимания отдыху."


def strain_comment(strain):
    if strain < 8:
        return "Нагрузка пока лёгкая."

    if strain < 14:
        return "Нагрузка умеренная."

    if strain < 18:
        return "Нагрузка высокая."

    return "Нагрузка очень высокая."


def sleep_comment(performance, consistency):
    comments = []

    if performance >= 85:
        comments.append("Сон по объёму хороший.")
    elif performance >= 70:
        comments.append("Сна было достаточно, но есть запас для улучшения.")
    else:
        comments.append("Сна было меньше оптимального.")

    if consistency < 60:
        comments.append("Регулярность сна низкая.")
    elif consistency < 80:
        comments.append("Регулярность сна средняя.")
    else:
        comments.append("Режим сна стабильный.")

    return " ".join(comments)


def get_today_text():
    access_token = refresh_whoop_token()

    if not access_token:
        return "❌ Не удалось обновить токен WHOOP."

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    recovery_response = requests.get(
        RECOVERY_URL,
        headers=headers,
        params={"limit": 1},
        timeout=30
    )

    cycle_response = requests.get(
        CYCLE_URL,
        headers=headers,
        params={"limit": 1},
        timeout=30
    )

    sleep_response = requests.get(
        SLEEP_URL,
        headers=headers,
        params={"limit": 5},
        timeout=30
    )

    if recovery_response.status_code != 200:
        return f"❌ Ошибка Recovery: {recovery_response.status_code}"

    if cycle_response.status_code != 200:
        return f"❌ Ошибка Cycle: {cycle_response.status_code}"

    if sleep_response.status_code != 200:
        return f"❌ Ошибка Sleep: {sleep_response.status_code}"

    recovery_records = recovery_response.json().get("records", [])
    cycle_records = cycle_response.json().get("records", [])
    sleep_records = sleep_response.json().get("records", [])

    if not recovery_records:
        return "WHOOP пока не вернул Recovery."

    recovery_score = recovery_records[0].get("score", {})

    recovery = recovery_score.get("recovery_score")
    resting_hr = recovery_score.get("resting_heart_rate")
    hrv = recovery_score.get("hrv_rmssd_milli")
    spo2 = recovery_score.get("spo2_percentage")
    skin_temp = recovery_score.get("skin_temp_celsius")

    strain = None

    if cycle_records:
        cycle_score = cycle_records[0].get("score")

        if cycle_score:
            strain = cycle_score.get("strain")

    latest_sleep = None

    for sleep in sleep_records:
        if not sleep.get("nap", False) and sleep.get("score_state") == "SCORED":
            latest_sleep = sleep
            break

    sleep_performance = None
    sleep_efficiency = None
    sleep_consistency = None
    sleep_duration = None
    respiratory_rate = None

    if latest_sleep:
        sleep_score = latest_sleep.get("score", {})

        sleep_performance = sleep_score.get(
            "sleep_performance_percentage"
        )

        sleep_efficiency = sleep_score.get(
            "sleep_efficiency_percentage"
        )

        sleep_consistency = sleep_score.get(
            "sleep_consistency_percentage"
        )

        respiratory_rate = sleep_score.get(
            "respiratory_rate"
        )

        stage_summary = sleep_score.get("stage_summary", {})

        total_sleep_milli = (
            stage_summary.get("total_light_sleep_time_milli", 0)
            + stage_summary.get("total_slow_wave_sleep_time_milli", 0)
            + stage_summary.get("total_rem_sleep_time_milli", 0)
        )

        sleep_duration = format_hours(total_sleep_milli)

    text = "📊 WHOOP сегодня\n\n"

    text += "💚 Восстановление\n"
    text += f"Восстановление: {recovery}%\n"
    text += f"❤️ Пульс в покое: {resting_hr:.0f} уд/мин\n"
    text += f"💓 HRV: {hrv:.2f} мс\n"
    text += f"🫁 SpO₂: {spo2}%\n"
    text += f"🌡 Температура кожи: {skin_temp:.2f} °C\n"

    if strain is not None:
        text += "\n🔥 Нагрузка\n"
        text += f"Strain: {strain:.1f}\n"

    if sleep_performance is not None:
        text += "\n😴 Сон\n"
        text += f"Продолжительность: {sleep_duration}\n"
        text += f"Sleep Performance: {sleep_performance}%\n"
        text += f"Эффективность: {sleep_efficiency:.0f}%\n"
        text += f"Регулярность: {sleep_consistency}%\n"
        text += f"Частота дыхания: {respiratory_rate:.1f}/мин\n"

    text += "\n🧠 Итог\n"
    text += recovery_comment(recovery)

    if sleep_performance is not None:
        text += "\n" + sleep_comment(
            sleep_performance,
            sleep_consistency
        )

    if strain is not None:
        text += "\n" + strain_comment(strain)

    return text


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет, София! 👋\n"
        "Я твой WHOOP-бот.\n\n"
        "Команды:\n"
        "/today — отчёт WHOOP за сегодня"
    )

async def recovery_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    access_token = refresh_whoop_token()

    if not access_token:
        await update.message.reply_text(
            "❌ Не удалось обновить токен WHOOP."
        )
        return

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(
        RECOVERY_URL,
        headers=headers,
        params={"limit": 1},
        timeout=30
    )

    if response.status_code != 200:
        await update.message.reply_text(
            f"❌ Ошибка Recovery: {response.status_code}"
        )
        return

    records = response.json().get("records", [])

    if not records:
        await update.message.reply_text(
            "WHOOP пока не вернул данные Recovery."
        )
        return

    score = records[0]["score"]

    recovery = score["recovery_score"]
    resting_hr = score["resting_heart_rate"]
    hrv = score["hrv_rmssd_milli"]
    spo2 = score["spo2_percentage"]
    skin_temp = score["skin_temp_celsius"]

    text = (
        "💚 Recovery\n\n"
        f"Восстановление: {recovery}%\n"
        f"❤️ Пульс в покое: {resting_hr:.0f} уд/мин\n"
        f"💓 HRV: {hrv:.2f} мс\n"
        f"🫁 SpO₂: {spo2}%\n"
        f"🌡 Температура кожи: {skin_temp:.2f} °C\n\n"
        f"🧠 {recovery_comment(recovery)}"
    )

    await update.message.reply_text(text)

async def sleep_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    access_token = refresh_whoop_token()

    if not access_token:
        await update.message.reply_text(
            "❌ Не удалось обновить токен WHOOP."
        )
        return

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(
        SLEEP_URL,
        headers=headers,
        params={"limit": 5},
        timeout=30
    )

    if response.status_code != 200:
        await update.message.reply_text(
            f"❌ Ошибка Sleep: {response.status_code}"
        )
        return

    records = response.json().get("records", [])

    latest_sleep = None

    for sleep in records:
        if not sleep.get("nap", False) and sleep.get("score_state") == "SCORED":
            latest_sleep = sleep
            break

    if not latest_sleep:
        await update.message.reply_text(
            "😴 WHOOP пока не вернул данные сна."
        )
        return

    score = latest_sleep.get("score", {})

    sleep_performance = score.get("sleep_performance_percentage")
    sleep_efficiency = score.get("sleep_efficiency_percentage")
    sleep_consistency = score.get("sleep_consistency_percentage")
    respiratory_rate = score.get("respiratory_rate")

    stage_summary = score.get("stage_summary", {})

    total_sleep_milli = (
        stage_summary.get("total_light_sleep_time_milli", 0)
        + stage_summary.get("total_slow_wave_sleep_time_milli", 0)
        + stage_summary.get("total_rem_sleep_time_milli", 0)
    )

    sleep_duration = format_hours(total_sleep_milli)

    text = (
        "😴 Сон\n\n"
        f"🕒 Продолжительность: {sleep_duration}\n"
        f"💤 Sleep Performance: {sleep_performance}%\n"
        f"⚡ Эффективность: {sleep_efficiency:.0f}%\n"
        f"📅 Регулярность: {sleep_consistency}%\n"
        f"🫁 Частота дыхания: {respiratory_rate:.1f}/мин\n\n"
        f"🧠 {sleep_comment(sleep_performance, sleep_consistency)}"
    )

    await update.message.reply_text(text)    
async def strain_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    access_token = refresh_whoop_token()

    if not access_token:
        await update.message.reply_text(
            "❌ Не удалось обновить токен WHOOP."
        )
        return

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(
        CYCLE_URL,
        headers=headers,
        params={"limit": 1},
        timeout=30
    )

    if response.status_code != 200:
        await update.message.reply_text(
            f"❌ Ошибка Strain: {response.status_code}"
        )
        return

    records = response.json().get("records", [])

    if not records:
        await update.message.reply_text(
            "🔥 WHOOP пока не вернул данные нагрузки."
        )
        return

    score = records[0].get("score")

    if not score:
        await update.message.reply_text(
            "🔥 Нагрузка пока не рассчитана."
        )
        return

    strain = score.get("strain")

    text = (
        "🔥 Нагрузка\n\n"
        f"Strain: {strain:.1f}\n\n"
        f"🧠 {strain_comment(strain)}"
    )

    await update.message.reply_text(text)

async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime, timedelta, timezone

    await update.message.reply_text(
        "⏳ Собираю данные WHOOP за последние 7 дней..."
    )

    access_token = refresh_whoop_token()

    if not access_token:
        await update.message.reply_text(
            "❌ Не удалось обновить токен WHOOP."
        )
        return

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=7)

    params = {
        "start": start_date.isoformat().replace("+00:00", "Z"),
        "end": end_date.isoformat().replace("+00:00", "Z"),
        "limit": 25
    }

    recovery_response = requests.get(
        RECOVERY_URL,
        headers=headers,
        params=params,
        timeout=30
    )

    cycle_response = requests.get(
        CYCLE_URL,
        headers=headers,
        params=params,
        timeout=30
    )

    sleep_response = requests.get(
        SLEEP_URL,
        headers=headers,
        params=params,
        timeout=30
    )

    if recovery_response.status_code != 200:
        await update.message.reply_text(
            f"❌ Ошибка Recovery: {recovery_response.status_code}"
        )
        return

    if cycle_response.status_code != 200:
        await update.message.reply_text(
            f"❌ Ошибка Cycle: {cycle_response.status_code}"
        )
        return

    if sleep_response.status_code != 200:
        await update.message.reply_text(
            f"❌ Ошибка Sleep: {sleep_response.status_code}"
        )
        return

    recovery_records = recovery_response.json().get("records", [])
    cycle_records = cycle_response.json().get("records", [])
    sleep_records = sleep_response.json().get("records", [])

    # ------------------------
    # RECOVERY
    # ------------------------

    recoveries = []
    hrvs = []

    for record in recovery_records:
        if record.get("score_state") != "SCORED":
            continue

        score = record.get("score", {})

        recovery = score.get("recovery_score")
        hrv = score.get("hrv_rmssd_milli")

        if recovery is not None:
            recoveries.append({
                "value": recovery,
                "cycle_id": record.get("cycle_id")
            })

        if hrv is not None:
            hrvs.append(hrv)

    # ------------------------
    # STRAIN
    # ------------------------

    strains = []

    for cycle in cycle_records:
        if cycle.get("score_state") != "SCORED":
            continue

        score = cycle.get("score", {})

        strain = score.get("strain")

        if strain is not None:
            strains.append(strain)

    # ------------------------
    # SLEEP
    # ------------------------

    sleep_durations = []

    for sleep in sleep_records:
        if sleep.get("nap", False):
            continue

        if sleep.get("score_state") != "SCORED":
            continue

        score = sleep.get("score", {})
        stage_summary = score.get("stage_summary", {})

        total_sleep_milli = (
            stage_summary.get("total_light_sleep_time_milli", 0)
            + stage_summary.get("total_slow_wave_sleep_time_milli", 0)
            + stage_summary.get("total_rem_sleep_time_milli", 0)
        )

        if total_sleep_milli > 0:
            sleep_durations.append(total_sleep_milli)

    if not recoveries:
        await update.message.reply_text(
            "За последние 7 дней нет данных Recovery."
        )
        return

    # ------------------------
    # СРЕДНИЕ ЗНАЧЕНИЯ
    # ------------------------

    avg_recovery = sum(
        item["value"] for item in recoveries
    ) / len(recoveries)

    avg_hrv = (
        sum(hrvs) / len(hrvs)
        if hrvs else None
    )

    avg_strain = (
        sum(strains) / len(strains)
        if strains else None
    )

    avg_sleep_milli = (
        sum(sleep_durations) / len(sleep_durations)
        if sleep_durations else None
    )

    # ------------------------
    # ЛУЧШИЙ / СЛАБЫЙ ДЕНЬ
    # ------------------------

    best_recovery = max(
        recoveries,
        key=lambda x: x["value"]
    )

    worst_recovery = min(
        recoveries,
        key=lambda x: x["value"]
    )

    cycle_dates = {}

    for cycle in cycle_records:
        cycle_id = cycle.get("id")
        cycle_start = cycle.get("start")

        if cycle_id and cycle_start:
            date = datetime.fromisoformat(
                cycle_start.replace("Z", "+00:00")
            )

            cycle_dates[cycle_id] = date.strftime("%d.%m")

    best_date = cycle_dates.get(
        best_recovery["cycle_id"],
        "—"
    )

    worst_date = cycle_dates.get(
        worst_recovery["cycle_id"],
        "—"
    )

    # ------------------------
    # ТЕКСТ
    # ------------------------

    text = "📅 WHOOP — последние 7 дней\n\n"

    text += f"💚 Средний Recovery: {avg_recovery:.1f}%\n"

    if avg_hrv is not None:
        text += f"💓 Средний HRV: {avg_hrv:.2f} мс\n"

    if avg_strain is not None:
        text += f"🔥 Средний Strain: {avg_strain:.1f}\n"

    if avg_sleep_milli is not None:
        text += (
            f"😴 Средний сон: "
            f"{format_hours(int(avg_sleep_milli))}\n"
        )

    text += "\n🏆 Лучший Recovery\n"
    text += (
        f"{best_recovery['value']}% — {best_date}\n"
    )

    text += "\n📉 Самый низкий Recovery\n"
    text += (
        f"{worst_recovery['value']}% — {worst_date}\n"
    )

    text += "\n🧠 Итог\n"

    if avg_recovery >= 67:
        text += "🟢 В среднем восстановление за неделю хорошее."
    elif avg_recovery >= 34:
        text += "🟡 В среднем восстановление за неделю среднее."
    else:
        text += "🔴 В среднем восстановление за неделю низкое."

    await update.message.reply_text(text)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import datetime

    access_token = refresh_whoop_token()

    if not access_token:
        await update.message.reply_text(
            "⚙️ Статус бота\n\n"
            "🟢 Telegram-бот работает\n"
            "🔴 WHOOP не подключён\n"
            "🔴 Токен не удалось обновить"
        )
        return

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(
        RECOVERY_URL,
        headers=headers,
        params={"limit": 1},
        timeout=30
    )

    if response.status_code == 200:
        now = datetime.now().strftime("%d.%m.%Y %H:%M")

        text = (
            "⚙️ Статус бота\n\n"
            "🟢 Telegram-бот работает\n"
            "🟢 WHOOP подключён\n"
            "🟢 Токен обновляется автоматически\n"
            "🟢 WHOOP API отвечает\n\n"
            f"🕒 Последнее успешное получение данных:\n{now}"
        )
    else:
        text = (
            "⚙️ Статус бота\n\n"
            "🟢 Telegram-бот работает\n"
            "🟡 Токен обновился\n"
            f"🔴 WHOOP API вернул ошибку {response.status_code}"
        )

    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 Команды Sofiya WHOOP Bot\n\n"
        "📊 /today — полный отчёт за сегодня\n"
        "💚 /recovery — восстановление\n"
        "😴 /sleep — сон\n"
        "🔥 /strain — нагрузка\n"
        "📅 /week — сводка за последние 7 дней\n"
        "⚙️ /status — проверить работу бота и WHOOP\n"
        "❓ /help — список команд"
    )

    await update.message.reply_text(text)

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⏳ Собираю Recovery, сон и нагрузку..."
    )

    text = get_today_text()

    await update.message.reply_text(text)


app = Application.builder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("recovery", recovery_command))
app.add_handler(CommandHandler("sleep", sleep_command))
app.add_handler(CommandHandler("strain", strain_command))
app.add_handler(CommandHandler("week", week_command))
app.add_handler(CommandHandler("status", status_command))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("today", today))

print("Бот запущен...")

app.run_polling()