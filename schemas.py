# Recibe y envia mensajes de la api
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date


class UsuarioCrear(BaseModel):
    nombre_usuario: str
    email: EmailStr
    contraseña: str
    descripcion: Optional[str] = None

class UsuarioUpdate(BaseModel):
    nombre_usuario: Optional[str] = None
    descripcion: Optional[str] = None
    foto_perfil: Optional[str] = None


class EventoCrear(BaseModel):
    nombre: str
    artista: str
    localizacion: str
    fecha: date
    ciudad: str
    image_Url: Optional[str]

class EventoUpdate(BaseModel):
    nombre: Optional[str] = None
    artista: Optional[str] = None
    localizacion: Optional[str] = None
    fecha: Optional[date] = None
    ciudad: Optional[str] = None
    image_Url: Optional[str] = None

class EventoUsiarioCrear(BaseModel):
    id_usuario: int
    id_evento: int
    estatus: Optional[str]
    comentario: Optional[str]