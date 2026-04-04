import asyncio
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import F
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
from fal_client import AsyncClient

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
FAL_KEY = os.getenv("FAL_KEY")
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN")
PROXY_URL = os.getenv("PROXY_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ====================== БАЗА ДАННЫХ ======================
Base = declarative_base()
engine = create_engine("sqlite:///bot.db")
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True)
    username = Column(String)
    daily_count = Column(Integer, default=0)
    last_reset = Column(DateTime, default=datetime.utcnow)
    is_premium = Column(Boolean, default=False)
    referral_code = Column(String, unique=True)
    referred_by = Column(Integer, nullable=True)
    total_generations = Column(Integer, default=0)

Base.metadata.create_all(engine)

# ====================== FAL CLIENT ======================
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

def improve_prompt(text: str) -> str:
    return f"Тёплая, красивая, эмоциональная открытка в стиле реализм, высокое качество, мягкий свет, {text}, для человека 30+ лет, очень трогательно и душевно"

# ====================== КЛАВИАТУРА ======================
def main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Открытка на праздники", callback_data="template_holiday")],
        [InlineKeyboardButton(text="❤️ Открытка любимому", callback_data="template_love")],
        [InlineKeyboardButton(text="🎂 Открытка на день рождения", callback_data="template_birthday")],
        [InlineKeyboardButton(text="🎄 Новогодняя открытка", callback_data="template_newyear")],
        [InlineKeyboardButton(text="✨ Улучшить промпт", callback_data="improve_prompt")],
        [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="⭐ Купить премиум (399 ₽/мес)", callback_data="buy_premium")]
    ])
    return keyboard

# ====================== ХЕНДЛЕРЫ ======================
@dp.message(Command("start"))
async def start(message: types.Message):
    session = Session()
    user = session.query(User).filter_by(user_id=message.from_user.id).first()
    if not user:
        referral_code = f"ref_{message.from_user.id}"
        user = User(
            user_id=message.from_user.id,
            username=message.from_user.username,
            referral_code=referral_code
        )
        session.add(user)
        session.commit()

    await message.answer(
        "Привет👋\n\n"
        "Я — ImageAi ОткрыткиBot ✨\n"
        "Генерирую тёплые открытки и фото для ваших родных и близких с помощью Flux AI.\n"
        "Бесплатно: 10 картинок в день\n\n"
        "Выбери шаблон или напиши свой текст:",
        reply_markup=main_keyboard()
    )
    session.close()

@dp.callback_query(lambda c: c.data == "template_holiday")
async def process_holiday_template(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.reply(
        "Напишите, кого хотите поздравить и с каким праздником.\n\n"
        "Пример:\n"
        "• мужу на день рождения\n"
        "• дочке на 8 марта\n"
        "• маме на юбилей"
    )

@dp.callback_query(lambda c: c.data.startswith("template_"))
async def process_other_templates(callback: types.CallbackQuery):
    await callback.answer()
    # Здесь можно добавить другие шаблоны позже
    await callback.message.reply("Этот шаблон скоро будет доступен ❤️")

@dp.callback_query(F.data == "improve_prompt")
async def improve_prompt_handler(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.reply("Отправь мне текст, который хочешь улучшить для генерации картинки.")

@dp.callback_query(F.data == "referral")
async def referral_handler(callback: types.CallbackQuery):
    session = Session()
    user = session.query(User).filter_by(user_id=callback.from_user.id).first()
    await callback.message.reply(
        f"🔗 Твоя реферальная ссылка:\n"
        f"https://t.me/ImageAiPostcards_bot?start={user.referral_code}\n\n"
        f"Приведи друга — получишь +5 генераций!"
    )
    session.close()

@dp.callback_query(F.data == "buy_premium")
async def buy_premium(callback: types.CallbackQuery):
    await callback.answer()
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="Премиум-подписка",
        description="Неограниченное количество генераций + приоритет",
        payload="premium_month",
        provider_token=PAYMENT_TOKEN,
        currency="RUB",
        prices=[types.LabeledPrice(label="1 месяц премиум", amount=39900)]
    )

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    session = Session()
    user = session.query(User).filter_by(user_id=message.from_user.id).first()
    user.is_premium = True
    session.commit()
    await message.answer("✅ Премиум активирован! Теперь у тебя неограниченное количество генераций.")
    session.close()

@dp.message()
async def handle_text(message: types.Message):
    session = Session()
    user = session.query(User).filter_by(user_id=message.from_user.id).first()

    if not user.is_premium:
        if (datetime.utcnow() - user.last_reset) > timedelta(days=1):
            user.daily_count = 0
            user.last_reset = datetime.utcnow()
        if user.daily_count >= 10:
            await message.answer("⏳ Сегодня лимит бесплатных генераций исчерпан.\nКупи премиум или дождись завтра!")
            session.close()
            return

    try:
        await message.answer("🖼 Генерирую картинку... Это займёт 10–15 секунд")

        improved = improve_prompt(message.text)
        image_url = await generate_image(improved)

        await message.answer_photo(image_url, caption="Готово! ✨")
        
        user.daily_count += 1
        user.total_generations += 1
        session.commit()

    except Exception as e:
        await message.answer("⚠️ Произошла ошибка при генерации. Попробуй ещё раз.")
        print(e)
    finally:
        session.close()

# ====================== ЗАПУСК ======================
async def main():
    print("✅ Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
