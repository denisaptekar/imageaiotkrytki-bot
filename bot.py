import asyncio
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from dotenv import load_dotenv
from fal_client import AsyncClient
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
FAL_KEY = os.getenv("FAL_KEY")
PAYMENT_TOKEN = "390540012:LIVE:93392"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ====================== БАЗА ДАННЫХ ======================
Base = declarative_base()
engine = create_engine('sqlite:///bot.db')
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True)
    daily_count = Column(Integer, default=0)
    last_reset = Column(DateTime, default=datetime.utcnow)
    is_premium = Column(Integer, default=0)
    referral_code = Column(String, unique=True)

Base.metadata.create_all(engine)

# ====================== FAL.AI ======================
fal_client = AsyncClient(key=FAL_KEY)
MODEL = "fal-ai/flux/schnell"

async def generate_image(prompt: str):
    result = await fal_client.subscribe(
        MODEL,
        arguments={
            "prompt": prompt,
            "image_size": {"width": 1024, "height": 1024},
            "num_inference_steps": 4,
            "guidance_scale": 3.5,
        }
    )
    return result["images"][0]["url"]

# ====================== КЛАВИАТУРА ======================
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Открытка на праздники", callback_data="template_holiday")],
        [InlineKeyboardButton(text="❤️ Семейный портрет", callback_data="template_family")],
        [InlineKeyboardButton(text="💎 Купить премиум 399 ₽/мес", callback_data="buy_premium")]
    ])

# ====================== ПЛАТЕЖИ ======================
@dp.callback_query(lambda c: c.data == "buy_premium")
async def buy_premium(callback: types.CallbackQuery):
    prices = [LabeledPrice(label="Премиум-подписка на месяц", amount=39900)]
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Премиум ImageAi ОткрыткиBot",
        description="Безлимит генераций + приоритет + эксклюзивные стили",
        payload="premium_month",
        provider_token=PAYMENT_TOKEN,
        currency="RUB",
        prices=prices,
    )

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(lambda message: message.successful_payment)
async def successful_payment(message: types.Message):
    await message.answer("🎉 Поздравляем! Премиум активирован — теперь безлимит ❤️")

# ====================== ХЕНДЛЕРЫ ======================
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Привет👋\n\n"
        "Я — ImageAi ОткрыткиBot ✨\n"
        "Генерирую тёплые открытки и фото для ваших родных и близких с помощью Flux AI.\n"
        "Бесплатно: 10 картинок в день\n\n"
        "Выбери шаблон или напиши свой текст:",
        reply_markup=main_keyboard()
    )

print("✅ Бот запущен и готов к работе!")
asyncio.run(dp.start_polling(bot))