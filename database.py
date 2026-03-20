# Fichero de configuración de la base de datos.
from sqlmodel import create_engine, Session

base_url = 'mysql+pymysql://david:@localhost:3306/FST'

engine  = create_engine(base_url, echo=True)

def get_session():
    with Session(engine) as session:
        yield session
