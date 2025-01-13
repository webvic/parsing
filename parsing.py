import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from datetime import datetime
from urllib.parse import urljoin
import time

# URL первой страницы
DOMAIN = "https://www.cian.ru/"

def get_full_url(base_url, link):
    return urljoin(base_url, link)

# Функция для получения HTML содержимого страницы
def get_html(url):
    headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    trys = 0
    while trys < 10:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        elif response.status_code == 429:
            print('Отказ. Ждем 2 сек ')
            time.sleep(2)           
            trys += 1
            continue
        else:
            print(f"Ошибка при получении страницы: {response.status_code}")
            return None   
    else:
        print('Не удалось получить код')
        return None   

def parse_geo(geo_block):
    try:
        # Извлекаем все ссылки с атрибутом data-name="GeoLabel"
        geo_links = geo_block.find_all("a", {"data-name": "GeoLabel"})
        
        # Извлекаем значения
        # Объединение текста из каждого <a> тега в строку
        address = ", ".join(tag.text.strip() for tag in geo_links)

    except Exception as e:
        print(f"Ошибка при парсинге геоданных: {e}")
        address = None

    return address  

def parse_card(card):
    data = {}

    # Ссылка на карточку
    link_tag = card.find('a', class_="_93444fe79c--media--9P6wN")
    data['card_url'] = link_tag['href'] if link_tag else None

    # Ссылка на первое изображение
    img_tag = card.find('img', class_="_93444fe79c--container--KIwW4")
    data['image_url'] = img_tag['src'] if img_tag else None

    # Адрес
    geo_block = card.find('div', class_="_93444fe79c--labels--L8WyJ")
    address = parse_geo(geo_block)

    # Извлекаем ЖК
    jk_tag = card.find('a', class_="_93444fe79c--jk--dIktL")
    if jk_tag:
        data['В ЖК'] = jk_tag.text.strip()
    
    data['Адрес'] = address

    # Удаленность от метро
    # <div class="_93444fe79c--remoteness--q8IXp">9 минут пешком</div>
    link_tag = card.find('div', class_="_93444fe79c--remoteness--q8IXp")
    remoutness = link_tag.get_text(strip=True)
    data['От метро'] = 'Пешком' if 'пешком' in remoutness.lower() else 'Транспортом'

    # Цена
    # Находим блок с ценой
    price_tag = card.find("span", {"data-mark": "MainPrice"})

    # Извлекаем текст цены
    if price_tag:
        price_text = price_tag.get_text(strip=True)
        # Убираем пробелы и символы валюты, оставляем только цифры
        price = int(re.sub(r"[^\d]", "", price_text))
        # print(f"Цена: {price}")
    else:
        print("Цена не найдена")

    data['Цена, ₽'] = price

    # Находим блок с ценой за квадратный метр
    price_per_sqm_tag = card.find("p", {"data-mark": "PriceInfo"})

    # Извлекаем текст цены за квадратный метр
    if price_per_sqm_tag:
        price_per_sqm_text = price_per_sqm_tag.get_text(strip=True)
        # Убираем пробелы и символы валюты, оставляем только цифры
        price_per_sqm = int(re.sub(r"[^\d]", "", price_per_sqm_text))
        # print(f"Цена за м²: {price_per_sqm}")
    else:
        print("Цена за м² не найдена")   

    data['Цена за м², ₽'] = price_per_sqm     

    # Находим блок с офером 
    offer_title_tag = card.find("span", {"data-mark": "OfferTitle"})

    # Извлекаем текст из тега
    if offer_title_tag:
        offer_text = offer_title_tag.get_text(strip=True)

        # Регулярное выражение
        pattern = r"(?P<rooms>\d+)-комн\..*?(?P<area>[\d,]+)\sм².*?(?P<floor>\d+)/(?P<total_floors>\d+)\sэтаж"

        # Применение регулярного выражения
        match = re.search(pattern, offer_text)

        if match:
            rooms = int(match.group("rooms"))
            area = float(match.group("area").replace(",", "."))  # Преобразование площади в число с плавающей точкой
            floor = int(match.group("floor"))
            total_floors = int(match.group("total_floors"))

            data['Комнат']=rooms
            data['Этаж']=floor
            data['Этажность']=total_floors
            data['Площадь']=area
    else:
        print("Информация об объекте не найдена")    

    # Описание
    description_tag = card.find('div', class_="_93444fe79c--description--SqTNp")
    data['description'] = description_tag.get_text(strip=True) if description_tag else None

    return data

# Функция для извлечения данных с одной страницы
def parse_page(soup):

    results_block= soup.find('div', class_="_93444fe79c--wrapper--W0WqH")

    # Находим список всех article с data-name="CardComponent"
    #  Пример открывающего тега блока: <article data-name="CardComponent" class="_93444fe79c--container--Povoi _93444fe79c--cont--OzgVc">
    cards = results_block.find_all('article', {
        'data-name': 'CardComponent',
        'class': '_93444fe79c--container--Povoi _93444fe79c--cont--OzgVc'
    })

    # Проверяем количество найденных блоков
    print(f"Найдено {len(cards)} блоков.")

    # Извлекаем данные из каждой карточки
    results = [parse_card(card) for card in cards]
    return results


# Функция для обработки всех страниц
def parse_all_pages(base_url):
    all_data = []
    url = base_url
    while url:
        print(f"Обрабатываем страницу: {url}")
        html = get_html(url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
        else:
            print (f'Парсинг прерван сервером. Возвращаем {len(all_data)} квартир, которые успели скачать')
            break
        
        # Парсинг данных текущей страницы
        data = parse_page(soup)  # Предполагается, что parse_page определён ранее
        all_data.extend(data)

        next_button = soup.find("a", {"class": "_93444fe79c--button--KVooB"}, string="Дальше")
        if next_button:
            url = next_button["href"]  # Переход на следующую страницу
            url = get_full_url(DOMAIN, url)
            time.sleep(1)
        else:
            url = None  # Конец пагинации

    return all_data

# URL справочника метро
metro_url = "https://www.cian.ru/metros-moscow.xml"

# Функция для получения словаря метро
def get_metro_dict(url=metro_url):
    # Скачиваем XML-файл
    response = requests.get(url)
    response.raise_for_status()  # Проверка на успешность запроса

    # Парсинг XML
    soup = BeautifulSoup(response.content, "xml")
    metro_dict = {}
    
    # Извлекаем данные о станциях
    for location in soup.find_all("location"):
        metro_id = int(location["id"])
        metro_name = location.text.strip()
        metro_dict[metro_id] = metro_name
    
    return metro_dict

def get_user_input_with_search(metro_codes):
    print("Введите количество комнат (например, 1, 2, 3):")
    rooms = input().strip()
    
    # Поиск станции метро
    while True:
        print("\nВведите часть названия станции метро:")
        search_query = input().strip().lower()
        
        # Поиск подходящих станций
        matches = [
            (code, name) for code, name in metro_codes.items()
            if search_query in name.lower()
        ]
        
        if not matches:
            print("Станции не найдены. Попробуйте ещё раз.")
            continue
        
        # Показ результатов поиска
        print("\nНайдены станции:")
        for i, (code, name) in enumerate(matches, start=1):
            print(f"{i}. {name} (код: {code})")
        
        if len(matches) == 1:
            metro_code, metro_name = matches[0]
            break
        else:
            print("\nВведите номер станции:")
            try:
                station_index = int(input().strip()) - 1
                if 0 <= station_index < len(matches):
                    metro_code, metro_name = matches[station_index]
                    break
                else:
                    print("Неверный номер. Попробуйте ещё раз.")
            except ValueError:
                print("Ошибка ввода. Попробуйте ещё раз.")
    
    # Убедитесь, что return имеет правильный отступ
    return rooms, metro_name, metro_code


# Формирование URL
def generate_url(rooms, metro_code):
    base_url = "https://www.cian.ru/cat.php"
    query_params = (
        f"deal_type=sale&engine_version=2&offer_type=flat&"
        f"metro%5B0%5D={metro_code}&room{rooms}=1"
    )
    return f"{base_url}?{query_params}"

if __name__ == "__main__":
    metro_codes = get_metro_dict()
    rooms, metro_name, metro_code = get_user_input_with_search(metro_codes)
    final_url = generate_url(rooms, metro_code)
    
    print("\nВы выбрали:")
    print(f"Количество комнат: {rooms}")
    print(f"Станция метро: {metro_name} (код: {metro_code})")
    print(f"Сформированный URL: {final_url}")

    # Сбор данных
    data = parse_all_pages(final_url)

    # Создание DataFrame
    df_all = pd.DataFrame(data)

    df_all['Количество'] = None  # Создаем столбец с пустыми значениями
    if "В ЖК" not in df_all.columns:
        df_all['В ЖК'] = None

    df_foot = df_all[df_all['От метро'] == 'Пешком']
    df_transp = df_all[df_all['От метро'] == 'Транспортом']
    df_jk = df_all[df_all['В ЖК'].notna()]
    df_second = df_all[df_all['В ЖК'].isna()]

    dfs = [df_all, df_foot, df_transp,df_jk,df_second]
    totals = ['СРЕДНЕЕ', 'Пешком', 'Транспортом', 'В ЖК', 'Вторичка']

    for df, total in zip(dfs, totals):

        average_price = df["Цена, ₽"].mean()
        average_price_per_sqm = df["Цена за м², ₽"].mean()
        average_area = df["Площадь"].mean()
        amount = len(df)

        # Добавление строк с итогами
        df_all.loc[total] = {
            'Количество': amount,
            'Комнат': '—',
            'Улица': '—',
            'Дом': '—',
            'Площадь': average_area,
            'Цена, ₽': average_price,
            'Цена за м², ₽': average_price_per_sqm,
            'Этаж': '—',
            'Этажность': '—',
            'description': 'Средние значения'
        }
    # Создание форматированных колонок
    df_all['Площадь, м²'] = df_all['Площадь'].apply(lambda x: f"{x:.1f}")
    df_all['Цена, млн. ₽'] = df_all['Цена, ₽'].apply(lambda x: f"{x / 1_000_000:.1f}")
    df_all['Цена за м², тыс. ₽'] = df_all['Цена за м², ₽'].apply(lambda x: f"{x / 1_000:.1f}")

    # Вывод DataFrame с итогами
    print(df_all[['В ЖК', 'Площадь, м²','Цена, млн. ₽', 'Цена за м², тыс. ₽', 'description']])
    print(df_all.iloc[-5:][['Количество','Площадь, м²','Цена, млн. ₽', 'Цена за м², тыс. ₽']])

    # Сохранение в CSV
    output_file = f"cian_flats_{metro_name}_{rooms}_{datetime.now().strftime('%Y%m%d')}.csv"
    df_all.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"Данные сохранены в файл: {output_file}")
