import os
from flask import url_for
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, DateTime, Boolean, LargeBinary
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from werkzeug.security import generate_password_hash, check_password_hash

Base = declarative_base()

# ===================== TABLA ROLES =====================
class Roles(Base):
    __tablename__ = 'roles'
    
    id_rol = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(50), nullable=False)

    empleados = relationship("Empleados", back_populates="rol")

    def __repr__(self):
        return f'<Rol {self.nombre}>'


# ===================== TABLA EMPLEADOS =====================
class Empleados(Base):
    __tablename__ = 'empleados'

    id_empleado = Column(Integer, primary_key=True, autoincrement=True)
    nombre_usuario = Column(String(50), unique=True, nullable=False)
    contraseña_hash = Column(Text, nullable=False)
    telefono = Column(String(20), nullable=False)
    fecha_registro = Column(DateTime, default=datetime.utcnow)
    activo = Column(Boolean, default=True)
    id_rol = Column(Integer, ForeignKey('roles.id_rol'), nullable=False)

    rol = relationship("Roles", back_populates="empleados")
    perfil = relationship(
        "Perfiles_Empleados", 
        back_populates="empleado", 
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __init__(self, nombre_usuario, contraseña, telefono, id_rol):
        self.nombre_usuario = nombre_usuario
        self.contraseña_hash = generate_password_hash(contraseña)
        self.telefono = telefono
        self.id_rol = id_rol

    def verificar_contraseña(self, contraseña):
        return check_password_hash(self.contraseña_hash, contraseña)

    def __repr__(self):
        return f'<Empleado {self.nombre_usuario}>'


# ===================== TABLA PERFILES EMPLEADOS =====================
class Perfiles_Empleados(Base):
    __tablename__ = 'perfiles_empleados'

    id_perfil_empleado = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    apellidoP = Column(String(100), nullable=False)
    apellidoM = Column(String(100), nullable=True)
    email = Column(String(100), unique=True, nullable=True)
    colonia = Column(Text, nullable=True)
    calle = Column(Text, nullable=True)
    no_exterior = Column(Text, nullable=True)
    foto_perfil = Column(LargeBinary(length=16777215), nullable=True)
    id_empleado = Column(Integer, ForeignKey('empleados.id_empleado'), nullable=False)

    empleado = relationship("Empleados", back_populates="perfil")

    def get_foto_perfil_url(self):
        if self.foto_perfil:
            return url_for('get_picture_profile', usuario_id=self.id_empleado)
        else:
            return url_for('static', filename='images/picture_profile_default.png')

    def guardar_foto_perfil(self, archivo_foto):
        if archivo_foto:
            archivo_foto.seek(0, os.SEEK_END)
            tamaño = archivo_foto.tell()
            archivo_foto.seek(0)
            if tamaño > 15 * 1024 * 1024:
                raise ValueError("La imagen no puede ser mayor a 15MB")

            extension_permitida = {'png', 'jpg', 'jpeg', 'gif'}
            extension = archivo_foto.filename.split('.')[-1].lower()
            if extension not in extension_permitida:
                raise ValueError("Formato de imagen no permitido")

            self.foto_perfil = archivo_foto.read()

    def __repr__(self):
        return f'<PerfilEmpleado {self.nombre} {self.apellidoP}>'


# ===================== TABLA PRODUCTOS =====================
class Productos(Base):
    __tablename__ = 'productos'

    id_producto = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    cantidad = Column(Integer, nullable=False)
    imagen = Column(LargeBinary(length=16777215), nullable=True)

    paquetes_productos = relationship("Paquetes_Productos", back_populates="producto")

    def __init__(self, nombre, cantidad):
        self.nombre = nombre
        self.cantidad = cantidad

    def __repr__(self):
        return f'<Producto {self.nombre}>'


# ===================== TABLA PAQUETES =====================
class Paquetes(Base):
    __tablename__ = 'paquetes'

    id_paquete = Column(Integer, primary_key=True, autoincrement=True)
    sucursal = Column(Text, nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

    paquetes_productos = relationship(
        "Paquetes_Productos", 
        back_populates="paquete",
        cascade="all, delete-orphan"
    )

    def __init__(self, sucursal="Por asignar"):
        self.sucursal = sucursal

    def __repr__(self):
        return f'<Paquete {self.id_paquete}>'


# ===================== TABLA INTERMEDIA PAQUETES_PRODUCTOS =====================
class Paquetes_Productos(Base):
    __tablename__ = 'paquetes_productos'

    id_paquete_producto = Column(Integer, primary_key=True, autoincrement=True)
    id_paquete = Column(Integer, ForeignKey('paquetes.id_paquete', ondelete='CASCADE'), nullable=False)
    id_producto = Column(Integer, ForeignKey('productos.id_producto'), nullable=False)
    cantidad = Column(Integer, nullable=False)

    paquete = relationship("Paquetes", back_populates="paquetes_productos")
    producto = relationship("Productos", back_populates="paquetes_productos")

    def __repr__(self):
        return f'<PaqueteProducto paquete={self.id_paquete} producto={self.id_producto}>'