import pyodbc

# No necesitas pasar 'app' si DB_CONFIG es global o accesible de otra manera
# pero si lo pones en app.config, entonces sí.
# Por simplicidad, asumiremos que DB_CONFIG está disponible globalmente aquí
# o que lo pasas a cada función que lo necesite.

# --- Configuración de la Base de Datos (copiada de app.py o importada) ---
DB_CONFIG = {
    'driver': '{ODBC Driver 17 for SQL Server}',
    'server': 'localhost',
    'database': 'ReporteAtento',
    'trusted_connection': 'yes'
}

def get_db_connection():
    """Crea y retorna una conexión a la base de datos SQL Server."""
    conn_str = (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
    )
    if DB_CONFIG['trusted_connection'].lower() == 'yes':
        conn_str += "Trusted_Connection=yes;"
    # else:
    #     conn_str += f"UID={DB_CONFIG['username']};PWD={DB_CONFIG['password']};" # Si usaras user/pass
    
    try:
        conn = pyodbc.connect(conn_str)
        return conn
    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        print(f"Error al conectar a la base de datos: {sqlstate}")
        print(ex)
        return None

# Aquí podrías añadir más funciones para interactuar con las tablas 'reportes' y 'usuarios'
# Ejemplo:
def get_user_by_username(username):
    conn = get_db_connection()
    if not conn:
        return None
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, username, password_hash FROM usuarios WHERE username = ?", (username,))
        user_data = cursor.fetchone()
        return user_data # Retorna una tupla (id, username, password_hash) o None
    except pyodbc.Error as e:
        print(f"Error al obtener usuario: {e}")
        return None
    finally:
        if conn:
            conn.close()

def create_user_db(username, password_hash):
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (username, password_hash) VALUES (?, ?)", (username, password_hash))
        conn.commit()
        return True
    except pyodbc.Error as e:
        print(f"Error al crear usuario: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_all_reports(search_term=None):
    conn = get_db_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    try:
        query = "SELECT id, cliente, contenido, estado FROM reportes"
        params = []
        if search_term:
            query += " WHERE cliente LIKE ? OR contenido LIKE ?"
            params.extend([f"%{search_term}%", f"%{search_term}%"])
        query += " ORDER BY id DESC" # O como prefieras ordenarlos
        
        cursor.execute(query, params)
        reports = cursor.fetchall() # Lista de tuplas
        # Convertir a lista de diccionarios para facilitar el uso en plantillas
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, report)) for report in reports]
    except pyodbc.Error as e:
        print(f"Error al obtener reportes: {e}")
        return []
    finally:
        if conn:
            conn.close()

# Las funciones de tu bot original como migrar_excel_a_db, 
# buscar_y_procesar_reportes_pendientes, generar_informe_csv
# podrían ir aquí también, pero su ejecución sería diferente en una app web
# (ej. a través de una ruta de admin, o como tareas programadas).