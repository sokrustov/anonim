import logging
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
DB_FILE = "bot_database.json"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    def __init__(self, filename):
        self.filename = filename
        self.data = self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "messages" not in data: data["messages"] = []
                    if "users" not in data: data["users"] = {}
                    if "banned" not in data: data["banned"] = []
                    if "user_states" not in data: data["user_states"] = {}
                    if "statistics" not in data: data["statistics"] = {"total_messages": 0, "total_users": 0}
                    return data
            except:
                return self._create_empty_db()
        return self._create_empty_db()

    def _create_empty_db(self):
        return {
            "users": {}, "user_states": {}, "messages": [], "banned": [],
            "statistics": {"total_messages": 0, "total_users": 0, "bot_started": datetime.now().isoformat()}
        }

    def save(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def add_user(self, user_id, username, full_name):
        uid = str(user_id)
        if uid not in self.data["users"]:
            self.data["users"][uid] = {
                "user_id": user_id, "username": username, "full_name": full_name,
                "first_seen": datetime.now().isoformat(), "messages_sent": 0, "messages_received": 0
            }
            self.data["statistics"]["total_users"] = len(self.data["users"])
        else:
            self.data["users"][uid]["username"] = username
        self.save()


db = Database(DB_FILE)


def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Моя ссылка", callback_data="get_link"),
         InlineKeyboardButton("📊 Статистика", callback_data="get_stats")],
        [InlineKeyboardButton("🆘 Тех. поддержка", url="https://t.me/svchostt_tech_bot")]
    ])


def get_admin_main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 Последние сообщения", callback_data="adm_logs_main")],
        [InlineKeyboardButton("👥 Список пользователей", callback_data="adm_all_users")],
        [InlineKeyboardButton("👤 Поиск по ID юзера", callback_data="adm_find_user")],
        [InlineKeyboardButton("🔄 Поиск переписки (A ↔️ B)", callback_data="adm_find_pair")],
        [InlineKeyboardButton("🚫 Управление баном", callback_data="adm_ban_panel")],
        [InlineKeyboardButton("📊 Статистика", callback_data="adm_global_stats")],
        [InlineKeyboardButton("❌ Закрыть", callback_data="adm_close")]
    ])


def get_back_to_admin_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ В меню админа", callback_data="adm_back_to_main")]])


def get_user_display(uid):
    uid_s = str(uid)
    user_info = db.data["users"].get(uid_s, {})
    username = user_info.get("username")
    status = "🔴 [BANNED]" if int(uid) in db.data["banned"] else ""
    user_tag = f"(@{username})" if username else "()"
    return f"<code>{uid}</code> {user_tag} {status}"


def format_messages(messages_list, title):
    if not messages_list:
        return "📭 Сообщений не найдено.", get_back_to_admin_kb()
    res = f"<b>{title}</b>\n" + "—" * 15 + "\n"
    for m in messages_list[-10:]:
        date = m.get('date', '').split('T')[-1][:5]
        s_id = m.get('from', '???')
        r_id = m.get('to', '???')
        res += f"🕒 {date}\nОт: {get_user_display(s_id)}\nКому: {get_user_display(r_id)}\n📝 {m.get('content', '[Медиа]')}\n\n"
    return res, get_back_to_admin_kb()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in db.data["banned"]:
        return await update.message.reply_text("🚫 Вы заблокированы.")

    db.add_user(user.id, user.username, user.full_name)
    if context.args:
        try:
            target = int(context.args[0])
            if target in db.data["banned"]:
                return await update.message.reply_text("❌ Получатель заблокирован.")
            if target != user.id:
                db.data["user_states"][str(user.id)] = {"state": "waiting_anon", "target_id": target}
                db.save()
                return await update.message.reply_text(f"✉️ Введите сообщение для `{target}`:",
                                                       reply_markup=InlineKeyboardMarkup(
                                                           [[InlineKeyboardButton("❌ Отмена",
                                                                                  callback_data="cancel_anon")]]))
        except:
            pass
    await update.message.reply_text(f"👋 Привет, {user.first_name}!", reply_markup=main_kb())


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    await update.message.reply_text("🛠 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=get_admin_main_kb())


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    if data == "get_link":
        await query.message.reply_text(f"🔗 Ссылка: `https://t.me/{context.bot.username}?start={user_id}`",
                                       parse_mode="Markdown")
    elif data == "get_stats":
        u = db.data["users"].get(str(user_id), {})
        await query.message.reply_text(
            f"📊 Статистика:\n✉️ Отправлено: {u.get('messages_sent', 0)}\n📩 Получено: {u.get('messages_received', 0)}")
    elif data == "cancel_anon":
        db.data["user_states"].pop(str(user_id), None)
        db.save()
        await query.edit_message_text("❌ Отменено.", reply_markup=main_kb())

    elif user_id == OWNER_ID:
        if data == "adm_back_to_main":
            context.user_data.clear()
            await query.edit_message_text("🛠 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=get_admin_main_kb())
        elif data == "adm_close":
            await query.message.delete()
        elif data == "adm_all_users":
            text = "👥 <b>Все пользователи:</b>\n\n" + "\n".join([f"• {get_user_display(u)}" for u in db.data["users"]])
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=get_back_to_admin_kb())
        elif data == "adm_logs_main":
            text, kb = format_messages(db.data.get("messages", []), "Последние сообщения")
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        elif data == "adm_find_user":
            context.user_data['adm_state'] = 'wait_user_id'
            await query.edit_message_text("👤 Введите ID пользователя:", reply_markup=get_back_to_admin_kb())
        elif data == "adm_find_pair":
            context.user_data['adm_state'] = 'wait_pair_ids'
            await query.edit_message_text("🔄 Введите два ID через пробел:", reply_markup=get_back_to_admin_kb())
        elif data == "adm_ban_panel":
            context.user_data['adm_state'] = 'wait_ban_id'
            await query.edit_message_text("🚫 Введите ID для бана/разбана:", reply_markup=get_back_to_admin_kb())
        elif data == "adm_global_stats":
            stats = db.data.get("statistics", {})
            res = f"📊 Статистика:\n👥 Юзеров: {stats.get('total_users', 0)}\n📨 Сообщений: {len(db.data['messages'])}"
            await query.edit_message_text(res, parse_mode="HTML", reply_markup=get_admin_main_kb())


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid_s = str(user.id)
    msg = update.message

    if user.id == OWNER_ID and context.user_data.get('adm_state'):
        state = context.user_data.get('adm_state')
        if state == 'wait_ban_id' and msg.text.isdigit():
            tid = int(msg.text)
            if tid in db.data["banned"]:
                db.data["banned"].remove(tid)
                res = f"✅ {tid} разбанен."
            else:
                db.data["banned"].append(tid)
                res = f"🚫 {tid} забанен."
            db.save()
            return await msg.reply_text(res, reply_markup=get_back_to_admin_kb())
        elif state == 'wait_user_id' and msg.text.isdigit():
            tid = msg.text
            filtered = [m for m in db.data["messages"] if str(m.get('from')) == tid or str(m.get('to')) == tid]
            text, kb = format_messages(filtered, f"Логи {tid}")
            return await msg.reply_text(text, parse_mode="HTML", reply_markup=kb)
        elif state == 'wait_pair_ids':
            try:
                u1, u2 = msg.text.split()
                filtered = [m for m in db.data["messages"] if (str(m.get('from')) == u1 and str(m.get('to')) == u2) or (
                            str(m.get('from')) == u2 and str(m.get('to')) == u1)]
                text, kb = format_messages(filtered, f"Диалог {u1}-{u2}")
                return await msg.reply_text(text, parse_mode="HTML", reply_markup=kb)
            except:
                pass

    state_data = db.data["user_states"].get(uid_s)
    if state_data and state_data.get("state") == "waiting_anon":
        target_id = state_data["target_id"]
        prefix = "✉️ <b>Вы получили новое анонимное сообщение:</b>\n\n"

        try:
            if msg.text:
                await context.bot.send_message(chat_id=target_id, text=f"{prefix}{msg.text}", parse_mode="HTML")
            elif msg.photo or msg.video or msg.voice or msg.document:
                new_caption = f"{prefix}{msg.caption if msg.caption else ''}"
                await context.bot.copy_message(chat_id=target_id, from_chat_id=user.id, message_id=msg.message_id,
                                               caption=new_caption, parse_mode="HTML")

            db.data["messages"].append({"from": user.id, "to": target_id, "date": datetime.now().isoformat(),
                                        "content": msg.text or "[Медиа]"})
            db.data["users"][uid_s]["messages_sent"] += 1
            if str(target_id) in db.data["users"]: db.data["users"][str(target_id)]["messages_received"] += 1
            db.data["user_states"].pop(uid_s, None)
            db.save()
            await msg.reply_text("✅ Доставлено!", reply_markup=main_kb())
        except:
            await msg.reply_text("❌ Ошибка доставки.")
    else:
        if user.id != OWNER_ID: await msg.reply_text("Выберите действие:", reply_markup=main_kb())


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == '__main__': main()