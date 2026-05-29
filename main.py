# Fichero principal de la app.
# Ativar el venv:
# venv\Scripts\activate
# uvicorn main:app --reload 


import os
from unittest import result

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from sqlmodel import Session, delete, func, select, desc
from database import engine, get_session
from models import Usuarios, Usuario_Eventos, Eventos, Seguidos, Generos, Evento_Generos, Usuario_Preferencias, Subscription
from schemas import UsuarioCrear, UsuarioUpdate, EventoCrear, EventoUpdate, EventoUsiarioCrear, LoginSchema
from security import hash_password
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from datetime import datetime, timedelta, timezone
from fastapi.middleware.cors import CORSMiddleware
from security import verify_password
import requests as request
import cloudinary
import cloudinary.uploader
import json
from pywebpush import WebPushException, webpush
import config 
import secrets
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType



from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

# Configuración de la conexión con Google
conf = ConnectionConfig(
    MAIL_USERNAME="davidcorreoard@gmail.com",
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM="davidcorreoard@gmail.com",
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_FROM_NAME="FST - Festival Show Tracker",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

CLAVE_SECRETA = 'fstAPLICACION2026marzo23'

app = FastAPI(title='FST Festival Show Tracker')

origins = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
    "https://backendfst-3trg.onrender.com",
    "front-end-fst.vercel.app"
]

# 2. Añade el middleware a la aplicación
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # Permite Angular
    allow_credentials=True,
    allow_methods=["*"],              # Permite GET, POST, DELETE, etc.
    allow_headers=["*"],              # Permite enviar el Token y otros headers
)

cloudinary.config(
    cloud_name='drcves0eu',
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)


def enviar_notificacion_fst(user_id_receptor: int, titulo: str, cuerpo: str, session, url_destino: str = "/"):
    print(f"\n--- INICIO ENVÍO PUSH FST ---")
    
    # 1. Buscamos la suscripción del usuario receptor usando SQLModel (select)
    sub_db = session.exec(select(Subscription).where(Subscription.user_id == user_id_receptor)).first()
    
    if not sub_db:
        print(f"❌ ABORTO: El usuario {user_id_receptor} no tiene suscripción activa.")
        return False

    try:
        # 2. Preparamos el payload (Estructura estándar)
        payload_dict = {
            "notification": {
                "title": titulo,
                "body": cuerpo,
                "icon": "/assets/icons/icon-192x192.png",
                "vibrate": [100, 50, 100],
                "data": { "url": url_destino }
            }
        }
        payload = json.dumps(payload_dict)
        
        # 3. Extraemos y enviamos
        sub_info = json.loads(sub_db.sub_json)
        
        webpush(
            subscription_info=sub_info,
            data=payload,
            vapid_private_key=config.VAPID_PRIVATE_KEY,
            vapid_claims=config.VAPID_CLAIMS
        )
        print(f"🚀 ¡EXITO! Notificación enviada al usuario {user_id_receptor}.")
        return True
        
    except Exception as e:
        print(f"❌ Error al enviar push: {e}")
        return False



@app.get('/')
def root():
    return {'menssage' : 'Bienvenido a la api de FST'}

TOKENS_RECUPERACION = {}
@app.post("/usuarios/recuperar-password/solicitar")
async def solicitar_recuperacion(datos: dict, session: Session = Depends(get_session)):
    email = datos.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="El email es obligatorio")
        
    user = session.exec(select(Usuarios).where(Usuarios.email == email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Este correo electrónico no está registrado")

    token = secrets.token_urlsafe(32)
    TOKENS_RECUPERACION[token] = email
    
    enlace_restablecer = f"http://localhost:4200/restablecer-password/{token}"
    
    # CUERPO DEL MENSAJE EN HTML
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2 style="color: #0E2967;">Recuperación de contraseña - FST</h2>
            <p>Hola, <strong>{user.nombre_usuario}</strong>.</p>
            <p>Hemos recibido una solicitud para restablecer la contraseña de tu cuenta en Festival Show Tracker.</p>
            <p>Para continuar, haz clic en el siguiente botón (este enlace es de un solo uso):</p>
            <p style="margin: 25px 0;">
                <a href="{enlace_restablecer}" 
                   style="background-color: #0E2967; color: white; padding: 12px 25px; text-decoration: none; border-radius: 25px; font-weight: bold; display: inline-block;">
                   Restablecer Contraseña
                </a>
            </p>
            <p style="font-size: 0.85rem; color: #666;">Si tú no has solicitado este cambio, puedes ignorar este correo de forma segura.</p>
        </body>
    </html>
    """

    # Construimos el esquema del correo
    message = MessageSchema(
        subject="Restablecer tu contraseña en FST",
        recipients=[email],  # Correo del usuario que lo solicita
        body=html_content,
        subtype=MessageType.html
    )

    try:
        fm = FastMail(conf)
        await fm.send_message(message)  # Se envía el correo real en segundo plano
        return {"message": "Enlace de recuperación enviado directamente a tu bandeja de entrada."}
    except Exception as e:
        print(f"Error enviando correo: {e}")
        raise HTTPException(status_code=500, detail="No se pudo enviar el correo de recuperación")


@app.post("/usuarios/recuperar-password/confirmar/{token}")
def confirmar_recuperacion(token: str, datos: dict, session: Session = Depends(get_session)):
    """
    Paso 2: El frontend envía el token de la URL junto con la nueva contraseña.
    Validamos el token, encriptamos la nueva contraseña y actualizamos en MySQL.
    """
    nueva_password = datos.get("password")
    if not nueva_password:
        raise HTTPException(status_code=400, detail="La nueva contraseña es obligatoria")
        
    # Comprobamos si el token existe en la memoria temporal
    email = TOKENS_RECUPERACION.get(token)
    if not email:
        raise HTTPException(status_code=400, detail="El enlace de recuperación es inválido o ha expirado")
        
    # Buscamos al usuario dueño de ese email para cambiarle la contraseña
    user = session.exec(select(Usuarios).where(Usuarios.email == email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    # Encriptamos la nueva contraseña usando tu función hash_password
    user.contraseña = hash_password(nueva_password)
    
    # Guardamos los cambios en la base de datos
    session.add(user)
    session.commit()
    
    # Eliminamos el token de la memoria para que no se pueda reutilizar por seguridad
    del TOKENS_RECUPERACION[token]
    
    return {"message": "Contraseña restablecida con éxito. Ya puedes iniciar sesión."}


@app.post('/upload-imagen')
async def upload_image(file: UploadFile = File(...)):
    try:
        # Subir la imagen a Cloudinary
        result = cloudinary.uploader.upload(file.file)

        # devolvemos lo que nos da cloudinary
        return { 'image_url': result['secure_url'] }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/login")
def login(datos: LoginSchema, session: Session = Depends(get_session)):
    # 1. Buscar usuario
    # Usamos datos.email porque coincide con tu LoginSchema
    user = session.exec(select(Usuarios).where(Usuarios.email == datos.email)).first()

    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    if not verify_password(datos.password, user.contraseña): 
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    # 3. Crear Token
    token = jwt.encode(
        {"id": user.id, "exp": datetime.now(timezone.utc) + timedelta(hours=24)}, 
        CLAVE_SECRETA, 
        algorithm="HS256"
    )
    
    return {"token": token, "id": user.id}


@app.get('/usuarios/buscar')
def buscarUsuarios(q: str, session: Session = Depends(get_session)):
    # Buscamos al usuario cuyo nombre contenga q
    statement = select(Usuarios).where(Usuarios.nombre_usuario.contains(q))
    resultados = session.exec(statement).all()
    return resultados

@app.get('/usuarios')
def listar_usuarios(session: Session = Depends(get_session)):
    # 1. Consulta con LEFT JOIN para obtener usuarios y sus géneros (si tienen)
    # Importante: Asegúrate de tener los modelos de Usuario_Preferencias y Generos importados
    statement = (
        select(Usuarios, Generos.nombre)
        .join(Usuario_Preferencias, Usuarios.id == Usuario_Preferencias.id_usuario, isouter=True)
        .join(Generos, Usuario_Preferencias.id_genero == Generos.id, isouter=True)
    )
    
    resultados = session.exec(statement).all()

    # 2. Transformación manual a tu estilo
    usuarios_dict = {}
    
    for usuario, genero_nombre in resultados:
        # Si es la primera vez que vemos a este usuario, creamos su entrada
        if usuario.id not in usuarios_dict:
            usuarios_dict[usuario.id] = {
                'id': usuario.id,
                'nombre_usuario': usuario.nombre_usuario,
                'email': usuario.email,
                'descripcion': usuario.descripcion,
                'foto_perfil': usuario.foto_perfil,
                'generos_favoritos': [] # Iniciamos lista vacía
            }
        
        # Si el usuario tiene un género, lo añadimos a su lista
        if genero_nombre:
            usuarios_dict[usuario.id]['generos_favoritos'].append(genero_nombre)

    # Devolvemos los valores del diccionario como lista
    return list(usuarios_dict.values())

@app.get('/usuarios/{usuario_id}')
def getUsuariobyId(usuario_id: int, session: Session = Depends(get_session)):
    usuario = session.get(Usuarios, usuario_id)
    return usuario


@app.post('/usuarios')
def crear_usuario(datos: UsuarioCrear, session: Session = Depends(get_session)):
    # Encriptar la contraseña
    hashed_pwd = hash_password(datos.password)

    nuevo_usuario = Usuarios(
        nombre_usuario=datos.nombre_usuario,
        email=datos.email,
        contraseña=hashed_pwd,
        descripcion=datos.descripcion
    )

    try:
        # Lo guardamos en mysql
        session.add(nuevo_usuario)
        session.commit()
        session.refresh(nuevo_usuario)
        return {'message' : 'Usuario creado con exito', 'id' : nuevo_usuario.id}
    except Exception as e:
        print(e)
        session.rollback()
        raise HTTPException(status_code=400, detail='El usuario o email ya existen')


# Usaremos patch por que put reemplaza todos los datos mientras que patch solo cambia los valores que le pasemos
@app.patch('/usuarios/{usuario_id}')
def actualizar_usuario(
    usuario_id: int,
    datos_nuevos: UsuarioUpdate,
    session: Session = Depends(get_session)
):
    # Buscamos el usuario en la base de datos
    usuario_db = session.get(Usuarios, usuario_id)
    if not usuario_db:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')
    
    # Actualizamos los datos
    datos_dic = datos_nuevos.model_dump(exclude_unset=True)

    for key, value in datos_dic.items():
        setattr(usuario_db, key, value)
    try:
        # Guardar los cambios 
        session.add(usuario_db)
        session.commit()
        session.refresh(usuario_db)

        return {'message' : 'Perfil actualizado', 'usuario' : usuario_db}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail='el nombre ya esta en uso elige otro')


@app.delete('/usuarios/{usuario_id}')
def eliminar_usuario(usuario_id: int, session: Session = Depends(get_session)):
    # Buscamos el usuario 
    usuario_db = session.get(Usuarios, usuario_id)
    if not usuario_db:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')
    
    # Eliminamos al usuarios
    session.delete(usuario_db)
    session.commit()

    # Lanzamos un mensaje
    return {'message' : 'Usuario eliminado con exito'}


@app.get('/eventos/buscar')
def buscar_conciertos_general(q: str, session: Session = Depends(get_session)):
    """
    Recibe la búsqueda del servicio de Angular (?q=infierno)
    y filtra los conciertos por nombre o artista en MySQL.
    """
    if not q:
        return []
        
    statement = select(Eventos).where(
        (Eventos.nombre.ilike(f"%{q}%")) | (Eventos.artista.ilike(f"%{q}%"))
    )
    
    return session.exec(statement).all()

@app.get('/eventos')
def listar_eventos(session: Session = Depends(get_session)):
    # 1. Consulta SQL ajustada
    statement = (
        select(Eventos, Generos.nombre)
        .select_from(Eventos)
        .join(Evento_Generos, Eventos.id == Evento_Generos.id_evento, isouter=True)
        .join(Generos, Evento_Generos.id_genero == Generos.id, isouter=True)
    )
    resultados = session.exec(statement).all()
    
    # 2. Diccionario para agrupar géneros por ID de evento
    eventos_dict = {}
    
    for evento, nombre_genero in resultados:
        if evento.id not in eventos_dict:
            # Crear entrada inicial
            eventos_dict[evento.id] = {
                'id': evento.id,
                'id_remoto': evento.id_remoto,
                'nombre': evento.nombre,
                'artista': evento.artista,
                'localizacion': evento.localizacion,
                'fecha': evento.fecha,
                'ciudad': evento.ciudad,
                'image_Url': evento.image_Url,
                'generos': []  # Lista preparada para Angular
            }
        
        # Si tiene género, lo añadimos a la lista (evitando duplicados si fuera necesario)
        if nombre_genero and nombre_genero not in eventos_dict[evento.id]['generos']:
            eventos_dict[evento.id]['generos'].append(nombre_genero)

    # 3. Convertir de vuelta a lista para Angular
    return list(eventos_dict.values())

@app.get('/eventos/{evento_id}')
def getEventoById(evento_id: int, session: Session = Depends(get_session)):
    evento = session.exec(select(Eventos).where(Eventos.id == evento_id)).first()
    return evento


@app.post('/eventos/{usuario_id}')
def crear_evento(datos: EventoCrear, usuario_id: int , session: Session = Depends(get_session)):
    
    nuevo_evento = Eventos(
        nombre=datos.nombre,
        artista=datos.artista,
        localizacion=datos.localizacion,
        fecha=datos.fecha, 
        ciudad=datos.ciudad,
        image_Url=datos.image_Url,
        id_creador=usuario_id
    )

    try: 
        # Lo guardamos en sql
        session.add(nuevo_evento)
        session.commit()
        session.refresh(nuevo_evento)
        return {'message' : 'Evento creado con exito', 'id' : nuevo_evento.id}
    except Exception as e:
        session.rollback()
        print(f"ERROR REAL DE LA DB: {e}")
        raise HTTPException(status_code=400, detail='El evento ya existe')


@app.patch('/eventos/{evento_id}')
def actualizar_evento(
    evento_id: int,
    datos_nuevos: EventoUpdate,
    session: Session = Depends(get_session)
):
    # Buscamos el evento en la base de datos
    evento_db = session.get(Eventos, evento_id)
    if not evento_db:
        raise HTTPException(status_code=404, detail='Evento no encontrado')
    
    # Actuaizamos los datos
    datos_dic = datos_nuevos.model_dump(exclude_unset=True)

    for key, value in datos_dic.items():
        setattr(evento_db, key, value)
    
    # Guardamos los cambios
    session.add(evento_db)
    session.commit()
    session.refresh(evento_db)

    return {'message' : 'Perfil actualizado', 'usuario' : evento_db}

@app.delete('/eventos/{evento_id}')
def eliminar_evento(evento_id: int, session: Session = Depends(get_session)):
    evento_db = session.get(Eventos,evento_id)
    if not evento_db:
        raise HTTPException(status_code=404, detail='Evento no encontrado')
    # Eliminamos el evento
    session.delete(evento_db)
    session.commit()

    # Lanzamos un mensaje
    return {'message' : 'Evento eliminado con exito'}

@app.get('/eventos/usuario/{usuario_id}')
def listar_eventos_por_creador(usuario_id: int, session: Session = Depends(get_session)):
    statement = select(Eventos).where(Eventos.id_creador == usuario_id)

    try:
        eventos = session.exec(statement).all()
        return eventos

    except Exception as e:
        raise HTTPException(status_code=500, detail='Error al obtener los evntos')


@app.post('/evento_usuario')
def asistirEvento(usuario_id: int, evento_id: int, status: str, comentario: str = None ,session: Session = Depends(get_session)):
    # Comprobar si hay relacion 
    statement = select(Usuario_Eventos).where(
        Usuario_Eventos.id_usuario == usuario_id,
        Usuario_Eventos.id_evento == evento_id
    )

    existente = session.exec(statement).first()

    if existente:
        raise HTTPException(status_code=400, detail='Este usuario ya tiene este evento en su libreria')
    

    # Crear la nueva relacion en la tabla
    nueva_relacion = Usuario_Eventos(
        id_usuario=usuario_id,
        id_evento=evento_id,
        estatus=status,
        comentario=comentario
    )
    
    try:
        session.add(nueva_relacion)
        session.commit()
        session.refresh(nueva_relacion)
        return {'message' : 'relacion guardada con exito', 'datos' : nueva_relacion}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail='Error al guardar la relacion')


@app.delete('/evento_usuario')
def eliminarAsistencia(usuario_id: int, evento_id: int, session: Session = Depends(get_session)):
    # Comprobar si existe
    statement = select(Usuario_Eventos).where(
        Usuario_Eventos.id_usuario == usuario_id,
        Usuario_Eventos.id_evento == evento_id
    )
    existente = session.exec(statement).first()
    if not existente:
        raise HTTPException(status_code=400, detail='Esta relacion no existe')
    
    # Eliminamos el evento
    session.delete(existente)
    session.commit()
    return {'message' : 'Relacion eliminada con exito'}


@app.get('/usuarios/{usuario_id}/eventos')
def obtener_usuarios_eventos(usuario_id: int, session: Session = Depends(get_session)):
    try:
        # Definimos la consulta con JOIN explícito para evitar ambigüedades
        statement = (
            select(Eventos, Usuario_Eventos.estatus, Usuario_Eventos.comentario)
            .select_from(Eventos) # <-- Indicamos que partimos de Eventos
            .join(Usuario_Eventos, Eventos.id == Usuario_Eventos.id_evento)
            .where(Usuario_Eventos.id_usuario == usuario_id)
        )

        resultados = session.exec(statement).all()

        listado = []
        for evento, estatus, comentario in resultados:
            listado.append({
                'id': evento.id,
                'id_remoto': evento.id_remoto,
                'nombre': evento.nombre,
                'artista': evento.artista,
                'fecha': evento.fecha,
                'ciudad': evento.ciudad,
                'image_Url': evento.image_Url,
                'estatus': estatus,
                'comentario': comentario
            })
        return listado

    except Exception as e:
        print(f"DEBUG ERROR EN ENDPOINT: {e}")
        session.rollback() # Limpiamos la transacción tras el error
        raise HTTPException(status_code=500, detail=f"Error al obtener eventos: {str(e)}")

@app.get('/usuarios/perfil-publico/{id_perfil}')
def obtener_perfil_publico(id_perfil: int, id_usuario_logueado: int, session: Session = Depends(get_session)):
    # Buscamos al usuario del perfil
    usuario = session.get(Usuarios, id_perfil)
    if not usuario:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')
    # Conta a cuantos sigue
    siguiendo_count = session.exec(select(func.count(Seguidos.id_seguido)).where(Seguidos.id_seguidor == id_perfil)).one()

    # Contar cuantos le siguen
    seguidores_count = session.exec(select(func.count(Seguidos.id_seguidor)).where(Seguidos.id_seguido == id_perfil)).one()

    check_seguimiento = session.exec(select(Seguidos).where(Seguidos.id_seguidor == id_usuario_logueado, Seguidos.id_seguido == id_perfil)).first()
    return {
            "id": usuario.id,
            "nombre_usuario": usuario.nombre_usuario,
            "foto_perfil": usuario.foto_perfil,
            "descripcion": usuario.descripcion,
            "siguiendo_count": siguiendo_count,
            "seguidores_count": seguidores_count,
            "ya_le_sigo": True if check_seguimiento else False
        }

@app.post('/usuarios/seguir/{id_a_seguir}')
def seguir_usuario(id_a_seguir: int, id_seguidorFront: int, session: Session = Depends(get_session)):

    # 1. Validaciones existentes...
    if id_a_seguir == id_seguidorFront:
        raise HTTPException(status_code=400, detail='No puedes seguirte a ti mismo')
    
    usuario_a_seguir = session.get(Usuarios, id_a_seguir)
    if not usuario_a_seguir:
        raise HTTPException(status_code=404, detail='El usuario no existe')
    
    statement = select(Seguidos).where(
        Seguidos.id_seguidor == id_seguidorFront,
        Seguidos.id_seguido == id_a_seguir
    )
    ya_sigue = session.exec(statement).first()
    if ya_sigue:
        raise HTTPException(status_code=400, detail='Ya sigues a este usuario')
    
    # 2. Obtener nombre del seguidor para el mensaje
    seguidor = session.get(Usuarios, id_seguidorFront)
    nombre_seguidor = seguidor.nombre_usuario if seguidor else "Alguien"

    # 3. Crear la relación
    nuevo_seguido = Seguidos(id_seguidor=id_seguidorFront, id_seguido=id_a_seguir)
    session.add(nuevo_seguido)
    session.commit()

    # 4. DISPARAR NOTIFICACIÓN (AQUÍ ESTÁ LA INTEGRACIÓN)
    enviar_notificacion_fst(
        user_id_receptor=id_a_seguir,
        titulo="¡Nuevo seguidor!",
        cuerpo=f"{nombre_seguidor} ha empezado a seguirte.",
        session=session,
        url_destino=f"/perfil/{id_seguidorFront}" # abre el perfil de quien te sigue
    )

    return {'message' : f'Ahora sigues a {usuario_a_seguir.nombre_usuario}'}

@app.delete('/usuarios/unfollow/{id_seguido}')
def dejar_de_seguir(id_seguido: int, id_seguidorFront: int, session: Session = Depends(get_session)):
    
    # Comprobar si existe relacion
    statement = select(Seguidos).where(
        Seguidos.id_seguidor == id_seguidorFront,
        Seguidos.id_seguido == id_seguido
    )

    sigue = session.exec(statement).first()

    if not sigue:
        raise HTTPException(status_code=404, detail='No sigues a este usuario')
    
    session.delete(sigue)
    session.commit()
    return {'message' : 'Has dejado de seguir a este usuario'}

@app.get('/usuarios/{usuario_id}/siguiendo')
def obtener_seguidos(usuario_id: int, session: Session = Depends(get_session)):
    # Buscamos a los usuarios a los que sigue el anfitrion de la cuenta
    statement = (
        select(Usuarios)
        .join(Seguidos, Usuarios.id == Seguidos.id_seguido)
        .where(Seguidos.id_seguidor == usuario_id)
        )
    
    lista_seguidos = session.exec(statement).all()
    return lista_seguidos

@app.get('/usuarios/{usuario_id}/seguidores')
def obtener_seguidores(usuario_id: int, session: Session = Depends(get_session)):
    statement = (select(Usuarios).join(Seguidos, Usuarios.id == Seguidos.id_seguidor).where(Seguidos.id_seguido == usuario_id))
    return session.exec(statement).all()

@app.get('/usuarios/feed/{mi_id}')
def obtener_feed_social(mi_id: int, session: Session = Depends(get_session)):

    # Sacamos los ids de la gente que el usuario sigue 
    seguidos_ids = session.exec(select(Seguidos.id_seguido).where(Seguidos.id_seguidor == mi_id)).all()

    if not seguidos_ids:
        return {'message': 'No Sigues a ninguna cuenta'}
    
    # Buscamos la actividad de los usuarios que seguimos
    statemnt = (
        select(Usuarios, Eventos, Usuario_Eventos)
        .join(Usuario_Eventos, Usuarios.id == Usuario_Eventos.id_usuario)
        .join(Eventos, Eventos.id == Usuario_Eventos.id_evento)
        .where(Usuarios.id.in_(seguidos_ids))
        .order_by(desc(Usuario_Eventos.id_evento))
        .limit(20)
    )

    resultado = session.exec(statemnt).all()

    # Mejoramos para que angular los lea mejor
    feed = []
    for usuario, evento, relacion in resultado:
        feed.append({
            'usuario_nombre':usuario.nombre_usuario,
            'usuario_foto':usuario.foto_perfil,
            'evento_id': evento.id,
            'evento_nombre': evento.nombre,
            'evento_fecha':evento.fecha,
            'evento_imagen': evento.image_Url,
            'accion': relacion.estatus,
            'comentario': relacion.comentario,
        })

    return feed

@app.get('/eventos/{evento_id}/comentarios')
def obtener_comentarios(evento_id: int, session: Session = Depends(get_session)):
    statement = select(Usuario_Eventos, Usuarios).join(Usuarios).where(Usuario_Eventos.id_evento == evento_id)
    resultados = session.exec(statement).all()

    comentarios = []
    for relacion, usuario in resultados:
        comentarios.append({
            'id_usuario': usuario.id,
            'nombre_usuario': usuario.nombre_usuario,
            'foto_perfil': usuario.foto_perfil,
            'estatus': relacion.estatus,
            'comentario': relacion.comentario
        })

    return comentarios


@app.patch('/usuarios/evento/comentario')
def actualizar_comentario(datos_entrada: Usuario_Eventos, session: Session = Depends(get_session)):

    relacion = session.exec(select(Usuario_Eventos).where(
        Usuario_Eventos.id_usuario == datos_entrada.id_usuario,
        Usuario_Eventos.id_evento == datos_entrada.id_evento
    )).first()

    if not relacion:
        raise HTTPException(status_code=404, detail='No tienes relacion con este evento')
    
    relacion.comentario = datos_entrada.comentario
    session.add(relacion)
    session.commit()

    return {'message': 'comentario actualizado'}

import json
from models import Subscription

@app.post("/usuarios/push/subscribe/{user_id}")
def subscribe_user(user_id: int, sub_data: dict, session: Session = Depends(get_session)):
    # Buscamos si ya existe para actualizarla en lugar de crear un duplicado
    statement = select(Subscription).where(Subscription.user_id == user_id)
    sub = session.exec(statement).first()
    
    if sub:
        # Actualizamos la suscripción existente
        sub.sub_json = str(sub_data)
        session.add(sub)
    else:
        # Creamos una nueva
        new_sub = Subscription(user_id=user_id, sub_json=str(sub_data))
        session.add(new_sub)
        
    session.commit()
    return {"message": "Suscripción guardada"}

@app.delete("/usuarios/push/unsubscribe/{user_id}")
def unsubscribe_user(user_id: int, session: Session = Depends(get_session)):
    # Buscamos la suscripción del usuario
    statement = select(Subscription).where(Subscription.user_id == user_id)
    sub = session.exec(statement).first()
    
    if not sub:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")
    
    session.delete(sub)
    session.commit()
    return {"message": "Suscripción eliminada con éxito"}

@app.get("/usuarios/check-push/{user_id}")
def check_push_status(user_id: int, session: Session = Depends(get_session)):
    statement = select(Subscription).where(Subscription.user_id == user_id)
    sub = session.exec(statement).first()
    
    # Devuelve true si existe, false si no
    return {"activo": sub is not None}

@app.get("/generos")
def get_generos(session: Session = Depends(get_session)):
    return session.exec(select(Generos)).all()

@app.get("/usuarios/{user_id}/preferencias")
def get_user_preferencias(user_id: int, session: Session = Depends(get_session)):
    # Buscamos los IDs de género vinculados a este usuario
    statement = select(Usuario_Preferencias.id_genero).where(Usuario_Preferencias.id_usuario == user_id)
    return session.exec(statement).all()

@app.post("/usuarios/{user_id}/preferencias")
def set_user_preferencias(user_id: int, generos_ids: list[int], session: Session = Depends(get_session)):
    # 1. Eliminar relaciones actuales
    session.exec(delete(Usuario_Preferencias).where(Usuario_Preferencias.id_usuario == user_id))
    
    # 2. Insertar nuevas
    for g_id in generos_ids:
        nueva_preferencia = Usuario_Preferencias(id_usuario=user_id, id_genero=g_id)
        session.add(nueva_preferencia)
    
    session.commit()
    return {"message": "Preferencias actualizadas"}

@app.post("/generos/eventos/{evento_id}/generos")
def set_evento_generos(evento_id: int, generos_ids: list[int], session: Session = Depends(get_session)):
    # 1. Limpiamos las asociaciones previas para ese evento
    session.exec(delete(Evento_Generos).where(Evento_Generos.id_evento == evento_id))
    
    # 2. Insertamos las nuevas relaciones
    for g_id in generos_ids:
        nueva_asociacion = Evento_Generos(id_evento=evento_id, id_genero=g_id)
        session.add(nueva_asociacion)
        
    session.commit()
    return {"message": "Géneros del evento actualizados"}

@app.get("/generos/eventos/{evento_id}/generos")
def get_evento_generos(evento_id: int, session: Session = Depends(get_session)):
    statement = select(Evento_Generos.id_genero).where(Evento_Generos.id_evento == evento_id)
    return session.exec(statement).all()

@app.get("/eventos/recomendados/{user_id}")
def get_eventos_recomendados(user_id: int, session: Session = Depends(get_session)):
    # 1. Primero, obtenemos los IDs de géneros favoritos del usuario
    fav_generos = session.exec(select(Usuario_Preferencias.id_genero).where(Usuario_Preferencias.id_usuario == user_id)).all()
    
    # 2. Buscamos eventos que tengan al menos uno de esos géneros
    statement = select(Eventos).join(Evento_Generos).where(Evento_Generos.id_genero.in_(fav_generos)).distinct()
    return session.exec(statement).all()

@app.get('/eventos/buscar-predictivo/match')
def buscar_eventos_predictivo(q: str, session: Session = Depends(get_session)):
    """
    Endpoint para el autocompletado en Angular.
    Busca coincidencias parciales por nombre y devuelve los datos clave
    (nombre, ciudad, fecha) para alertar sobre posibles duplicados.
    """
    if not q or len(q) < 3:
        return []

    # Buscamos coincidencias parciales (case-insensitive gracias a ilike)
    # Limitamos a 5 resultados para que la respuesta sea instantánea en el Front
    statement = (
        select(Eventos)
        .where(Eventos.nombre.ilike(f"%{q}%"))
        .limit(5)
    )
    
    resultados = session.exec(statement).all()
    
    # Formateamos la respuesta limpia con lo justo y necesario
    feed_predictivo = []
    for evento in resultados:
        feed_predictivo.append({
            'id': evento.id,
            'nombre': evento.nombre,
            'ciudad': evento.ciudad,
            'fecha': evento.fecha.strftime("%Y-%m-%d") if isinstance(evento.fecha, datetime) else str(evento.fecha)
        })
        
    return feed_predictivo

