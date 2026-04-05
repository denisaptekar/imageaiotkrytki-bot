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

# ====================== ПРОМПТ (теперь использует твой текст напрямую) ======================
def improve_prompt(user_text: str) -> str:
    # Минимальное улучшение качества, но основной смысл — твой запрос
    return f"{user_text}, красивая открытка, реалистичный стиль, высокое качество, детализация, мягкий свет, эмоционально"

# ====================== КЛАВИАТУРА ======================
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Открытка на праздники", callback_data="holiday")],
        [InlineKeyboardButton(text="❤️ Семейный портрет", callback_data="family")],
        [InlineKeyboardButton(text="✨ Улучшить мой промпт", callback_data="improve")],
        [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="💎 Купить премиум 399 ₽/мес", callback_data="premium")]
    ])

# ====================== СТАРТ ======================
@dp.message(Command("start"))
async def start(message: types.Message):
    gif_url = "https://s1.ezgif.com/tmp/ezgif-1c78684ada49012a.gif"   # потом перезальём лучше
    await message.answer_animation(
        animation=gif_url,
        caption="Привет 👋\n\nЯ — ImageAi ОткрыткиBot ✨\nГенерирую картинки по твоему тексту.\nПросто напиши, что хочешь увидеть!",
        reply_markup=main_keyboard()
    )

# ====================== КНОПКИ ======================
@dp.callback_query(lambda c: c.data == "holiday")
async def holiday_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.reply("Напиши, кого поздравляем и с каким праздником.")

@dp.callback_query(lambda c: c.data == "family")
async def family_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.reply("Опиши, кого нарисовать (кто на фото, настроение и т.д.)")

@dp.callback_query(lambda c: c.data == "improve")
async def improve_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.reply("Отправь текст, который хочешь улучшить перед генерацией.")

@dp.callback_query(lambda c: c.data == "referral")
async def referral_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.reply(f"🔗 Твоя реферальная ссылка:\nhttps://t.me/ImageAiPostcards_bot?start=ref_{callback.from_user.id}\n\nПриведи друга — +5 генераций!")

@dp.callback_query(lambda c: c.data == "premium")
async def premium_handler(callback: types.CallbackQuery):
    await callback.answer()
    await bot.send_invoice(
        callback.from_user.id,
        title="Премиум 1 месяц",
        description="Неограниченное количество генераций",
        payload="premium_month",
        provider_token=PAYMENT_TOKEN,
        currency="RUB",
        prices=[types.LabeledPrice(label="Премиум", amount=39900)]
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
        await message.answer("⏳ Лимит 10 бесплатных картинок исчерпан.")
        session.close()
        return

    try:
        await message.answer("🖼 Генерирую по твоему запросу... (10–15 сек)")
        prompt = improve_prompt(message.text)   # теперь почти твой текст + минимальное улучшение качества
        url = await generate_image(prompt)
        await message.answer_photo(url, caption=f"Готово по запросу:\n{message.text}")
        user.daily_count += 1
        session.commit()
    except Exception as e:
        await message.answer(f"⚠️ Ошибка:\n{str(e)[:400]}")
    finally:
        session.close()

# ====================== ЗАПУСК ======================
async def main():
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
