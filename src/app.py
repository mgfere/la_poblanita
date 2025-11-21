import datetime
from flask import Flask, redirect, render_template, request, session, url_for, Response
from functools import wraps
from io import BytesIO
from PIL import Image
from database import db_session
from database.models import Empleados, Productos, Paquetes, Paquetes_Productos, Perfiles_Empleados, Roles
from werkzeug.security import generate_password_hash
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message
from config import Config
import json
import math
import os

app = Flask(__name__)
app.secret_key = 'LA POBLANITA'

app.config.from_object(Config)
correo = Mail(app)
serializador = URLSafeTimedSerializer(Config.SECRET_KEY)

# ===== FUNCIÓN DE PAGINACIÓN MANUAL =====
def paginate(query, page, per_page):

    page = max(1, page)
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    
    class Pagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = math.ceil(total / per_page) if per_page > 0 else 0
            
        @property
        def has_prev(self):
            return self.page > 1
            
        @property
        def has_next(self):
            return self.page < self.pages
            
        @property
        def prev_num(self):
            return self.page - 1 if self.has_prev else None
            
        @property
        def next_num(self):
            return self.page + 1 if self.has_next else None
            
        def iter_pages(self, left_edge=2, left_current=2, right_current=2, right_edge=2):

            total_pages = self.pages
            if total_pages <= 1:
                return

            left_range = range(1, min(left_edge, total_pages) + 1)
            right_range = range(max(total_pages - right_edge + 1, left_edge + 1), total_pages + 1)
            
            current_page = self.page
            middle_range = range(
                max(current_page - left_current, left_edge + 1),
                min(current_page + right_current + 1, right_range[0] if right_range else total_pages + 1)
            )
            
            last = 0
            for page_num in left_range:
                yield page_num
                last = page_num
                
            if last + 1 < middle_range[0] if middle_range else last + 1 < right_range[0] if right_range else False:
                yield None
                
            for page_num in middle_range:
                yield page_num
                last = page_num
                
            if last + 1 < right_range[0] if right_range else False:
                yield None
                
            for page_num in right_range:
                yield page_num

    return Pagination(items, page, per_page, total)


# ===== FUNCIONES DE BÚSQUEDA =====
def buscar_empleados(termino):
    """
    Buscador de empleados por nombre, apellidos, usuario, email o teléfono
    """
    return db_session.query(Empleados).join(Perfiles_Empleados).filter(
        (Empleados.nombre_usuario.ilike(f'%{termino}%')) |
        (Perfiles_Empleados.nombre.ilike(f'%{termino}%')) |
        (Perfiles_Empleados.apellidoP.ilike(f'%{termino}%')) |
        (Perfiles_Empleados.apellidoM.ilike(f'%{termino}%')) |
        (Perfiles_Empleados.email.ilike(f'%{termino}%')) |
        (Empleados.telefono.ilike(f'%{termino}%'))
    )

def buscar_productos(termino):
    """
    Buscador de productos por nombre o código de barras exacto
    """
    producto_por_codigo = db_session.query(Productos).filter(
        Productos.codigo_barras == termino
    ).first()
    
    if producto_por_codigo:
        return db_session.query(Productos).filter(Productos.codigo_barras == termino)
    else:
        return db_session.query(Productos).filter(
            Productos.nombre.ilike(f'%{termino}%')
        )

def buscar_paquetes(termino):
    """
    Buscador de paquetes por ID, sucursal o productos contenidos
    """
    # Buscador por ID de paquete
    if termino.isdigit():
        paquete_id = int(termino)
        return db_session.query(Paquetes).filter(
            (Paquetes.id_paquete == paquete_id) |
            (Paquetes.sucursal.ilike(f'%{termino}%'))
        ).filter(Paquetes.paquetes_productos.any())
    
    # Buscador por sucursal o productos
    return db_session.query(Paquetes).filter(
        (Paquetes.sucursal.ilike(f'%{termino}%')) |
        (Paquetes.paquetes_productos.any(
            Paquetes_Productos.producto.has(Productos.nombre.ilike(f'%{termino}%'))
        ))
    ).filter(Paquetes.paquetes_productos.any())

# ===== FUNCIONES AUXILIARES =====
def get_usuario_actual():
    return db_session.query(Empleados).filter_by(id_empleado=session['usuario_id']).first() if 'usuario_id' in session else None

def get_perfil_usuario_actual():
    usuario = get_usuario_actual()
    if usuario and usuario.perfil:
        return usuario.perfil
    return None

def get_rol_usuario_actual():
    usuario = get_usuario_actual()
    if usuario and usuario.rol:
        return usuario.rol.nombre
    return 'user'

def requiere_login(f):
    def decorador(*args, **kwargs):
        return f(*args, **kwargs) if get_usuario_actual() else redirect(url_for('login'))
    decorador.__name__ = f.__name__
    return decorador

def requiere_rol(*roles):
    def decorador(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            usuario = get_usuario_actual()
            rol_actual = get_rol_usuario_actual()
            if not usuario or rol_actual not in roles:
                return render_template('auth/access_denied.html', usuario=usuario, perfil=get_perfil_usuario_actual())
            return f(*args, **kwargs)
        return decorated_function
    return decorador

def puede_editar_empleado(usuario_actual, empleado_id):
    rol_actual = get_rol_usuario_actual()
    if rol_actual == 'boss': 
        return True
    elif rol_actual == 'admin':
        empleado = db_session.query(Empleados).filter_by(id_empleado=empleado_id).first()
        return empleado and empleado.rol and empleado.rol.nombre == 'user'
    return False

def puede_cambiar_rol(usuario_actual, nuevo_rol_id):
    rol_actual = get_rol_usuario_actual()
    if rol_actual == 'boss': 
        return True
    elif rol_actual == 'admin':
        nuevo_rol = db_session.query(Roles).filter_by(id_rol=nuevo_rol_id).first()
        return nuevo_rol and nuevo_rol.nombre == 'user'
    return False

def manejar_imagen(archivo):

    if not archivo or not archivo.filename:
        return None
    
    if not archivo.content_type.startswith('image/'):
        print(f"Archivo no es una imagen: {archivo.content_type}")
        return None
    
    try:
        # Tamaño máximo 15MB
        max_size = 15 * 1024 * 1024

        archivo.seek(0, 2)
        file_size = archivo.tell()
        archivo.seek(0)
        
        if file_size > max_size:
            print(f"Imagen demasiado grande: {file_size} bytes")
            return None
        
        imagen_data = archivo.read()
        
        if len(imagen_data) > max_size:
            print(f"Imagen demasiado grande después de leer: {len(imagen_data)} bytes")
            return None
        
        if len(imagen_data) <= 1 * 1024 * 1024:
            print(f"Imagen aceptada sin compresión: {len(imagen_data)} bytes")
            return imagen_data
        
        try:
            imagen = Image.open(BytesIO(imagen_data))
            print(f"Imagen original: {imagen.format}, tamaño: {imagen.size}, modo: {imagen.mode}")
            
            # Formatos JPEG, PNG o WEBP
            formato_original = imagen.format
            formatos_sin_perdida = ['JPEG', 'PNG', 'WEBP']
            
            # Redimensiona
            max_width, max_height = 600, 600
            if imagen.width > max_width or imagen.height > max_height:
                imagen.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                print(f"Imagen redimensionada a: {imagen.size}")
            
            # Comprime la imagen
            calidad = 85
            max_intentos = 5
            
            for intento in range(max_intentos):
                output = BytesIO()
                
                if formato_original in formatos_sin_perdida:

                    if formato_original == 'JPEG' and imagen.mode in ('RGBA', 'P'):
                        imagen = imagen.convert('RGB')
                    elif formato_original == 'PNG':
  
                        imagen.save(output, format='PNG', optimize=True)
                    else:
                        imagen.save(output, format=formato_original, optimize=True)
                else:

                    if imagen.mode in ('RGBA', 'P'):
                        imagen = imagen.convert('RGB')
                    imagen.save(output, format='JPEG', quality=calidad, optimize=True)
                
                imagen_comprimida = output.getvalue()
                
                if len(imagen_comprimida) <= 1 * 1024 * 1024:
                    print(f"Imagen comprimida exitosamente: {len(imagen_data)} -> {len(imagen_comprimida)} bytes (calidad: {calidad}%)")
                    return imagen_comprimida
                
                calidad -= 15
                if calidad < 30:
                    break
            
            if len(imagen_comprimida) <= 15 * 1024 * 1024:
                print(f"Imagen comprimida (último intento): {len(imagen_data)} -> {len(imagen_comprimida)} bytes")
                return imagen_comprimida
            else:
                print(f"Imagen demasiado grande después de compresión: {len(imagen_comprimida)} bytes")
                return None
            
        except Exception as e:
            print(f"Error procesando imagen con PIL: {e}")

            if len(imagen_data) <= 1 * 1024 * 1024:
                return imagen_data
            return None
            
    except Exception as e:
        print(f"Error general procesando imagen: {e}")
        return None

def validar_stock_paquete(productos_seleccionados):
    insuficientes = []
    for item in productos_seleccionados:
        producto = db_session.query(Productos).filter_by(id_producto=item['id']).first()
        if not producto or producto.cantidad < item['cantidad']:
            insuficientes.append({
                'nombre': producto.nombre if producto else f'Producto {item["id"]}',
                'solicitado': item['cantidad'],
                'disponible': producto.cantidad if producto else 0
            })
    return insuficientes

def crear_rol_user_si_no_existe():

    roles_por_defecto = ['user', 'admin', 'boss']
    
    for nombre_rol in roles_por_defecto:
        rol_existente = db_session.query(Roles).filter_by(nombre=nombre_rol).first()
        if not rol_existente:
            try:
                nuevo_rol = Roles(nombre=nombre_rol)
                db_session.add(nuevo_rol)
                db_session.commit()
                print(f"Rol '{nombre_rol}' creado automáticamente")
            except Exception as e:
                db_session.rollback()
                print(f"Error creando rol {nombre_rol}: {e}")
    
    return db_session.query(Roles).filter_by(nombre='user').first()

# ===== RUTAS DE AUTENTICACIÓN =====
@app.route('/')
def index(): 
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = db_session.query(Empleados).filter_by(nombre_usuario=request.form['nombre_usuario']).first()
        if usuario and usuario.verificar_contraseña(request.form['contraseña']) and usuario.activo:
            session['usuario_id'] = usuario.id_empleado
            return redirect(url_for('home'))
        return render_template('auth/login.html', error='Usuario o contraseña incorrectos')
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            if db_session.query(Empleados).filter_by(nombre_usuario=request.form['nombre_usuario']).first():
                return render_template('auth/register.html', error='El usuario ya existe')
            
            rol_user = crear_rol_user_si_no_existe()
            if not rol_user:
                return render_template('auth/register.html', error='Error en la configuración del sistema. Contacte al administrador.')
            
            usuario = Empleados(
                nombre_usuario=request.form['nombre_usuario'],
                contraseña=request.form['contraseña'],
                telefono=request.form['telefono'],
                id_rol=rol_user.id_rol
            )
            db_session.add(usuario)
            db_session.commit()
            
            perfil = Perfiles_Empleados(
                nombre="",
                apellidoP="",
                apellidoM="",
                id_empleado=usuario.id_empleado
            )
            db_session.add(perfil)
            db_session.commit()
            
            return redirect(url_for('login'))
            
        except Exception as e:
            db_session.rollback()
            print(f"Error en registro: {e}")
            return render_template('auth/register.html', error='Error en el registro. Intente nuevamente.')
    
    return render_template('auth/register.html')

@app.route('/logout')
def logout():
    session.pop('usuario_id', None)
    return redirect(url_for('login'))

# ===== RUTAS DE RECUPERACIÓN DE CONTRASEÑA =====
@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    error = None
    mensaje = None
    
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        
        empleado = db_session.query(Empleados).join(Perfiles_Empleados).filter(
            Perfiles_Empleados.email.ilike(email),
            Empleados.activo == True
        ).first()
        
        if empleado:
            token = serializador.dumps(email, salt='reinicio-contraseña')
            url_reinicio = url_for('reset_password', token=token, _external=True)

            # PRODUCCION mostrar link
            if not app.debug:
                mensaje = f"""
                Se encontró el usuario. Da clic en el enlace para restablecer tu contraseña:
                <br><br>
                <a href='{url_reinicio}' class='btn btn-success'>Restablecer Contraseña</a>
                <br><br>
                Este enlace expira en 1 hora.
                """
            else:
                # LOCAL seguir enviando correo normal
                try:
                    msg = Message(
                        "Recuperación de Contraseña - La Poblanita",
                        sender=app.config['MAIL_USERNAME'],
                        recipients=[email]
                    )
                    msg.body = f"Enlace de recuperación:\n\n{url_reinicio}"
                    correo.send(msg)
                    
                    mensaje = "Se ha enviado un enlace de recuperación a tu correo."
                except Exception as e:
                    error = f"Error enviando correo: {str(e)}"
        else:
            mensaje = "Si el correo existe, se enviará el enlace."
    
    return render_template('auth/reset_password_request.html', error=error, mensaje=mensaje)




@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    error = None
    mensaje = None
    
    try:
        email = serializador.loads(token, salt='reinicio-contraseña', max_age=3600)
        print(f"Email recuperado del token: {email}")
    except Exception as e:
        error = "El enlace es inválido o ha expirado."
        print(f"Error cargando token: {e}")
        return render_template('auth/reset_password.html', error=error)
    
    empleado = db_session.query(Empleados).join(Perfiles_Empleados).filter(
        Perfiles_Empleados.email.ilike(email),
        Empleados.activo == True
    ).first()
    
    if not empleado:
        error = "Usuario no encontrado o inactivo."
        print(f"Empleado no encontrado para email: {email}")
        return render_template('auth/reset_password.html', error=error)
    
    print(f"Empleado encontrado: {empleado.nombre_usuario}")
    
    if request.method == 'POST':
        nueva_contraseña = request.form['nueva_contraseña']
        
        if len(nueva_contraseña) < 6:
            error = "La nueva contraseña debe tener al menos 6 caracteres."
        else:
            try:
                empleado.contraseña_hash = generate_password_hash(nueva_contraseña)
                db_session.commit()
                mensaje = "Contraseña actualizada correctamente."
                print(f"Contraseña actualizada para usuario: {empleado.nombre_usuario}")
            except Exception as e:
                error = "Error al actualizar la contraseña. Intente nuevamente."
                print(f"Error actualizando contraseña: {e}")
                db_session.rollback()
    
    return render_template('auth/reset_password.html', error=error, mensaje=mensaje)

# ===== RUTAS PRINCIPALES =====
@app.route('/home')
@requiere_login
def home():
    return render_template('pages/home.html', 
                         usuario=get_usuario_actual(), 
                         perfil=get_perfil_usuario_actual())

# ===== GESTIÓN DE PRODUCTOS =====
@app.route('/products')
@requiere_login
def products():
    pagina = request.args.get('pagina', 1, type=int)
    busqueda = request.args.get('busqueda', '').strip()
    filtro_nombre = request.args.get('filtro_nombre', '').strip()
    filtro_codigo = request.args.get('filtro_codigo', '').strip()
    filtro_stock_min = request.args.get('filtro_stock_min', '').strip()
    filtro_stock_max = request.args.get('filtro_stock_max', '').strip()
    
    por_pagina = 10
    productos_query = db_session.query(Productos)
    if busqueda:
        productos_query = buscar_productos(busqueda)
    if filtro_nombre:
        productos_query = productos_query.filter(Productos.nombre.ilike(f'%{filtro_nombre}%'))
    if filtro_codigo:
        productos_query = productos_query.filter(Productos.codigo_barras.ilike(f'%{filtro_codigo}%'))
    if filtro_stock_min:
        try:
            productos_query = productos_query.filter(Productos.cantidad >= int(filtro_stock_min))
        except ValueError:
            pass
    if filtro_stock_max:
        try:
            productos_query = productos_query.filter(Productos.cantidad <= int(filtro_stock_max))
        except ValueError:
            pass
    productos_paginados = paginate(productos_query, pagina, por_pagina)
    
    return render_template('pages/management_products.html', 
                         productos=productos_paginados.items,
                         pagination=productos_paginados,
                         busqueda=busqueda,
                         filtro_nombre=filtro_nombre,
                         filtro_codigo=filtro_codigo,
                         filtro_stock_min=filtro_stock_min,
                         filtro_stock_max=filtro_stock_max,
                         usuario=get_usuario_actual(),
                         perfil=get_perfil_usuario_actual())

@app.route('/products/add', methods=['POST'])
@requiere_login
@requiere_rol('user', 'admin', 'boss')
def add_product():
    try:
        codigo_barras = request.form.get('codigo_barras')
        if not codigo_barras:
            pagina = request.args.get('pagina', 1, type=int)
            busqueda = request.args.get('busqueda', '').strip()
            if busqueda:
                productos_query = buscar_productos(busqueda)
            else:
                productos_query = db_session.query(Productos)
            productos_paginados = paginate(productos_query, pagina, 10)
            return render_template('pages/management_products.html', 
                                productos=productos_paginados.items,
                                pagination=productos_paginados,
                                busqueda=busqueda,
                                usuario=get_usuario_actual(),
                                perfil=get_perfil_usuario_actual(),
                                error="El código de barras es obligatorio")
        producto = Productos(
            nombre=request.form['nombre'], 
            cantidad=int(request.form['cantidad']),
            codigo_barras=codigo_barras
        )
        imagen_data = manejar_imagen(request.files.get('imagen'))
        if imagen_data: 
            producto.imagen = imagen_data
        db_session.add(producto)
        db_session.commit()
    except Exception as e: 
        print(f"Error agregando producto: {e}")
        db_session.rollback()
    return redirect(url_for('products'))

@app.route('/products/edit/<int:id>', methods=['POST'])
@requiere_login
@requiere_rol('user', 'admin', 'boss')
def edit_product(id):
    producto = db_session.query(Productos).filter_by(id_producto=id).first()
    if producto:
        try:
            codigo_barras = request.form.get('codigo_barras')
            if not codigo_barras:
                # Manejar el error
                pagina = request.args.get('pagina', 1, type=int)
                busqueda = request.args.get('busqueda', '').strip()
                
                if busqueda:
                    productos_query = buscar_productos(busqueda)
                else:
                    productos_query = db_session.query(Productos)
                    
                productos_paginados = paginate(productos_query, pagina, 10)
                return render_template('pages/management_products.html', 
                                    productos=productos_paginados.items,
                                    pagination=productos_paginados,
                                    busqueda=busqueda,
                                    usuario=get_usuario_actual(),
                                    perfil=get_perfil_usuario_actual(),
                                    error="El código de barras es obligatorio")
            
            producto.nombre = request.form['nombre']
            producto.cantidad = int(request.form['cantidad'])
            producto.codigo_barras = codigo_barras
            imagen_data = manejar_imagen(request.files.get('imagen'))
            if imagen_data: 
                producto.imagen = imagen_data
            db_session.commit()
        except Exception as e: 
            print(f"Error editando producto: {e}")
            db_session.rollback()
    return redirect(url_for('products'))

@app.route('/products/delete/<int:id>', methods=['POST'])
@requiere_login
@requiere_rol('user', 'admin', 'boss')
def delete_product(id):
    producto = db_session.query(Productos).filter_by(id_producto=id).first()
    if producto:
        # Verifica si el producto está en algún paquete
        paquetes_con_producto = db_session.query(Paquetes_Productos).filter_by(id_producto=id).all()
        
        if paquetes_con_producto:
            ids_paquetes = [p.id_paquete for p in paquetes_con_producto]
            error_msg = f"""
            No se puede eliminar el producto '{producto.nombre}' porque está siendo usado en los siguientes paquetes:
            {', '.join([f'PQ-{pid}' for pid in ids_paquetes])}
            
            Por favor, elimina primero los paquetes que contienen este producto antes de eliminarlo.
            """
            # Obtiene la página actual
            pagina = request.args.get('pagina', 1, type=int)
            busqueda = request.args.get('busqueda', '').strip()
            
            if busqueda:
                productos_query = buscar_productos(busqueda)
            else:
                productos_query = db_session.query(Productos)
                
            productos_paginados = paginate(productos_query, pagina, 10)
            return render_template('pages/management_products.html', 
                                productos=productos_paginados.items,
                                pagination=productos_paginados,
                                busqueda=busqueda,
                                usuario=get_usuario_actual(),
                                perfil=get_perfil_usuario_actual(),
                                error=error_msg)
        else:
            db_session.delete(producto)
            db_session.commit()
    
    return redirect(url_for('products'))

# ===== GESTIÓN DE PAQUETES =====
@app.route('/packages')
@requiere_login
def packages():
    pagina = request.args.get('pagina', 1, type=int)
    filtro_fecha_desde = request.args.get('filtro_fecha_desde', '').strip()
    filtro_fecha_hasta = request.args.get('filtro_fecha_hasta', '').strip()
    filtro_sucursal = request.args.get('filtro_sucursal', '').strip()
    
    por_pagina = 10
    
    paquetes_query = db_session.query(Paquetes).filter(Paquetes.paquetes_productos.any())
    
    if filtro_fecha_desde:
        try:
            fecha_desde = datetime.strptime(filtro_fecha_desde, '%Y-%m-%d')
            paquetes_query = paquetes_query.filter(Paquetes.fecha_creacion >= fecha_desde)
        except ValueError:
            pass
    
    if filtro_fecha_hasta:
        try:
            fecha_hasta = datetime.strptime(filtro_fecha_hasta, '%Y-%m-%d')
            fecha_hasta = fecha_hasta.replace(hour=23, minute=59, second=59)
            paquetes_query = paquetes_query.filter(Paquetes.fecha_creacion <= fecha_hasta)
        except ValueError:
            pass

    if filtro_sucursal:
        paquetes_query = paquetes_query.filter(Paquetes.sucursal.ilike(f'%{filtro_sucursal}%'))
    
    paquetes_paginados = paginate(paquetes_query, pagina, por_pagina)
    
    sucursales = db_session.query(Paquetes.sucursal).distinct().all()
    sucursales = [s[0] for s in sucursales if s[0]]
    
    return render_template('pages/management_packages.html', 
                         paquetes=paquetes_paginados.items,
                         pagination=paquetes_paginados,
                         filtro_fecha_desde=filtro_fecha_desde,
                         filtro_fecha_hasta=filtro_fecha_hasta,
                         filtro_sucursal=filtro_sucursal,
                         sucursales=sucursales,
                         usuario=get_usuario_actual(),
                         perfil=get_perfil_usuario_actual())

@app.route('/packages/generate', methods=['POST'])
@requiere_login
def generate_package():
    try:
        productos_data = request.form.get('productos_data')
        if not productos_data: 
            return redirect(url_for('products'))
        
        productos_seleccionados = json.loads(productos_data)
        insuficientes = validar_stock_paquete(productos_seleccionados)
        
        if insuficientes:
            error_msg = "No se puede generar el paquete ya que no hay suficiente stock para\n" + "\n".join([f"( {p['nombre']}: Solicitado {p['solicitado']}, Disponible {p['disponible']} )" for p in insuficientes])
            pagina = request.args.get('pagina', 1, type=int)
            busqueda = request.args.get('busqueda', '').strip()
            
            if busqueda:
                productos_query = buscar_productos(busqueda)
            else:
                productos_query = db_session.query(Productos)
                
            productos_paginados = paginate(productos_query, pagina, 10)
            return render_template('pages/management_products.html', 
                                productos=productos_paginados.items,
                                pagination=productos_paginados,
                                busqueda=busqueda,
                                usuario=get_usuario_actual(),
                                perfil=get_perfil_usuario_actual(),
                                error=error_msg)
        
        paquete = Paquetes()
        db_session.add(paquete)
        db_session.flush()
        
        productos_del_paquete = []
        
        for item in productos_seleccionados:
            producto = db_session.query(Productos).filter_by(id_producto=item['id']).first()
            if producto and producto.cantidad >= item['cantidad']:
                paquete_producto = Paquetes_Productos(
                    id_paquete=paquete.id_paquete,
                    id_producto=producto.id_producto,
                    cantidad=item['cantidad']
                )
                db_session.add(paquete_producto)
                productos_del_paquete.append({
                    'producto': producto,
                    'cantidad': item['cantidad']
                })
        
        db_session.commit()
        
        return render_template('pages/confirm_package.html', 
                             paquete=paquete, 
                             productos_del_paquete=productos_del_paquete,
                             usuario=get_usuario_actual(),
                             perfil=get_perfil_usuario_actual())
        
    except Exception as e:
        print(f"Error generando paquete: {e}")
        db_session.rollback()
        return redirect(url_for('products'))

@app.route('/packages/confirm/<int:id>', methods=['POST'])
@requiere_login
def confirm_package(id):
    try:
        sucursal = request.form.get('sucursal')
        
        if not sucursal:
            paquete = db_session.query(Paquetes).filter_by(id_paquete=id).first()
            productos_del_paquete = []
            if paquete:
                for item in paquete.paquetes_productos:
                    producto = db_session.query(Productos).filter_by(id_producto=item.id_producto).first()
                    if producto:
                        productos_del_paquete.append({
                            'producto': producto,
                            'cantidad': item.cantidad
                        })
            return render_template('pages/confirm_package.html', 
                                 paquete=paquete, 
                                 productos_del_paquete=productos_del_paquete,
                                 usuario=get_usuario_actual(),
                                 perfil=get_perfil_usuario_actual(),
                                 error="Por favor selecciona una sucursal")
        
        paquete = db_session.query(Paquetes).filter_by(id_paquete=id).first()
        if not paquete: 
            return redirect(url_for('products'))
        
        paquete.sucursal = sucursal
        
        insuficientes = []
        for item in paquete.paquetes_productos:
            producto = db_session.query(Productos).filter_by(id_producto=item.id_producto).first()
            if producto and producto.cantidad < item.cantidad:
                insuficientes.append({
                    'nombre': producto.nombre, 
                    'solicitado': item.cantidad, 
                    'disponible': producto.cantidad
                })
        
        if insuficientes:
            db_session.delete(paquete)
            db_session.commit()
            error_msg = "Stock insuficiente:\n" + "\n".join([f"- {p['nombre']}: Solicitado {p['solicitado']}, Disponible {p['disponible']}" for p in insuficientes])
            pagina = request.args.get('pagina', 1, type=int)
            busqueda = request.args.get('busqueda', '').strip()
            
            if busqueda:
                productos_query = buscar_productos(busqueda)
            else:
                productos_query = db_session.query(Productos)
                
            productos_paginados = paginate(productos_query, pagina, 10)
            return render_template('pages/management_products.html', 
                                productos=productos_paginados.items,
                                pagination=productos_paginados,
                                busqueda=busqueda,
                                usuario=get_usuario_actual(),
                                perfil=get_perfil_usuario_actual(),
                                error=error_msg)
        
        for item in paquete.paquetes_productos:
            producto = db_session.query(Productos).filter_by(id_producto=item.id_producto).first()
            if producto: 
                producto.cantidad -= item.cantidad
        
        db_session.commit()
        return redirect(url_for('packages'))
        
    except Exception as e:
        print(f"Error confirmando paquete: {e}")
        db_session.rollback()
        return redirect(url_for('products'))

@app.route('/packages/cancel/<int:id>', methods=['POST'])
@requiere_login
def cancel_package(id):
    paquete = db_session.query(Paquetes).filter_by(id_paquete=id).first()
    if paquete: 
        db_session.delete(paquete)
        db_session.commit()
    return redirect(url_for('products'))

@app.route('/packages/delete/<int:id>', methods=['POST'])
@requiere_login
@requiere_rol('user', 'admin', 'boss')
def delete_package(id):
    paquete = db_session.query(Paquetes).filter_by(id_paquete=id).first()
    if paquete:
        db_session.delete(paquete)
        db_session.commit()
    return redirect(url_for('packages'))

# ===== GESTIÓN DE EMPLEADOS =====
@app.route('/employees')
@requiere_login
@requiere_rol('admin', 'boss')
def employees():
    pagina = request.args.get('pagina', 1, type=int)
    busqueda = request.args.get('busqueda', '').strip()
    por_pagina = 10
    
    # Consulta con búsqueda y paginación
    if busqueda:
        empleados_query = buscar_empleados(busqueda)
    else:
        empleados_query = db_session.query(Empleados)
    
    empleados_paginados = paginate(empleados_query, pagina, por_pagina)
    
    roles = db_session.query(Roles).all()
    return render_template('pages/management_employees.html', 
                         empleados=empleados_paginados.items,
                         pagination=empleados_paginados,
                         busqueda=busqueda,
                         roles=roles,
                         usuario=get_usuario_actual(),
                         perfil=get_perfil_usuario_actual())

@app.route('/employees/add', methods=['POST'])
@requiere_login
@requiere_rol('admin', 'boss')
def add_employee():
    try:
        if db_session.query(Empleados).filter_by(nombre_usuario=request.form['nombre_usuario']).first():
            return redirect(url_for('employees'))
        
        usuario_actual = get_usuario_actual()
        rol_solicitado_id = int(request.form.get('id_rol', 1))
        
        rol_user = db_session.query(Roles).filter_by(nombre='user').first()
        if not rol_user:
            rol_user = crear_rol_user_si_no_existe()
        
        if not puede_cambiar_rol(usuario_actual, rol_solicitado_id):
            rol_solicitado_id = rol_user.id_rol
        
        empleado = Empleados(
            nombre_usuario=request.form['nombre_usuario'],
            contraseña=request.form['contraseña'],
            telefono=request.form['telefono'],
            id_rol=rol_solicitado_id
        )
        if 'activo' in request.form:
            empleado.activo = bool(int(request.form['activo']))
        else:
            empleado.activo = True
        
        db_session.add(empleado)
        db_session.flush()
        
        perfil = Perfiles_Empleados(
            nombre=request.form.get('nombre', ''),
            apellidoP=request.form.get('apellidoP', ''),
            apellidoM=request.form.get('apellidoM', ''),
            email=request.form.get('email', ''),
            colonia=request.form.get('colonia', ''),
            calle=request.form.get('calle', ''),
            no_exterior=request.form.get('no_exterior', ''),
            id_empleado=empleado.id_empleado
        )
        foto_data = manejar_imagen(request.files.get('foto_perfil'))
        if foto_data: 
            perfil.foto_perfil = foto_data
        db_session.add(perfil)
        db_session.commit()
        
        print(f"Empleado {empleado.nombre_usuario} agregado exitosamente")
        
    except Exception as e: 
        print(f"Error agregando empleado: {e}")
        db_session.rollback()
    
    return redirect(url_for('employees'))

@app.route('/employees/edit/<int:id>', methods=['POST'])
@requiere_login
@requiere_rol('admin', 'boss')
def edit_employee(id):
    empleado = db_session.query(Empleados).filter_by(id_empleado=id).first()
    usuario_actual = get_usuario_actual()
    
    if empleado and puede_editar_empleado(usuario_actual, id):
        try:
            empleado.telefono = request.form.get('telefono', empleado.telefono)
            
            if 'activo' in request.form:
                empleado.activo = bool(int(request.form['activo']))
            
            # Solo boss puede cambiar roles
            rol_actual = get_rol_usuario_actual()
            if rol_actual == 'boss' and 'id_rol' in request.form:
                nuevo_rol_id = int(request.form['id_rol'])
                if puede_cambiar_rol(usuario_actual, nuevo_rol_id):
                    empleado.id_rol = nuevo_rol_id
            
            # Actualiza el perfil
            perfil = empleado.perfil
            if perfil:
                campos_perfil = ['nombre', 'apellidoP', 'apellidoM', 'email', 'colonia', 'calle', 'no_exterior']
                for campo in campos_perfil:
                    if request.form.get(campo):
                        setattr(perfil, campo, request.form[campo])
                
                foto_data = manejar_imagen(request.files.get('foto_perfil'))
                if foto_data: 
                    perfil.foto_perfil = foto_data
            
            db_session.commit()
        except Exception as e: 
            print(f"Error editando empleado: {e}")
            db_session.rollback()
    
    return redirect(url_for('employees'))

@app.route('/employees/delete/<int:id>', methods=['POST'])
@requiere_login
@requiere_rol('admin', 'boss')
def delete_employee(id):
    empleado = db_session.query(Empleados).filter_by(id_empleado=id).first()
    usuario_actual = get_usuario_actual()
    
    if (empleado and empleado.id_empleado != usuario_actual.id_empleado and 
        puede_editar_empleado(usuario_actual, id)):
        db_session.delete(empleado)
        db_session.commit()
    
    return redirect(url_for('employees'))

# ===== RUTAS DE ARCHIVOS =====
@app.route('/profile_picture/<int:usuario_id>')
def profile_picture(usuario_id):
    empleado = db_session.query(Empleados).filter_by(id_empleado=usuario_id).first()
    if empleado and empleado.perfil and empleado.perfil.foto_perfil:
        return Response(empleado.perfil.foto_perfil, mimetype='image/jpeg')
    return redirect(url_for('static', filename='images/picture_profile_default.png'))

@app.route('/product_image/<int:producto_id>')
def product_image(producto_id):
    producto = db_session.query(Productos).filter_by(id_producto=producto_id).first()
    if producto and producto.imagen:
        try:
            imagen = Image.open(BytesIO(producto.imagen))
            formato = imagen.format.lower() if imagen.format else 'jpeg'
            
            mime_types = {
                'jpeg': 'image/jpeg',
                'jpg': 'image/jpeg', 
                'png': 'image/png',
                'gif': 'image/gif',
                'webp': 'image/webp'
            }
            
            mimetype = mime_types.get(formato, 'image/jpeg')
            return Response(producto.imagen, mimetype=mimetype)
            
        except Exception as e:
            print(f"Error detectando formato de imagen: {e}")
            return Response(producto.imagen, mimetype='image/jpeg')
    
    return redirect(url_for('static', filename='images/product_default.png'))

# ===== RUTAS DE PERFIL =====
@app.route('/profile')
@requiere_login
def profile():
    return render_template('auth/profile.html', 
                         usuario=get_usuario_actual(),
                         perfil=get_perfil_usuario_actual())

@app.route('/profile/edit', methods=['GET', 'POST'])
@requiere_login
def profile_edit():
    usuario = get_usuario_actual()
    perfil = get_perfil_usuario_actual()
    
    if request.method == 'POST':
        try:
            # Actualiza los datos
            if request.form.get('telefono'):
                usuario.telefono = request.form['telefono']
            
            # Actualiza el perfil
            if perfil:
                campos_perfil = ['nombre', 'apellidoP', 'apellidoM', 'email', 'colonia', 'calle', 'no_exterior']
                for campo in campos_perfil:
                    if request.form.get(campo):
                        setattr(perfil, campo, request.form[campo])
                
                foto_data = manejar_imagen(request.files.get('foto_perfil'))
                if foto_data: 
                    perfil.foto_perfil = foto_data
            
            db_session.commit()
            return redirect(url_for('profile'))
        except Exception as e: 
            print(f"Error editando perfil: {e}")
    
    return render_template('auth/profile_edit.html', 
                         usuario=usuario, 
                         perfil=perfil)

@app.route('/profile/delete_picture', methods=['POST'])
@requiere_login
def delete_profile_picture():
    perfil = get_perfil_usuario_actual()
    if perfil:
        perfil.foto_perfil = None
        db_session.commit()
    return redirect(url_for('profile'))

@app.route('/profile/other/<int:id>')
@requiere_login
@requiere_rol('admin', 'boss')
def profile_other(id):
    empleado = db_session.query(Empleados).filter_by(id_empleado=id).first()
    if not empleado:
        return redirect(url_for('employees'))
    
    perfil_empleado = empleado.perfil
    return render_template('auth/profile_other.html', 
                         empleado=empleado, 
                         perfil=perfil_empleado,
                         usuario=get_usuario_actual(),
                         perfil_actual=get_perfil_usuario_actual())

# ===== RUTAS DE COMPATIBILIDAD =====
@app.route('/get_foto_perfil/<int:usuario_id>')
def get_foto_perfil(usuario_id):
    return profile_picture(usuario_id)

# ===== CONFIGURACIÓN =====
@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

if __name__ == '__main__':
    app.run(debug=False)