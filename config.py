import pymysql
from pymysql.cursors import DictCursor

# Conexion a la base de datos MySQL alojada en Railway
DB_CONFIG = {
    "host": "altaria.proxy.rlwy.net",
    "user": "root",
    "password": "",
    "database": "mecanografia_db",
    "port": 31500,
    "cursorclass": DictCursor,
}


def get_connection():
    return pymysql.connect(**DB_CONFIG)
