import customtkinter as ctk
from customtkinter import CTkToplevel
import tkinter as tk
from tkinter import messagebox
import multiprocessing
import sys
import os
import json
import threading
import time

CONFIG_FILE = "config.json"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def run_bot(token):
    import io
    import sys

    if sys.platform == "win32":
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

    import logging
    import threading
    from telegram import (
        Update,
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        ReplyKeyboardMarkup,
        KeyboardButton,
    )
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        ContextTypes,
        ConversationHandler,
        filters,
    )

    ADMIN_ID = 450146311
    STREAMERS_FILE = "streamers.json"
    USERS_FILE = "users.json"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    def load_json(filename):
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_json(filename, data):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_or_create_user(filename, user_id):
        data = load_json(filename)
        user_id_str = str(user_id)
        if user_id_str not in data:
            data[user_id_str] = {"registration_date": datetime.now().isoformat()}
        return data

    def validate_twitch_link(link):
        link = link.strip()
        if link.startswith("https://www.twitch.tv/"):
            return link
        elif link.startswith("twitch.tv/"):
            return "https://www." + link
        return None

    def get_channel_name(link):
        if link.startswith("https://www.twitch.tv/"):
            return link.replace("https://www.twitch.tv/", "")
        elif link.startswith("twitch.tv/"):
            return link.replace("twitch.tv/", "")
        return link

    def load_clicks():
        if os.path.exists("clicks.json"):
            try:
                with open("clicks.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_clicks(data):
        with open("clicks.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def track_click(twitch_link, telegram_id):
        data = load_clicks()
        link_key = twitch_link.replace("https://www.twitch.tv/", "twitch.tv/")
        if link_key not in data:
            data[link_key] = {"clicks": [], "total_clicks": 0}
        if telegram_id not in data[link_key]["clicks"]:
            data[link_key]["clicks"].append(telegram_id)
            data[link_key]["total_clicks"] = len(data[link_key]["clicks"])
        save_clicks(data)

    from datetime import datetime

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [[KeyboardButton("🚀 Старт")]]
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text(
            "👋 Привет! Я Twich-Alert!\n\nЯ помогу тебе:\n🔹 Настроить оповещения для своего канала\n🔹 Подписаться на любимых стримеров\n\nНажми кнопку ниже, чтобы начать!",
            reply_markup=reply_markup,
        )
        return "WAITING_START"

    async def handle_start_pressed(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text

        if "старт" in text.lower():
            keyboard = [
                [KeyboardButton("📡 Я стример")],
                [KeyboardButton("👀 Я зритель")],
                [KeyboardButton("🔄 Сменить роль")],
            ]
            reply_markup = ReplyKeyboardMarkup(
                keyboard, resize_keyboard=True, one_time_keyboard=True
            )
            await update.message.reply_text(
                "Отлично! Теперь выбери кто ты:", reply_markup=reply_markup
            )
            return "ROLE_SELECTION"

        return await start(update, context)

    async def handle_start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        keyboard = [
            [KeyboardButton("📡 Я стример")],
            [KeyboardButton("👀 Я зритель")],
            [KeyboardButton("🔄 Сменить роль")],
        ]
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text(
            "Отлично! Теперь выбери кто ты:", reply_markup=reply_markup
        )
        return "ROLE_SELECTION"

    async def handle_role_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text

        if (
            "сменить" in text.lower()
            or "назад" in text.lower()
            or "старт" in text.lower()
        ):
            return await handle_start_button(update, context)

        if "стример" in text.lower():
            context.user_data["role"] = "streamer"
            await update.message.reply_text(
                "📡 Отлично! Пришли ссылку на свой Twitch канал\n\nНапример: https://www.twitch.tv/имя_стримера"
            )
            return "STREAMER_CHANNEL"
        elif "зритель" in text.lower():
            context.user_data["role"] = "viewer"
            await update.message.reply_text(
                "👀 Понял! Пришли ссылку на канал стримера, на которого хочешь подписаться\n\nНапример: https://www.twitch.tv/имя_стримера"
            )
            return "VIEWER_ADD_STREAMER"
        else:
            return await start(update, context)

    async def handle_streamer_channel(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        link = validate_twitch_link(update.message.text)
        if not link:
            await update.message.reply_text(
                "Неверный формат ссылки! Пример: https://www.twitch.tv/имя_стримера"
            )
            return "STREAMER_CHANNEL"

        user_id = str(update.effective_user.id)
        data = get_or_create_user(STREAMERS_FILE, user_id)

        if "channels" not in data[user_id]:
            data[user_id]["channels"] = {}

        if link in data[user_id]["channels"]:
            await update.message.reply_text("⚠️ Этот канал уже привязан!")
            return await show_streamer_menu(update, context)

        data[user_id]["channels"][link] = {
            "alert_text": "",
            "notifications_enabled": True,
        }
        save_json(STREAMERS_FILE, data)

        keyboard = [
            [KeyboardButton("⚙️ Настроить оповещение")],
            [KeyboardButton("🔔 Включить/Отключить рассылку")],
            [KeyboardButton("🗑️ Удалить канал")],
        ]
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text(
            f"✅ Канал {link} успешно привязан!", reply_markup=reply_markup
        )
        return "STREAMER_MENU"

    async def show_streamer_menu(update, context, text=None):
        user_id = str(update.effective_user.id)
        data = load_json(STREAMERS_FILE)

        if (
            user_id not in data
            or "channels" not in data[user_id]
            or not data[user_id]["channels"]
        ):
            keyboard = [[KeyboardButton("➕ Добавить канал")]]
            reply_markup = ReplyKeyboardMarkup(
                keyboard, resize_keyboard=True, one_time_keyboard=True
            )
            await update.message.reply_text(
                "📡 У тебя пока нет привязанных каналов.\nПришли ссылку на свой Twitch канал:",
                reply_markup=reply_markup,
            )
            return "STREAMER_CHANNEL"

        keyboard = []
        for link in data[user_id]["channels"].keys():
            channel_name = get_channel_name(link)
            keyboard.append([KeyboardButton(f"📺 {channel_name}")])
        keyboard.append([KeyboardButton("➕ Добавить канал")])
        keyboard.append([KeyboardButton("👀 Стать зрителем")])
        keyboard.append([KeyboardButton("💡 Предложить функцию")])

        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )
        msg = text or "📡 Выбери канал:"
        await update.message.reply_text(msg, reply_markup=reply_markup)
        return "STREAMER_CHANNEL_SELECT"

    async def switch_to_viewer(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["role"] = "viewer"
        return await show_viewer_menu(update, context)

    async def switch_to_streamer(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["role"] = "streamer"
        return await show_streamer_menu(update, context)

    async def handle_streamer_channel_select(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        text = update.message.text

        if "добавить" in text.lower():
            await update.message.reply_text(
                "📡 Пришли ссылку на Twitch канал\nНапример: https://www.twitch.tv/имя_стримера"
            )
            return "STREAMER_CHANNEL"

        if "зритель" in text.lower():
            return await switch_to_viewer(update, context)

        if "предложить" in text.lower():
            await update.message.reply_text(
                "💡 Напиши свой вопрос, пожелание или идею по улучшению бота.\n\nСообщение будет отправлено разработчику анонимно."
            )
            return "FEATURE_SUGGESTION"

        if text.startswith("📺 "):
            channel_name = text[2:]
            link = f"https://www.twitch.tv/{channel_name}"
            context.user_data["selected_channel"] = link
            return await show_channel_menu(update, context)

        return await show_streamer_menu(update, context)

    async def show_channel_menu(update, context, text=None):
        user_id = str(update.effective_user.id)
        link = context.user_data.get("selected_channel")
        data = load_json(STREAMERS_FILE)

        if not link or user_id not in data or link not in data[user_id]["channels"]:
            await update.message.reply_text("❌ Канал не найден!")
            return await show_streamer_menu(update, context)

        channel_data = data[user_id]["channels"][link]

        keyboard = [
            [KeyboardButton("✏️ Редактировать описание")],
            [KeyboardButton("🔴 Стрим начался!")],
            [KeyboardButton("🔔 Включить/Отключить рассылку")],
            [KeyboardButton("🗑️ Удалить канал")],
            [KeyboardButton("⬅️ Назад к каналам")],
        ]
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )

        status = (
            "🔔 включены"
            if channel_data.get("notifications_enabled", True)
            else "🔕 выключены"
        )
        desc = channel_data.get("alert_text", "не настроено 😕")

        msg = f"📺 Канал: {link}\n\n📯 Оповещения: {status}\n\n📝 Описание:\n{desc}"

        await update.message.reply_text(msg, reply_markup=reply_markup)
        return "STREAMER_CHANNEL_MENU"

    async def handle_streamer_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user_id = str(update.effective_user.id)
        data = load_json(STREAMERS_FILE)

        if "настроить" in text.lower():
            await update.message.reply_text(
                "✏️ Пришли текст оповещения, который будут получать твои подписчики:"
            )
            return "STREAMER_SET_ALERT"

        elif "включить" in text.lower() or "рассылка" in text.lower():
            if user_id in data and "channels" in data[user_id]:
                for link in data[user_id]["channels"]:
                    data[user_id]["channels"][link]["notifications_enabled"] = not data[
                        user_id
                    ]["channels"][link].get("notifications_enabled", True)
                save_json(STREAMERS_FILE, data)
                await update.message.reply_text("🔄 Рассылка переключена!")
            return await show_streamer_menu(update, context)

        elif "удалить" in text.lower():
            return await show_streamer_menu(update, context)

        return "STREAMER_MENU"

    async def handle_streamer_channel_menu(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        text = update.message.text
        user_id = str(update.effective_user.id)
        link = context.user_data.get("selected_channel")
        data = load_json(STREAMERS_FILE)

        if "редактировать" in text.lower():
            await update.message.reply_text("✏️ Пришли новый текст оповещения:")
            return "STREAMER_EDIT_ALERT"

        elif "стрим начался" in text.lower():
            if user_id in data and link in data[user_id]["channels"]:
                alert_text = data[user_id]["channels"][link].get("alert_text", "")
                if not alert_text:
                    keyboard = [[KeyboardButton("⚙️ Настроить описание")]]
                    reply_markup = ReplyKeyboardMarkup(
                        keyboard, resize_keyboard=True, one_time_keyboard=True
                    )
                    await update.message.reply_text(
                        "⚠️ Сначала настрой описание оповещения!",
                        reply_markup=reply_markup,
                    )
                    return "STREAMER_CHANNEL_MENU"

                preview_text = f"📢 *Оповещение о стриме!* 📢\n\n{alert_text}\n\n🎥 Смотреть: {link}"
                keyboard = [
                    [KeyboardButton("✅ Отправить")],
                    [KeyboardButton("❌ Отмена")],
                ]
                reply_markup = ReplyKeyboardMarkup(
                    keyboard, resize_keyboard=True, one_time_keyboard=True
                )
                await update.message.reply_text(preview_text, reply_markup=reply_markup)
                return "STREAMER_SEND_CONFIRM"
            return "STREAMER_CHANNEL_MENU"

        elif "включить" in text.lower() or "рассылка" in text.lower():
            if user_id in data and link in data[user_id]["channels"]:
                data[user_id]["channels"][link]["notifications_enabled"] = not data[
                    user_id
                ]["channels"][link].get("notifications_enabled", True)
                save_json(STREAMERS_FILE, data)
                await update.message.reply_text("🔄 Рассылка переключена!")
            return await show_channel_menu(update, context)

        elif "удалить" in text.lower():
            if user_id in data and link in data[user_id]["channels"]:
                del data[user_id]["channels"][link]
                save_json(STREAMERS_FILE, data)
                await update.message.reply_text("🗑️ Канал удалён!")
            context.user_data.pop("selected_channel", None)
            return await show_streamer_menu(update, context)

        elif "назад" in text.lower():
            context.user_data.pop("selected_channel", None)
            return await show_streamer_menu(update, context)

        return "STREAMER_CHANNEL_MENU"

    async def handle_streamer_set_alert(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        user_id = str(update.effective_user.id)
        alert_text = update.message.text
        data = load_json(STREAMERS_FILE)

        if user_id in data and "channels" in data[user_id]:
            for link in data[user_id]["channels"]:
                data[user_id]["channels"][link]["alert_text"] = alert_text
            save_json(STREAMERS_FILE, data)

        keyboard = [
            [KeyboardButton("📝 Показать описание")],
            [KeyboardButton("✏️ Редактировать")],
            [KeyboardButton("⬅️ Назад")],
        ]
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text(
            "✅ Описание сохранено!", reply_markup=reply_markup
        )
        return "STREAMER_ALERT_MENU"

    async def handle_streamer_edit_alert(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        user_id = str(update.effective_user.id)
        alert_text = update.message.text
        link = context.user_data.get("selected_channel")
        data = load_json(STREAMERS_FILE)

        if user_id in data and link in data[user_id]["channels"]:
            data[user_id]["channels"][link]["alert_text"] = alert_text
            save_json(STREAMERS_FILE, data)

        return await show_channel_menu(update, context)

    async def handle_streamer_alert_menu(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        text = update.message.text
        user_id = str(update.effective_user.id)
        data = load_json(STREAMERS_FILE)

        if "показать" in text.lower():
            if user_id in data and "channels" in data[user_id]:
                for link, ch in data[user_id]["channels"].items():
                    await update.message.reply_text(
                        f"📺 Канал: {link}\n\n📝 Описание: {ch.get('alert_text', 'не настроено')}"
                    )
            return "STREAMER_ALERT_MENU"

        elif "редактировать" in text.lower():
            await update.message.reply_text("✏️ Пришли новый текст:")
            return "STREAMER_SET_ALERT"

        elif "назад" in text.lower():
            return await show_streamer_menu(update, context)

        return "STREAMER_ALERT_MENU"

    async def handle_streamer_send_confirm(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        text = update.message.text
        user_id = str(update.effective_user.id)
        link = context.user_data.get("selected_channel")

        if "отмена" in text.lower():
            return await show_channel_menu(update, context)

        if "отправить" in text.lower() or "подтвердить" in text.lower():
            data = load_json(STREAMERS_FILE)
            users_data = load_json(USERS_FILE)
            clicks_data = load_clicks()

            if user_id in data and link in data[user_id]["channels"]:
                alert_text = data[user_id]["channels"][link].get("alert_text", "")
                channel_name = get_channel_name(link).capitalize()

                message_text = f"📢 *Оповещение о стриме!* 📢\n\n{alert_text}"

                inline_keyboard = [
                    [
                        InlineKeyboardButton(
                            "🔴 Смотреть!", callback_data=f"watch_{user_id}_{link}"
                        )
                    ]
                ]
                inline_reply_markup = InlineKeyboardMarkup(inline_keyboard)

                sent_count = 0
                for uid, user_info in users_data.items():
                    if "subscriptions" in user_info:
                        for sub_link in user_info["subscriptions"]:
                            if sub_link == link:
                                sub_data = user_info["subscriptions"][sub_link]
                                if sub_data.get("notifications_enabled", True):
                                    try:
                                        await context.bot.send_message(
                                            chat_id=int(uid),
                                            text=message_text,
                                            reply_markup=inline_reply_markup,
                                        )
                                        sent_count += 1
                                    except Exception as e:
                                        logger.error(f"Failed to send to {uid}: {e}")

                link_key = link.replace("https://www.twitch.tv/", "twitch.tv/")
                clicks_count = clicks_data.get(link_key, {}).get("total_clicks", 0)

                await update.message.reply_text(
                    f"✅ Оповещение отправлено {sent_count} пользователям!\n\n📊 Переходов по ссылке: {clicks_count}"
                )

            return await show_channel_menu(update, context)

    async def handle_viewer_add_streamer(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        link = validate_twitch_link(update.message.text)
        if not link:
            await update.message.reply_text(
                "⚠️ Неверный формат ссылки!\nПример: https://www.twitch.tv/имя_стримера"
            )
            return "VIEWER_ADD_STREAMER"

        user_id = str(update.effective_user.id)
        data = get_or_create_user(USERS_FILE, user_id)

        if "subscriptions" not in data[user_id]:
            data[user_id]["subscriptions"] = {}

        if link in data[user_id]["subscriptions"]:
            await update.message.reply_text("⚠️ Этот стример уже добавлен!")
            return await show_viewer_menu(update, context)

        data[user_id]["subscriptions"][link] = {"notifications_enabled": True}
        save_json(USERS_FILE, data)

        keyboard = [
            [KeyboardButton("🔔 Включить")],
            [KeyboardButton("🔕 Выключить")],
            [KeyboardButton("🗑️ Удалить")],
        ]
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text(
            f"✅ Стример {link} добавлен в твои подписки!", reply_markup=reply_markup
        )
        return "VIEWER_MENU"

    async def show_viewer_menu(update, context, text=None):
        user_id = str(update.effective_user.id)
        data = load_json(USERS_FILE)

        if (
            user_id not in data
            or "subscriptions" not in data[user_id]
            or not data[user_id]["subscriptions"]
        ):
            keyboard = [[KeyboardButton("➕ Добавить стримера")]]
            reply_markup = ReplyKeyboardMarkup(
                keyboard, resize_keyboard=True, one_time_keyboard=True
            )
            await update.message.reply_text(
                "👀 У тебя пока нет подписок.\nПришли ссылку на канал стримера:",
                reply_markup=reply_markup,
            )
            return "VIEWER_ADD_STREAMER"

        keyboard = []
        for link in data[user_id]["subscriptions"].keys():
            sub_data = data[user_id]["subscriptions"][link]
            status = "🔔" if sub_data.get("notifications_enabled", True) else "🔕"
            channel_name = get_channel_name(link)
            keyboard.append([KeyboardButton(f"{status} {channel_name}")])
        keyboard.append([KeyboardButton("➕ Добавить стримера")])
        keyboard.append([KeyboardButton("📡 Стать стримером")])
        keyboard.append([KeyboardButton("💡 Предложить функцию")])

        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )
        msg = text or "👀 Твои подписки:"
        await update.message.reply_text(msg, reply_markup=reply_markup)
        return "VIEWER_SUBS_SELECT"

    async def handle_viewer_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user_id = str(update.effective_user.id)
        data = load_json(USERS_FILE)

        if "включить" in text.lower() or "оповещен" in text.lower():
            if user_id in data and "subscriptions" in data[user_id]:
                for link in data[user_id]["subscriptions"]:
                    data[user_id]["subscriptions"][link][
                        "notifications_enabled"
                    ] = not data[user_id]["subscriptions"][link].get(
                        "notifications_enabled", True
                    )
                save_json(USERS_FILE, data)
                await update.message.reply_text("🔄 Оповещения переключены!")
            return await show_viewer_menu(update, context)

        elif "удалить" in text.lower():
            return await show_viewer_menu(update, context)

        return "VIEWER_MENU"

    async def handle_viewer_subs_select(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        text = update.message.text

        if "добавить" in text.lower():
            await update.message.reply_text(
                "👀 Пришли ссылку на канал стримера:\nНапример: https://www.twitch.tv/имя_стримера"
            )
            return "VIEWER_ADD_STREAMER"

        if "стример" in text.lower():
            return await switch_to_streamer(update, context)

        if "предложить" in text.lower():
            await update.message.reply_text(
                "💡 Напиши свой вопрос, пожелание или идею по улучшению бота.\n\nСообщение будет отправлено разработчику анонимно."
            )
            return "FEATURE_SUGGESTION"

        if "🔔" in text or "🔕" in text:
            parts = text.split(" ", 1)
            if len(parts) > 1:
                channel_name = parts[1]
                link = f"https://www.twitch.tv/{channel_name}"
                context.user_data["selected_streamer"] = link
                return await show_streamer_sub_menu(update, context)

        return await show_viewer_menu(update, context)

    async def show_streamer_sub_menu(update, context, text=None):
        user_id = str(update.effective_user.id)
        link = context.user_data.get("selected_streamer")
        data = load_json(USERS_FILE)

        if (
            not link
            or user_id not in data
            or link not in data[user_id]["subscriptions"]
        ):
            await update.message.reply_text("❌ Стример не найден!")
            return await show_viewer_menu(update, context)

        sub_data = data[user_id]["subscriptions"][link]
        status = (
            "🔔 включены"
            if sub_data.get("notifications_enabled", True)
            else "🔕 выключены"
        )

        keyboard = [
            [KeyboardButton("🔔 Включить")],
            [KeyboardButton("🔕 Выключить")],
            [KeyboardButton("🗑️ Удалить")],
            [KeyboardButton("⬅️ Назад к подпискам")],
        ]
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )

        msg = f"📡 Стример: {link}\n\n📯 Оповещения: {status}"
        await update.message.reply_text(msg, reply_markup=reply_markup)
        return "VIEWER_SUB_MENU"

    async def handle_viewer_sub_menu(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        text = update.message.text
        user_id = str(update.effective_user.id)
        link = context.user_data.get("selected_streamer")
        data = load_json(USERS_FILE)

        if "🔔 Включить" in text:
            if user_id in data and link in data[user_id]["subscriptions"]:
                data[user_id]["subscriptions"][link]["notifications_enabled"] = True
                save_json(USERS_FILE, data)
                await update.message.reply_text("✅ Оповещения включены!")
            return await show_streamer_sub_menu(update, context)

        elif "🔕 Выключить" in text:
            if user_id in data and link in data[user_id]["subscriptions"]:
                data[user_id]["subscriptions"][link]["notifications_enabled"] = False
                save_json(USERS_FILE, data)
                await update.message.reply_text("🔕 Оповещения выключены!")
            return await show_streamer_sub_menu(update, context)

        elif "удалить" in text.lower():
            if user_id in data and link in data[user_id]["subscriptions"]:
                del data[user_id]["subscriptions"][link]
                save_json(USERS_FILE, data)
                await update.message.reply_text("🗑️ Стример удалён из подписок!")
            context.user_data.pop("selected_streamer", None)
            return await show_viewer_menu(update, context)

        elif "назад" in text.lower():
            context.user_data.pop("selected_streamer", None)
            return await show_viewer_menu(update, context)

        return "VIEWER_SUB_MENU"

    async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            return

        keyboard = [
            [KeyboardButton("📊 Просмотр баз")],
            [KeyboardButton("📢 Рассылка всем")],
        ]
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text(
            "⚙️ Панель администратора:", reply_markup=reply_markup
        )
        return "ADMIN_MENU"

    async def handle_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text

        if "просмотр" in text.lower() or "баз" in text.lower():
            streamers = load_json(STREAMERS_FILE)
            users = load_json(USERS_FILE)
            await update.message.reply_text(
                f"📊 Статистика:\n\n📡 Стримеров: {len(streamers)}\n👀 Зрителей: {len(users)}"
            )
            return "ADMIN_MENU"

        elif "рассылка" in text.lower():
            await update.message.reply_text(
                "📢 Введи текст для рассылки всем пользователям:"
            )
            return "ADMIN_BROADCAST"

        return "ADMIN_MENU"

    async def handle_admin_broadcast(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        message_text = update.message.text
        streamers = load_json(STREAMERS_FILE)
        users = load_json(USERS_FILE)

        all_ids = set()
        all_ids.update(streamers.keys())
        all_ids.update(users.keys())

        sent_count = 0
        for uid in all_ids:
            try:
                await context.bot.send_message(chat_id=int(uid), text=message_text)
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send to {uid}: {e}")

        await update.message.reply_text(
            f"✅ Рассылка отправлена {sent_count} пользователям!"
        )
        return "ADMIN_MENU"

    async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "❓ Я не понимаю эту команду.\n\nНажми /start чтобы начать заново!"
        )

    async def handle_feature_suggestion(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        suggestion_text = update.message.text
        user_id = str(update.effective_user.id)

        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"💡 Предложение от пользователя (ID: {user_id}):\n\n{suggestion_text}",
        )

        keyboard = [[KeyboardButton("🔄 Вернуться в меню")]]
        reply_markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text(
            "✅ Спасибо! Твоё предложение отправлено разработчику!",
            reply_markup=reply_markup,
        )
        return "FEATURE_SUGGESTION_CONFIRM"

    async def handle_feature_suggestion_confirm(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        text = update.message.text
        if "вернуться" in text.lower() or "меню" in text.lower():
            context.user_data.clear()
            return await start(update, context)
        return await handle_feature_suggestion(update, context)

    application = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_start_pressed),
        ],
        states={
            "WAITING_START": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_start_pressed)
            ],
            "ROLE_SELECTION": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_role_selection)
            ],
            "STREAMER_CHANNEL": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_streamer_channel)
            ],
            "STREAMER_MENU": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_streamer_menu)
            ],
            "STREAMER_CHANNEL_SELECT": [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handle_streamer_channel_select
                )
            ],
            "STREAMER_CHANNEL_MENU": [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handle_streamer_channel_menu
                )
            ],
            "STREAMER_SET_ALERT": [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handle_streamer_set_alert
                )
            ],
            "STREAMER_EDIT_ALERT": [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handle_streamer_edit_alert
                )
            ],
            "STREAMER_ALERT_MENU": [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handle_streamer_alert_menu
                )
            ],
            "STREAMER_SEND_CONFIRM": [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handle_streamer_send_confirm
                )
            ],
            "VIEWER_ADD_STREAMER": [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handle_viewer_add_streamer
                )
            ],
            "VIEWER_MENU": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_viewer_menu)
            ],
            "VIEWER_SUBS_SELECT": [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handle_viewer_subs_select
                )
            ],
            "VIEWER_SUB_MENU": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_viewer_sub_menu)
            ],
            "FEATURE_SUGGESTION": [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handle_feature_suggestion
                )
            ],
            "FEATURE_SUGGESTION_CONFIRM": [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, handle_feature_suggestion_confirm
                )
            ],
            "ADMIN_MENU": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_menu)
            ],
            "ADMIN_BROADCAST": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_broadcast)
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("admin", admin_command),
            MessageHandler(filters.COMMAND, unknown_command),
        ],
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    application.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Bot started")
    application.run_polling()


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("watch_"):
        parts = data.split("_", 2)
        if len(parts) >= 3:
            link = parts[2]

            user_id = str(update.effective_user.id)
            track_click(link, user_id)

            clicks_data = load_clicks()
            link_key = link.replace("https://www.twitch.tv/", "twitch.tv/")
            clicks_count = clicks_data.get(link_key, {}).get("total_clicks", 0)

            channel_name = get_channel_name(link).capitalize()

            inline_keyboard = [[InlineKeyboardButton("🔴 Перейти на канал", url=link)]]
            inline_reply_markup = InlineKeyboardMarkup(inline_keyboard)

            await query.edit_message_text(
                text=f"✅ Переход засчитан!\n\n📊 Всего переходов: {clicks_count}",
                reply_markup=inline_reply_markup,
            )


class TrayIcon:
    def __init__(self, app):
        self.app = app
        self.running = True
        self._start_tray_thread()

    def _start_tray_thread(self):
        thread = threading.Thread(target=self._tray_loop, daemon=True)
        thread.start()

    def _tray_loop(self):
        try:
            from pystray import Menu, MenuItem
            from PIL import Image
        except ImportError:
            self.app.after(0, self._show_tray_error)
            return

        def create_image():
            try:
                from PIL import Image, ImageDraw

                image = Image.new("RGB", (64, 64), color="#3B8ED0")
                draw = ImageDraw.Draw(image)
                draw.ellipse([16, 16, 48, 48], fill="white")
                return image
            except:
                return None

        def on_stop(icon, item):
            self.app.after(0, self.app.stop_bot)

        def on_start(icon, item):
            self.app.after(0, self.app.start_bot)

        def on_restart(icon, item):
            self.app.after(0, self.app.restart_bot)

        def on_exit(icon, item):
            self.app.after(0, self.app.exit_app)

        menu = Menu(
            MenuItem("Стоп", on_stop),
            MenuItem("Старт", on_start),
            MenuItem("Перезапуск", on_restart),
            MenuItem("Выход", on_exit),
        )

        thread = threading.Thread(
            target=self._run_icon, args=(create_image, menu), daemon=True
        )
        thread.start()

    def _run_icon(self, create_image, menu):
        from pystray import Icon

        image = create_image()
        self.icon_obj = Icon("twitch_alert", image, "Twich-Alert", menu)
        self.icon_obj.run()

    def _show_tray_error(self):
        messagebox.showwarning("Предупреждение", "pystray не установлен")

    def stop(self):
        try:
            self.icon_obj.stop()
        except:
            pass


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Twich-Alert Bot Launcher")
        self.geometry("400x200")
        self.resizable(False, False)

        self.bot_process = None
        self.token = ""
        self.tray = None
        self.bot_running = False

        self.setup_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.load_config()

    def setup_ui(self):
        self.label = ctk.CTkLabel(
            self, text="Twich-Alert Bot Launcher", font=("Arial", 16, "bold")
        )
        self.label.pack(pady=20)

        self.token_label = ctk.CTkLabel(self, text="Введите токен бота:")
        self.token_label.pack(pady=5)

        self.token_entry = ctk.CTkEntry(
            self, width=300, placeholder_text="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
        )
        self.token_entry.pack(pady=5)

        self.token_entry.bind("<Control-v>", self._paste_token)
        self.token_entry.bind("<Control-V>", self._paste_token)
        self.token_entry.bind("<Button-3>", self._paste_token)

        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.pack(pady=20)

        self.start_button = ctk.CTkButton(
            self.button_frame, text="Запустить", command=self.start_bot, width=120
        )
        self.start_button.pack(side="left", padx=5)

        self.cancel_button = ctk.CTkButton(
            self.button_frame,
            text="Отмена",
            command=self.cancel,
            width=120,
            fg_color="gray",
        )
        self.cancel_button.pack(side="left", padx=5)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.token = config.get("bot_token", "")
                    if self.token:
                        self.token_entry.insert(0, self.token)
            except:
                pass

    def _paste_token(self, event=None):
        try:
            clipboard = self.clipboard_get()
            self.token_entry.insert("end", clipboard)
        except:
            pass
        return "break"

    def save_config(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"bot_token": self.token}, f)

    def start_bot(self):
        if self.bot_running and self.bot_process:
            messagebox.showinfo("Инфо", "Бот уже запущен!")
            return

        self.token = self.token_entry.get().strip()
        if not self.token:
            messagebox.showerror("Ошибка", "Введите токен бота!")
            return

        self.save_config()
        self.withdraw()

        self.bot_process = multiprocessing.Process(target=run_bot, args=(self.token,))
        self.bot_process.daemon = True
        self.bot_process.start()

        self.bot_running = True
        self.show_running_window()

    def show_running_window(self):
        self.running_window = CTkToplevel(self)
        self.running_window.title("Twich-Alert")
        self.running_window.geometry("400x150")
        self.running_window.resizable(False, False)

        label = ctk.CTkLabel(
            self.running_window,
            text="Бот запущен!\nДля отключения или перезапуска бота\nвоспользуйтесь иконкой в трее!",
            font=("Arial", 14),
        )
        label.pack(expand=True, pady=20)

        ok_button = ctk.CTkButton(
            self.running_window, text="OK", command=self.running_window.withdraw
        )
        ok_button.pack(pady=10)

        self.running_window.withdraw()
        self.setup_tray()

    def setup_tray(self):
        self.tray = TrayIcon(self)

    def stop_bot(self):
        if self.bot_process and self.bot_process.is_alive():
            self.bot_process.terminate()
            self.bot_process = None
        self.bot_running = False
        messagebox.showinfo("Инфо", "Бот остановлен!")

    def restart_bot(self):
        self.stop_bot()
        time.sleep(1)
        if self.token:
            self.bot_process = multiprocessing.Process(
                target=run_bot, args=(self.token,)
            )
            self.bot_process.daemon = True
            self.bot_process.start()
            self.bot_running = True
            messagebox.showinfo("Инфо", "Бот перезапущен!")
        else:
            messagebox.showwarning("Предупреждение", "Токен не сохранён!")

    def cancel(self):
        self.on_closing()

    def on_closing(self):
        if self.bot_process and self.bot_process.is_alive():
            self.bot_process.terminate()
        if self.tray:
            self.tray.stop()
        self.destroy()
        sys.exit()

    def exit_app(self):
        self.on_closing()


def main():
    multiprocessing.freeze_support()
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
