
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

import config



import os

# Файл для хранения данных в Volume
DATA_FILE = Path(__file__).parent / 'data' / 'feeding_data.json'


def load_data():
    """Загрузка данных из файла"""
    # Создаем файл если не существует
    if not os.path.exists(DATA_FILE):
        base_data = {'users': {}}
        save_data(base_data)
        return base_data

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading data: {e}")
        # Если ошибка, создаем новый файл
        base_data = {'users': {}}
        save_data(base_data)
        return base_data


def save_data(data):
    """Сохранение данных в файл"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving data: {e}")
        return False

def get_moscow_time():
    """Получить московское время (фиксированное смещение +3)"""
    moscow_tz = timezone(timedelta(hours=3))
    moscow_time = datetime.now(moscow_tz)
    return moscow_time.strftime("%H:%M"), moscow_time

def create_main_keyboard():
    """Основная клавиатура с кнопками"""
    keyboard = [
        [KeyboardButton("120"), KeyboardButton("90"), KeyboardButton("60"),
         KeyboardButton("150"), KeyboardButton("Ввести объем вручную")],
        [KeyboardButton("Заснул"), KeyboardButton("Проснулся")],
        [KeyboardButton("История"), KeyboardButton("Редактировать последнюю запись")],
        [KeyboardButton("Как пользоваться ботом")]
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


from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_today_summary(user_id):
    """Получить сводку за сегодня"""
    data = load_data()
    user_records = data.get(str(user_id), [])

    if not user_records:
        return None

    # Получаем сегодняшнюю дату
    today = datetime.now().date()

    # Фильтруем записи за сегодня
    today_records = [
        record for record in user_records
        if datetime.fromisoformat(record['timestamp']).date() == today
    ]

    if not today_records:
        return None

    # Вычисляем статистику по кормлениям
    feeding_volume = 0
    feeding_count = 0

    # Вычисляем статистику по снам
    sleep_durations = []
    open_sleeps = []  # Список для отслеживания незакрытых снов

    # Сортируем записи по времени (от старых к новым)
    sorted_records = sorted(today_records, key=lambda x: x['timestamp'])

    for record in sorted_records:
        if record['type'] == 'кормление':
            # Извлекаем объем из строки "120 мл"
            volume_str = record['volume'].replace(' мл', '').strip()
            try:
                volume = int(volume_str)
                feeding_volume += volume
                feeding_count += 1
            except ValueError:
                pass

        elif record['type'] == 'сон':
            if record['action'] == 'заснул':
                # Добавляем начало сна в список
                open_sleeps.append({
                    'timestamp': record['timestamp'],
                    'time': record['time']
                })
            elif record['action'] == 'проснулся' and open_sleeps:
                # Берем последний незакрытый сон
                last_sleep = open_sleeps.pop()
                sleep_start = datetime.fromisoformat(last_sleep['timestamp'])
                sleep_end = datetime.fromisoformat(record['timestamp'])
                sleep_duration = (sleep_end - sleep_start).total_seconds() / 60
                sleep_durations.append(sleep_duration)

    # Форматируем результат
    feeding_info = f"🍼 {feeding_volume} мл ({feeding_count} кормлений)"

    sleep_count = len(sleep_durations)
    total_sleep_minutes = sum(sleep_durations)

    if sleep_count > 0:
        sleep_duration_text = format_sleep_duration(total_sleep_minutes)
        sleep_info = f"😴 {sleep_count} снов ({sleep_duration_text})"
        return f"{feeding_info}, {sleep_info}"
    else:
        return feeding_info


async def send_today_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправить сводку за сегодня"""
    user_id = update.effective_user.id
    summary = get_today_summary(user_id)

    if summary:
        message = f"**Сегодня** - {summary}"
    else:
        message = "📝 Сегодня еще нет записей"

    if update.callback_query:
        await update.callback_query.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
    else:
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )

def get_russian_date(date):
    """Конвертируем дату в русский формат"""
    months = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    if date == today:
        return "Сегодня"
    elif date == yesterday:
        return "Вчера"
    else:
        return f"{date.day} {months[date.month]}"


def calculate_daily_totals(records):
    """Вычисляем итоги по дням с расчетом продолжительности каждого сна"""
    daily_data = {}

    # Сначала сортируем все записи по времени (от старых к новым)
    sorted_records = sorted(records, key=lambda x: x['timestamp'])

    for record in sorted_records:
        record_date = datetime.fromisoformat(record['timestamp']).date()

        if record_date not in daily_data:
            daily_data[record_date] = {
                'feeding_volume': 0,
                'feeding_count': 0,
                'sleep_durations': [],  # Продолжительности каждого сна в минутах
                'all_records': []  # Все записи дня с дополнительной информацией
            }

        if record['type'] == 'кормление':
            # Извлекаем объем из строки "120 мл"
            volume_str = record['volume'].replace(' мл', '').strip()
            try:
                volume = int(volume_str)
                daily_data[record_date]['feeding_volume'] += volume
                daily_data[record_date]['feeding_count'] += 1
            except ValueError:
                pass

            # Добавляем запись без информации о сне
            daily_data[record_date]['all_records'].append({
                **record,
                'time_obj': datetime.fromisoformat(record['timestamp']).time(),
                'sleep_duration': None
            })

        elif record['type'] == 'сон':
            if record['action'] == 'заснул':
                # Добавляем запись "заснул" без продолжительности
                daily_data[record_date]['all_records'].append({
                    **record,
                    'time_obj': datetime.fromisoformat(record['timestamp']).time(),
                    'sleep_duration': None
                })

            elif record['action'] == 'проснулся':
                # Ищем ближайшее предыдущее "заснул" во ВСЕХ записях
                sleep_duration = None

                # Проходим по всем предыдущим записям в обратном порядке
                for prev_record in reversed(sorted_records[:sorted_records.index(record)]):
                    if prev_record['type'] == 'сон' and prev_record['action'] == 'заснул':
                        # Нашли "заснул" - вычисляем продолжительность
                        sleep_start = datetime.fromisoformat(prev_record['timestamp'])
                        sleep_end = datetime.fromisoformat(record['timestamp'])
                        sleep_duration = (sleep_end - sleep_start).total_seconds() / 60

                        # Обновляем запись "заснул" с продолжительностью
                        prev_date = datetime.fromisoformat(prev_record['timestamp']).date()
                        if prev_date in daily_data:
                            for rec in daily_data[prev_date]['all_records']:
                                if (rec['type'] == 'сон' and
                                        rec['action'] == 'заснул' and
                                        rec['timestamp'] == prev_record['timestamp']):
                                    rec['sleep_duration'] = sleep_duration
                                    break

                        # Добавляем продолжительность в общий список дня начала сна
                        daily_data[prev_date]['sleep_durations'].append(sleep_duration)
                        break

                # Добавляем запись "проснулся" с продолжительностью
                daily_data[record_date]['all_records'].append({
                    **record,
                    'time_obj': datetime.fromisoformat(record['timestamp']).time(),
                    'sleep_duration': sleep_duration
                })

    return daily_data


def format_sleep_duration(minutes):
    """Форматируем продолжительность сна в читаемый вид"""
    if minutes is None or minutes <= 0:
        return "?"

    hours = int(minutes // 60)
    mins = int(minutes % 60)

    if hours == 0:
        return f"{mins} мин"
    elif mins == 0:
        return f"{hours} час" + ("а" if 2 <= hours % 10 <= 4 and (hours % 100 < 10 or hours % 100 >= 20) else "ов")
    else:
        hours_text = f"{hours} час" + (
            "а" if 2 <= hours % 10 <= 4 and (hours % 100 < 10 or hours % 100 >= 20) else "ов")
        mins_text = f"{mins} мин"
        return f"{hours_text} {mins_text}"


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE, show_all=False):
    """Показать историю записей с группировкой по дням"""
    user_id = str(update.effective_user.id)
    data = load_data()
    user_records = data.get(user_id, [])

    if not user_records:
        await update.message.reply_text(
            "📝 История пуста. Начните добавлять записи!",
            reply_markup=create_main_keyboard()
        )
        return

    # Вычисляем итоги по дням
    daily_totals = calculate_daily_totals(user_records)

    # Сортируем дни по убыванию (новые дни первыми)
    sorted_dates = sorted(daily_totals.keys(), reverse=True)

    # Формируем текст истории
    history_text = "📊 История кормлений и сна:\n\n"

    # Показываем последние 3 дня или все дни если show_all=True
    dates_to_show = sorted_dates if show_all else sorted_dates[:3]

    for date in dates_to_show:
        daily_data = daily_totals[date]
        date_label = get_russian_date(date)

        # Рассчитываем общую статистику по дню
        total_sleep_minutes = sum(daily_data['sleep_durations'])
        sleep_count = len(daily_data['sleep_durations'])

        # Формируем информацию о кормлениях и сне
        feeding_info = ""
        sleep_info = ""

        if daily_data['feeding_count'] > 0:
            feeding_info = f"🍼 {daily_data['feeding_volume']} мл ({daily_data['feeding_count']} кормлений)"

        if sleep_count > 0:
            sleep_duration_text = format_sleep_duration(total_sleep_minutes)
            sleep_info = f"😴 {sleep_count} снов ({sleep_duration_text})"

        # Объединяем информацию
        stats_parts = []
        if feeding_info:
            stats_parts.append(feeding_info)
        if sleep_info:
            stats_parts.append(sleep_info)

        stats_text = " - " + ", ".join(stats_parts) if stats_parts else ""

        history_text += f"**{date_label}**{stats_text}\n\n"

        # Сортируем все записи дня от новых к старым (в обратном порядке времени)
        daily_data['all_records'].sort(key=lambda x: x['time_obj'], reverse=True)

        # Выводим все записи дня
        for record in daily_data['all_records']:
            if record['type'] == 'кормление':
                history_text += f"   🍼 {record['volume']} в {record['time']}\n"
            elif record['type'] == 'сон':
                emoji = "😴" if record['action'] == 'заснул' else "🌅"
                if record['action'] == 'проснулся' and record['sleep_duration'] is not None:
                    duration_text = format_sleep_duration(record['sleep_duration'])
                    history_text += f"   {emoji} {record['action'].capitalize()} в {record['time']} ({duration_text})\n"
                else:
                    history_text += f"   {emoji} {record['action'].capitalize()} в {record['time']}\n"

        history_text += "\n\n"

    # Добавляем информацию о скрытых днях
    if not show_all and len(sorted_dates) > 3:
        hidden_days = len(sorted_dates) - 3
        hidden_volume = sum(daily_totals[date]['feeding_volume'] for date in sorted_dates[3:])
        hidden_count = sum(daily_totals[date]['feeding_count'] for date in sorted_dates[3:])
        hidden_sleep_count = sum(len(daily_totals[date]['sleep_durations']) for date in sorted_dates[3:])
        hidden_sleep_duration = sum(sum(daily_totals[date]['sleep_durations']) for date in sorted_dates[3:])

        hidden_sleep_text = format_sleep_duration(hidden_sleep_duration)
        history_text += f"... и еще {hidden_days} дней ({hidden_volume} мл, {hidden_count} кормлений, {hidden_sleep_count} снов ({hidden_sleep_text}))\n\n"

    # Создаем инлайн-кнопки
    keyboard = []
    if not show_all and len(sorted_dates) > 3:
        keyboard.append([InlineKeyboardButton("📂 Показать всю историю", callback_data="show_full_history")])

    if show_all:
        keyboard.append([InlineKeyboardButton("📁 Скрыть старые дни", callback_data="hide_old_history")])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    # Отправляем сообщение
    if update.callback_query:
        await update.callback_query.edit_message_text(
            history_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            history_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )



async def handle_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на инлайн-кнопки истории"""
    query = update.callback_query
    await query.answer()

    if query.data == "show_full_history":
        await show_history(update, context, show_all=True)
    elif query.data == "hide_old_history":
        await show_history(update, context, show_all=False)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    user_id = str(update.effective_user.id)
    # ИСПОЛЬЗУЕМ МОСКОВСКОЕ ВРЕМЯ
    current_time, current_datetime = get_moscow_time()

    # Загружаем данные
    data = load_data()
    if user_id not in data:
        data[user_id] = []

    # ПРОВЕРЯЕМ СОСТОЯНИЯ РЕДАКТИРОВАНИЯ ПЕРВЫМИ
    if context.user_data.get('editing_volume'):
        await handle_edit_input(update, context)
        await send_today_summary(update, context)  # ДОБАВЛЕНО
        return

    elif context.user_data.get('editing_time'):
        await handle_edit_input(update, context)
        await send_today_summary(update, context)  # ДОБАВЛЕНО
        return

    elif text in ["120", "90", "60", "150"]:
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
        await send_today_summary(update, context)  # ДОБАВЛЕНО

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
        await send_today_summary(update, context)  # ДОБАВЛЕНО

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
        await send_today_summary(update, context)  # ДОБАВЛЕНО

    elif text == "История":
        await show_history(update, context)

    elif text == "Редактировать последнюю запись":
        await edit_last_record(update, context)

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
                await send_today_summary(update, context)  # ДОБАВЛЕНО
            else:
                await update.message.reply_text("❌ Объем должен быть положительным числом")
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите число (объем в мл)")

    else:
        await handle_unknown_command(update, context)


async def show_help(update: Update):
    """Показать справку по использованию бота"""
    help_text = (
        "🤖 Как пользоваться ботом:\n\n"
        "🍼 **Кормление:**\n"
        "- Нажмите на кнопку с объемом (120, 90, 60, 150 мл)\n"
        "- Или выберите 'Ввести объем вручную' для произвольного объема\n\n"
        "😴 **Сон:**\n"
        "- 'Заснул' - записать время начала сна\n"
        "- 'Проснулся' - записать время окончания сна\n\n"
        "📊 **История:**\n"
        "- Просмотр последних записей о кормлениях и сне\n\n"
        "Все записи автоматически сохраняются с текущим временем!"
    )

    await update.message.reply_text(
        help_text,
        reply_markup=create_main_keyboard()
    )

async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нераспознаных команд"""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, Виктория! 👋\n"
        "Я бот для отслеживания кормлений и сна твоего малыша.\n"
        "Твоя команда мне не понятна, выбери объем съеденного или обозначь заснул или проснулся малыш.",
        reply_markup=create_main_keyboard()
    )

def get_last_record(user_id):
        """Получить последнюю запись пользователя"""
        data = load_data()
        user_records = data.get(str(user_id), [])
        if not user_records:
            return None

        # Сортируем по времени (новые первыми)
        user_records.sort(key=lambda x: x['timestamp'], reverse=True)
        return user_records[0]

def delete_last_record(user_id):
        """Удалить последнюю запись пользователя"""
        data = load_data()
        user_id_str = str(user_id)
        user_records = data.get(user_id_str, [])
        if not user_records:
            return False

        # Сортируем и удаляем последнюю
        user_records.sort(key=lambda x: x['timestamp'], reverse=True)
        deleted_record = user_records.pop(0)
        data[user_id_str] = user_records
        save_data(data)
        return deleted_record


def update_last_record(user_id, new_time=None, new_volume=None):
    """Обновить последнюю запись"""
    data = load_data()
    user_id_str = str(user_id)
    user_records = data.get(user_id_str, [])
    if not user_records:
        return False

    # Сортируем и обновляем последнюю
    user_records.sort(key=lambda x: x['timestamp'], reverse=True)
    record = user_records[0]

    if new_time:
        # Обновляем время
        record['time'] = new_time
        # Обновляем timestamp с московским временем
        # Получаем текущую дату с московским временем
        _, current_moscow_datetime = get_moscow_time()
        # Обновляем timestamp
        old_timestamp = datetime.fromisoformat(record['timestamp'])
        hours, minutes = map(int, new_time.split(':'))
        new_timestamp = old_timestamp.replace(hour=hours, minute=minutes)
        record['timestamp'] = new_timestamp.isoformat()

    if new_volume and record['type'] == 'кормление':
        record['volume'] = f"{new_volume} мл"

    data[user_id_str] = user_records
    save_data(data)
    return True

async def edit_last_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать меню редактирования последней записи"""
        user_id = update.effective_user.id
        last_record = get_last_record(user_id)

        if not last_record:
            await update.message.reply_text(
                "❌ Нет записей для редактирования",
                reply_markup=create_main_keyboard()
            )
            return

        # Формируем текст записи
        if last_record['type'] == 'кормление':
            record_text = f"🍼 Кормление: {last_record['volume']} в {last_record['time']}"
        else:
            emoji = "😴" if last_record['action'] == 'заснул' else "🌅"
            record_text = f"{emoji} {last_record['action'].capitalize()} в {last_record['time']}"

        # Создаем клавиатуру для редактирования
        keyboard = []
        if last_record['type'] == 'кормление':
            keyboard.append([InlineKeyboardButton("✏️ Изменить объем", callback_data="edit_volume")])

        keyboard.append([InlineKeyboardButton("🕐 Изменить время", callback_data="edit_time")])
        keyboard.append([InlineKeyboardButton("🗑️ Удалить запись", callback_data="delete_record")])
        keyboard.append([InlineKeyboardButton("↩️ Назад", callback_data="cancel_edit")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"📝 Редактирование последней записи:\n{record_text}\n\nВыберите действие:",
            reply_markup=reply_markup
        )


async def handle_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки редактирования"""
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data == "edit_volume":
        context.user_data['editing_volume'] = True
        await query.edit_message_text(
            "✏️ Введите новый объем в мл:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Отмена", callback_data="cancel_edit")]])
        )

    elif query.data == "edit_time":
        context.user_data['editing_time'] = True
        await query.edit_message_text(
            "🕐 Введите новое время (формат ЧЧ:ММ, например 14:30):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Отмена", callback_data="cancel_edit")]])
        )

    elif query.data == "delete_record":
        # Подтверждение удаления
        keyboard = [
            [InlineKeyboardButton("✅ Да, удалить", callback_data="confirm_delete")],
            [InlineKeyboardButton("❌ Нет, отмена", callback_data="cancel_edit")]
        ]
        await query.edit_message_text(
            "❓ Вы уверены, что хотите удалить последнюю запись?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "confirm_delete":
        deleted_record = delete_last_record(user_id)
        if deleted_record:
            if deleted_record['type'] == 'кормление':
                record_text = f"🍼 Кормление: {deleted_record['volume']} в {deleted_record['time']}"
            else:
                emoji = "😴" if deleted_record['action'] == 'заснул' else "🌅"
                record_text = f"{emoji} {deleted_record['action'].capitalize()} в {deleted_record['time']}"

            # Сразу возвращаем в главное меню с сообщением об удалении
            await query.edit_message_text(
                f"✅ Запись удалена:\n{record_text}",
                reply_markup=None
            )

            # Отправляем сводку за сегодня
            await send_today_summary(update, context)  # ДОБАВЛЕНО
        else:
            await query.edit_message_text(
                "❌ Ошибка при удалении записи или записей больше нет",
                reply_markup=create_main_keyboard()
            )

    elif query.data == "cancel_edit":
        # Полностью закрываем меню редактирования
        await query.edit_message_text(
            "✏️ Редактирование отменено",
            reply_markup=None
        )

        # Возвращаем в главное меню
        await query.message.reply_text(
            "Выберите действие:",
            reply_markup=create_main_keyboard()
        )

        # Очищаем состояние редактирования
        context.user_data.pop('editing_volume', None)
        context.user_data.pop('editing_time', None)


async def handle_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода данных при редактировании"""
    user_id = update.effective_user.id
    text = update.message.text.strip()  # Убираем лишние пробелы

    if context.user_data.get('editing_volume'):
        try:
            volume = int(text)
            if volume > 0:
                if update_last_record(user_id, new_volume=volume):
                    await update.message.reply_text(
                        f"✅ Объем обновлен: {volume} мл",
                        reply_markup=create_main_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        "❌ Ошибка при обновлении объема",
                        reply_markup=create_main_keyboard()
                    )
            else:
                await update.message.reply_text(
                    "❌ Объем должен быть положительным числом",
                    reply_markup=create_main_keyboard()
                )
        except ValueError:
            await update.message.reply_text(
                "❌ Пожалуйста, введите число (объем в мл)",
                reply_markup=create_main_keyboard()
            )

        # Очищаем состояние независимо от результата
        context.user_data.pop('editing_volume', None)

    elif context.user_data.get('editing_time'):
        try:
            # Проверяем формат времени
            if ':' in text and len(text) == 5:
                hours, minutes = map(int, text.split(':'))
                if 0 <= hours <= 23 and 0 <= minutes <= 59:
                    time_str = f"{hours:02d}:{minutes:02d}"  # Форматируем как 14:05
                    if update_last_record(user_id, new_time=time_str):
                        await update.message.reply_text(
                            f"✅ Время обновлено: {time_str}",
                            reply_markup=create_main_keyboard()
                        )
                    else:
                        await update.message.reply_text(
                            "❌ Ошибка при обновлении времени",
                            reply_markup=create_main_keyboard()
                        )
                else:
                    await update.message.reply_text(
                        "❌ Неверный формат времени. Часы: 0-23, минуты: 0-59",
                        reply_markup=create_main_keyboard()
                    )
            else:
                await update.message.reply_text(
                    "❌ Неверный формат времени. Используйте ЧЧ:ММ (например, 14:30)",
                    reply_markup=create_main_keyboard()
                )
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат времени. Используйте ЧЧ:ММ (например, 14:30)",
                reply_markup=create_main_keyboard()
            )

        # Очищаем состояние независимо от результата
        context.user_data.pop('editing_time', None)

def main():
    """Основная функция"""
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))

    # Обработчики callback запросов
    application.add_handler(
        CallbackQueryHandler(handle_history_callback, pattern="^(show_full_history|hide_old_history)$"))
    application.add_handler(CallbackQueryHandler(handle_edit_callback, pattern="^(edit_volume|edit_time|delete_record|confirm_delete|cancel_edit)$"))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    print("Бот запущен...")
    application.run_polling()


if __name__ == '__main__':
    main()