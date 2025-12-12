# -*- coding: utf-8 -*-
"""
SISTEMA COMPLETO DE GESTIÓN DE VUELOS CON CRUD COMPLETO
Incluye: Crear, Leer, Actualizar, Eliminar (CRUD) para todas las tablas
Sistema de reservas automáticas
"""

from flask import Flask, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
import bcrypt
import psycopg2
import psycopg2.extras
import os
import json
import random
import string
from functools import wraps

# ==================== CONFIGURACIÓN ====================
app = Flask(__name__)
app.secret_key = 'clave-secreta-muy-segura-para-produccion-123'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==================== CONEXIÓN BASE DE DATOS ====================
def get_db_connection():
    """Conectar a PostgreSQL usando psycopg2 con SSL"""
    try:
        conn = psycopg2.connect(
            host='dpg-d4u0hcfgi27c73a9b4rg-a.virginia-postgres.render.com',
            database='sistema_2tdl',
            user='yova',
            password='j0smlHpbZTp1qgZsruJUHI9XW7Gv9gtt',
            port=5432,
            sslmode='require'  # SSL obligatorio
        )
        return conn
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {str(e)[:100]}")
        return None
# ==================== CREAR TABLAS AUTOMÁTICAMENTE ====================
def init_database():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Tabla usuarios
        cur.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                nombre VARCHAR(100) NOT NULL,
                email VARCHAR(100),
                rol VARCHAR(20) NOT NULL CHECK (rol IN ('admin', 'responsable', 'empleado', 'consulta')),
                activo BOOLEAN DEFAULT TRUE,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla aerolíneas
        cur.execute('''
            CREATE TABLE IF NOT EXISTS aerolineas (
                id SERIAL PRIMARY KEY,
                codigo VARCHAR(3) UNIQUE NOT NULL,
                nombre VARCHAR(100) NOT NULL,
                pais_origen VARCHAR(50),
                fecha_fundacion DATE,
                activa BOOLEAN DEFAULT TRUE,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla vuelos
        cur.execute('''
            CREATE TABLE IF NOT EXISTS vuelos (
                id SERIAL PRIMARY KEY,
                numero_vuelo VARCHAR(10) NOT NULL,
                aerolinea_id INTEGER REFERENCES aerolineas(id),
                origen VARCHAR(100) NOT NULL,
                destino VARCHAR(100) NOT NULL,
                fecha_salida TIMESTAMP NOT NULL,
                fecha_llegada TIMESTAMP NOT NULL,
                capacidad INTEGER NOT NULL,
                asientos_disponibles INTEGER NOT NULL,
                estado VARCHAR(20) DEFAULT 'programado' 
                    CHECK (estado IN ('programado', 'en_vuelo', 'aterrizado', 'cancelado')),
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla pasajeros
        cur.execute('''
            CREATE TABLE IF NOT EXISTS pasajeros (
                id SERIAL PRIMARY KEY,
                pasaporte VARCHAR(20) UNIQUE NOT NULL,
                nombre VARCHAR(100) NOT NULL,
                apellido VARCHAR(100) NOT NULL,
                nacionalidad VARCHAR(50),
                fecha_nacimiento DATE,
                telefono VARCHAR(20),
                email VARCHAR(100),
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla reservas
        cur.execute('''
            CREATE TABLE IF NOT EXISTS reservas (
                id SERIAL PRIMARY KEY,
                codigo_reserva VARCHAR(10) UNIQUE NOT NULL,
                vuelo_id INTEGER REFERENCES vuelos(id),
                pasajero_id INTEGER REFERENCES pasajeros(id),
                fecha_reserva TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                asiento VARCHAR(5),
                clase VARCHAR(20) DEFAULT 'economica' 
                    CHECK (clase IN ('economica', 'ejecutiva', 'primera')),
                precio DECIMAL(10,2),
                estado VARCHAR(20) DEFAULT 'confirmada' 
                    CHECK (estado IN ('confirmada', 'cancelada')),
                UNIQUE(vuelo_id, pasajero_id, asiento)
            )
        ''')
        
        # Tabla logs
        cur.execute('''
            CREATE TABLE IF NOT EXISTS logs_auditoria (
                id SERIAL PRIMARY KEY,
                usuario_id INTEGER,
                accion VARCHAR(50) NOT NULL,
                tabla_afectada VARCHAR(50),
                registro_id INTEGER,
                detalles TEXT,
                ip_address VARCHAR(45),
                fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Verificar si ya hay usuarios
        cur.execute("SELECT COUNT(*) FROM usuarios")
        if cur.fetchone()[0] == 0:
            # Usuarios por defecto
            usuarios_default = [
                ('admin', bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), 
                 'Administrador', 'admin@sistema.com', 'admin'),
                ('responsable', bcrypt.hashpw('responsable123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), 
                 'Responsable', 'responsable@sistema.com', 'responsable'),
                ('empleado1', bcrypt.hashpw('empleado123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), 
                 'Empleado Uno', 'empleado@sistema.com', 'empleado'),
                ('consulta', bcrypt.hashpw('consulta123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'), 
                 'Usuario Consulta', 'consulta@sistema.com', 'consulta')
            ]
            
            for user in usuarios_default:
                cur.execute(
                    "INSERT INTO usuarios (username, password_hash, nombre, email, rol) VALUES (%s, %s, %s, %s, %s)",
                    user
                )
            
            # Aerolíneas por defecto
            aerolineas_default = [
                ('AA', 'American Airlines', 'Estados Unidos', '1930-01-01'),
                ('DL', 'Delta Air Lines', 'Estados Unidos', '1924-03-02'),
                ('UA', 'United Airlines', 'Estados Unidos', '1926-04-06'),
                ('LA', 'LATAM Airlines', 'Chile', '1929-03-05'),
                ('AV', 'Avianca', 'Colombia', '1919-12-05')
            ]
            
            for aero in aerolineas_default:
                cur.execute(
                    "INSERT INTO aerolineas (codigo, nombre, pais_origen, fecha_fundacion) VALUES (%s, %s, %s, %s)",
                    aero
                )
            
            # Algunos vuelos de ejemplo
            vuelos_default = [
                ('AA123', 1, 'Miami (MIA)', 'Nueva York (JFK)', '2025-12-15 08:00:00', '2025-12-15 11:00:00', 150, 150),
                ('DL456', 2, 'Atlanta (ATL)', 'Los Ángeles (LAX)', '2025-12-16 10:00:00', '2025-12-16 13:00:00', 200, 200),
                ('UA789', 3, 'Chicago (ORD)', 'Dallas (DFW)', '2025-12-17 14:00:00', '2025-12-17 16:00:00', 180, 180),
                ('LA101', 4, 'Santiago (SCL)', 'Lima (LIM)', '2025-12-18 09:00:00', '2025-12-18 11:00:00', 220, 220),
                ('AV202', 5, 'Bogotá (BOG)', 'Miami (MIA)', '2025-12-19 07:00:00', '2025-12-19 10:00:00', 170, 170)
            ]
            
            for vuelo in vuelos_default:
                cur.execute(
                    "INSERT INTO vuelos (numero_vuelo, aerolinea_id, origen, destino, fecha_salida, fecha_llegada, capacidad, asientos_disponibles) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    vuelo
                )
            
            # Algunos pasajeros de ejemplo
            pasajeros_default = [
                ('P1234567', 'Juan', 'Pérez', 'México', '1985-05-15', '555-1234', 'juan@email.com'),
                ('P7654321', 'María', 'García', 'España', '1990-08-20', '555-5678', 'maria@email.com'),
                ('P9876543', 'Carlos', 'Rodríguez', 'Colombia', '1988-03-10', '555-8765', 'carlos@email.com'),
                ('P4567890', 'Ana', 'López', 'Argentina', '1995-11-30', '555-4321', 'ana@email.com')
            ]
            
            for pasajero in pasajeros_default:
                cur.execute(
                    "INSERT INTO pasajeros (pasaporte, nombre, apellido, nacionalidad, fecha_nacimiento, telefono, email) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    pasajero
                )
            
            print("✅ Datos iniciales insertados")
        
        conn.commit()
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error inicializando BD: {e}")

# Ejecutar inicialización
print("🔧 Inicializando base de datos...")
init_database()

# ==================== MODELO USUARIO ====================
class User(UserMixin):
    def __init__(self, id, username, nombre, rol):
        self.id = id
        self.username = username
        self.nombre = nombre
        self.rol = rol

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM usuarios WHERE id = %s AND activo = TRUE', (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user:
        return User(user[0], user[1], user[3], user[5])
    return None

# ==================== DECORADORES Y FUNCIONES ====================
def role_required(*roles):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.rol not in roles:
                flash('No tiene permisos para acceder a esta página', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

def registrar_log(accion, tabla=None, registro_id=None, detalles=None):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        ip_address = request.remote_addr if request else '127.0.0.1'
        
        if detalles:
            detalles_str = json.dumps(detalles, ensure_ascii=False)
        else:
            detalles_str = None
        
        cur.execute('''
            INSERT INTO logs_auditoria (usuario_id, accion, tabla_afectada, registro_id, detalles, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (current_user.id, accion, tabla, registro_id, detalles_str, ip_address))
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error registrando log: {e}")

# ==================== FUNCIONES HTML ====================
def get_flashed_messages_html():
    from flask import get_flashed_messages
    messages = get_flashed_messages(with_categories=True)
    if not messages:
        return ''
    
    html = ''
    for category, message in messages:
        alert_class = 'alert-' + category if category else 'alert-info'
        html += f'''
        <div class="alert {alert_class} alert-dismissible fade show" role="alert">
            {message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        '''
    return html

def get_navbar():
    return f'''
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container-fluid">
            <a class="navbar-brand" href="/dashboard">
                <i class="bi bi-airplane"></i> Sistema Vuelos
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="/dashboard">
                            <i class="bi bi-speedometer2"></i> Dashboard
                        </a>
                    </li>
    ''' + get_menu_items() + '''
                </ul>
                <ul class="navbar-nav">
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                            <i class="bi bi-person-circle"></i> {current_user.nombre}
                            <span class="badge bg-light text-dark ms-1">{current_user.rol}</span>
                        </a>
                        <ul class="dropdown-menu dropdown-menu-end">
                            <li><a class="dropdown-item" href="/logout">
                                <i class="bi bi-box-arrow-right"></i> Cerrar Sesión
                            </a></li>
                        </ul>
                    </li>
                </ul>
            </div>
        </div>
    </nav>
    '''

def get_menu_items():
    rol = current_user.rol
    items = ''
    
    if rol in ['admin', 'responsable', 'empleado']:
        items += '''
        <li class="nav-item dropdown">
            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                <i class="bi bi-airplane-fill"></i> Operaciones
            </a>
            <ul class="dropdown-menu">
                <li><a class="dropdown-item" href="/vuelos">Vuelos</a></li>
                <li><a class="dropdown-item" href="/pasajeros">Pasajeros</a></li>
                <li><a class="dropdown-item" href="/reservas">Reservas</a></li>
                <li><a class="dropdown-item" href="/aerolineas">Aerolíneas</a></li>
            </ul>
        </li>
        '''
    
    if rol in ['admin', 'responsable']:
        items += '''
        <li class="nav-item">
            <a class="nav-link" href="/logs">
                <i class="bi bi-clock-history"></i> Logs
            </a>
        </li>
        '''
    
    if rol == 'admin':
        items += '''
        <li class="nav-item">
            <a class="nav-link" href="/usuarios">
                <i class="bi bi-people-fill"></i> Usuarios
            </a>
        </li>
        '''
    
    return items

def get_footer():
    return f'''
    <footer class="footer mt-5 py-3 bg-light border-top">
        <div class="container text-center">
            <span class="text-muted">
                Sistema de Gestión de Vuelos &copy; 2025 | 
                Usuario: {current_user.nombre} | 
                Rol: {current_user.rol} | 
                Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M")}
            </span>
        </div>
    </footer>
    '''

def get_base_html(title, content, extra_js=''):
    return f'''
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - Sistema Vuelos</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.1/font/bootstrap-icons.css">
        <style>
            body {{ background-color: #f8f9fa; }}
            .navbar {{ box-shadow: 0 2px 4px rgba(0,0,0,.1); }}
            .card {{ border: none; box-shadow: 0 0.125rem 0.25rem rgba(0,0,0,0.075); }}
            .stat-card {{ transition: transform 0.3s; cursor: pointer; }}
            .stat-card:hover {{ transform: translateY(-5px); }}
            .access-card {{ border-left: 4px solid #0d6efd; }}
            .access-card:hover {{ background-color: #f8f9fa; }}
            .btn-group-sm {{ white-space: nowrap; }}
        </style>
    </head>
    <body>
        {get_navbar()}
        
        <div class="container-fluid mt-3">
            {get_flashed_messages_html()}
            {content}
        </div>
        
        {get_footer()}
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        <script>
        function confirmarEliminacion() {{
            return confirm('¿Está seguro de eliminar este registro? Esta acción no se puede deshacer.');
        }}
        </script>
        {extra_js}
    </body>
    </html>
    '''

# ==================== RUTA LOGIN ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM usuarios WHERE username = %s AND activo = TRUE', (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):
            user_obj = User(user[0], user[1], user[3], user[5])
            login_user(user_obj, remember=True)
            registrar_log('LOGIN', detalles={'username': username, 'rol': user[5]})
            flash(f'¡Bienvenido, {user[3]}!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('Usuario o contraseña incorrectos', 'danger')
    
    return '''
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login - Sistema Vuelos</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.1/font/bootstrap-icons.css">
        <style>
            body { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding-top: 100px;
            }
            .login-card { 
                max-width: 400px; 
                margin: 0 auto;
                border-radius: 10px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="row justify-content-center">
                <div class="col-md-6 col-lg-4">
                    <div class="card login-card">
                        <div class="card-header bg-primary text-white text-center py-4">
                            <h4><i class="bi bi-airplane-fill"></i> Sistema de Vuelos</h4>
                            <p class="mb-0 mt-2">Inicio de Sesión</p>
                        </div>
                        <div class="card-body p-4">
    ''' + get_flashed_messages_html() + '''
                            <form method="POST" action="/login">
                                <div class="mb-3">
                                    <label for="username" class="form-label">Usuario</label>
                                    <input type="text" class="form-control" id="username" name="username" required autofocus>
                                </div>
                                <div class="mb-3">
                                    <label for="password" class="form-label">Contraseña</label>
                                    <input type="password" class="form-control" id="password" name="password" required>
                                </div>
                                <div class="d-grid gap-2">
                                    <button type="submit" class="btn btn-primary btn-lg">
                                        <i class="bi bi-box-arrow-in-right"></i> Iniciar Sesión
                                    </button>
                                </div>
                            </form>
                            
                            <hr class="my-4">
                            
                            <div class="alert alert-info">
                                <h6><i class="bi bi-info-circle"></i> Usuarios de Prueba:</h6>
                                <small>
                                    <strong>Admin:</strong> admin / admin123<br>
                                    <strong>Responsable:</strong> responsable / responsable123<br>
                                    <strong>Consulta:</strong> consulta / consulta123<br>
                                    <strong>Empleado:</strong> empleado1 / empleado123
                                </small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    '''

# ==================== DASHBOARD ====================
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    
    hoy = datetime.now().date()
    
    # Estadísticas
    cur.execute("SELECT COUNT(*) FROM vuelos WHERE DATE(fecha_salida) = %s", (hoy,))
    vuelos_hoy = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(DISTINCT p.id) FROM pasajeros p JOIN reservas r ON p.id = r.pasajero_id JOIN vuelos v ON r.vuelo_id = v.id WHERE DATE(v.fecha_salida) = %s", (hoy,))
    pasajeros_hoy = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM aerolineas WHERE activa = TRUE")
    aerolineas_activas = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM reservas WHERE fecha_reserva::date = %s", (hoy,))
    reservas_hoy = cur.fetchone()[0]
    
    # Proximos vuelos
    cur.execute("""
        SELECT v.*, a.nombre as aerolinea_nombre, a.codigo as aerolinea_codigo
        FROM vuelos v
        JOIN aerolineas a ON v.aerolinea_id = a.id
        WHERE v.fecha_salida >= NOW()
        ORDER BY v.fecha_salida
        LIMIT 5
    """)
    proximos_vuelos = cur.fetchall()
    
    cur.close()
    conn.close()
    
    # Generar HTML de estadísticas
    stats_html = f'''
    <div class="row mb-4">
        <div class="col-md-3">
            <div class="card text-white bg-primary stat-card" onclick="location.href='/vuelos'">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h5 class="card-title">Vuelos Hoy</h5>
                            <h2 class="card-text">{vuelos_hoy}</h2>
                        </div>
                        <i class="bi bi-airplane fs-1"></i>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-md-3">
            <div class="card text-white bg-success stat-card" onclick="location.href='/pasajeros'">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h5 class="card-title">Pasajeros Hoy</h5>
                            <h2 class="card-text">{pasajeros_hoy}</h2>
                        </div>
                        <i class="bi bi-people fs-1"></i>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-md-3">
            <div class="card text-white bg-info stat-card" onclick="location.href='/aerolineas'">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h5 class="card-title">Aerolíneas Activas</h5>
                            <h2 class="card-text">{aerolineas_activas}</h2>
                        </div>
                        <i class="bi bi-building fs-1"></i>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="col-md-3">
            <div class="card text-white bg-warning stat-card" onclick="location.href='/reservas'">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h5 class="card-title">Reservas Hoy</h5>
                            <h2 class="card-text">{reservas_hoy}</h2>
                        </div>
                        <i class="bi bi-ticket-perforated fs-1"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    '''
    
    # Generar HTML de accesos rápidos
    acceso_rapidos_html = '''
    <div class="card mb-4">
        <div class="card-header bg-primary text-white">
            <h5><i class="bi bi-lightning-charge"></i> Accesos Rápidos</h5>
        </div>
        <div class="card-body p-0">
            <div class="list-group list-group-flush">
    '''
    
    # ACCESOS RÁPIDOS SEGÚN ROL
    if current_user.rol in ['admin', 'responsable', 'empleado']:
        acceso_rapidos_html += '''
                <a href="/vuelos" class="list-group-item list-group-item-action access-card">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-1"><i class="bi bi-airplane text-primary"></i> Gestionar Vuelos</h6>
                            <small class="text-muted">Crear, editar, eliminar y ver vuelos</small>
                        </div>
                        <i class="bi bi-arrow-right text-muted"></i>
                    </div>
                </a>
                
                <a href="/pasajeros" class="list-group-item list-group-item-action access-card">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-1"><i class="bi bi-people text-success"></i> Gestionar Pasajeros</h6>
                            <small class="text-muted">Administrar información de pasajeros</small>
                        </div>
                        <i class="bi bi-arrow-right text-muted"></i>
                    </div>
                </a>
                
                <a href="/reservas" class="list-group-item list-group-item-action access-card">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-1"><i class="bi bi-ticket-perforated text-warning"></i> Gestionar Reservas</h6>
                            <small class="text-muted">Crear y cancelar reservas de vuelos</small>
                        </div>
                        <i class="bi bi-arrow-right text-muted"></i>
                    </div>
                </a>
                
                <a href="/nueva-reserva" class="list-group-item list-group-item-action access-card">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-1"><i class="bi bi-plus-circle text-success"></i> Nueva Reserva</h6>
                            <small class="text-muted">Asignar pasajero a vuelo</small>
                        </div>
                        <i class="bi bi-arrow-right text-muted"></i>
                    </div>
                </a>
        '''
    
    if current_user.rol in ['admin', 'responsable']:
        acceso_rapidos_html += '''
                <a href="/aerolineas" class="list-group-item list-group-item-action access-card">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-1"><i class="bi bi-building text-info"></i> Aerolíneas</h6>
                            <small class="text-muted">Administrar aerolíneas del sistema</small>
                        </div>
                        <i class="bi bi-arrow-right text-muted"></i>
                    </div>
                </a>
                
                <a href="/logs" class="list-group-item list-group-item-action access-card">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-1"><i class="bi bi-clock-history text-secondary"></i> Ver Logs</h6>
                            <small class="text-muted">Auditar acciones del sistema</small>
                        </div>
                        <i class="bi bi-arrow-right text-muted"></i>
                    </div>
                </a>
        '''
    
    if current_user.rol == 'admin':
        acceso_rapidos_html += '''
                <a href="/usuarios" class="list-group-item list-group-item-action access-card">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-1"><i class="bi bi-people-fill text-dark"></i> Usuarios</h6>
                            <small class="text-muted">Administrar usuarios del sistema</small>
                        </div>
                        <i class="bi bi-arrow-right text-muted"></i>
                    </div>
                </a>
        '''
    
    acceso_rapidos_html += '''
            </div>
        </div>
    </div>
    '''
    
    # Información del sistema
    if current_user.rol == 'admin':
        permisos = 'Control total del sistema (crear, modificar, eliminar cualquier registro)'
    elif current_user.rol == 'responsable':
        permisos = 'Gestionar registros (sin borrado masivo de tablas completas)'
    elif current_user.rol == 'empleado':
        permisos = 'Operaciones de venta, check-in y gestión básica'
    else:
        permisos = 'Solo consulta (no puede realizar modificaciones)'
    
    info_sistema_html = f'''
    <div class="card">
        <div class="card-header">
            <h5><i class="bi bi-info-circle"></i> Información del Sistema</h5>
        </div>
        <div class="card-body">
            <p><strong>Rol actual:</strong> <span class="badge bg-secondary">{current_user.rol}</span></p>
            <p><strong>Permisos:</strong> {permisos}</p>
            <p><strong>Usuario:</strong> {current_user.username}</p>
            <p><strong>Base de datos:</strong> PostgreSQL en Render</p>
            <hr>
            <small class="text-muted">
                Sistema de Gestión de Vuelos v2.0<br>
                Desarrollado para producción<br>
                Última actualización: {datetime.now().strftime("%d/%m/%Y %H:%M")}
            </small>
        </div>
    </div>
    '''
    
    # Próximos vuelos
    proximos_vuelos_html = '''
    <div class="card">
        <div class="card-header">
            <h5><i class="bi bi-airplane-engines"></i> Próximos Vuelos</h5>
        </div>
        <div class="card-body">
    '''
    
    if proximos_vuelos:
        proximos_vuelos_html += '''
            <div class="table-responsive">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>Vuelo</th>
                            <th>Aerolínea</th>
                            <th>Origen</th>
                            <th>Destino</th>
                            <th>Salida</th>
                            <th>Estado</th>
                            <th>Asientos</th>
                        </tr>
                    </thead>
                    <tbody>
        '''
        for vuelo in proximos_vuelos:
            estado_color = 'success' if vuelo[8] == 'programado' else 'warning' if vuelo[8] == 'en_vuelo' else 'info' if vuelo[8] == 'aterrizado' else 'danger'
            proximos_vuelos_html += f'''
                        <tr>
                            <td><strong>{vuelo[1]}</strong></td>
                            <td>{vuelo[14]} - {vuelo[13]}</td>
                            <td>{vuelo[3]}</td>
                            <td>{vuelo[4]}</td>
                            <td>{vuelo[5].strftime('%d/%m %H:%M')}</td>
                            <td><span class="badge bg-{estado_color}">{vuelo[8]}</span></td>
                            <td>{vuelo[7]}/{vuelo[6]}</td>
                        </tr>
            '''
        proximos_vuelos_html += '''
                    </tbody>
                </table>
            </div>
        '''
    else:
        proximos_vuelos_html += '<p class="text-muted text-center py-4">No hay vuelos programados</p>'
    
    proximos_vuelos_html += '''
        </div>
    </div>
    '''
    
    # Contenido completo
    content = f'''
    <div class="row mb-4">
        <div class="col-12">
            <h1><i class="bi bi-speedometer2"></i> Dashboard</h1>
            <p class="lead">Bienvenido, {current_user.nombre}! <span class="badge bg-secondary">{current_user.rol}</span></p>
            <p class="text-muted">Fecha: {hoy.strftime("%d/%m/%Y")}</p>
        </div>
    </div>

    {stats_html}

    <div class="row">
        <div class="col-md-4">
            {acceso_rapidos_html}
            {info_sistema_html}
        </div>
        
        <div class="col-md-8">
            {proximos_vuelos_html}
        </div>
    </div>
    '''
    
    return get_base_html('Dashboard', content)

# ==================== RUTAS BÁSICAS RESTANTES ====================
@app.route('/vuelos')
@login_required
def listar_vuelos():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM vuelos ORDER BY fecha_salida')
    vuelos = cur.fetchall()
    cur.close()
    conn.close()
    
    vuelos_html = ''
    for vuelo in vuelos:
        estado_color = 'success' if vuelo[8] == 'programado' else 'warning' if vuelo[8] == 'en_vuelo' else 'info' if vuelo[8] == 'aterrizado' else 'danger'
        vuelos_html += f'''
        <tr>
            <td><strong>{vuelo[1]}</strong></td>
            <td>{vuelo[3]}</td>
            <td>{vuelo[4]}</td>
            <td>{vuelo[5].strftime('%d/%m %H:%M')}</td>
            <td><span class="badge bg-{estado_color}">{vuelo[8]}</span></td>
            <td>{vuelo[7]}/{vuelo[6]}</td>
        </tr>
        '''
    
    content = f'''
    <div class="row mb-4">
        <div class="col-12">
            <h1><i class="bi bi-airplane"></i> Gestionar Vuelos</h1>
        </div>
    </div>
    
    <div class="card">
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>Vuelo</th>
                            <th>Origen</th>
                            <th>Destino</th>
                            <th>Salida</th>
                            <th>Estado</th>
                            <th>Asientos</th>
                        </tr>
                    </thead>
                    <tbody>
                        {vuelos_html}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    '''
    
    return get_base_html('Gestionar Vuelos', content)

@app.route('/pasajeros')
@login_required
def listar_pasajeros():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM pasajeros ORDER BY apellido, nombre')
    pasajeros = cur.fetchall()
    cur.close()
    conn.close()
    
    pasajeros_html = ''
    for p in pasajeros:
        pasajeros_html += f'''
        <tr>
            <td><code>{p[1]}</code></td>
            <td>{p[2]}</td>
            <td>{p[3]}</td>
            <td>{p[4] if p[4] else 'N/A'}</td>
            <td>{p[7] if p[7] else 'N/A'}</td>
        </tr>
        '''
    
    content = f'''
    <div class="row mb-4">
        <div class="col-12">
            <h1><i class="bi bi-people"></i> Gestionar Pasajeros</h1>
        </div>
    </div>
    
    <div class="card">
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>Pasaporte</th>
                            <th>Nombre</th>
                            <th>Apellido</th>
                            <th>Nacionalidad</th>
                            <th>Email</th>
                        </tr>
                    </thead>
                    <tbody>
                        {pasajeros_html}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    '''
    
    return get_base_html('Gestionar Pasajeros', content)

@app.route('/reservas')
@login_required
def listar_reservas():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM reservas ORDER BY fecha_reserva DESC')
    reservas = cur.fetchall()
    cur.close()
    conn.close()
    
    reservas_html = ''
    for r in reservas:
        estado_color = 'success' if r[8] == 'confirmada' else 'danger'
        reservas_html += f'''
        <tr>
            <td><code>{r[1]}</code></td>
            <td>{r[2]}</td>
            <td>{r[3]}</td>
            <td>{r[4].strftime('%d/%m %H:%M')}</td>
            <td><span class="badge bg-{estado_color}">{r[8]}</span></td>
        </tr>
        '''
    
    content = f'''
    <div class="row mb-4">
        <div class="col-12">
            <h1><i class="bi bi-ticket-perforated"></i> Reservas</h1>
        </div>
    </div>
    
    <div class="card">
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>Código</th>
                            <th>Vuelo ID</th>
                            <th>Pasajero ID</th>
                            <th>Fecha</th>
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                        {reservas_html}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    '''
    
    return get_base_html('Reservas', content)

@app.route('/aerolineas')
@login_required
def listar_aerolineas():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM aerolineas ORDER BY nombre')
    aerolineas = cur.fetchall()
    cur.close()
    conn.close()
    
    aerolineas_html = ''
    for a in aerolineas:
        estado = 'Activa' if a[5] else 'Inactiva'
        color = 'success' if a[5] else 'danger'
        aerolineas_html += f'''
        <tr>
            <td><strong>{a[1]}</strong></td>
            <td>{a[2]}</td>
            <td>{a[3] if a[3] else 'N/A'}</td>
            <td><span class="badge bg-{color}">{estado}</span></td>
        </tr>
        '''
    
    content = f'''
    <div class="row mb-4">
        <div class="col-12">
            <h1><i class="bi bi-building"></i> Aerolíneas</h1>
        </div>
    </div>
    
    <div class="card">
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>Código</th>
                            <th>Nombre</th>
                            <th>País Origen</th>
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                        {aerolineas_html}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    '''
    
    return get_base_html('Aerolíneas', content)

@app.route('/logout')
@login_required
def logout():
    registrar_log('LOGOUT', detalles={'username': current_user.username})
    logout_user()
    flash('Has cerrado sesión exitosamente', 'info')
    return redirect('/login')

# ==================== INICIAR APLICACIÓN ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
