import os
os.environ["TZ"] = "UTC"
import logging
import nest_asyncio
nest_asyncio.apply()
import re
from telegram import Update, ReplyKeyboardMarkup, ChatMember
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from ai import generate_training_passage
import json
from datetime import datetime
import pymongo

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
CHANNEL_USERNAME = "ElDocEnglish"
DATA_FILE = "users_data.txt"
CEFR_LEVELS = ["A1 - كفتة 🤏", "A2 - مبتدئ 👽", "B1 - نص نص 🐢", "B2 - فنان 🎨", "C1 -  معلم شاورما 🗡️", "C2 - مواطن امريكي اصلي 🇺🇸"]

PLACEMENT_PASSAGES = [
    # ... نفس الفقرات السابقة ...
]

# MongoDB setup
mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client["readingbot"]
users_collection = db["users"]

def save_user(user_id, username, name):
    now = datetime.utcnow()
    user = users_collection.find_one({"user_id": user_id})
    if user:
        users_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "last_active": now,
                "username": username,
                "name": name
            }, "$inc": {"usage_count": 1}}
        )
    else:
        users_collection.insert_one({
            "user_id": user_id,
            "username": username,
            "name": name,
            "first_join": now,
            "last_active": now,
            "usage_count": 1
        })

async def check_channel_membership(update: Update):
    user_id = update.message.from_user.id
    try:
        member = await update.message.bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        if member.status not in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            return False
        return True
    except Exception:
        return False

async def send_long_message(update, text):
    max_len = 4000
    for i in range(0, len(text), max_len):
        await update.message.reply_text(
            text[i:i+max_len],
            disable_web_page_preview=True,
            protect_content=True
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    username = user.username or ""
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    save_user(user_id, username, name)

    # اشتراك إجباري
    if not await check_channel_membership(update):
        await update.message.reply_text(
            f"🔴 للاستخدام يجب الاشتراك في القناة أولاً:\n\n"
            f"👉 [اضغط هنا للاشتراك](https://t.me/{CHANNEL_USERNAME})\n\n"
            f"ثم أرسل /start بعد الاشتراك.",
            disable_web_page_preview=True,
            protect_content=True,
            reply_markup=ReplyKeyboardMarkup([["اشتركت ✅"]], one_time_keyboard=True)
        )
        return

    welcome_message = (
        "👋 Ladies and gentlemen, we are pleased to announce ~ Doctors English Reading Assistant!\n"
        "📚 هتوصلك فقرات قراءة وأسئلة حسب مستواك.\n"
        "🔔 يُرجى الاشتراك في القناة: @ElDocEnglish\n"
        "______________________________________\n"
        "🔴🔴 ®   جميع الحقوق محفوظة لقناة Doctors English   ® 🔴🔴\n"
        "______________________________________"
    )

    levels_message = (
        "🧠 مستويات الإنجليزي حسب معيار CEFR:\n\n"
        "🔸 A1 - كفتة 🤏\n"
        "🔸 A2 - مبتدئ 👽\n"
        "🔸 B1 - نص نص 🐢\n"
        "🔸 B2 - فنان 🎨\n"
        "🔸 C1 -  معلم شاورما 🗡️\n"
        "🔸 C2 - مواطن امريكي اصلي 🇺🇸\n\n"
        "❓  تعرف انت أي مستوى؟"
    )

    await update.message.reply_text(welcome_message, disable_web_page_preview=True, protect_content=True)
    await update.message.reply_text(
        levels_message,
        reply_markup=ReplyKeyboardMarkup([["Yes", "No"]], one_time_keyboard=True),
        disable_web_page_preview=True,
        protect_content=True
    )

async def send_ready_question(update, text="هل أنت جاهز للفقرة ؟"):
    keyboard = ReplyKeyboardMarkup([["جاهز 🚀"]], one_time_keyboard=True)
    await update.message.reply_text(text, reply_markup=keyboard, disable_web_page_preview=True, protect_content=True)

def get_static_placement_passage(level):
    for passage in PLACEMENT_PASSAGES:
        if passage["level"] == level:
            return {
                "paragraph": passage["paragraph"],
                "questions": passage["questions"],
                "answers": passage["answers"]
            }
    return None

async def send_placement_passage(update, context, level, user_state):
    await update.message.reply_text(f"📤 جاري إرسال فقرة مستوى {level} التأسيسية، اتقل علينا خمسة🤌...", disable_web_page_preview=True, protect_content=True)
    await update.message.reply_chat_action("typing")
    data = get_static_placement_passage(level)
    if not data or "answers" not in data or not data["answers"]:
        await update.message.reply_text("❌ حدث خطأ أثناء إنشاء الفقرة. حاول مرة أخرى.", disable_web_page_preview=True, protect_content=True)
        return
    user_state["step"] = "waiting_ready_testing"
    user_state["pending_data"] = data

    await send_ready_question(update)

async def send_training_passage(update, context, level, user_state):
    await update.message.reply_text(f"📤 تدريب جديد لمستوى {level} ، ثواني و يكون عندك..", disable_web_page_preview=True, protect_content=True)
    await update.message.reply_chat_action("typing")
    try:
        data = await generate_training_passage(level)
    except Exception as e:
        await update.message.reply_text("❌ حدث خطأ أثناء توليد الفقرة (استثناء داخلي).", disable_web_page_preview=True, protect_content=True)
        return
    if not data or "answers" not in data or not data["answers"]:
        await update.message.reply_text("❌ حدث خطأ أثناء توليد الفقرة. تحقق من اتصال الذكاء الاصطناعي أو المفتاح.", disable_web_page_preview=True, protect_content=True)
        return
    user_state["step"] = "training_answer"
    user_state["pending_data"] = data
    user_state["correct_answers"] = data["answers"]

    message = f"📖 فقرة المستوى:\n\n{data['paragraph']}\n\n"
    for i, q in enumerate(data["questions"], 1):
        question_without_answer = re.sub(r'(Answer|الإجابة)\s*[:\-]?.*', '', q, flags=re.IGNORECASE).strip()
        message += f"{question_without_answer}\n\n"
    message += "\n📩 أرسل إجاباتك كحروف (مثال: a b c b a)"
    message += "\n______________________________________"
    message += "\n🔴🔴 ®   جميع الحقوق محفوظة لقناة Doctors English   ® 🔴🔴"
    await send_long_message(update, message)
    return

def grade_answers(user_answers, correct_answers):
    score = 0
    correct_list = []
    wrong_list = []
    for i, (ua, ca) in enumerate(zip(user_answers, correct_answers)):
        if ua.lower() == ca.lower():
            score += 1
            correct_list.append(i+1)
        else:
            wrong_list.append(i+1)
    return score, correct_list, wrong_list

def get_next_level(current_level, result):
    idx = CEFR_LEVELS.index(current_level)
    if result == "upgrade" and idx < len(CEFR_LEVELS) - 1:
        return CEFR_LEVELS[idx + 1]
    elif result == "downgrade" and idx > 0:
        return CEFR_LEVELS[idx - 1]
    return current_level

user_states = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = str(user.id)
    username = user.username or ""
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    save_user(user_id, username, name)

    # اشتراك إجباري
    if not await check_channel_membership(update):
        await update.message.reply_text(
            f"🔴 للاستخدام يجب الاشتراك في القناة أولاً:\n\n"
            f"👉 [اضغط هنا للاشتراك](https://t.me/{CHANNEL_USERNAME})\n\n"
            f"ثم أرسل /start بعد الاشتراك.",
            disable_web_page_preview=True,
            protect_content=True,
            reply_markup=ReplyKeyboardMarkup([["اشتركت ✅"]], one_time_keyboard=True)
        )
        return

    user_state = user_states.get(user_id)
    if not user_state:
        user_state = {
            "step": "ask_known_level",
            "results": {},
            "waiting": False,
            "placement_index": 0,
            "placement_scores": [],
            "training_history": []
        }
        user_states[user_id] = user_state

    text = update.message.text.strip()

    if user_state.get("waiting", False):
        await update.message.reply_text("اهدى علينا يبن الحلال 🤌", disable_web_page_preview=True, protect_content=True)
        return

    if user_state.get("step") == "waiting_ready_testing":
        if text.lower() == "جاهز 🚀":
            data = user_state.get("pending_data")
            if not data:
                await update.message.reply_text("❌ خطأ داخلي، حاول /start من جديد.", disable_web_page_preview=True, protect_content=True)
                return
            user_state["step"] = "testing_answer"
            user_state["correct_answers"] = data["answers"]
            message = f"📖 فقرة المستوى:\n\n{data['paragraph']}\n\n"
            for i, q in enumerate(data["questions"], 1):
                question_without_answer = re.sub(r'(Answer|الإجابة)\s*[:\-]?.*', '', q, flags=re.IGNORECASE).strip()
                message += f"{question_without_answer}\n\n"
            message += "\n📩 أرسل إجاباتك كحروف (مثال: a b c b a)"
            message += "\n______________________________________"
            message += "\n🔴🔴 ®   جميع الحقوق محفوظة لقناة Doctors English   ® 🔴🔴"
            await send_long_message(update, message)
            return
        else:
            await update.message.reply_text('من فضلك اضغط "جاهز 🚀" عندما تكون مستعدًا.', disable_web_page_preview=True, protect_content=True)
            return

    if user_state.get("step") == "waiting_ready_training":
        if text.lower() == "جاهز 🚀":
            user_state["pending_data"] = None
            await send_training_passage(update, context, user_state["level"], user_state)
            return
        else:
            await update.message.reply_text('من فضلك اضغط "جاهز 🚀" عندما تكون مستعدًا.', disable_web_page_preview=True, protect_content=True)
            return

    if user_state.get("step") in ["testing_answer", "training_answer"]:
        data = user_state.get("correct_answers", [])
        user_answers = [a.strip().lower() for a in text.split() if a.strip().lower() in ["a", "b", "c", "d"]]

        if len(user_answers) != len(data):
            await update.message.reply_text(
                f"❌ عدد الإجابات يجب أن يكون {len(data)}. رجاءً أعد إرسال الإجابات بشكل صحيح.",
                disable_web_page_preview=True,
                protect_content=True
            )
            return

        score, correct_list, wrong_list = grade_answers(user_answers, data)

        if user_state.get("step") == "testing_answer":
            index = user_state.get("placement_index", 0)
            user_state.setdefault("placement_scores", [])
            user_state["placement_scores"].append(score)
            user_state["placement_index"] = index + 1

            msg = f"✅ أجبت {score} من {len(data)} صحيحة.\n"
            if correct_list:
                msg += f"✔ الإجابات الصحيحة: {', '.join(map(str, correct_list))}\n"
            if wrong_list:
                msg += f"❌ الإجابات الخاطئة: {', '.join(map(str, wrong_list))}\n"
            msg += "\n______________________________________"
            await update.message.reply_text(msg, disable_web_page_preview=True, protect_content=True)

            if user_state["placement_index"] < len(CEFR_LEVELS):
                user_state["step"] = "waiting_ready_testing"
                user_state["pending_data"] = None
                level = CEFR_LEVELS[user_state["placement_index"]]
                await update.message.reply_text(
                    f"🔜 ننتقل إلى فقرة مستوى {level} التأسيسية.",
                    disable_web_page_preview=True,
                    protect_content=True
                )
                await send_placement_passage(update, context, level, user_state)
                return
            else:
                total_scores = user_state.get("placement_scores", [])
                avg_score = sum(total_scores) / len(total_scores)
                if avg_score >= 5:
                    final_level_index = len(CEFR_LEVELS) - 1
                elif avg_score >= 4:
                    final_level_index = len(CEFR_LEVELS) - 2
                elif avg_score >= 3:
                    final_level_index = len(CEFR_LEVELS) - 3
                else:
                    final_level_index = 0

                final_level = CEFR_LEVELS[final_level_index]
                user_state["step"] = "waiting_ready_training"
                user_state["level"] = final_level
                user_state["placement_index"] = 0
                user_state["pending_data"] = None

                summary = (
                    f"✅ انتهيت من تقييم المستويات التأسيسية.\n"
                    f"🎯 مستواك النهائي حسب التأسيس: {final_level}\n"
                    f"📝 الدرجات على الفقرات: {total_scores}\n"
                    "______________________________________\n"
                    "💪 أنت دلوقتي جاهز تبدأ التدريبات!\n"
                    "طول ما انت هنا، معناه انك بتستثمر في نفسك...\n"
                )
                await update.message.reply_text(summary, disable_web_page_preview=True, protect_content=True)
                await send_ready_question(update, text=f" مستعد نبدأ التدريبات بناءاً على مستواك؟")
                return

        else:
            # التدريب
            level = user_state.get("level", "A1")
            msg = f"✅ أجبت {score} من {len(data)} صحيحة.\n"
            if correct_list:
                msg += f"✔ الإجابات الصحيحة: {', '.join(map(str, correct_list))}\n"
            if wrong_list:
                msg += f"❌ الإجابات الخاطئة: {', '.join(map(str, wrong_list))}\n"
            msg += f"\n🌟 مستواك الحالي: {level}\n"

            old_level = level
            if score <= 4:
                result = "downgrade"
            elif score == 8:
                result = "upgrade"
            else:
                result = "hold"

            new_level = get_next_level(level, result)
            user_state["level"] = new_level
            user_state["training_history"].append({
                "old_level": old_level,
                "new_level": new_level,
                "score": score
            })
            user_state["step"] = "waiting_ready_training"
            user_state["pending_data"] = None

            if result == "upgrade":
                msg += f"\n🎉 تم ترقية مستواك من {old_level} إلى {new_level}!"
            elif result == "downgrade":
                msg += f"\n⚠️ تم تخفيض مستواك من {old_level} إلى {new_level}."
            else:
                msg += f"\n✅ تم تثبيت مستواك على {old_level}."

            msg += "\n______________________________________"
            await update.message.reply_text(msg, disable_web_page_preview=True, protect_content=True)
            await send_ready_question(update, text="هل أنت جاهز للتدريب ؟")
            return

    if user_state.get("step") == "ask_known_level":
        if text.lower() == "yes":
            user_state["step"] = "choose_level"
            await update.message.reply_text(
                "من فضلك اختر مستواك:",
                reply_markup=ReplyKeyboardMarkup([[lvl] for lvl in CEFR_LEVELS], one_time_keyboard=True),
                disable_web_page_preview=True,
                protect_content=True
            )
        elif text.lower() == "no":
            user_state["step"] = "testing"
            user_state["placement_index"] = 0
            user_state["placement_scores"] = []
            await send_placement_passage(update, context, CEFR_LEVELS[0], user_state)
        else:
            await update.message.reply_text("من فضلك اختر Yes أو No.", disable_web_page_preview=True, protect_content=True)
        return

    if user_state.get("step") == "choose_level":
        if text.upper() in CEFR_LEVELS:
            user_state["step"] = "training"
            user_state["level"] = text.upper()
            await update.message.reply_text(
                f"تم اختيار مستواك: {text.upper()}.\nاستعد للتدريبات!",
                disable_web_page_preview=True,
                protect_content=True
            )
            await send_training_passage(update, context, user_state["level"], user_state)
        else:
            await update.message.reply_text("من فضلك اختر مستوى من القائمة.", disable_web_page_preview=True, protect_content=True)
        return

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    await app.bot.delete_webhook(drop_pending_updates=True)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if str(e).startswith("This event loop is already running"):
            import nest_asyncio
            nest_asyncio.apply()
            loop = asyncio.get_event_loop()
            loop.create_task(main())
            loop.run_forever()
        else:
            raise
