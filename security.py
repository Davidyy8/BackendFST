import bcrypt

def hash_password(contraseña: str) -> str:
    # Convertimos la contraseña a bytes
    pwd_bytes = contraseña.encode('utf-8')
    # Generamos la "sal" (salt)
    salt = bcrypt.gensalt()
    # Generamos el hash
    hash_bytes = bcrypt.hashpw(pwd_bytes, salt)
    # Devolvemos el hash como texto (string) para guardarlo en la DB
    return hash_bytes.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Compara la contraseña plana con el hash de la DB
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )