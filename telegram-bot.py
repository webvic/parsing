import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from parsing import get_metro_dict, parsing_site
from tabulate import tabulate

# Настройка логгирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# Шаги для ConversationHandler
ENTERING_ROOMS, ENTERING_METRO, CHOOSING_METRO = range(3)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Добро пожаловать! Сколько комнат вас интересует? (Например, 1, 2, 3):")
    return ENTERING_ROOMS

# Обработка выбора количества комнат
async def choose_rooms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()

    # Проверка, что пользователь ввел корректное число
    if user_input.isdigit() and 1 <= int(user_input) <= 5:
        context.user_data["rooms"] = user_input
        await update.message.reply_text(f"Вы выбрали {user_input}-комнатную квартиру. Теперь введите часть названия станции метро:")
        return ENTERING_METRO
    else:
        await update.message.reply_text("Пожалуйста, введите корректное количество комнат (например, 1, 2, 3).")
        return ENTERING_ROOMS

# Поиск станции метро
async def search_metro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip().lower()

    # Формируем сообщение только если длина ввода >= 3 символов
    if len(user_input) < 3:
        await update.message.reply_text("Введите хотя бы 3 буквы для поиска станции метро.")
        return ENTERING_METRO  # Возвращаемся на текущий шаг диалога

    # Поиск совпадений в справочнике
    matches = [
        (code, name)
        for code, name in metro_codes.items()
        if user_input in name.lower()
    ]

    # Если совпадений нет
    if not matches:
        await update.message.reply_text("Станции не найдены. Попробуйте ввести другую часть названия.")
        return ENTERING_METRO

    # Если найдены совпадения
    response = "Найдены следующие станции метро:\n"
    for i, (code, name) in enumerate(matches, start=1):
        response += f"{i}. {name} (код: {code})\n"

    response += "\nВведите номер станции, чтобы выбрать её:"
    await update.message.reply_text(response)

    # Сохраняем список найденных станций в context.user_data
    context.user_data["metro_matches"] = matches

    return CHOOSING_METRO

async def process_parsing(update: Update, context: ContextTypes.DEFAULT_TYPE, metro_code, metro_name):
    """Общий функционал для обработки выбранной станции метро."""
    rooms = context.user_data.get("rooms")

    # Уведомление пользователя
    await update.message.reply_text(f"Ищем {rooms}-комнатные квартиры у метро {metro_name}...")

    # Парсинг сайта
    df = parsing_site(rooms, metro_name, metro_code)

    # Отправка результатов
    await send_results_as_table(update, context, df)


async def choose_metro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        matches = context.user_data.get("metro_matches", [])

        # Если найдено только одно совпадение
        if len(matches) == 1:
            metro_code, metro_name = matches[0]
            await update.message.reply_text(
                f"Выбрана станция: {metro_name}"
            )
            # Переходим сразу к парсингу
            await process_parsing(update, context, metro_code, metro_name)
            return ConversationHandler.END

        # Если станций больше одной, ожидаем выбор
        try:
            station_index = int(update.message.text.strip()) - 1

            if 0 <= station_index < len(matches):
                metro_code, metro_name = matches[station_index]
                await process_parsing(update, context, metro_code, metro_name)
            else:
                await update.message.reply_text("Неверный номер станции. Попробуйте снова.")
                return CHOOSING_METRO
        except ValueError:
            await update.message.reply_text("Ошибка ввода. Пожалуйста, введите номер станции.")
            return CHOOSING_METRO
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {e}")
        return ConversationHandler.END

    return ConversationHandler.END

# Отмена
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Диалог отменён. Напишите /start, чтобы начать снова.")
    return ConversationHandler.END


async def send_results_as_table(update, context, df):
    """
    Форматирует DataFrame как таблицу и отправляет пользователю.
    """
    if df.empty:
        await update.message.reply_text("К сожалению, ничего не найдено для вашего запроса.")
        return

    # Оставляем только нужные колонки для отображения
    columns_to_show = ['N', 'S, м²', 'M₽', 'K₽/м²']
    df_for_display = df.loc[["СРЕДН.", "Пешком", "Трансп.", "В ЖК", "Втор."], columns_to_show]

    # Преобразование в текстовую таблицу
    table_text = df_for_display.to_markdown(tablefmt="grid")

    # Отправка таблицы
    await update.message.reply_text(f"```\n{table_text}\n```", parse_mode="Markdown")


TOKEN = '7658930193:AAEyx9h-97BuQiDJAbNYBP6ItoOu54tKfHo'

# Главная функция
def main():

    # Создание приложения Telegram
    application = Application.builder().token(TOKEN).build()

    # Настройка ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ENTERING_ROOMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_rooms)],
            ENTERING_METRO: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_metro)],
            CHOOSING_METRO: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_metro)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Регистрация обработчиков
    application.add_handler(conv_handler)

    # Запуск бота
    application.run_polling()

if __name__ == "__main__":
    metro_codes = get_metro_dict()
    main()
