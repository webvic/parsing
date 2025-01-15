import logging
import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler
)
from parsing import get_metro_dict, parsing_site
from tabulate import tabulate
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv


# Настройка логгирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# Шаги для ConversationHandler
ENTERING_ROOMS, ENTERING_METRO, CHOOSING_METRO, POST_RESULTS = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Приветствует пользователя и предлагает выбрать количество комнат с помощью кнопок.
    """
    await choose_rooms_buttons(update, context)
    return ENTERING_ROOMS


# Обработка выбора количества комнат
async def choose_rooms_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает кнопки для выбора количества комнат.
    """
    keyboard = [
        [InlineKeyboardButton(str(i), callback_data=f"choose_rooms:{i}") for i in range(1, 6)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_message(update, "Сколько комнат вас интересует?", reply_markup=reply_markup)
    return ENTERING_ROOMS

# Поиск станции метро
async def search_metro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip().lower()

    if len(user_input) < 3:
        await update.message.reply_text("Введите хотя бы 3 буквы для поиска станции метро.")
        return ENTERING_METRO

    matches = [
        (code, name)
        for code, name in metro_codes.items()
        if user_input in name.lower()
    ]

    if not matches:
        await update.message.reply_text("Станции не найдены. Попробуйте ввести другую часть названия.")
        return ENTERING_METRO

    context.user_data["metro_matches"] = matches

    # Переход на кнопки выбора станций
    await choose_metro_buttons(update, context)
    return CHOOSING_METRO

async def process_parsing(update: Update, context: ContextTypes.DEFAULT_TYPE, metro_code, metro_name):
    """Общий функционал для обработки выбранной станции метро."""
    rooms = context.user_data.get("rooms")
    query = update.callback_query

    # Уведомление пользователя
    if query:
        await query.message.reply_text(f"Ищем {rooms}-комнатные квартиры у метро {metro_name}...")
    else:
        await update.message.reply_text(f"Ищем {rooms}-комнатные квартиры у метро {metro_name}...")

    # Парсинг сайта
    df = parsing_site(rooms, metro_name, metro_code)

    # Отправка результатов
    await send_results_as_table(update, context, df)



MAX_BUTTON_NUM = 6

async def choose_metro_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Получаем список станций из пользовательских данных
        matches = context.user_data.get("metro_matches", [])
        
        if not matches:  # Если список пуст
            await send_message(update, "Не удалось найти станции метро. Попробуйте снова.")
            return ENTERING_METRO

        # Инициализация сообщения о превышении количества кнопок
        message = "Выберите станцию метро:"
        if len(matches) > MAX_BUTTON_NUM:
            message += '\n☝ Показаны не все результаты. Уточните поиск, если нужно.'

        buttons = [
            [InlineKeyboardButton(name[:24], callback_data=f"choose_metro:{code}:{name[:24]}")]
            for code, name in matches[:MAX_BUTTON_NUM]
        ]
        buttons.append([InlineKeyboardButton("🔄 Уточнить поиск", callback_data="repeat_search")])


        # Создаём клавиатуру
        reply_markup = InlineKeyboardMarkup(buttons)

        # отладка
        logging.info(f"Кнопки для отправки: {buttons}")
        reply_markup = InlineKeyboardMarkup(buttons)

        # Отправка сообщения с кнопками напрямую
        await update.message.reply_text(
            text=message,  # Текст сообщения
            reply_markup=reply_markup  # Клавиатура с кнопками
        )

        return CHOOSING_METRO

    except Exception as e:
        logging.error(f"Ошибка в choose_metro_buttons: {e}")
        await send_message(update, "Произошла ошибка. Попробуйте снова.")
        return ENTERING_METRO


async def metro_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "repeat_search":
        await query.edit_message_text("Введите часть названия станции метро для нового поиска:")
        return ENTERING_METRO

    if data.startswith("choose_metro:"):
        _, metro_code, metro_name = data.split(":")
        await process_parsing(update, context, metro_code, metro_name)
        return POST_RESULTS  # Возвращаем состояние для обработки кнопок


        

# Отмена
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Диалог отменён. Напишите /start, чтобы начать снова.")
    return ConversationHandler.END

async def send_message(update: Update, text: str, **kwargs):
    """
    Универсальная функция отправки сообщения.
    """
    if update.callback_query:
        await update.callback_query.message.reply_text(text, **kwargs)
    else:
        await update.message.reply_text(text, **kwargs)


async def send_results_as_table(update: Update, context: ContextTypes.DEFAULT_TYPE, df):
    """
    Форматирует DataFrame как таблицу и отправляет пользователю.
    """
    if df.empty:
        await send_message(update, "К сожалению, ничего не найдено для вашего запроса.")
        return POST_RESULTS  # Возвращаем состояние для обработки кнопок

    # Формирование таблицы
    table = tabulate(df, headers='keys', tablefmt='grid', showindex=True)
    await send_message(update, f"Результаты:\n\n```\n{table}\n```", parse_mode="Markdown")

    # Добавление кнопок для выбора действия
    keyboard = [
        [InlineKeyboardButton("Новый поиск", callback_data="new_search")],
        [InlineKeyboardButton("Закончить", callback_data="end_conversation")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_message(update, "Что вы хотите сделать дальше?", reply_markup=reply_markup)

    return POST_RESULTS  # Возвращаем состояние для обработки кнопок


async def handle_post_results_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action = query.data

    logging.info(f"Получены данные кнопки: {action}")

    if action == "new_search":
        # Редактируем сообщение для перехода на новый поиск
        await query.message.edit_text("Начинаем новый поиск. Сколько комнат вы хотите?")
        # Показываем кнопки выбора количества комнат
        await choose_rooms_buttons(update, context)
        return ENTERING_ROOMS

    if action == "end_conversation":
        # Завершаем диалог
        await query.message.edit_text("Спасибо за использование бота! До свидания!")
        return ConversationHandler.END





async def room_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает выбор количества комнат через кнопки.
    """
    query = update.callback_query
    data = query.data

    if data.startswith("choose_rooms:"):
        rooms = data.split(":")[1]
        context.user_data["rooms"] = rooms
        await query.edit_message_text(f"Вы выбрали {rooms}-комнатную квартиру. Теперь введите часть названия станции метро:")
        return ENTERING_METRO

async def show_start_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Начать поиск", callback_data="start_search")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Нажмите кнопку ниже, чтобы начать:", reply_markup=reply_markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Приветствует пользователя и предлагает выбрать количество комнат с помощью кнопок.
    """
    await choose_rooms_buttons(update, context)  # Показываем кнопки для выбора
    return ENTERING_ROOMS


# Загрузка переменных из .env
load_dotenv()

# Получение токена из переменных окружения
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise ValueError("Токен Telegram бота не найден в переменных окружения!")

def main():
    # Создание приложения Telegram
    application = Application.builder().token(TOKEN).build()

    # ConversationHandler для обработки диалогов
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ENTERING_ROOMS: [CallbackQueryHandler(room_button_handler)],
            ENTERING_METRO: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_metro)],
            CHOOSING_METRO: [CallbackQueryHandler(metro_button_handler)],
            POST_RESULTS: [CallbackQueryHandler(handle_post_results_buttons, pattern="^(new_search|end_conversation)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Добавление ConversationHandler в приложение
    application.add_handler(conv_handler)

    # Обработчик для кнопки "Начать новый поиск" вне контекста текущего диалога
    application.add_handler(CallbackQueryHandler(start, pattern="start_search"))

    # Запуск бота
    application.run_polling()


if __name__ == "__main__":
    metro_codes = get_metro_dict()
    main()
