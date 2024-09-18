import streamlit as st
import pandas as pd
import random
import altair as alt

from helper import read_sql

st.title("Estimation 🔍")
st.markdown(
"""
##### Здесь собрана информация о тестах, которые уже оценены аналитиками или ожидают своей оценки
"""
)
st.sidebar.markdown("#### by CVM&Analytics team")
st.divider()
main_table = "delta.`abfss://deltalake@p0dbscv0sa0dbrks.dfs.core.windows.net/data/ab/main`"
st.header("Эксперименты, ожидающие оценки", divider=True)
query_for_estimation = f"""
    select
        experiment_short_name,
        target_metric,
        hypothesis,
        status,
        fact_effect,
        p_value,
        stat_sagnificant
    from {main_table}
    where status = 'design not approved'
"""

with st.spinner("Downloading data..."):
    df_metrics_by_unit = read_sql(query=query_for_estimation)
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
            "status": "Статус эксперимента",
            "fact_effect": "Эффект, %",
            "p_value": "P-value",
            "stat_sagnificant": "Статистическая значимость"
        },
        hide_index=True,
    )

st.divider()

st.header("Эксперименты, закончившиеся в последний месяц и прошедшие оценку", divider=True)

query_with_estimation = f"""
    select
        experiment_short_name,
        target_metric,
        hypothesis,
        status,
        fact_effect,
        p_value,
        stat_sagnificant
    from {main_table}
    where status = 'in progress'
"""

with st.spinner("Downloading data..."):
    df_metrics_by_unit = read_sql(query=query_with_estimation)
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
            "status": "Статус эксперимента",
            "fact_effect": "Эффект, %",
            "p_value": "P-value",
            "stat_sagnificant": "Статистическая значимость"
        },
        hide_index=True,
    )
    
st.divider()

st.header("Аналитика эксперимента", divider=True)


dynamic_table = "delta.`abfss://deltalake@p0dbscv0sa0dbrks.dfs.core.windows.net/data/ab/dynamic_example`"
query_for_data = f"select * from {dynamic_table}"
query_for_exp = f"""
    select
        experiment_short_name,
        target_metric,
        hypothesis,
        status,
        start_of_test,
        days_for_test,
        ci_left_bound,
        ci_right_bound,
        ci_length,
        fact_effect,
        p_value,
        var_decrease_in_test,
        stat_sagnificant,
        experiment_id
    from {main_table}
    where status = 'finished with estimation'
"""

with st.spinner("Downloading data..."):
    df_metrics_by_unit = read_sql(query=query_for_data)
    #df_metrics_by_unit.to_csv(r"C:\Users\repin\Desktop\GitHub\dodo\streamlit-dev\dynamic.csv", index=False)
    df_metrics_by_unit['SaleDate'] = pd.to_datetime(df_metrics_by_unit['SaleDate'])

    input = st.text_input("Идентификатор эксперимента", "D613748ED532A03B6CF1014A9ECFC282")
    st.write("Выбранный идентификатор:", input)
    
    # Создаем линейный график с выделением периода
    line_chart = alt.Chart(df_metrics_by_unit).mark_line().encode(
            x='SaleDate:T',  # Ось X - дата
            y='revenue:Q',  # Ось Y - доход
            color='period:N',  # Цвет выделения в зависимости от периода
            strokeDash='group:N'  # Различаем группы (контроль и тест) штриховкой линии
        ).properties(
            title='Динамика доходов по периодам и группам'
        )
    st.altair_chart(line_chart, use_container_width=True, theme=None,)

    df_metrics_by_unit = read_sql(query=query_for_exp).T
    st.dataframe(
        df_metrics_by_unit,
        column_config={
            "experiment_short_name": "Эксперимент",
            "target_metric": "Целевая метрика",
            "hypothesis": "Гипотеза",
            "status": "Статус эксперимента",
            "start_of_test": "Начало эксперимента",
            "days_for_test": "Количество дней в эксперименте",
            "ci_left_bound": "Левая граница ДИ",
            "ci_right_bound": "Правая граница ДИ",
            "ci_length": "Длина ДИ",
            "fact_effect": "Эффект, %",
            "p_value": "P-value",
            "stat_sagnificant": "Статистическая значимость",
            "var_decrease_in_test": "Снижение дисперсии на тесте",
            "experiment_id": "Идентификатор эксперимента"
        },
        hide_index=False,
        use_container_width=True
    )
    st.button("Обновить")

