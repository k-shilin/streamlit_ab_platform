import streamlit as st
import time
import numpy as np
import pandas as pd
import random
import pydeck as pdk

from datetime import datetime
from helper import read_sql

#st.set_page_config(page_title="Plotting Demo", page_icon="📈")

st.title("A/B Home 🏠")

st.markdown(
"""
##### Приветствую тебя, пытливый экспериментатор!

##### Добро пожаловать в интереснейшний мир экспериментов - здесь тебе предстоит познать как радость от прокрасившихся тестов, так и горечь от глубоко закопанных некогда лучших идей.
"""
)
st.sidebar.markdown("#### by CVM&Analytics team")
st.divider()

st.header("Какие эксперименты запущены?", divider=True)

main_table = "delta.`abfss://deltalake@p0dbscv0sa0dbrks.dfs.core.windows.net/data/ab/main`"
units_table = "delta.`abfss://deltalake@p0dbscv0sa0dbrks.dfs.core.windows.net/data/ab/units`"
geo_table = "delta.`abfss://deltalake@p0dbscv0sa0dbrks.dfs.core.windows.net/data/ab/units_geo`"

query_in_progress = f"""
    select
        experiment_short_name,
        target_metric,
        hypothesis,
        start_of_test,
        status,
        alpha,
        beta,
        load_datetime,
        days_for_test
    from {main_table}
    where status = 'in progress'
"""


with st.spinner("Downloading data..."):
    df_metrics_by_unit = read_sql(query=query_in_progress)
    len_df = df_metrics_by_unit.shape[0]
    df_metrics_by_unit["dynamic"] = [[random.randint(0, 100) for _ in range(30)] for i in range(len_df)]
    column_to_move = df_metrics_by_unit.pop("dynamic")
    df_metrics_by_unit.insert(2, "dynamic", column_to_move)
    
    def add_days_to_the_end(x):
        return (datetime.now() - datetime.strptime(x, "%Y-%m-%d")).days
    df_metrics_by_unit["days_to_the_end"] = df_metrics_by_unit["start_of_test"].apply(lambda x: add_days_to_the_end(x))
    df_metrics_by_unit["time_to_end_percent"] = np.round(df_metrics_by_unit["days_to_the_end"] / df_metrics_by_unit["days_for_test"], 4)
    column_to_move = df_metrics_by_unit.pop("time_to_end_percent")
    df_metrics_by_unit.insert(3, "time_to_end_percent", column_to_move)
    
    st.dataframe(
        df_metrics_by_unit,
        column_config={
            "experiment_short_name": "Эксперимент",
            "target_metric": "Целевая метрика",
            "dynamic": st.column_config.AreaChartColumn(
                "Динамика целевой метрики",
                width="medium",
                y_min=0,
                y_max=100,
            ),
            "days_to_the_end": "Дней до завершения теста",
            "days_for_test": "Всего дней в тесте",
            "time_to_end_percent": st.column_config.ProgressColumn(
                "Прошло времени с момента запуска",
                help="Время в %",
                min_value=0,
                max_value=1,
            ),
            "hypothesis": "Гипотеза",
            "start_of_test": "Дата начала теста",
            "status": "Статус эксперимента",
            "alpha": "Ошибка первого рода",
            "beta": "Ошибка второго рода",
            "load_datetime": "Дата загрузки"
        },
        hide_index=True,
    )
st.divider()

st.header("Какие эксперименты планируются к запуску?", divider=True)
st.markdown(
    """
    ##### Таблица содержит информацию об экспериментах, которые находятся на этапе формирования дизайна
    """
)

query_not_approved = f"""
    select
        experiment_short_name,
        target_metric,
        hypothesis,
        design_date,
        status,
        alpha,
        beta,
        load_datetime
    from {main_table}
    where status = 'design not approved'
"""

with st.spinner("Downloading data..."):
    df_metrics_by_unit = read_sql(query=query_not_approved)
    len_df = df_metrics_by_unit.shape[0]
    df_metrics_by_unit["dynamic"] = [[random.randint(0, 100) for _ in range(30)] for i in range(len_df)]

    column_to_move = df_metrics_by_unit.pop("dynamic")
    df_metrics_by_unit.insert(2, "dynamic", column_to_move)

    st.dataframe(
        df_metrics_by_unit,
        column_config={
            "experiment_short_name": "Эксперимент",
            "target_metric": "Целевая метрика",
            "dynamic": st.column_config.AreaChartColumn(
                "Динамика целевой метрики",
                width="medium",
                y_min=0,
                y_max=100,
            ),
            "hypothesis": "Гипотеза",
            "design_date": "Дата дизайна",
            "status": "Статус эксперимента",
            "alpha": "Ошибка первого рода",
            "beta": "Ошибка второго рода",
            "load_datetime": "Дата загрузки"
        },
        hide_index=True,
    )
st.button("Обновить")
st.divider()


# Функция для отображения карты с точками из датафрейма
def plot_map(df):
    # Преобразование данных в нужный формат (если необходимо)
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    df['units_cnt'] = [int(i) for i in np.random.normal(7, 5, len(df))]
    df['units_cnt'] = pd.to_numeric(df['units_cnt'], errors='coerce')
    
    # Фильтрация некорректных строк
    df = df.dropna(subset=['latitude', 'longitude', 'units_cnt'])

    # Определение минимального и максимального значений units_cnt
    min_units = df['units_cnt'].min()
    max_units = df['units_cnt'].max()

    # Функция для динамического изменения цвета в зависимости от значения units_cnt
    def get_color(units_cnt):
        # Нормализация значений units_cnt в диапазоне от 0 до 1
        norm_value = (units_cnt - min_units) / (max_units - min_units) if max_units != min_units else 0.5
        
        # Интерполяция от зеленого (0, 255, 0) до красного (255, 0, 0)
        red = int(255 * norm_value)
        green = int(255 * (1 - norm_value))
        return [red, green, 0]  # Цвет в формате [R, G, B]

    # Определяем цвет точек на основе нормализованного значения units_cnt
    df['color'] = df['units_cnt'].apply(get_color)

    # Определяем начальное положение
    russia_view = pdk.ViewState(
        latitude=55.7558,  # широта
        longitude=37.6176,  # долгота
        zoom=3,  # уровень масштабирования
        min_zoom=2,
        max_zoom=15,
        pitch=0,  # угол наклона
    )

    # Определяем слой для отображения точек
    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["longitude", "latitude"],
        get_fill_color="color",  # Цвет зависит от столбца 'color'
        get_radius=100,  # Базовый радиус точек
        radius_scale=100,  # Масштабирование радиуса
        radius_min_pixels=3,  # Минимальный радиус (в пикселях)
        radius_max_pixels=10,  # Максимальный радиус (в пикселях)
        pickable=True,  # Включить возможность "подсвечивать" точки при наведении
        auto_highlight=True,  # Автоматическое выделение точек при наведении
    )

    # Создаем карту с темным стилем и добавляем слой с точками
    st.pydeck_chart(
        pdk.Deck(
            map_style="mapbox://styles/mapbox/dark-v9",  # темный стиль карты
            initial_view_state=russia_view,
            layers=[scatter_layer],  # Слой с точками
            tooltip={
                "html": (
                    "<b>Unit Name:</b> {unit_name}<br/>"
                    "<b>Units Count:</b> {units_cnt}<br/>"
                    "<b>Address:</b> {Address}<br/>"
                    "<b>City:</b> {CityName}<br/>"
                    "<b>Region:</b> {RegionName}<br/>"
                    "<b>Partner:</b> {Partner}"
                ),
                "style": {"color": "white"}
            },
        )
    )


geo_query = f""" select * from {geo_table}"""
with st.spinner("Downloading data..."):
    units_geo = read_sql(query=geo_query)
    st.header("Карта загруженности пиццерий тестами", divider=True)
    st.markdown(
        """
        ##### На карте - все пиццерии Додо в РФ. Градиентом отмечены пиццерии в зависимости от загрузки тестами. Пиццерии, отмеченные красным, участвуют в большем количестве тестов на текущий момент. Учитывай это при дизайне эксперимента.
        """
    )
    plot_map(units_geo)

st.divider()

st.header("Полезные ссылки: A/B тесты и где они обитают", divider=True)
st.write("""
1. [Наша методология](https://excalidraw.com/#room=b2a7611dc161be832ffb,zNzDpeivzbHNAX04ZV-1mw)
2. [Статья коллег из X5](https://habr.com/ru/companies/X5Tech/articles/466349/)
3. [Статья коллег из Озон](https://habr.com/ru/companies/ozontech/articles/712306/)
4. [Видео на тему 'Почему важно следовать дизайну эксперимента?'](https://www.youtube.com/watch?v=ly-pqx1P34k)
""")

st.divider()

st.header("FAQ", divider=True)
with st.expander("Хочу протестировать гипотезу, с чего начать?"):
    st.write('''
        В полезных ссылках ты можешь найти линк на нашу методологию - ознакомься с ней. Если остались вопросы, стучись в чат команды аналитиков.
        Но если коротко, то:
        
            - всегда начинаем с дизайна эксперимента, дизайн - наше все, 'ни шагу вправо, ни шагу влево'
            
            - дизайн ты можешь сделать самостоятельно в разделе Design <-- ссылка на раздел
            
            - как только аналитик аппрувнет твой дизайн - можешь смело договариваться с партнерами о вносимых изменениях
            
        Встретимся после теста!
    ''')

with st.expander("Мой эксперимент закончился, как забрать приз/деньги/вымпел/ручку/грамоту?"):
    st.write('''
        Поздравляем, что ты дошел до этапа оценки эксперимента, но сейчас аналитику нужно применить запрещенную вне Хогвартса магию и оценить тест ручками.
        Да, пока ручками, но мы работаем над этим.
        
        Не переживай, как только тест закончился, уведомление об этом уже осчастливило одного аналитика, и он в скором времени обновит страницу Estimation и результаты твоего теста появятся там.
        Если чувствуешь необходимость в интерпретации результатов - напиши в чат.
    ''')

with st.expander("Что-то у вас тут сломалось, не работает совсем"):
    st.write('''
        Печаль, пиши нам в ad_hoc_analytics - мы придем на третий день с Востока вместе с восходом солнца. Шутка, постараемся быстро все исправить.
    ''')
