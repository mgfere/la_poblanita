import os
from flask import url_for
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Date, Boolean, DECIMAL, Time, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from werkzeug.security import generate_password_hash, check_password_hash

Base = declarative_base()

class Empleados(Base):
    __tablename__ = 'empleados'
    
    id_empleado = Column(Integer, primary_key=True, autoincrement=True)
    nombre_usuario = Column(String(50), unique=True, nullable=False)
    contraseña_hash = Column(Text, nullable=False)
    nombre = Column(String(100), nullable=True)
    apellidoP = Column(String(100), nullable=True)
    apellidoM = Column(String(100), nullable=True)
    email = Column(String(100), unique=True, nullable=True)
    telefono = Column(String(20), nullable=False)
    colonia = Column(Text, nullable=True)
    calle = Column(Text, nullable=True)
    no_exterior = Column(Text, nullable=True)
    foto_perfil = Column(LargeBinary, nullable=True)
    fecha_registro = Column(DateTime, default=datetime.utcnow)
    activo = Column(Boolean, default=True)
    rol = Column(String(20), default='user')  # user, admin, boss
    
    productos_creados = relationship("Productos", back_populates="creado_por")

    def __init__(self, telefono, nombre_usuario, contraseña, rol='user'):
        self.telefono = telefono
        self.nombre_usuario = nombre_usuario
        self.contraseña_hash = generate_password_hash(contraseña)
        self.rol = rol

    def verificar_contraseña(self, contraseña):
        return check_password_hash(self.contraseña_hash, contraseña)
    
    def get_foto_perfil_url(self):
        if self.foto_perfil:
            # Si la foto esta en la base de datos como blob
            return url_for('get_picture_profile', usuario_id=self.id_empleado)
        else:
            # Foto predeterminada
            return url_for('static', filename='images/picture_profile_default.png')
    
    def guardar_foto_perfil(self, archivo_foto):
        # Guarda la foto de perfil en la base de datos
        if archivo_foto:
            # Validar tamaño (15MB máximo)
            archivo_foto.seek(0, os.SEEK_END)
            tamaño = archivo_foto.tell()
            archivo_foto.seek(0)
            
            if tamaño > 15 * 1024 * 1024:  # 15MB
                raise ValueError("La imagen no puede ser mayor a 15MB")
            
            # Validar tipo de archivo
            extension_permitida = {'png', 'jpg', 'jpeg', 'gif'}
            extension = archivo_foto.filename.split('.')[-1].lower()
            if extension not in extension_permitida:
                raise ValueError("Formato de imagen no permitido")
            
            # Leer y guardar la imagen
            self.foto_perfil = archivo_foto.read()
    
    def __repr__(self):
        return f'<Empleado {self.nombre_usuario}>'

class Productos(Base):
    __tablename__ = 'productos'
    
    id_producto = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    cantidad = Column(Integer, nullable=False)
    imagen = Column(LargeBinary, nullable=True)
    id_empleado = Column(Integer, ForeignKey('empleados.id_empleado'), nullable=False)
    
    creado_por = relationship("Empleados", back_populates="productos_creados")

    def __init__(self, nombre, cantidad, id_empleado):
        self.nombre = nombre
        self.cantidad = cantidad
        self.id_empleado = id_empleado

    def __repr__(self):
        return f'<Producto {self.nombre}>'

# En models.py, agrega esta nueva tabla y relación
class PaqueteProducto(Base):
    __tablename__ = 'paquete_producto'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_paquete = Column(Integer, ForeignKey('paquete.id_paquete'), nullable=False)
    id_producto = Column(Integer, ForeignKey('productos.id_producto'), nullable=False)
    cantidad = Column(Integer, nullable=False)
    
    producto = relationship("Productos")

# Y actualiza la clase Paquetes para incluir la relación
class Paquetes(Base):
    __tablename__ = 'paquete'
    
    id_paquete = Column(Integer, primary_key=True, autoincrement=True)
    sucursal = Column(Text, nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    
    # Agregar esta relación
    productos = relationship("PaqueteProducto", cascade="all, delete-orphan")

    def __init__(self, sucursal="Por asignar"):  # VALOR POR DEFECTO
        self.sucursal = sucursal

    def __repr__(self):
        return f'<Paquete {self.id_paquete}>'