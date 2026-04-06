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

# ====================== FLUX PRO ======================
fal_client = AsyncClient(key=FAL_KEY)

async def generate_image(prompt: str):
    result = await fal_client.subscribe(
        "fal-ai/flux-pro",   # ← Переключили на Pro
        arguments={
            "prompt": prompt,
            "image_size": "square",      # лучше для открыток
            "num_inference_steps": 8,
            "guidance_scale": 4
        }
    )
    return result["images"][0]["url"]

# ====================== ПРОМПТ ДЛЯ ОТКРЫТОК ======================
def improve_prompt(user_text: str) -> str:
    text = user_text.lower()
    if "открытка" in text:
        return f"{user_text}, поздравительная открытка с большим красивым текстом, цветы, бант, блёстки, праздничный дизайн, нежный фон, высокое качество, ultra sharp, masterpiece"
    return f"{user_text}, красивая открытка, высокое качество, ultra sharp, masterpiece"

# ====================== КЛАВИАТУРА ======================
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Открытка на праздники", callback_data="holiday")],
        [InlineKeyboardButton(text="❤️ Семейный портрет", callback_data="family")],
        [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="💎 Купить премиум 599 ₽/мес", callback_data="premium")]
    ])

# ====================== НОВОЕ ПРИВЕТСТВИЕ ======================
@dp.message(Command("start"))
async def start(message: types.Message):
    gif_url = "https://s1.ezgif.com/tmp/ezgif-1c78684ada49012a.gif"
    await message.answer_animation(
        animation=gif_url,
        caption="Привет 👋\n\n"
                "Я — ImageAi ✨\n"
                "Генерирую открытки для ваших родных и близких с помощью Flux AI.\n"
                "Бесплатно: 5 картинок в день\n\n"
                "Оформите премиум по скидке за <s>899</s> 599₽ в месяц\n\n"
                "Выбери шаблон или напиши свой текст:",
        reply_markup=main_keyboard(),
        parse_mode="HTML"   # нужно для зачёркивания
    )

# ====================== КНОПКИ ======================
@dp.callback_query(lambda c: c.data == "holiday")
async def holiday_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.reply("Напишите, кого поздравляем и с каким праздником.")

@dp.callback_query(lambda c: c.data == "family")
async def family_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.reply("Опишите семейный портрет.")

@dp.callback_query(lambda c: c.data == "referral")
async def referral_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.reply(f"🔗 Ваша реферальная ссылка:\nhttps://t.me/ImageAiPostcards_bot?start=ref_{callback.from_user.id}")

@dp.callback_query(lambda c: c.data == "premium")
async def premium_handler(callback: types.CallbackQuery):
    await callback.answer()
    await bot.send_invoice(
        callback.from_user.id,
        title="Премиум 1 месяц",
        description="Неограниченное количество генераций + Flux Pro",
        payload="premium_month",
        provider_token=PAYMENT_TOKEN,
        currency="RUB",
        prices=[types.LabeledPrice(label="Премиум 1 месяц", amount=59900)]   # 599 рублей
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

    if not user.is_premium and user.daily_count >= 5:   # ← лимит 5
        await message.answer("⏳ Лимит 5 бесплатных картинок исчерпан.")
        session.close()
        return

    try:
        await message.answer("🖼 Генерирую открытку на Flux Pro...")
        prompt = improve_prompt(message.text)
        url = await generate_image(prompt)
        await message.answer_photo(url, caption=f"Готово по запросу:\n«{message.text}»")
        user.daily_count += 1
        session.commit()
    except Exception as e:
        await message.answer(f"⚠️ Ошибка:\n{str(e)[:400]}")
    finally:
        session.close()

# ====================== ЗАПУСК ======================
async def main():
    print("✅ Бот запущен на Flux Pro!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
