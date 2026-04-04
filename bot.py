import asyncio
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from fal_client import AsyncClient

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
FAL_KEY = os.getenv("FAL_KEY")
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ====================== БАЗА ДАННЫХ ======================
Base = declarative_base()
engine = create_engine("sqlite:///bot.db")
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True)
    daily_count = Column(Integer, default=0)
    last_reset = Column(DateTime, default=datetime.utcnow)
    is_premium = Column(Boolean, default=False)

Base.metadata.create_all(engine)

# ====================== FAL ======================
fal_client = AsyncClient(key=FAL_KEY)

async def generate_image(prompt: str):
    result = await fal_client.subscribe(
        "fal-ai/flux/schnell",
        arguments={
            "prompt": prompt,
            "image_size": "landscape_16_9",
            "num_inference_steps": 4,
            "guidance_scale": 3.5
        }
    )
    return result["images"][0]["url"]

def improve_prompt(text: str):
    return f"Тёплая, красивая, эмоциональная открытка, реализм, мягкий свет, {text}, для 30+, очень душевно"

# ====================== КЛАВИАТУРА ======================
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Открытка на праздники", callback_data="holiday")],
        [InlineKeyboardButton(text="❤️ Семейный портрет", callback_data="family")],
        [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="💎 Купить премиум 399 ₽/мес", callback_data="premium")]
    ])

# ====================== СТАРТ С ГИФКОЙ ======================
@dp.message(Command("start"))
async def start(message: types.Message):
    gif_url = "https://s1.ezgif.com/tmp/ezgif-1c78684ada49012a.gif"

    await message.answer_animation(
        animation=gif_url,
        caption="Привет 👋\n\n"
                "Я — ImageAi ОткрыткиBot ✨\n"
                "Генерирую тёплые открытки и фото для ваших родных и близких с помощью Flux AI.\n"
                "Бесплатно: 10 картинок в день\n\n"
                "Выбери шаблон или напиши свой текст:",
        reply_markup=main_keyboard()
    )

# ====================== ОБРАБОТЧИКИ КНОПОК ======================
@dp.callback_query(lambda c: c.data == "holiday")
async def holiday_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.reply(
        "Напишите, кого хотите поздравить и с каким праздником.\n\n"
        "Пример:\n"
        "• мужу на день рождения\n"
        "• дочке на 8 марта\n"
        "• маме на юбилей"
    )

@dp.callback_query(lambda c: c.data == "family")
async def family_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.reply("Опишите, кого нарисовать (кто на фото, настроение и т.д.)")

@dp.callback_query(lambda c: c.data == "referral")
async def referral_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.reply(
        f"🔗 Ваша реферальная ссылка:\n"
        f"https://t.me/ImageAiPostcards_bot?start=ref_{callback.from_user.id}\n\n"
        f"Приведи друга — получишь +5 бесплатных генераций!"
    )

@dp.callback_query(lambda c: c.data == "premium")
async def premium_handler(callback: types.CallbackQuery):
    await callback.answer()
    await bot.send_invoice(
        callback.from_user.id,
        title="Премиум-подписка 1 месяц",
        description="Неограниченное количество генераций + приоритет",
        payload="premium_month",
        provider_token=PAYMENT_TOKEN,
        currency="RUB",
        prices=[types.LabeledPrice(label="Премиум 1 месяц", amount=39900)]
    )

# ====================== ГЕНЕРАЦИЯ КАРТИНОК ======================
@dp.message()
async def handle_text(message: types.Message):
    session = Session()
    user = session.query(User).filter_by(user_id=message.from_user.id).first()
    if not user:
        user = User(user_id=message.from_user.id)
        session.add(user)
        session.commit()

    if not user.is_premium:
        if (datetime.utcnow() - user.last_reset) > timedelta(days=1):
            user.daily_count = 0
            user.last_reset = datetime.utcnow()
        if user.daily_count >= 10:
            await message.answer("⏳ Сегодня лимит бесплатных генераций (10 шт) исчерпан.\nКупите премиум!")
            session.close()
            return

    try:
        await message.answer("🖼 Генерирую картинку... (10–15 секунд)")
        prompt = improve_prompt(message.text)
        url = await generate_image(prompt)
        await message.answer_photo(url, caption="Готово! ✨")
        user.daily_count += 1
        session.commit()
    except Exception:
        await message.answer("⚠️ Ошибка генерации. Попробуйте ещё раз.")
    finally:
        session.close()

# ====================== ЗАПУСК ======================
async def main():
    print("✅ Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
