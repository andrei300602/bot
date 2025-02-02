import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime, timedelta
import asyncio

# Ініціалізація бота та диспетчера
bot = Bot(token="7417072887:AAGX25vnMZs9b5wf46JLH10BLTRcL23z0bc")
dp = Dispatcher(storage=MemoryStorage())

# ID групи адміністраторів
ADMIN_GROUP_ID = -1002181219489  # Замініть на ID вашої групи

# Глобальний словник для збереження замовлень
user_orders = {}

# Визначення станів для Finite State Machine (FSM)
class OrderState(StatesGroup):
    enter_name = State()
    select_date = State()
    select_location = State()
    view_menu = State()
    order_details = State()
    payment_confirmation = State()

# Перевірка робочого часу
def is_working_hours(start_hour=11, end_hour=15):
    now = datetime.now()
    start_time = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    end_time = now.replace(hour=end_hour, minute=0, second=0, microsecond=0)
    return start_time <= now <= end_time

# Команда /start
@dp.message(Command("start"))
async def start_command(message: Message, state: FSMContext):
    if not is_working_hours():
        await message.answer("Бот приймає замовлення лише з 11:00 до 15:00.")
        return

    user_id = message.from_user.id
    today = datetime.now().date()
    if user_orders.get(user_id) == today:
        await message.answer(
            "Упс, ви вже оформили замовлення сьогодні. Воно буде доставлено на ту дату, яку ви вказали.\n"
            "Якщо якісь дані в замовленні потребують уточнення, зверніться до менеджера Ideal Food Service.\n"
            "Чекаємо на вас завтра!"
        )
        return

    await message.answer("Привіт! Введіть, будь ласка, ваше ім'я:")
    await state.set_state(OrderState.enter_name)

# Введення імені
@dp.message(OrderState.enter_name, F.text)
async def enter_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)

    # Клавіатура для вибору дати
    today = datetime.now().date()
    dates = [
        (today + timedelta(days=1)).strftime("%d-%m-%Y"),
        (today + timedelta(days=2)).strftime("%d-%m-%Y"),
        (today + timedelta(days=3)).strftime("%d-%m-%Y")
    ]
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=date)] for date in dates],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Оберіть дату доставки:", reply_markup=keyboard)
    await state.set_state(OrderState.select_date)

# Вибір дати
@dp.message(OrderState.select_date, F.text)
async def select_date(message: Message, state: FSMContext):
    await state.update_data(order_date=message.text)

    # Клавіатура з локаціями
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Адреса 1: вул. Щусева, 26 (Дорогожичі)")],
            [KeyboardButton(text="Адреса 2: вул. Дмитріївська, 30 (цирк)")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Оберіть локацію для доставки:", reply_markup=keyboard)
    await state.set_state(OrderState.select_location)

# Вибір локації
@dp.message(OrderState.select_location, F.text)
async def select_location(message: Message, state: FSMContext):
    await state.update_data(location=message.text)
    await message.answer("Ознайомтеся з нашим меню:", reply_markup=ReplyKeyboardRemove())

    # Відправка меню (фото з папки "menu")
    menu_folder = "menu"  # Папка, де зберігаються фото меню
    if not os.path.exists(menu_folder) or not os.listdir(menu_folder):
        await message.answer("Наразі меню недоступне. Спробуйте пізніше.")
        await state.clear()
        return

    from aiogram.types import FSInputFile

    # Відправка меню (фото з папки "menu")
    menu_folder = "menu"  # Папка, де зберігаються фото меню
    for file_name in os.listdir(menu_folder):
        if file_name.endswith(('.png', '.jpg', '.jpeg')):
            photo_path = os.path.join(menu_folder, file_name)
            photo = FSInputFile(photo_path)  # Використання FSInputFile для передачі фото
            await message.answer_photo(photo)

    await message.answer("Введіть текстом, що бажаєте замовити:")
    await state.set_state(OrderState.order_details)

# Введення деталей замовлення
@dp.message(OrderState.order_details, F.text)
async def order_details(message: Message, state: FSMContext):
    await state.update_data(order_details=message.text)
    await message.answer(
        "Дякуємо! Ось реквізити для оплати:\n\n"
        "**Александровський Сергій Олександрович,**\n\n"
        "Код отримувача: 3080116335\n"
        "Рахунок отримувача: UA743052990000026003035025470\n"
        "Назва банку: АТ КБ ПРИВАТБАНК\n"
        "5169335104296443\n\n"
        "Після оплати надішліть фото підтвердження."
    )
    await state.set_state(OrderState.payment_confirmation)

# Підтвердження оплати
@dp.message(OrderState.payment_confirmation, F.photo)
async def payment_confirmation(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data.get("name")
    order_date = data.get("order_date")
    location = data.get("location")
    order_details = data.get("order_details")
    photo_file_id = message.photo[-1].file_id

    # Запис замовлення
    user_id = message.from_user.id
    user_orders[user_id] = datetime.now().date()

    # Надсилання замовлення у групу адміністраторів
    await bot.send_message(
        chat_id=ADMIN_GROUP_ID,
        text=f"Нове замовлення!\n\n"
             f"Ім'я: {name}\n"
             f"Дата доставки: {order_date}\n"
             f"Локація: {location}\n"
             f"Деталі замовлення: {order_details}"
    )
    await bot.send_photo(chat_id=ADMIN_GROUP_ID, photo=photo_file_id)

    await message.answer("Ваше замовлення успішно прийняте! Дякуємо!")
    await state.clear()

# Якщо користувач надсилає щось, окрім фото
@dp.message(OrderState.payment_confirmation)
async def invalid_photo(message: Message):
    await message.answer("Будь ласка, надішліть фото підтвердження оплати.")

# Головна функція
async def main():
    print("Бот запущений!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
