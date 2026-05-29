# Modelos de las tablas, traducción de als tablas de sql a python.

from typing import Optional, Text
from sqlmodel import Field, SQLModel, UniqueConstraint, Column, Text
from datetime import date

class Usuarios(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    nombre_usuario: str = Field(nullable=False, unique=True)
    email: str = Field(nullable=False, unique=True)
    contraseña: str = Field(sa_column=Column('contraseña', nullable=False))

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
    id_creador: Optional[int] = Field(default=None, foreign_key="usuarios.id")

# EL CANDADO: Evita duplicados de estos 3 campos juntos
    __table_args__ = (
        UniqueConstraint('artista', 'fecha', 'ciudad', name='_artista_fecha_sala_uc'),
    )

class Usuario_Eventos(SQLModel,table=True):
    id_usuario: int = Field(foreign_key="usuarios.id",primary_key=True)
    id_evento: int = Field(foreign_key="eventos.id" ,primary_key=True)

    estatus: str = Field(nullable=True)
    comentario: str = Field(nullable=True)


class Seguidos(SQLModel, table=True):
    id_seguidor: int = Field(foreign_key="usuarios.id", primary_key=True)
    id_seguido: int = Field(foreign_key="usuarios.id", primary_key=True)

from typing import List, Optional
from sqlmodel import Field, SQLModel, Relationship

# 1. Catálogo de géneros (ej: "Jazz", "Rock", "Blues")
class Generos(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(nullable=False, unique=True)

# 2. Tabla intermedia para los Eventos (Muchos a Muchos)
class Evento_Generos(SQLModel, table=True):
    id_evento: int = Field(foreign_key="eventos.id", primary_key=True)
    id_genero: int = Field(foreign_key="generos.id", primary_key=True)

# 3. Tabla intermedia para las Preferencias del Usuario (Muchos a Muchos)
class Usuario_Preferencias(SQLModel, table=True):
    id_usuario: int = Field(foreign_key="usuarios.id", primary_key=True)
    id_genero: int = Field(foreign_key="generos.id", primary_key=True)

class Subscription(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="usuarios.id")
    # Usamos Text para asegurar que quepa toda la cadena JSON (endpoint + keys)
    sub_json: str = Field(sa_column=Column(Text, nullable=False))