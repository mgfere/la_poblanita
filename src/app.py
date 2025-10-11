from flask import Flask, redirect, render_template, request, session, url_for, Response
from functools import wraps
from database import db_session
from database.models import Empleados, Productos, Paquetes, PaqueteProducto
import json

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'

# ===== FUNCIONES AUXILIARES =====
def get_usuario_actual():
    return db_session.query(Empleados).filter_by(id_empleado=session['usuario_id']).first() if 'usuario_id' in session else None

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
            if not usuario or usuario.rol not in roles:
                # Renderiza el template de acceso denegado
                return render_template('auth/access_denied.html', usuario=usuario)
            return f(*args, **kwargs)
        return decorated_function
    return decorador

def puede_editar_empleado(usuario_actual, empleado_id):
    if usuario_actual.rol == 'boss': return True
    elif usuario_actual.rol == 'admin':
        empleado = db_session.query(Empleados).filter_by(id_empleado=empleado_id).first()
        return empleado and empleado.rol == 'user'
    return False

def puede_cambiar_rol(usuario_actual, nuevo_rol):
    if usuario_actual.rol == 'boss': return True
    elif usuario_actual.rol == 'admin': return nuevo_rol == 'user'
    return False

def manejar_imagen(archivo):
    if archivo and archivo.filename and archivo.content_length <= 15 * 1024 * 1024:
        return archivo.read()
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

# ===== RUTAS DE AUTENTICACIÓN =====
@app.route('/')
def index(): return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = db_session.query(Empleados).filter_by(nombre_usuario=request.form['nombre_usuario']).first()
        if usuario and usuario.verificar_contraseña(request.form['contraseña']):
            session['usuario_id'] = usuario.id_empleado
            return redirect(url_for('home'))
        return render_template('auth/login.html', error='Usuario o contraseña incorrectos')
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if db_session.query(Empleados).filter_by(nombre_usuario=request.form['nombre_usuario']).first():
            return render_template('auth/register.html', error='El usuario ya existe')
        usuario = Empleados(request.form['telefono'], request.form['nombre_usuario'], request.form['contraseña'])
        db_session.add(usuario)
        db_session.commit()
        return redirect(url_for('login'))
    return render_template('auth/register.html')

@app.route('/logout')
def logout():
    session.pop('usuario_id', None)
    return redirect(url_for('login'))

# ===== RUTAS PRINCIPALES =====
@app.route('/home')
@requiere_login
def home():
    return render_template('pages/home.html', usuario=get_usuario_actual())

# ===== GESTIÓN DE PRODUCTOS =====
@app.route('/products')
@requiere_login
def products():  # QUITADO: @requiere_rol('admin', 'boss')
    return render_template('pages/management_products.html', productos=db_session.query(Productos).all(), usuario=get_usuario_actual())

@app.route('/products/add', methods=['POST'])
@requiere_login
@requiere_rol('admin', 'boss')  # Solo admin/boss pueden agregar
def add_product():
    try:
        producto = Productos(request.form['nombre'], int(request.form['cantidad']), session['usuario_id'])
        imagen_data = manejar_imagen(request.files.get('imagen'))
        if imagen_data: producto.imagen = imagen_data
        db_session.add(producto)
        db_session.commit()
    except Exception as e: print(f"Error agregando producto: {e}")
    return redirect(url_for('products'))

@app.route('/products/edit/<int:id>', methods=['POST'])
@requiere_login
@requiere_rol('admin', 'boss')  # Solo admin/boss pueden editar
def edit_product(id):
    producto = db_session.query(Productos).filter_by(id_producto=id).first()
    if producto:
        try:
            producto.nombre, producto.cantidad = request.form['nombre'], int(request.form['cantidad'])
            imagen_data = manejar_imagen(request.files.get('imagen'))
            if imagen_data: producto.imagen = imagen_data
            db_session.commit()
        except Exception as e: print(f"Error editando producto: {e}")
    return redirect(url_for('products'))

@app.route('/products/delete/<int:id>', methods=['POST'])
@requiere_login
@requiere_rol('admin', 'boss')
def delete_product(id):
    producto = db_session.query(Productos).filter_by(id_producto=id).first()
    if producto:
        # Verificar si el producto está en algún paquete
        paquetes_con_producto = db_session.query(PaqueteProducto).filter_by(id_producto=id).all()
        
        if paquetes_con_producto:
            # Obtener información de los paquetes que contienen este producto
            ids_paquetes = [p.id_paquete for p in paquetes_con_producto]
            error_msg = f"""
            No se puede eliminar el producto '{producto.nombre}' porque está siendo usado en los siguientes paquetes:
            {', '.join([f'PQ-{pid}' for pid in ids_paquetes])}
            
            Por favor, elimina primero los paquetes que contienen este producto antes de eliminarlo.
            """
            return render_template('pages/management_products.html', 
                                productos=db_session.query(Productos).all(), 
                                usuario=get_usuario_actual(),
                                error=error_msg)
        else:
            # Eliminar el producto si no está en uso
            db_session.delete(producto)
            db_session.commit()
    
    return redirect(url_for('products'))

# ===== GESTIÓN DE PAQUETES =====
@app.route('/packages/generate', methods=['POST'])
@requiere_login
def generate_package():
    try:
        productos_data = request.form.get('productos_data')
        if not productos_data: return redirect(url_for('products'))
        
        productos_seleccionados = json.loads(productos_data)
        insuficientes = validar_stock_paquete(productos_seleccionados)
        
        if insuficientes:
            error_msg = "No hay suficiente stock para:\n" + "\n".join([f"- {p['nombre']}: Solicitado {p['solicitado']}, Disponible {p['disponible']}" for p in insuficientes])
            return render_template('pages/management_products.html', productos=db_session.query(Productos).all(), usuario=get_usuario_actual(), error=error_msg)
        
        paquete = Paquetes()
        db_session.add(paquete)
        db_session.flush()
        
        # Guardar información de productos para el template
        productos_del_paquete = []
        
        for item in productos_seleccionados:
            producto = db_session.query(Productos).filter_by(id_producto=item['id']).first()
            if producto and producto.cantidad >= item['cantidad']:
                paquete_producto = PaqueteProducto(
                    id_paquete=paquete.id_paquete,
                    id_producto=producto.id_producto,
                    cantidad=item['cantidad']
                )
                db_session.add(paquete_producto)
                # Guardar información para el template
                productos_del_paquete.append({
                    'producto': producto,
                    'cantidad': item['cantidad']
                })
        
        db_session.commit()
        
        # Pasar los productos directamente al template
        return render_template('pages/confirm_package.html', 
                             paquete=paquete, 
                             productos_del_paquete=productos_del_paquete,
                             usuario=get_usuario_actual())
        
    except Exception as e:
        print(f"Error generando paquete: {e}")
        db_session.rollback()
        return redirect(url_for('products'))

@app.route('/packages/confirm/<int:id>', methods=['POST'])
@requiere_login
def confirm_package(id):  # QUITADO: @requiere_rol('admin', 'boss')
    try:
        paquete = db_session.query(Paquetes).filter_by(id_paquete=id).first()
        if not paquete: return redirect(url_for('products'))
        
        insuficientes = []
        for item in paquete.productos:
            producto = db_session.query(Productos).filter_by(id_producto=item.id_producto).first()
            if producto and producto.cantidad < item.cantidad:
                insuficientes.append({'nombre': producto.nombre, 'solicitado': item.cantidad, 'disponible': producto.cantidad})
        
        if insuficientes:
            db_session.delete(paquete)
            db_session.commit()
            error_msg = "Stock insuficiente:\n" + "\n".join([f"- {p['nombre']}: Solicitado {p['solicitado']}, Disponible {p['disponible']}" for p in insuficientes])
            return render_template('pages/management_products.html', productos=db_session.query(Productos).all(), usuario=get_usuario_actual(), error=error_msg)
        
        for item in paquete.productos:
            producto = db_session.query(Productos).filter_by(id_producto=item.id_producto).first()
            if producto: producto.cantidad -= item.cantidad
        
        db_session.commit()
        return redirect(url_for('packages'))
        
    except Exception as e:
        print(f"Error confirmando paquete: {e}")
        db_session.rollback()
        return redirect(url_for('products'))

@app.route('/packages/cancel/<int:id>', methods=['POST'])
@requiere_login
def cancel_package(id):  # QUITADO: @requiere_rol('admin', 'boss')
    paquete = db_session.query(Paquetes).filter_by(id_paquete=id).first()
    if paquete: db_session.delete(paquete); db_session.commit()
    return redirect(url_for('products'))

@app.route('/packages')
@requiere_login
def packages():  # QUITADO: @requiere_rol('admin', 'boss')
    return render_template('pages/management_packages.html', paquetes=db_session.query(Paquetes).filter(Paquetes.productos.any()).all(), usuario=get_usuario_actual())

@app.route('/packages/delete/<int:id>', methods=['POST'])
@requiere_login
@requiere_rol('admin', 'boss')  # Solo admin/boss pueden eliminar paquetes
def delete_package(id):
    paquete = db_session.query(Paquetes).filter_by(id_paquete=id).first()
    if paquete:
        db_session.delete(paquete)
        db_session.commit()
    return redirect(url_for('packages'))

# ===== GESTIÓN DE EMPLEADOS =====
@app.route('/employees')
@requiere_login
@requiere_rol('admin', 'boss')  # Solo admin/boss pueden ver empleados
def employees():
    return render_template('pages/management_employees.html', empleados=db_session.query(Empleados).all(), usuario=get_usuario_actual())

@app.route('/employees/add', methods=['POST'])
@requiere_login
@requiere_rol('admin', 'boss')
def add_employee():
    try:
        if db_session.query(Empleados).filter_by(nombre_usuario=request.form['nombre_usuario']).first():
            return redirect(url_for('employees'))
        
        usuario_actual = get_usuario_actual()
        rol_solicitado = request.form.get('rol', 'user')
        if not puede_cambiar_rol(usuario_actual, rol_solicitado): rol_solicitado = 'user'
        
        empleado = Empleados(request.form['telefono'], request.form['nombre_usuario'], request.form['contraseña'], rol_solicitado)
        
        for campo in ['nombre', 'apellidoP', 'apellidoM', 'email', 'colonia', 'calle', 'no_exterior']:
            if request.form.get(campo): setattr(empleado, campo, request.form[campo])
        
        foto_data = manejar_imagen(request.files.get('foto_perfil'))
        if foto_data: empleado.foto_perfil = foto_data
        
        db_session.add(empleado)
        db_session.commit()
    except Exception as e: print(f"Error agregando empleado: {e}")
    return redirect(url_for('employees'))

@app.route('/employees/edit/<int:id>', methods=['POST'])
@requiere_login
@requiere_rol('admin', 'boss')
def edit_employee(id):
    empleado = db_session.query(Empleados).filter_by(id_empleado=id).first()
    usuario_actual = get_usuario_actual()
    
    if empleado and puede_editar_empleado(usuario_actual, id):
        try:
            for campo in ['nombre', 'apellidoP', 'apellidoM', 'email', 'telefono', 'colonia', 'calle', 'no_exterior']:
                if request.form.get(campo): setattr(empleado, campo, request.form[campo])
            
            if usuario_actual.rol == 'boss' and 'rol' in request.form:
                nuevo_rol = request.form['rol']
                if puede_cambiar_rol(usuario_actual, nuevo_rol): empleado.rol = nuevo_rol
            
            foto_data = manejar_imagen(request.files.get('foto_perfil'))
            if foto_data: empleado.foto_perfil = foto_data
            
            db_session.commit()
        except Exception as e: print(f"Error editando empleado: {e}")
    return redirect(url_for('employees'))

@app.route('/employees/delete/<int:id>', methods=['POST'])
@requiere_login
@requiere_rol('admin', 'boss')
def delete_employee(id):
    empleado = db_session.query(Empleados).filter_by(id_empleado=id).first()
    usuario_actual = get_usuario_actual()
    
    if empleado and empleado.id_empleado != usuario_actual.id_empleado and puede_editar_empleado(usuario_actual, id):
        db_session.delete(empleado)
        db_session.commit()
    return redirect(url_for('employees'))

@app.route('/employees/update_role/<int:id>', methods=['POST'])
@requiere_login
@requiere_rol('boss')
def update_employee_role(id):
    empleado = db_session.query(Empleados).filter_by(id_empleado=id).first()
    if empleado and empleado.id_empleado != get_usuario_actual().id_empleado:
        nuevo_rol = request.form.get('rol')
        if nuevo_rol in ['user', 'admin', 'boss']:
            empleado.rol = nuevo_rol
            db_session.commit()
    return redirect(url_for('employees'))

# ===== RUTAS DE ARCHIVOS =====
@app.route('/profile_picture/<int:usuario_id>')
def profile_picture(usuario_id):
    usuario = db_session.query(Empleados).filter_by(id_empleado=usuario_id).first()
    if usuario and usuario.foto_perfil: return Response(usuario.foto_perfil, mimetype='image/jpeg')
    return redirect(url_for('static', filename='images/picture_profile_default.png'))

@app.route('/product_image/<int:producto_id>')
def product_image(producto_id):
    producto = db_session.query(Productos).filter_by(id_producto=producto_id).first()
    if producto and producto.imagen: return Response(producto.imagen, mimetype='image/jpeg')
    return redirect(url_for('static', filename='images/product_default.png'))

# ===== RUTAS DE PERFIL =====
@app.route('/profile')
@requiere_login
def profile():
    return render_template('auth/profile.html', usuario=get_usuario_actual())

@app.route('/profile/edit', methods=['GET', 'POST'])
@requiere_login
def profile_edit():
    usuario = get_usuario_actual()
    if request.method == 'POST':
        try:
            for campo in ['nombre', 'apellidoP', 'apellidoM', 'email', 'telefono', 'colonia', 'calle', 'no_exterior']:
                if request.form.get(campo): setattr(usuario, campo, request.form[campo])
            foto_data = manejar_imagen(request.files.get('foto_perfil'))
            if foto_data: usuario.foto_perfil = foto_data
            db_session.commit()
            return redirect(url_for('profile'))
        except Exception as e: print(f"Error editando perfil: {e}")
    return render_template('auth/profile_edit.html', usuario=usuario)

@app.route('/profile/delete_picture', methods=['POST'])
@requiere_login
def delete_profile_picture():
    usuario = get_usuario_actual()
    usuario.foto_perfil = None
    db_session.commit()
    return redirect(url_for('profile'))

# ===== RUTAS DE COMPATIBILIDAD =====
@app.route('/get_foto_perfil/<int:usuario_id>')
def get_foto_perfil(usuario_id):
    return profile_picture(usuario_id)

# ===== CONFIGURACIÓN =====
@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

if __name__ == '__main__':
    app.run(debug=True)