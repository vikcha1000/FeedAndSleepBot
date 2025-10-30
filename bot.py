
from datetime import datetime
import json
import os

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

import config

# Файл для хранения данных
DATA_FILE = 'feeding_data.json'

def load_data():
    """Загрузка данных из файла"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data):
    """Сохранение данных в файл"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def create_main_keyboard():
    """Основная клавиатура с кнопками"""
    keyboard = [
        [KeyboardButton("120"), KeyboardButton("90"), KeyboardButton("60"),
         KeyboardButton("150"), KeyboardButton("Ввести объем вручную")],
        [KeyboardButton("Заснул"), KeyboardButton("Проснулся")],
        [KeyboardButton("История"), KeyboardButton("Как пользоваться ботом")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n"
        "Я бот для отслеживания кормлений и сна твоего малыша.\n\n"
        "Выбери объем съеденного или обозначь заснул или проснулся малыш.",
        reply_markup=create_main_keyboard()
    )


async def show_history(update: Update, user_id: str):
    """Показать историю записей"""
    data = load_data()
    user_records = data.get(user_id, [])

    if not user_records:
        await update.message.reply_text(
            "📝 История пуста. Начните добавлять записи!",
            reply_markup=create_main_keyboard()
        )
        return

    # Сортируем записи по времени (новые сверху)
    user_records.sort(key=lambda x: x['timestamp'], reverse=True)

    history_text = "📊 История записей:\n\n"

    for i, record in enumerate(user_records[:10], 1):  # Последние 10 записей
        if record['type'] == 'кормление':
            history_text += f"{i}. 🍼 Кормление: {record['volume']} в {record['time']}\n"
        elif record['type'] == 'сон':
            emoji = "😴" if record['action'] == 'заснул' else "🌅"
            history_text += f"{i}. {emoji} {record['action'].capitalize()} в {record['time']}\n"

    history_text += f"\nВсего записей: {len(user_records)}"

    await update.message.reply_text(
        history_text,
        reply_markup=create_main_keyboard()
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    user_id = str(update.effective_user.id)
    current_time = datetime.now().strftime("%H:%M")

    # Загружаем данные
    data = load_data()
    if user_id not in data:
        data[user_id] = []

    if text in ["120", "90", "60", "150"]:
        # Сохраняем объем кормления
        record = {
            'type': 'кормление',
            'volume': f"{text} мл",
            'time': current_time,
            'timestamp': datetime.now().isoformat()
        }
        data[user_id].append(record)
        save_data(data)

        await update.message.reply_text(
            f"✅ Записано кормление: {text} мл в {current_time}",
            reply_markup=create_main_keyboard()
        )

    elif text == "Ввести объем вручную":
        context.user_data['waiting_for_volume'] = True
        await update.message.reply_text(
            "🍼 Введите объем кормления в мл:",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Отмена")]], resize_keyboard=True)
        )

    elif text == "Заснул":
        # Сохраняем время засыпания
        record = {
            'type': 'сон',
            'action': 'заснул',
            'time': current_time,
            'timestamp': datetime.now().isoformat()
        }
        data[user_id].append(record)
        save_data(data)

        await update.message.reply_text(
            f"😴 Записан сон: заснул в {current_time}",
            reply_markup=create_main_keyboard()
        )

    elif text == "Проснулся":
        # Сохраняем время пробуждения
        record = {
            'type': 'сон',
            'action': 'проснулся',
            'time': current_time,
            'timestamp': datetime.now().isoformat()
        }
        data[user_id].append(record)
        save_data(data)

        await update.message.reply_text(
            f"🌅 Записан сон: проснулся в {current_time}",
            reply_markup=create_main_keyboard()
        )

    elif text == "История":
        await show_history(update, user_id)

    elif text == "Как пользоваться ботом":
        await show_help(update)

    elif text == "Отмена":
        context.user_data.pop('waiting_for_volume', None)
        await update.message.reply_text(
            "❌ Отменено",
            reply_markup=create_main_keyboard()
        )

    elif context.user_data.get('waiting_for_volume'):
        # Обработка ручного ввода объема
        try:
            volume = int(text)
            if volume > 0:
                record = {
                    'type': 'кормление',
                    'volume': f"{volume} мл",
                    'time': current_time,
                    'timestamp': datetime.now().isoformat()
                }
                data[user_id].append(record)
                save_data(data)

                context.user_data.pop('waiting_for_volume', None)
                await update.message.reply_text(
                    f"✅ Записан объем: {volume} мл в {current_time}",
                    reply_markup=create_main_keyboard()
                )
            else:
                await update.message.reply_text("❌ Объем должен быть положительным числом")
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите число (объем в мл)")

    else:
        await handle_unknown_command(update, context)


async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нераспознаных команд"""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, Виктория! 👋\n"
        "Я бот для отслеживания кормлений и сна твоего малыша.\n"
        "Твоя команда мне не понятна, выбери объем съеденного или обозначь заснул или проснулся малыш.",
        reply_markup=create_main_keyboard()
    )

def main():
    """Основная функция"""
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    print("Бот запущен...")
    application.run_polling()


if __name__ == '__main__':
    main()