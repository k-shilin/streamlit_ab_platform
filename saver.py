import pandas as pd
import numpy as np
import warnings
import hashlib
import pytz
from datetime import datetime
import streamlit as st
from databricks import sql

table_name_dict = {
    "main":"delta.`abfss://deltalake@p0dbscv0sa0dbrks.dfs.core.windows.net/data/ab/main`"
}


# Настройки для Pandas
warnings.filterwarnings("ignore")
pd.set_option("display.max_colwidth", 500)
pd.set_option("display.float_format", lambda x: "%.3f" % x)

# Схемы данных
table_schema_dict = dict(
    metrics=["experiment_id", "additional_metrics"],
    products=["experiment_id", "productuuid", "product_name"],
    conflicts=["experiment_id", "conflict_experiment_id", "conflict_metric"],
    units=["experiment_id", "unit_name", "unituuid", "unit_group"],
    main=[
        "experiment_id", "experiment_short_name", "design_date", "estimation_date", "target_metric", "alpha", "beta",
        "mde",
        "status", "start_of_test", "days_for_knn", "days_for_validation", "days_for_test", "n_iter_bootstrap",
        "ci_left_bound",
        "ci_right_bound", "ci_length", "fact_effect", "effect_left_bound", "effect_right_bound", "theta",
        "var_decrease_in_design",
        "var_decrease_in_test", "stat_sagnificant", "p_value", "hypothesis", "comment", "load_datetime",
        "update_datetime"
    ]
)


# Функция подключения к Databricks
def get_databricks_connection():
    connection = sql.connect(
        server_hostname=st.secrets["databricks"]["server_hostname"],
        http_path=st.secrets["databricks"]["http_path"],
        access_token=st.secrets["databricks"]["access_token"]
    )
    return connection


# Получение списка experiment_id из таблицы
def check_id_table(connection, table_name):
    query = f"SELECT experiment_id FROM {table_name_dict[table_name]}"
    with connection.cursor() as cursor:
        cursor.execute(query)
        result = cursor.fetchall()
        ids = [row[0] for row in result]
    return ids


# Вставка данных в таблицу
import pandas as pd
import numpy as np
from databricks import sql
from datetime import datetime
import pytz

# Словарь схем таблиц
table_schema_dict = dict(
    metrics=[
        {"name": "experiment_id", "type": "string"},
        {"name": "additional_metrics", "type": "string"},
    ],
    main=[
        {"name": "experiment_id", "type": "string"},
        {"name": "experiment_short_name", "type": "string"},
        {"name": "design_date", "type": "string"},
        {"name": "alpha", "type": "float"},
        # Добавьте остальные поля...
    ]
)


def get_databricks_connection():
    connection = sql.connect(
        server_hostname="your-server-hostname",
        http_path="your-http-path",
        access_token="your-access-token"
    )
    return connection


def check_id_table(connection, table_name):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT experiment_id FROM {table_name}")
        rows = cursor.fetchall()
    return [row[0] for row in rows]


def insert_into_cvm_ab(*, table_name: str, params_dict: dict) -> None:
    # Создаем подключение к базе данных через Databricks SQL
    connection = get_databricks_connection()

    # Получаем текущую дату и время в московском часовом поясе
    moscow_tz = pytz.timezone("Europe/Moscow")
    time_in_msc = datetime.now(moscow_tz)

    # Получаем схему таблицы
    schema = table_schema_dict.get(table_name)

    if schema is None:
        raise ValueError(f"Schema for table '{table_name}' not found.")

    # Проверка, является ли схема списком
    if isinstance(schema, list):
        # Если схема — это список, мы создаем словарь с None для каждого поля
        schema_dict = {field['name']: None for field in schema}
    else:
        raise TypeError("Schema should be a list of fields.")

    # Обновляем словарь значениями из params_dict
    schema_dict.update(params_dict)

    if table_name == "main":
        # Добавляем дату загрузки для таблицы main
        schema_dict["load_datetime"] = [time_in_msc.strftime("%Y-%m-%d %H:%M:%S")]
        df = pd.DataFrame(schema_dict)
    else:
        # Создаем DataFrame с правильной длиной для других таблиц
        max_length = max(len(v) if isinstance(v, list) else 1 for v in schema_dict.values())
        df = pd.DataFrame({
            k: v * max_length if isinstance(v, list) and len(v) < max_length else v
            for k, v in schema_dict.items()
        })

    # Замена NaN на None для корректной вставки в базу
    df = df.where(pd.notnull(df), None)

    # Проверка на существование экспериментального ID в таблице
    ids = check_id_table(connection, table_name)
    if params_dict["experiment_id"][0] in ids:
        raise ValueError(
            f"Experiment with id '{params_dict['experiment_id'][0]}' already exists in {table_name}. You can only update existing experiments.")

    # Генерация SQL-запроса для вставки данных
    with connection.cursor() as cursor:
        for index, row in df.iterrows():
            columns = ', '.join(row.index)

            # Обработка значений, чтобы None превращался в NULL
            values = ', '.join(
                [f"'{val}'" if isinstance(val, str) else 'NULL' if val is None else str(val) for val in row.values]
            )

            query = f"INSERT INTO {table_name} ({columns}) VALUES ({values})"

            # Логирование запроса для отладки (если нужно)
            print(query)

            cursor.execute(query)


# Удаление данных из таблицы
def delete_from_cvm_ab(*, table_name: str, experiment_id: str) -> None:
    connection = get_databricks_connection()

    ids = check_id_table(connection, table_name)
    if experiment_id not in ids:
        raise ValueError(f"Experiment with id '{experiment_id}' does not exist in {table_name}")

    with connection.cursor() as cursor:
        query = f"DELETE FROM {table_name_dict[table_name]} WHERE experiment_id = '{experiment_id}'"
        cursor.execute(query)


# Обновление данных в таблице
def update_cvm_ab(*, table_name: str, experiment_id: str, column_name: str, new_value: str) -> None:
    connection = get_databricks_connection()

    moscow_tz = pytz.timezone("Europe/Moscow")
    time_in_msc = datetime.now(moscow_tz)

    ids = check_id_table(connection, table_name)
    if experiment_id not in ids:
        raise ValueError(
            f"Experiment with id '{experiment_id}' does not exist in {table_name}. You should create the experiment first.")

    with connection.cursor() as cursor:
        if table_name == "main":
            query = f"""
            UPDATE {table_name_dict[table_name]}
            SET {column_name} = '{new_value}', update_datetime = '{time_in_msc.strftime('%Y-%m-%d %H:%M:%S')}'
            WHERE experiment_id = '{experiment_id}'
            """
        else:
            query = f"""
            UPDATE {table_name_dict[table_name]}
            SET {column_name} = '{new_value}'
            WHERE experiment_id = '{experiment_id}'
            """
        cursor.execute(query)


# Генерация уникального experiment_id
def get_exp_id(*, exp_short_name: str) -> str:
    hash_line = exp_short_name + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return hashlib.md5(hash_line.encode()).hexdigest().upper()


# Функция записи данных
def write_data_to_cvm_ab(*, design_params_dict: dict) -> None:
    design_params_dict["experiment_id"] = [get_exp_id(exp_short_name=design_params_dict["experiment_short_name"])]
    design_params_dict["design_date"] = [str(datetime.now())[:10]]

    tables = ["main", "metrics", "products", "conflicts", "units"]
    for table in tables:
        print(f"Start log data in {table}")
        insert_into_cvm_ab(table_name=table, params_dict=design_params_dict)


# Функция записи данных для этапа дизайна
def write_data_to_cvm_ab_design(*, design_params_dict: dict) -> None:
    design_params_dict["experiment_id"] = [get_exp_id(exp_short_name=design_params_dict["experiment_short_name"])]
    design_params_dict["design_date"] = [str(datetime.now())[:10]]
    design_params_dict["status"] = ["design not approved"]

    tables = ["main"]
    for table in tables:
        print(f"Start log data in {table}")
        insert_into_cvm_ab(table_name=table, params_dict=design_params_dict)
