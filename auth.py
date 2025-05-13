from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
from passlib.hash import pbkdf2_sha256 # Para hashear contraseñas
# Cambiar la siguiente línea:
from db_utils import get_user_by_username, create_user_db # Asumiendo que db_utils.py está en el mismo nivel

# Creamos un Blueprint para las rutas de autenticación
auth_bp = Blueprint('auth', __name__, template_folder='templates')

# Necesitamos configurar LoginManager en app.py, pero definimos la clase User aquí
class User(UserMixin):
    def __init__(self, id, username, password_hash=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash # Solo se usa al crear/verificar, no se guarda en sesión directamente

    @staticmethod
    def get(user_id):
        # Esta función será llamada por el user_loader en app.py
        conn = None
        try:
            # Necesitamos una función en db_utils para obtener usuario por ID
            # Por ahora, simularemos o adaptaremos get_user_by_username si es necesario
            # o mejor, crear get_user_by_id en db_utils.py
            # Cambiar la siguiente línea:
            from db_utils import get_db_connection # Importación local para evitar circularidad si es necesario
            conn = get_db_connection()
            if not conn:
                return None
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, password_hash FROM usuarios WHERE id = ?", (user_id,))
            user_data = cursor.fetchone()
            if user_data:
                return User(id=user_data[0], username=user_data[1], password_hash=user_data[2])
            return None
        except Exception as e:
            print(f"Error en User.get: {e}")
            return None
        finally:
            if conn:
                conn.close()

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not username or not password or not confirm_password:
            flash('Todos los campos son obligatorios.', 'danger')
            return redirect(url_for('auth.signup'))

        if password != confirm_password:
            flash('Las contraseñas no coinciden.', 'danger')
            return redirect(url_for('auth.signup'))

        existing_user = get_user_by_username(username)
        if existing_user:
            flash('El nombre de usuario ya existe.', 'warning')
            return redirect(url_for('auth.signup'))

        # Hashear la contraseña
        password_hash = pbkdf2_sha256.hash(password)
        
        if create_user_db(username, password_hash):
            flash('¡Cuenta creada exitosamente! Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Ocurrió un error al crear la cuenta. Inténtalo de nuevo.', 'danger')
            return redirect(url_for('auth.signup'))

    return render_template('signup.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Nombre de usuario y contraseña son obligatorios.', 'danger')
            return redirect(url_for('auth.login'))

        user_data = get_user_by_username(username) # Retorna (id, username, password_hash)

        if user_data and pbkdf2_sha256.verify(password, user_data[2]): # user_data[2] es password_hash
            user_obj = User(id=user_data[0], username=user_data[1])
            login_user(user_obj) # Flask-Login maneja la sesión
            flash('Inicio de sesión exitoso.', 'success')
            # Redirigir a la página principal después del login (la crearemos después)
            return redirect(url_for('views.dashboard')) # Asumiendo que tendrás un blueprint 'views' con 'dashboard'
        else:
            flash('Nombre de usuario o contraseña incorrectos.', 'danger')
            return redirect(url_for('auth.login'))

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required # Solo usuarios logueados pueden desloguearse
def logout():
    logout_user()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('auth.login'))