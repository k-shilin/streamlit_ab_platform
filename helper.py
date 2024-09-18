import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import matplotlib.pyplot as plt
from databricks import sql
import streamlit as st

server_hostname = st.secrets["databricks"]["server_hostname"]
http_path = st.secrets["databricks"]["http_path"]
databricks_token = st.secrets["databricks"]["access_token"]

#@st.cache_data
def read_sql(query: str) -> pd.DataFrame:

    # Создание подключения
    connection = sql.connect(
        server_hostname=server_hostname,
        http_path=http_path,
        access_token=databricks_token
    )

    try:
        # Выполнение запроса
        cursor = connection.cursor()
        cursor.execute(query)

        # Получение данных и имен столбцов
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        # Преобразование результата в DataFrame
        df = pd.DataFrame.from_records(rows, columns=columns)

    finally:
        # Закрытие курсора и соединения
        cursor.close()
        connection.close()

    return df
