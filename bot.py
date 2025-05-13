import pandas as pd
import pyodbc
from datetime import datetime

# --- Configuración de la Base de Datos ---
DB_CONFIG = {
    'driver': '{ODBC Driver 17 for SQL Server}', # O el driver específico que tengas, e.g., '{ODBC Driver 17 for SQL Server}'
    'server': 'localhost', # Ejemplo: 'localhost\SQLEXPRESS' o el nombre de tu servidor
    'database': 'ReporteAtento',    # El nombre de la base de datos que creaste o usarás
    'trusted_connection': 'yes'      # Cambia a 'no' si usas username/password
}

# --- Nombres de Archivos ---
EXCEL_FILE = 'reportes_pendientes.xlsx'
CSV_REPORT_FILE = 'envios_realizados.csv'

def crear_conexion_db():
    """Crea y retorna una conexión a la base de datos SQL Server."""
    conn_str = (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
    )
    if DB_CONFIG['trusted_connection'].lower() == 'yes':
        conn_str += "Trusted_Connection=yes;"
    else:
        conn_str += f"UID={DB_CONFIG['username']};PWD={DB_CONFIG['password']};"
    
    try:
        conn = pyodbc.connect(conn_str)
        print("Conexión a la base de datos establecida exitosamente.")
        return conn
    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        print(f"Error al conectar a la base de datos: {sqlstate}")
        print(ex)
        return None

def migrar_excel_a_db(conn):
    """Lee datos del archivo Excel y los migra a la tabla 'reportes' en la BD."""
    if not conn:
        print("No hay conexión a la base de datos para migrar datos.")
        return

    try:
        df = pd.read_excel(EXCEL_FILE)
        print(f"Leyendo datos desde {EXCEL_FILE}...")

        cursor = conn.cursor()

        # Validación básica de datos incompletos
        if df[['id', 'cliente', 'contenido', 'estado']].isnull().any().any():
            print("Advertencia: Se encontraron filas con datos incompletos en el Excel. Estas filas no se migrarán.")
            # Opcional: podrías loguear cuáles son o manejarlas de otra forma
            df.dropna(subset=['id', 'cliente', 'contenido', 'estado'], inplace=True) # Elimina filas con NaN en columnas clave

        if df.empty:
            print("No hay datos válidos para migrar después de la validación.")
            return

        migrados = 0
        existentes = 0
        for index, row in df.iterrows():
            try:
                # Verificar si el reporte ya existe para evitar duplicados
                cursor.execute("SELECT id FROM reportes WHERE id = ?", (row['id'],))
                if cursor.fetchone():
                    print(f"Reporte con ID {row['id']} ya existe en la base de datos. Omitiendo.")
                    existentes += 1
                    continue

                # Insertar nuevo reporte
                cursor.execute("""
                    INSERT INTO reportes (id, cliente, contenido, estado)
                    VALUES (?, ?, ?, ?)
                """, (row['id'], row['cliente'], row['contenido'], row['estado']))
                migrados += 1
            except pyodbc.Error as ex:
                print(f"Error al insertar fila ID {row['id']}: {ex}")
                conn.rollback() # Revertir en caso de error en esta fila específica
                continue # Continuar con la siguiente fila
        
        conn.commit()
        print(f"Migración completada: {migrados} reportes nuevos insertados, {existentes} reportes ya existían.")

    except FileNotFoundError:
        print(f"Error: El archivo {EXCEL_FILE} no fue encontrado.")
    except Exception as e:
        print(f"Ocurrió un error durante la migración de Excel a BD: {e}")
        if conn:
            conn.rollback() # Revertir toda la transacción si hay un error mayor

# --- Funciones principales del bot (se implementarán a continuación) ---

def buscar_y_procesar_reportes_pendientes(conn):
    """Busca reportes pendientes, los "envía" y actualiza su estado."""
    if not conn:
        print("No hay conexión a la base de datos para procesar reportes.")
        return

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, cliente, contenido FROM reportes WHERE estado = 'pendiente'")
        reportes_pendientes = cursor.fetchall()

        if not reportes_pendientes:
            print("No se encontraron reportes pendientes.")
            return

        print(f"\nProcesando {len(reportes_pendientes)} reportes pendientes...")
        procesados_count = 0
        for reporte in reportes_pendientes:
            reporte_id, cliente, contenido = reporte
            
            # 1. Simular envío
            print(f"  Enviando reporte ID: {reporte_id} a Cliente: {cliente}...")
            print(f"  Contenido: {contenido[:50]}...") # Mostrar solo una parte del contenido

            # 2. Actualizar estado a 'enviado'
            try:
                cursor.execute("UPDATE reportes SET estado = 'enviado' WHERE id = ?", (reporte_id,))
                
                # 3. Registrar en log_envios
                # Modificación aquí: datetime.now() cambiado a datetime.now().date()
                cursor.execute("""
                    INSERT INTO log_envios (reporte_id, cliente, fecha_envio)
                    VALUES (?, ?, ?)
                """, (reporte_id, cliente, datetime.now().date()))
                
                conn.commit() # Commit por cada reporte procesado exitosamente
                print(f"  Reporte ID: {reporte_id} marcado como enviado y logueado.")
                procesados_count += 1
            except pyodbc.Error as ex:
                print(f"  Error al actualizar o loguear reporte ID {reporte_id}: {ex}")
                conn.rollback() # Revertir cambios para este reporte específico

        print(f"\nProceso completado. {procesados_count} reportes fueron procesados y enviados (simulado).")

    except Exception as e:
        print(f"Ocurrió un error al procesar reportes pendientes: {e}")
        if conn:
            conn.rollback()

def generar_informe_csv(conn):
    """Genera un archivo CSV con los logs de envío del día."""
    if not conn:
        print("No hay conexión a la base de datos para generar el informe.")
        return

    try:
        # Obtener la fecha de hoy para filtrar los logs
        hoy_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        hoy_fin = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)

        query = """
            SELECT log_id, reporte_id, cliente, fecha_envio 
            FROM log_envios 
            WHERE fecha_envio >= ? AND fecha_envio <= ?
            ORDER BY fecha_envio DESC
        """
        df_logs = pd.read_sql_query(query, conn, params=(hoy_inicio, hoy_fin))

        if df_logs.empty:
            print(f"No se encontraron envíos registrados hoy ({hoy_inicio.strftime('%Y-%m-%d')}) para generar el informe.")
            return

        df_logs.to_csv(CSV_REPORT_FILE, index=False, encoding='utf-8-sig')
        print(f"Informe de envíos del día generado exitosamente: {CSV_REPORT_FILE}")

    except Exception as e:
        print(f"Ocurrió un error al generar el informe CSV: {e}")

# --- Menú Principal --- (Esta función se eliminará o se comentará)
# def mostrar_menu():
#     print("\n--- Bot de Gestión de Reportes ---")
#     print("1. Migrar datos de Excel a Base de Datos")
#     print("2. Procesar y enviar reportes pendientes")
#     print("3. Generar informe de envíos del día (CSV)")
#     print("4. Salir")
#     return input("Seleccione una opción: ")

def main():
    """Función principal del bot que ejecuta todos los pasos automáticamente."""
    print("--- Iniciando Bot de Gestión de Reportes (Modo Automático) ---")
    db_conn = crear_conexion_db()

    if not db_conn:
        print("No se pudo establecer la conexión con la base de datos. El programa terminará.")
        return

    try:
        # Paso 1: Migrar datos de Excel a Base de Datos
        print("\n--- Paso 1: Migrando datos de Excel a Base de Datos ---")
        migrar_excel_a_db(db_conn)

        # Paso 2: Procesar y enviar reportes pendientes
        print("\n--- Paso 2: Procesando y enviando reportes pendientes ---")
        buscar_y_procesar_reportes_pendientes(db_conn)

        # Paso 3: Generar informe de envíos del día (CSV)
        print("\n--- Paso 3: Generando informe de envíos del día (CSV) ---")
        generar_informe_csv(db_conn)

    except Exception as e:
        print(f"Ocurrió un error inesperado durante la ejecución automática: {e}")
    finally:
        if db_conn:
            db_conn.close()
            print("\nConexión a la base de datos cerrada.")
        print("--- Bot de Gestión de Reportes ha finalizado su ejecución. ---")

if __name__ == "__main__":
    main()