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

# ====================== УЛУЧШЕННЫЙ ПРОМПТ ======================
def improve_prompt(user_text: str) -> str:
    text = user_text.lower()
    
    if any(word in text for word in ["8 марта", "восьмое марта", "8марта", "женский день"]):
        return f"Нежная красивая открытка на 8 марта, весенние цветы, тюльпаны, мимоза, тёплый солнечный свет, радостная атмосфера, реализм, высокое качество, для дочери, очень душевно и трогательно"
    
    elif any(word in text for word in ["день рождения", "др", "юбилей", "годовщина"]):
        return f"Праздничная красивая открытка на день рождения, шары, торт, цветы, тёплый свет, радостная атмосфера, реализм, высокое качество, {user_text}, очень душевно"
    
    elif any(word in text for word in ["семейный портрет", "семья", "мама", "папа", "дети"]):
        return f"Тёплый семейный портрет, реализм, мягкий свет, очень душевно и эмоционально, {user_text}, высокое качество"
    
    elif any(word in text for word in ["новый год", "новогодняя", "рождество"]):
        return f"Новогодняя волшебная открытка, ёлка, снег, тёплый свет, реализм, высокое качество, {user_text}"
    
    else:
        # Универсальный улучшенный промпт для любых запросов
        return f"Тёплая, красивая, эмоциональная открытка или фото в реалистичном стиле, мягкий тёплый свет, высокое качество, очень душевно и трогательно, {user_text}, для людей 30+ лет"

# ====================== КЛАВИАТУРА ======================
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Открытка на праздники", callback_data="holiday")],
        [InlineKeyboardButton(text="❤️ Семейный портрет", callback_data="family")],
        [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="💎 Купить премиум 399 ₽/мес", callback_data="premium")]
    ])

# ====================== СТАРТ ======================
@dp.message(Command("start"))
async def start(message: types.Message):
    # Лучшая гифка (перезалей на imgur для хорошего качества)
    gif_url = "https://s1.ezgif.com/tmp/ezgif-1c78684ada49012a.gif"
    
    await message.answer_animation(
        animation=gif_url,
        caption="Привет 👋\n\nЯ — ImageAi ОткрыткиBot ✨\nГенерирую тёплые открытки с помощью Flux AI.\nБесплатно: 10 картинок в день\n\nВыбери шаблон или напиши свой текст:",
        reply_markup=main_keyboard()
    )

# ====================== КНОПКИ ======================
@dp.callback_query(lambda c: c.data == "holiday")
async def holiday_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.reply("Напишите, кого поздравляем и с каким праздником.\nПример: дочке на 8 марта")

@dp.callback_query(lambda c: c.data == "family")
async def family_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.reply("Опишите семейный портрет (кто на фото, настроение и т.д.)")

@dp.callback_query(lambda c: c.data == "referral")
async def referral_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.reply(f"🔗 Ваша реферальная ссылка:\nhttps://t.me/ImageAiPostcards_bot?start=ref_{callback.from_user.id}\n\nПриведи друга — +5 генераций!")

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
        await message.answer("🖼 Генерирую картинку... (10–15 секунд)")
        prompt = improve_prompt(message.text)
        url = await generate_image(prompt)
        await message.answer_photo(url, caption="Готово! ✨")
        user.daily_count += 1
        session.commit()
    except Exception as e:
        await message.answer(f"⚠️ Ошибка:\n{str(e)[:400]}")
    finally:
        session.close()

# ====================== ЗАПУСК ======================
async def main():
    print("✅ Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
