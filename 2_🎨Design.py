import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dictionaries import CHANNELS_DICT, COUNTRIES_DICT, SOURCES_DICT, TARGETS_DICT, CATEGORIES_DICT
from design_flow import TestDesign, send_message_to_loop
from saver_for_design import write_data_to_cvm_ab_design

#Настройка состояний
if 'show_form_block' not in st.session_state:
    st.session_state['show_form_block'] = True

if 'show_matrix' not in st.session_state:
    st.session_state['show_matrix'] = False

if 'choose_final_params' not in st.session_state:
    st.session_state['choose_final_params'] = False

if 'hm' not in st.session_state:
    st.session_state['hm'] = None

if 'show_confirmation' not in st.session_state:
    st.session_state['show_confirmation'] = False

if 'confirmation_action' not in st.session_state:
    st.session_state['confirmation_action'] = None

def add_choose_final_params():
    st.session_state['choose_final_params'] = True

def reset_app():
    st.session_state['show_form_block'] = True
    st.session_state['show_matrix'] = False
    st.session_state['choose_final_params'] = False
    st.session_state['hm'] = None

if st.session_state['show_form_block']:
    st.set_page_config(page_title="", page_icon="🌍")
    st.sidebar.markdown("#### by CVM&Analytics team")


    server_hostname = st.secrets["databricks"]["server_hostname"]
    http_path = st.secrets["databricks"]["http_path"]
    databricks_token = st.secrets["databricks"]["access_token"]

    st.markdown("# A/B Design")
    st.subheader('1. Выбор параметров теста')

    # Инициализация переменной products
    products = None
    with st.form('matrix_params_form'):
        st.subheader('**Укажите параметры теста для расчета**')
        # Input widgets
        target_metric = st.selectbox('Целевая метрика', ['Выручка', 'Кол-во заказов', 'Маржа'])
        countries = st.multiselect('Страна', ['Россия', 'Казахстан'], ['Россия'])
        channels = st.multiselect('Канал', ['Доставка', 'Ресторан', 'Самовывоз'], ['Доставка', 'Ресторан', 'Самовывоз'])
        sources = st.multiselect('Источник заказа', ['МП', 'Касса', 'Сайт', 'Киоск', 'Все'], ['Все'])
        categories = st.multiselect('Категория продуктов', ['комбо', 'пицца', 'напитки', 'закуски', 'соусы', 'товары', 'десерты', 'кусочки'], ['комбо', 'пицца', 'напитки', 'закуски', 'соусы', 'десерты', 'кусочки'])

        st.write('Загрузите  CSV c продуктами')
        uploaded_file = st.file_uploader("Выберите файл с Id продуктов, если необходимо")
        if uploaded_file is not None:
            products = pd.read_csv(uploaded_file)
            products = list(products[list(products.columns)[0]].values)
            products = ", ".join([f"'{id}'" for id in products])

        submitted = st.form_submit_button('Подтвердить')


if submitted:
    st.session_state['show_matrix'] = False
    st.session_state['choose_final_params'] = False

    st.header('2. Расчет матрицы')
    st.markdown(':hourglass_flowing_sand: Происходит расчет матрицы. Это может занять пару минут.')

    test_params = {
        "target_metric": TARGETS_DICT[target_metric],
        "alpha": 0.05,
        "beta": 0.2,
        "start_period": str(datetime.now().date() - timedelta(days=30)),
        "end_period": str(datetime.now().date() - timedelta(days=1)),
    }

    if sources == ['Все']:
        sources = list(SOURCES_DICT.keys())

    query_params = {
        'country': TestDesign.mapping_values(countries, COUNTRIES_DICT),
        'channel': TestDesign.mapping_values(channels, CHANNELS_DICT),
        'source': TestDesign.mapping_values(sources, SOURCES_DICT),
        'category': TestDesign.mapping_values(categories, CATEGORIES_DICT)
    }
    # Если загрузили список продуктов, то добавляем условие в запрос
    if products:
        query_params['products_subq'] = f"and ord.ComboProductUUId in ({products})"
    else:
        query_params['products_subq'] = ""

    # Создаем экземпляр класса
    design = TestDesign(params_dict=test_params)
    orders_table = "delta.`abfss://deltalake@p0dbsbb0sa0dbrks.dfs.core.windows.net/data/gold/OrderCompositionExtended`"
    deps_table = "delta.`abfss://deltalake@p0dbsbb0sa0dbrks.dfs.core.windows.net/data/gold/DepartmentUnitsInfo`"

    query = f"""
        select ord.UnitUUId,  
            dep.Name,
          ord.SaleDate,
          sum(ord.ProductTotalPrice) as revenue,
          count(distinct ord.OrderUUId) as cnt_orders
    from {orders_table} ord
    inner join {deps_table} dep
          on ord.UnitUUId=dep.UUId
    where 1=1
    and ord.BusinessId='DodoPizza'
    and ord.CountryId_int=({query_params['country']})
    and ord.SaleDate>='{design.start_cuped_period}'
    and ord.SaleDate<'{design.end_period}'
    and ord.OrderType in ({query_params['channel']})
    and ord.OrderSource in ({query_params['source']})
    and ord.ComboProductCategoryId in ({query_params['category']})
    {query_params['products_subq']}
    group by ord.UnitUUId,  
            dep.name,
          ord.SaleDate
    """

    df_metrics_by_unit = TestDesign.read_sql(query=query,
                                            server_hostname=server_hostname,
                                             http_path=http_path,
                                             access_token=databricks_token)

    # Оставляем только данные по юнитам без пропусков
    df_metrics_by_unit['cnt_unique_dates'] = (df_metrics_by_unit
                                              .groupby(['UnitUUId'])['SaleDate']
                                              .transform('nunique')
                                              )
    df_metrics_by_unit = (df_metrics_by_unit
                          [df_metrics_by_unit['cnt_unique_dates']
                           == df_metrics_by_unit['cnt_unique_dates'].max()]
                          .drop(columns=['cnt_unique_dates'])
                          )

    df_metrics_by_unit['SaleDate'] = pd.to_datetime(df_metrics_by_unit['SaleDate'])
    df_metrics_by_unit[design.target_metric] = df_metrics_by_unit[design.target_metric].astype(float)
    df = df_metrics_by_unit[df_metrics_by_unit['SaleDate'] >= design.start_period].reset_index(drop=True)
    # Исторические данные для CUPED
    df_history = df_metrics_by_unit[df_metrics_by_unit['SaleDate'] < design.start_period].reset_index(drop=True)
    # Считаем CUPED метрику
    df_cuped = design.calculate_cuped_metric(df, df_history)
    # Считаем матрицу эффект для CUPED метрики
    df_sample_size = design.get_sample_size_matrix(design.get_sample_size_standart, df_cuped, is_cuped=True)
    df_matrix, hm = design.get_day_matrix(df_sample_size)

    # Сохраняем результаты в session_state
    st.session_state['hm'] = hm

    # Строим графики
    st.balloons()
    st.session_state['show_matrix'] = True

if st.session_state['show_matrix']:
    if st.session_state['hm'] is not None:
        st.altair_chart(st.session_state['hm'], use_container_width=True)
    st.button("Перейти к подтверждению параметров", on_click=add_choose_final_params)

if st.session_state['choose_final_params']:

    st.header('3. Введите финальные параметры для утверждения дизайна теста')
    with st.form('final_params_form'):
        st.subheader('**Укажите параметры теста для расчета**')
        # Input widgets
        responsible_name = st.text_input("Заказчик (Имя, Фамилия):")
        test_name = st.text_input("Название теста:")
        test_len = st.selectbox('Длина теста', [14,21,28,35,42,49,56])
        cnt_units = st.text_input("Кол-во пиццерий:")
        mde_lst = [round(x,3) for x in list(np.linspace(0.01, 0.10, 19))]
        mde = st.selectbox('Минимальный эффект', mde_lst)
        target_metric = st.selectbox('Целевая метрика', ['Выручка', 'Кол-во заказов', 'Маржа'])
        countries = st.multiselect('Страна', ['Россия', 'Казахстан'], ['Россия'])
        channels = st.multiselect('Канал', ['Доставка', 'Ресторан', 'Самовывоз'], ['Доставка', 'Ресторан', 'Самовывоз'])
        sources = st.multiselect('Источник заказа', ['МП', 'Касса', 'Сайт', 'Киоск', 'Все'], ['Все'])
        categories = st.multiselect('Категория продуктов', ['комбо', 'пицца', 'напитки', 'закуски', 'соусы', 'товары', 'десерты', 'кусочки'],
                                    ['комбо', 'пицца', 'напитки', 'закуски', 'соусы', 'десерты', 'кусочки'])

        st.write('Загрузите  CSV c продуктами')
        uploaded_file = st.file_uploader("Выберите файл с Id продуктов, если необходимо")
        if uploaded_file is not None:
            products = pd.read_csv(uploaded_file)
            products = list(products[list(products.columns)[0]].values)
            products = ", ".join([f"'{id}'" for id in products])

        hypo = st.text_input("Проверяемая гипотеза:")
        comment = st.text_input("Комментарий:")
        submitted = st.form_submit_button('Подтвердить финальные праметры и записать в таблицу')

    if submitted:
        design_params_dict = {
            "experiment_short_name": test_name,
            "target_metric": target_metric,
            "alpha": 0.05,
            "beta": 0.2,
            "mde": mde,
            "days_for_test": test_len,
            "hypothesis":hypo,
            "comment":comment
        }
        exp_id = write_data_to_cvm_ab_design(design_params_dict=design_params_dict, return_exp_id=True)


        message = f"Ура, работа!:pepe_party:\n"
        message += f"ID: {exp_id}\n"
        message+= f"Заказчик: {responsible_name}\n"
        message += f"Название теста: {test_name}\n"
        message += f"Страна: {countries}\n"
        message += f"Кол-во пиццерий в тесте: {test_len}\n"
        message += f"Длина теста: {test_len}\n"
        message += f"Целевая метрика: {target_metric}\n"
        message += f"Канал: {channels}\n"
        message += f"Гипотеза: {hypo}\n"
        message += f"Комментарий: {comment}\n"
        send_message_to_loop(message)
        st.markdown('Логируем дизайн теста и отправляем на подтверждение аналитикам')
        st.markdown('Данные успешно записаны!')


else:
    st.write('☝️ Выберите параметры и нажмите подтвердить!')




