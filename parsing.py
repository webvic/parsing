import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from datetime import datetime

# URL первой страницы
BASE_URL = "https://www.cian.ru/cat.php?deal_type=sale&district[0]=107&engine_version=2&offer_type=flat&room4=1&room5=1"

# Функция для получения HTML содержимого страницы
def get_html(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

def parse_geo(geo_block):
    try:
        # Извлекаем все ссылки с атрибутом data-name="GeoLabel"
        geo_links = geo_block.find_all("a", {"data-name": "GeoLabel"})
        
        # Извлекаем значения
        city = geo_links[0].text.strip() if len(geo_links) > 0 else None
        area = geo_links[1].text.strip() if len(geo_links) > 1 else None
        district = geo_links[2].text.strip() if len(geo_links) > 2 else None
        metro = geo_links[3].text.strip() if len(geo_links) > 3 else None
        street = geo_links[4].text.strip() if len(geo_links) > 4 else None
        house = geo_links[5].text.strip() if len(geo_links) > 5 else None

    except Exception as e:
        print(f"Ошибка при парсинге геоданных: {e}")
        city, district, metro, street, house = None, None, None, None, None

    # Возвращаем результат в виде словаря
    geo = {
        "Город": city,
        "Округ": area,
        "Район": district,
        "Метро": metro,
        "Улица": street,
        "Дом": house,
    }
    return geo

def parse_card(card):
    data = {}

    # Ссылка на карточку
    link_tag = card.find('a', class_="_93444fe79c--media--9P6wN")
    data['card_url'] = link_tag['href'] if link_tag else None

    # Ссылка на первое изображение
    img_tag = card.find('img', class_="_93444fe79c--container--KIwW4")
    data['image_url'] = img_tag['src'] if img_tag else None

    # Геокомпоненты
    geo_block = card.find('div', class_="_93444fe79c--labels--L8WyJ")
    geo_data = parse_geo(geo_block)
    
    data.update(geo_data)

    # Цена
    # Находим блок с ценой
    price_tag = card.find("span", {"data-mark": "MainPrice"})

    # Извлекаем текст цены
    if price_tag:
        price_text = price_tag.get_text(strip=True)
        # Убираем пробелы и символы валюты, оставляем только цифры
        price = int(re.sub(r"[^\d]", "", price_text))
        print(f"Цена: {price}")
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
        print(f"Цена за м²: {price_per_sqm}")
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

        # Вывод результатов
        print(f"Количество комнат: {rooms}")
        print(f"Этаж: {floor}")
        print(f"Этажность: {total_floors}")
    else:
        print("Информация об объекте не найдена")    

    data['Комнат']=rooms
    data['Этаж']=floor
    data['Этажность']=total_floors
    data['Площадь']=area

    # Описание
    description_tag = card.find('div', class_="_93444fe79c--description--SqTNp")
    data['description'] = description_tag.get_text(strip=True) if description_tag else None

    return data

# Функция для извлечения данных с одной страницы
def parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
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
        data = parse_page(html)
        all_data.extend(data)

        # Переход на следующую страницу
        soup = BeautifulSoup(html, "html.parser")
        next_page = soup.find("a", class_="c6e8ba5398--button--2xPMX")
        url = next_page["href"] if next_page else None
    return all_data

# Сбор данных
data = parse_all_pages(BASE_URL)

# Создание DataFrame
df = pd.DataFrame(data)

# Сохранение в CSV
output_file = f"cian_flats_{datetime.now().strftime('%Y%m%d')}.csv"
df.to_csv(output_file, index=False, encoding="utf-8-sig")
print(f"Данные сохранены в файл: {output_file}")

average_price = df["Цена, ₽"].mean()
average_price_per_sqm = df["Цена за м², ₽"].mean()
average_area = df["Площадь"].mean()

# Добавление строки ИТОГО
df.loc['ИТОГО'] = {
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

# Вывод DataFrame с итогами
print(df[['Комнат','Улица','Дом', 'Площадь','Цена, ₽', 'Цена за м², ₽', 'Этаж', 'Этажность','description']])

