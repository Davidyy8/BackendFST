# Fichero principal de la app.
# Ativar el venv:
# venv\Scripts\activate

from fastapi import FastAPI, Depends, HTTPException
from sqlmodel import Session, select, desc
from database import engine, get_session
from models import Usuarios, Usuario_Eventos, Eventos, Seguidos
from schemas import UsuarioCrear, UsuarioUpdate, EventoCrear, EventoUpdate, EventoUsiarioCrear
from security import hash_password

app = FastAPI(title='FST Festival Show Tracker')

@app.get('/')
def root():
    return {'menssage' : 'Bienvenido a la api de FST'}

@app.get('/usuarios')
def listar_usuarios(session: Session = Depends(get_session)):
    # Select from usuarios 
    usuarios = session.exec(select(Usuarios)).all()
    return usuarios

@app.post('/usuarios')
def crear_usuario(datos: UsuarioCrear, session: Session = Depends(get_session)):
    # Encriptar la contraseña
    hashed_pwd = hash_password(datos.contraseña)

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
    
    # Guardar los cambios 
    session.add(usuario_db)
    session.commit()
    session.refresh(usuario_db)

    return {'message' : 'Perfil actualizado', 'usuario' : usuario_db}

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


@app.get('/eventos')
def listar_eventos(session: Session = Depends(get_session)):
    # Select de los Eventos
    eventos = session.exec(select(Eventos)).all()
    return eventos


@app.post('/eventos')
def crear_evento(datos: EventoCrear, session: Session = Depends(get_session)):
    
    nuevo_evento = Eventos(
        nombre=datos.nombre,
        artista=datos.artista,
        localizacion=datos.localizacion,
        fecha=datos.fecha,
        ciudad=datos.ciudad,
        image_Url=datos.image_Url
    )

    try: 
        # Lo guardamos en sql
        session.add(nuevo_evento)
        session.commit()
        session.refresh(nuevo_evento)
        return {'message' : 'Evento creado con exito', 'id' : nuevo_evento.id}
    except Exception as e:
        session.rollback()
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


@app.post('/evento_usario')
def asistirEvento(usuario_id: int, evento_id: int, status: str, comentario: str = None ,session: Session = Depends(get_session)):
    # Comprobar si hay relacion 
    statement = select(Usuario_Eventos).where(
        Usuario_Eventos.id_usuario == usuario_id,
        Usuario_Eventos.id_evento == evento_id
    )

    existente = session.exec(statement).first

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
        session.refresh()
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
    existente = session.exec(statement).first
    if not existente:
        raise HTTPException(status_code=400, detail='Esta relacion no existe')
    
    # Eliminamos el evento
    session.delete(existente)
    session.commit()
    return {'message' : 'Relacion eliminada con exito'}


@app.get('/usuarios/{usuario_id}/eventos')
def obtener_usuarios_eventos(usuario_id: int, session: Session = Depends(get_session)):
    # Definimos la consulta con un join
    statement = (
        select(Eventos, Usuario_Eventos.estatus, Usuario_Eventos.comentario)
        .join(Usuario_Eventos)
        .where(Usuario_Eventos.id_usuario == usuario_id) 
    )

    # ejecutamos la consulta
    resultados = session.exec(statement).all()


    # Convertimos la respuesta a un formato facil de leer con angular
    listado = []
    for evento, estatus, comentario in resultados:
        listado.append({
            'id':evento.id,
            'id_remoto':evento.id_remoto,
            'nombre':evento.nombre,
            'artista':evento.artista,
            'fecha':evento.fecha,
            'ciudad':evento.ciudad,
            'image_Url':evento.image_Url,
            'otro datos': {
                'estatus':estatus,
                'comentario': comentario
            }
        })
    return listado



@app.post('/usuarios/seguir/{id_a_seguir}')
def seguir_usuario(id_a_seguir: int, id_seguidorFront: int, session: Session = Depends(get_session)):

    # Comprobamos que los ids no sean iguales
    if id_a_seguir == id_seguidorFront:
        raise HTTPException(status_code=400, detail='No puedes seguirte a ti mismo')
    
    # Comprobamos que el usuario a seguir existe
    usuario_a_seguir = session.get(Usuarios, id_a_seguir)
    if not usuario_a_seguir:
        raise HTTPException(status_code=404, detail='El usuario no existe')
    
    # Verificamos si ya lo seguimos
    statement = select(Seguidos).where(
        Seguidos.id_seguidor == id_seguidorFront,
        Seguidos.id_seguido == id_a_seguir
    )

    ya_sigue = session.exec(statement).first()
    if ya_sigue:
        raise HTTPException(status_code=400, detail='Ya sigues a este usuario')
    
    # Crear la relacion
    nuevo_seguido = Seguidos(id_seguidor=id_seguidorFront, id_seguido=id_a_seguir)
    session.add(nuevo_seguido)
    session.commit()

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



@app.get('/feed/{mi_id}')
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
        .where(Usuarios.id in (seguidos_ids))
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
            'evento_nombre': evento.nombre,
            'evento_fecha':evento.fecha,
            'evento_imagen': evento.image_Url,
            'accion': relacion.estatus,
            'comentario': relacion.comentario,
        })

    return feed