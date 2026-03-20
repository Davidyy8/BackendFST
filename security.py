# Fichero para controlar la contraseña
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

def hash_password(contraseña: str):
    return pwd_context.hash(contraseña)