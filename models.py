# Modelos de las tablas, traducción de als tablas de sql a python.

from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import date

class Usuarios(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    nombre_usuario: str = Field(nullable=False, unique=True)
    email: str = Field(nullable=False, unique=True)
    contraseña: str = Field(nullable=False)

    descripcion: str = Field(nullable=True)
    foto_perfil: str = Field(nullable=True)


class Eventos(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    id_remoto: str = Field(unique=True, nullable=True)
    nombre: str = Field(nullable=True)
    artista: str = Field(nullable=False)
    localizacion: str = Field(nullable=False)
    fecha: date = Field(nullable=False)
    ciudad: str = Field(nullable=False)

    image_Url: str = Field(nullable=True)


class Usuario_Eventos(SQLModel,table=True):
    id_usuario: int = Field(foreign_key="Usuarios.id",primary_key=True)
    id_evento: int = Field(foreign_key="Eventos.id" ,primary_key=True)

    estatus: str = Field(nullable=True)
    comentario: str = Field(nullable=True)


class Seguidos(SQLModel, table=True):
    id_seguidor: int = Field(foreign_key="Usuarios.id", primary_key=True)
    id_seguido: int = Field(foreign_key="Usuarios.id", primary_key=True)