import asyncio
from aiogram import Bot, Dispatcher, types
from datetime import datetime
from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

import os

TOKEN = os.getenv("TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


class Form(StatesGroup):
    master = State()
    has_service = State()
    service_amount = State()
    service_payment = State()
    has_cream = State()
    cream_payment = State()
    confirm = State()


# ❌ ОТМЕНА (ОДИН РАЗ!)
@dp.message_handler(lambda message: message.text == "❌ Отмена", state="*")
async def cancel(msg: types.Message, state: FSMContext):
    await state.finish()

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🪡 Пирсинг", "🎨 Тату")

    await msg.answer("❌ Отменено", reply_markup=kb)
    await Form.master.set()


# ▶️ СТАРТ
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🪡 Пирсинг", "🎨 Тату")
    kb.add("❌ Отмена")

    await msg.answer("Выберите мастера:", reply_markup=kb)
    await Form.master.set()


# 👤 ВЫБОР МАСТЕРА
@dp.message_handler(state=Form.master)
async def choose_master(msg: types.Message, state: FSMContext):
    await state.update_data(master=msg.text)

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Да", "Нет")
    kb.add("❌ Отмена")

    await msg.answer("Была услуга?", reply_markup=kb)
    await Form.has_service.set()


# 💉 УСЛУГА
@dp.message_handler(state=Form.has_service)
async def has_service(msg: types.Message, state: FSMContext):
    if msg.text == "Да":
        await state.update_data(has_service=True)
        await msg.answer("Введите сумму услуги:", reply_markup=ReplyKeyboardRemove())
        await Form.service_amount.set()
    else:
        await state.update_data(has_service=False)
        await ask_cream(msg)


# 💰 СУММА
@dp.message_handler(state=Form.service_amount)
async def service_amount(msg: types.Message, state: FSMContext):
    try:
        amount = float(msg.text)
    except:
        return await msg.answer("Введите число")

    await state.update_data(service_amount=amount)

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Кэш", "Банк")
    kb.add("❌ Отмена")

    await msg.answer("Тип оплаты:", reply_markup=kb)
    await Form.service_payment.set()


# 💳 ОПЛАТА УСЛУГИ
@dp.message_handler(state=Form.service_payment)
async def service_payment(msg: types.Message, state: FSMContext):
    await state.update_data(service_payment=msg.text)
    await ask_cream(msg)


# 🧴 СПРОСИТЬ ПРО КРЕМ
async def ask_cream(msg):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Да", "Нет")
    kb.add("❌ Отмена")

    await msg.answer("Был крем?", reply_markup=kb)
    await Form.has_cream.set()


# 🧴 КРЕМ
@dp.message_handler(state=Form.has_cream)
async def has_cream(msg: types.Message, state: FSMContext):
    if msg.text == "Да":
        await state.update_data(has_cream=True)

        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("Кэш", "Банк")
        kb.add("❌ Отмена")

        await msg.answer("Крем = 10€\nТип оплаты:", reply_markup=kb)
        await Form.cream_payment.set()
    else:
        await state.update_data(has_cream=False)
        await finish(msg, state)


# 💳 ОПЛАТА КРЕМА
@dp.message_handler(state=Form.cream_payment)
async def cream_payment(msg: types.Message, state: FSMContext):
    await state.update_data(cream_payment=msg.text)
    await finish(msg, state)


# 🧠 ФИНАЛ
async def finish(msg, state: FSMContext):
    data = await state.get_data()

    master = data["master"]

    percent = 0.4 if "Пирсинг" in master else 0.5

    service_amount = data.get("service_amount", 0)
    has_service = data.get("has_service", False)
    has_cream = data.get("has_cream", False)

    master_income = 0
    company_service = 0

    if has_service:
        master_income = service_amount * percent
        company_service = service_amount - master_income

    cream_amount = 10 if has_cream else 0
    company_total = company_service + cream_amount

    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    # 👤 ТЕКСТ ДЛЯ МАСТЕРА (БЕЗ ПРОЦЕНТОВ)
    text_user = f"📅 {now}\n👤 Мастер: {master}\n\n"

    if has_service:
        text_user += f"💉 Услуга:\n💰 {service_amount}\n"
        text_user += f"{'💵 Кэш' if data['service_payment']=='Кэш' else '💳 Банк'}\n"

    if has_cream:
        text_user += "\n🧴 Крем:\n💰 10\n"
        text_user += f"{'💵 Кэш' if data['cream_payment']=='Кэш' else '💳 Банк'}\n"

    # 📊 ТЕКСТ ДЛЯ ГРУППЫ (С ПРОЦЕНТАМИ)
    text_group = text_user + f"\n📊\n👤 Мастер: {round(master_income,2)}\n🏢 Компания: {round(company_total,2)}"

    # сохраняем именно групповой текст
    await state.update_data(final_text=text_group)

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Да", "❌ Нет")

    # показываем мастеру БЕЗ процентов
    await msg.answer(f"Проверь:\n\n{text_user}\n\nОтправить?", reply_markup=kb)

    await Form.confirm.set()


# ✅ ПОДТВЕРЖДЕНИЕ
@dp.message_handler(state=Form.confirm)
async def confirm_handler(msg: types.Message, state: FSMContext):
    if "Да" in msg.text:
        data = await state.get_data()
        text = data.get("final_text")

        await bot.send_message(GROUP_ID, text)

        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("+ Новая запись")

        await msg.answer("✅ Записано", reply_markup=ReplyKeyboardRemove())
        await msg.answer("Начать заново?", reply_markup=kb)

        await state.finish()

    else:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("+ Новая запись")

        await msg.answer("❌ Отменено", reply_markup=kb)

        await state.finish()


# ➕ НОВАЯ ЗАПИСЬ
@dp.message_handler(lambda message: "Новая запись" in message.text)
async def new_entry(msg: types.Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🪡 Пирсинг", "🎨 Тату")

    await msg.answer("Выберите мастера:", reply_markup=kb)
    await Form.master.set()


# 🚀 ЗАПУСК
if __name__ == "__main__":
    executor.start_polling(dp)
