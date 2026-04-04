import asyncio
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
from fal_client import AsyncClient

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
FAL_KEY = os.getenv("FAL_KEY")
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ====================== БАЗА ======================
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
        arguments={"prompt": prompt, "image_size": "landscape_16_9", "num_inference_steps": 4, "guidance_scale": 3.5}
    )
    return result["images"][0]["url"]

def improve_prompt(text: str):
    return f"Тёплая эмоциональная открытка, реализм, {text}, для 30+, очень душевно"

# ====================== КЛАВИАТУРА ======================
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Открытка на праздники", callback_data="holiday")],
        [InlineKeyboardButton(text="❤️ Семейный портрет", callback_data="family")],
        [InlineKeyboardButton(text="💎 Купить премиум 399 ₽/мес", callback_data="premium")]
    ])

# ====================== СТАРТ ======================
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Привет 👋\n\n"
        "Я — ImageAi ОткрыткиBot ✨\n"
        "Генерирую тёплые открытки с помощью Flux AI.\n"
        "Бесплатно: 10 картинок в день\n\n"
        "Выбери шаблон или напиши свой текст:",
        reply_markup=main_keyboard()
    )

# ====================== КНОПКИ ======================
@dp.callback_query(lambda c: c.data == "holiday")
async def holiday_handler(callback: types.CallbackQuery):
    await callback.answer("✅ Открыл форму")
    await callback.message.reply("Напиши, кого поздравляем и с каким праздником.\nПример: мужу на день рождения")

@dp.callback_query(lambda c: c.data == "family")
async def family_handler(callback: types.CallbackQuery):
    await callback.answer("✅ Открыл форму")
    await callback.message.reply("Опиши, кого нарисовать (кто на фото, настроение и т.д.)")

@dp.callback_query(lambda c: c.data == "premium")
async def premium_handler(callback: types.CallbackQuery):
    await callback.answer()
    await bot.send_invoice(
        callback.from_user.id,
        title="Премиум 1 месяц",
        description="Неограниченные генерации",
        payload="premium",
        provider_token=PAYMENT_TOKEN,
        currency="RUB",
        prices=[types.LabeledPrice("Премиум", 39900)]
    )

# ====================== ГЕНЕРАЦИЯ ======================
@dp.message()
async def handle_text(message: types.Message):
    session = Session()
    user = session.query(User).filter_by(user_id=message.from_user.id).first()
    if not user:
        user = User(user_id=message.from_user.id)
        session.add(user)
        session.commit()

    if not user.is_premium and user.daily_count >= 10:
        await message.answer("Лимит 10 бесплатных картинок на сегодня исчерпан.")
        session.close()
        return

    try:
        await message.answer("🖼 Генерирую картинку... (10–15 сек)")
        prompt = improve_prompt(message.text)
        url = await generate_image(prompt)
        await message.answer_photo(url, caption="Готово! ✨")
        user.daily_count += 1
        session.commit()
    except Exception as e:
        await message.answer("Ошибка генерации, попробуй ещё раз")
        print(e)
    finally:
        session.close()

# ====================== ЗАПУСК ======================
async def main():
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
