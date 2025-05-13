from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user # Import current_user
from auth import auth_bp, User # Importar el Blueprint y la clase User
from views import views_bp # <--- AÑADIR ESTA LÍNEA
# from db_utils import init_app_db # Si decides usarla

# --- Configuración de la Base de Datos (ya la tienes) ---
DB_CONFIG = {
    'driver': '{ODBC Driver 17 for SQL Server}',
    'server': 'localhost',
    'database': 'ReporteAtento',
    'trusted_connection': 'yes'
}

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_super_secreto_key_aqui_cambiala_por_algo_seguro' # ¡CAMBIA ESTO!
app.config['DB_CONFIG'] = DB_CONFIG

# Configuración de Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login' # Ruta a la que se redirige si se requiere login
login_manager.login_message = "Por favor, inicia sesión para acceder a esta página."
login_manager.login_message_category = "info"


@login_manager.user_loader
def load_user(user_id):
    # Flask-Login usa esta función para recargar el objeto usuario desde el ID de usuario almacenado en la sesión
    return User.get(user_id)

# Registrar Blueprints
app.register_blueprint(auth_bp, url_prefix='/auth') # Rutas de auth estarán bajo /auth
app.register_blueprint(views_bp) # <--- AÑADIR ESTA LÍNEA

@app.route('/')
def home():
    if current_user.is_authenticated:
        # Si el usuario está autenticado, redirigir al dashboard (que crearemos)
        return redirect(url_for('views.dashboard')) # Asumiendo que views.dashboard será la página principal
    # Si no, redirigir a la página de login
    return redirect(url_for('auth.login'))


if __name__ == '__main__':
    # init_app_db(app) # Si es necesario
    app.run(debug=True) # debug=True es útil para desarrollo, desactívalo en producción