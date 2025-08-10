import os
os.environ["TZ"] = "UTC"
import logging
import nest_asyncio
nest_asyncio.apply()
import re
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from ai import generate_training_passage
import json

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATA_FILE = "users_data.txt"
user_data = {}
CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

PLACEMENT_PASSAGES = [
    {
        "level": "A1",
        "paragraph": "This is my friend, Alex. He is from London. Alex likes to eat pizza and he likes to drink water. He has a cat. The cat's name is Leo. Leo is black and white.",
        "questions": [
            "1. Where is Alex from?\na) Italy\nb) London\nc) Egypt",
            "2. What does Alex like to eat?\na) Salad\nb) Pasta\nc) Pizza",
            "3. What is the cat's name?\na) Alex\nb) Leo\nc) London",
            "4. What color is the cat?\na) Red and white\nb) Black and white\nc) Brown and white",
            "5. Does Alex have a dog?\na) Yes\nb) No"
        ],
        "answers": ["b", "c", "b", "b", "b"]
    },
    {
        "level": "A2",
        "paragraph": "I went to the supermarket yesterday. I needed to buy some milk and bread for breakfast. When I was there, I also saw some fresh apples and bananas, so I decided to buy them too. The supermarket was very busy, and it took me a long time to get to the checkout counter.",
        "questions": [
            "1. When did the person go to the supermarket?\na) Today\nb) Tomorrow\nc) Yesterday",
            "2. What did they need to buy for breakfast?\na) Juice and eggs\nb) Milk and bread\nc) Cereal and coffee",
            "3. What fruit did they buy?\na) Oranges and grapes\nb) Apples and bananas\nc) Pears and peaches",
            "4. How was the supermarket?\na) Empty\nb) Quiet\nc) Busy",
            "5. Why did it take a long time to get to the checkout?\na) The person was slow.\nb) The supermarket was very busy.\nc) They got lost."
        ],
        "answers": ["c", "b", "b", "c", "b"]
    },
    {
        "level": "B1",
        "paragraph": "Sarah is planning her summer vacation. She wants to visit a new country. She has narrowed down her choices to two places: Spain and Greece. She loves the idea of exploring historic ruins in Greece, but she is also attracted to the beautiful beaches in Spain. She has a limited budget, so she needs to research flight and hotel prices carefully before making a final decision.",
        "questions": [
            "1. What is Sarah planning?\na) A new job\nb) Her summer vacation\nc) A party",
            "2. How many countries is she considering?\na) One\nb) Two\nc) Three",
            "3. What does she love the idea of doing in Greece?\na) Swimming in the sea\nb) Visiting family\nc) Exploring historic ruins",
            "4. What is an important factor in her decision?\na) The weather\nb) The food\nc) Her limited budget",
            "5. Which country does she think has beautiful beaches?\na) Spain\nb) Greece\nc) Italy"
        ],
        "answers": ["b", "b", "c", "c", "a"]
    },
    {
        "level": "B2",
        "paragraph": "The global push for renewable energy sources has gained significant momentum in recent years. Solar and wind power are now competitive with traditional fossil fuels in many regions. However, a major challenge remains: the intermittency of these sources. The sun doesn't always shine and the wind doesn't always blow. Consequently, developing efficient energy storage solutions, such as large-scale batteries, is crucial for a truly sustainable energy future.",
        "questions": [
            "1. What has gained momentum recently?\na) The use of fossil fuels\nb) The global push for renewable energy\nc) Tourism",
            "2. Which renewable sources are mentioned?\na) Hydropower and geothermal\nb) Solar and wind power\nc) Biomass and nuclear",
            "3. What is a major challenge for these sources?\na) Their high cost\nb) Their intermittent nature\nc) The lack of technology",
            "4. Why is the sun not a reliable energy source by itself?\na) It's too hot.\nb) It doesn't always shine.\nc) It's only available in some countries.",
            "5. What is crucial for a sustainable energy future?\na) Using more fossil fuels\nb) Developing energy storage solutions\nc) Building more power plants"
        ],
        "answers": ["b", "b", "b", "b", "b"]
    },
    {
        "level": "C1",
        "paragraph": "The novel \"1984\" by George Orwell serves as a powerful and enduring critique of totalitarianism. It explores themes of government surveillance, psychological manipulation, and the erosion of truth. The concept of \"Big Brother\" has become a cultural shorthand for a controlling, oppressive authority. Orwell’s masterful use of dystopian imagery and a chillingly plausible future continues to resonate with readers, prompting them to reflect on the nature of power and individual freedom in their own societies.",
        "questions": [
            "1. What is \"1984\" a critique of?\na) Democracy\nb) Totalitarianism\nc) Capitalism",
            "2. Which of the following is NOT a theme explored in the novel?\na) The importance of family\nb) Government surveillance\nc) The erosion of truth",
            "3. What has \"Big Brother\" become a cultural shorthand for?\na) A loving father\nb) A controlling authority\nc) A famous singer",
            "4. What literary device does Orwell use effectively?\na) Poetic verse\nb) Dystopian imagery\nc) Romantic metaphors",
            "5. What does the novel prompt readers to reflect on?\na) The history of Britain\nb) The nature of power and freedom\nc) The origins of the internet"
        ],
        "answers": ["b", "a", "b", "b", "b"]
    },
    {
        "level": "C2",
        "paragraph": "The advent of quantum computing promises to revolutionize fields ranging from cryptography to medicine. Unlike classical computers which use bits representing either 0 or 1, quantum computers leverage qubits, which can exist in a superposition of both states simultaneously. This allows them to perform complex calculations at an unprecedented speed. While still in its nascent stages, the potential of this technology to solve problems currently intractable for even the most powerful supercomputers is immense, but it also raises profound questions about future security and technological ethics.",
        "questions": [
            "1. What is a key difference between classical and quantum computers?\na) Classical computers use qubits, quantum computers use bits.\nb) Classical computers use bits, quantum computers use qubits.\nc) They both use the same type of processing unit.",
            "2. What allows quantum computers to perform calculations at an unprecedented speed?\na) They are much larger than classical computers.\nb) Their qubits can exist in a superposition of states.\nc) They use a new type of battery.",
            "3. What is the current stage of quantum computing development?\na) It is widely available to the public.\nb) It is still in its early (nascent) stages.\nc) It has been replaced by an even newer technology.",
            "4. What is a potential impact of this technology?\na) It will make all old computers obsolete immediately.\nb) It will solve problems that are currently too difficult.\nc) It will only be used for entertainment.",
            "5. What kind of questions does this technology raise?\na) Questions about grammar and spelling.\nb) Questions about politics and history.\nc) Questions about future security and ethics."
        ],
        "answers": ["b", "b", "b", "b", "c"]
    }
]

def get_static_placement_passage(level):
    for passage in PLACEMENT_PASSAGES:
        if passage["level"] == level:
            return {
                "paragraph": passage["paragraph"],
                "questions": passage["questions"],
                "answers": passage["answers"]
            }
    return None

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_data, f, indent=2, ensure_ascii=False)

async def send_long_message(update, text):
    max_len = 4000
    for i in range(0, len(text), max_len):
        await update.message.reply_text(text[i:i+max_len])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user_data[user_id] = {
        "step": "ask_known_level",
        "results": {},
        "waiting": False,
        "placement_index": 0,
        "placement_scores": [],
        "training_history": []
    }
    save_data()

    welcome_message = (
        "👋 Ladies and gentlemen, we are pleased to announce ~ Doctors English Reading Assistant!\n"
        "📚 هتوصلك فقرات قراءة وأسئلة حسب مستواك.\n"
        "🔔 يُرجى الاشتراك في القناة: @eldocenglish\n"
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

    await update.message.reply_text(welcome_message)
    await update.message.reply_text(
        levels_message,
        reply_markup=ReplyKeyboardMarkup([["Yes", "No"]], one_time_keyboard=True)
    )

async def send_ready_question(update, text="هل أنت جاهز للفقرة ؟"):
    keyboard = ReplyKeyboardMarkup([["جاهز 🚀"]], one_time_keyboard=True)
    await update.message.reply_text(text, reply_markup=keyboard)

async def send_placement_passage(update, context, level):
    user_id = str(update.message.from_user.id)
    user_state = user_data.get(user_id, {})
    user_state["waiting"] = True
    save_data()

    await update.message.reply_text(f"📤 جاري إرسال فقرة مستوى {level} التأسيسية، اتقل علينا خمسة🤌...")
    await update.message.reply_chat_action("typing")

    data = get_static_placement_passage(level)

    user_state["waiting"] = False
    save_data()

    if not data or "answers" not in data or not data["answers"]:
        await update.message.reply_text("❌ حدث خطأ أثناء إنشاء الفقرة. حاول مرة أخرى.")
        return

    user_state["step"] = "waiting_ready_testing"
    user_state["pending_data"] = data
    save_data()

    await send_ready_question(update)

async def send_training_passage(update, context, level):
    user_id = str(update.message.from_user.id)
    user_state = user_data.get(user_id, {})
    user_state["waiting"] = True
    save_data()

    await update.message.reply_text(f"📤 تدريب جديد لمستوى {level} ، ثواني و يكون عندك..")
    await update.message.reply_chat_action("typing")

    try:
        data = await generate_training_passage(level)
        print("=== Training Passage Data ===")
        print(data)
        print("============================")
    except Exception as e:
        print(f"Error in generate_training_passage: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء توليد الفقرة (استثناء داخلي).")
        user_state["waiting"] = False
        save_data()
        return

    user_state["waiting"] = False
    save_data()

    if not data or "answers" not in data or not data["answers"]:
        print("❌ مشكلة في بيانات الفقرة التدريبية:", data)
        await update.message.reply_text("❌ حدث خطأ أثناء توليد الفقرة. تحقق من اتصال الذكاء الاصطناعي أو المفتاح.")
        return

    user_state["step"] = "waiting_ready_training"
    user_state["pending_data"] = data
    save_data()

    await send_ready_question(update, text=" جاهز للتدريب؟")

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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    user_state = user_data.get(user_id)

    if not user_state:
        await update.message.reply_text("من فضلك ابدأ بالضغط على /start")
        return

    text = update.message.text.strip()

    if user_state.get("waiting", False):
        await update.message.reply_text("اهدى علينا يبن الحلال 🤌")
        return

    if user_state.get("step") in ["waiting_ready_testing", "waiting_ready_training"]:
        if text.lower() == "جاهز 🚀":
            data = user_state.get("pending_data")
            if not data:
                await update.message.reply_text("❌ خطأ داخلي، حاول /start من جديد.")
                return

            if user_state["step"] == "waiting_ready_testing":
                user_state["step"] = "testing_answer"
            else:
                user_state["step"] = "training_answer"

            user_state["correct_answers"] = data["answers"]
            save_data()

            message = f"📖 فقرة المستوى:\n\n{data['paragraph']}\n\n"
            # حذف أي جزء فيه "Answer:" أو "الإجابة:" من كل سؤال
            for i, q in enumerate(data["questions"], 1):
                question_without_answer = re.sub(r'(Answer|الإجابة)\s*[:\-]?.*', '', q, flags=re.IGNORECASE).strip()
                message += f"{question_without_answer}\n\n"
            message += "\n📩 أرسل إجاباتك كحروف (مثال: a b c b a)"
            message += "\n______________________________________"
            message += "\n🔴🔴 ®   جميع الحقوق محفوظة لقناة Doctors English   ® 🔴🔴"

            await send_long_message(update, message)
            save_data()
            return
        else:
            await update.message.reply_text('من فضلك اضغط "جاهز 🚀" عندما تكون مستعدًا.')
            return

    if user_state.get("step") in ["testing_answer", "training_answer"]:
        data = user_state.get("correct_answers", [])
        user_answers = [a.strip().lower() for a in text.split() if a.strip().lower() in ["a", "b", "c", "d"]]

        if len(user_answers) != len(data):
            await update.message.reply_text(
                f"❌ عدد الإجابات يجب أن يكون {len(data)}. رجاءً أعد إرسال الإجابات بشكل صحيح."
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
            await update.message.reply_text(msg)

            if user_state["placement_index"] < len(CEFR_LEVELS):
                user_state["step"] = "waiting_ready_testing"
                user_state["pending_data"] = None
                save_data()
                level = CEFR_LEVELS[user_state["placement_index"]]
                await update.message.reply_text(
                    f"🔜 ننتقل إلى فقرة مستوى {level} التأسيسية."
                )
                await send_placement_passage(update, context, level)
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
                save_data()

                summary = (
                    f"✅ انتهيت من تقييم المستويات التأسيسية.\n"
                    f"🎯 مستواك النهائي حسب التأسيس: {final_level}\n"
                    f"📝 الدرجات على الفقرات: {total_scores}\n"
                    "______________________________________\n"
                    "💪 أنت دلوقتي جاهز تبدأ التدريبات!\n"
                    "طول ما انت هنا، معناه انك بتستثمر في نفسك...\n"
                )
                await update.message.reply_text(summary)
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
            save_data()

            if result == "upgrade":
                msg += f"\n🎉 تم ترقية مستواك من {old_level} إلى {new_level}!"
            elif result == "downgrade":
                msg += f"\n⚠️ تم تخفيض مستواك من {old_level} إلى {new_level}."
            else:
                msg += f"\n✅ تم تثبيت مستواك على {old_level}."

            msg += "\n______________________________________"
            await update.message.reply_text(msg)
            await send_ready_question(update, text="هل أنت جاهز للتدريب ؟")
            return

    if user_state.get("step") == "ask_known_level":
        if text.lower() == "yes":
            user_state["step"] = "choose_level"
            save_data()
            await update.message.reply_text(
                "من فضلك اختر مستواك:",
                reply_markup=ReplyKeyboardMarkup([[lvl] for lvl in CEFR_LEVELS], one_time_keyboard=True)
            )
        elif text.lower() == "no":
            user_state["step"] = "testing"
            user_state["placement_index"] = 0
            user_state["placement_scores"] = []
            save_data()
            await send_placement_passage(update, context, CEFR_LEVELS[0])
        else:
            await update.message.reply_text("من فضلك اختر Yes أو No.")
        return

    if user_state.get("step") == "choose_level":
        if text.upper() in CEFR_LEVELS:
            user_state["step"] = "training"
            user_state["level"] = text.upper()
            save_data()
            await update.message.reply_text(
                f"تم اختيار مستواك: {text.upper()}.\nاستعد للتدريبات!"
            )
            await send_training_passage(update, context, user_state["level"])
        else:
            await update.message.reply_text("من فضلك اختر مستوى من القائمة.")
        return

async def main():
    global user_data
    user_data = load_data()
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