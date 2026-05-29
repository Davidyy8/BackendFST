# Fichero de configuración de la base de datos.
from sqlmodel import create_engine, Session
import os

# base_url = 'mysql+pymysql://root:2305@localhost:3306/FST'
DATABASE_URL = os.getenv('DATABASE_URL', 'mysql+pymysql://root:2305@localhost:3306/FST')
connect_args = {}
if "localhost" not in DATABASE_URL:
    connect_args = {"ssl": {"ssl_mode": "REQUIRED"}}
    
engine  = create_engine(DATABASE_URL, connect_args=connect_args)

def get_session():
    with Session(engine) as session:
        yield session
