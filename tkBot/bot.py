import pandas as pd
import pyodbc
from datetime import datetime
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk # ttk para el Treeview
import tkinter.font as tkFont # <--- AÑADIR ESTA LÍNEA

# --- Configuración de la Base de Datos ---
DB_CONFIG = {
    'driver': '{ODBC Driver 17 for SQL Server}',
    'server': 'localhost',
    'database': 'ReporteAtento',
    'trusted_connection': 'yes'
}

# --- Nombres de Archivos ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# EXCEL_FILE ya no será una constante global fija, se seleccionará desde la GUI
CSV_REPORT_FILE = os.path.join(SCRIPT_DIR, 'envios_realizados.csv')

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
        # Asumiendo que si no es trusted, username/password estarían en DB_CONFIG
        # conn_str += f"UID={DB_CONFIG['username']};PWD={DB_CONFIG['password']};"
        pass # Ajustar si se usa autenticación SQL
    
    try:
        conn = pyodbc.connect(conn_str)
        # print("Conexión a la base de datos establecida exitosamente.") # Silenciado para GUI
        return conn
    except pyodbc.Error as ex:
        # print(f"Error al conectar a la base de datos: {ex.args[0]}") # Silenciado para GUI
        # print(ex) # Silenciado para GUI
        return None

def migrar_excel_a_db(conn, excel_file_path):
    """Lee datos del archivo Excel y los migra a la tabla 'reportes' en la BD.
    Retorna (migrados, existentes, error_msg)
    """
    if not conn:
        return 0, 0, "No hay conexión a la base de datos para migrar datos."

    migrados = 0
    existentes = 0
    try:
        df = pd.read_excel(excel_file_path)
        # print(f"Leyendo datos desde {excel_file_path}...") # Silenciado para GUI

        cursor = conn.cursor()

        if df[['id', 'cliente', 'contenido', 'estado']].isnull().any().any():
            # print("Advertencia: Se encontraron filas con datos incompletos en el Excel...") # Silenciado
            df.dropna(subset=['id', 'cliente', 'contenido', 'estado'], inplace=True)

        if df.empty:
            return 0, 0, "No hay datos válidos para migrar después de la validación."

        for index, row in df.iterrows():
            try:
                cursor.execute("SELECT id FROM reportes WHERE id = ?", (row['id'],))
                if cursor.fetchone():
                    # print(f"Reporte con ID {row['id']} ya existe...") # Silenciado
                    existentes += 1
                    continue

                cursor.execute("""
                    INSERT INTO reportes (id, cliente, contenido, estado)
                    VALUES (?, ?, ?, ?)
                """, (row['id'], row['cliente'], row['contenido'], row['estado']))
                migrados += 1
            except pyodbc.Error as ex:
                # print(f"Error al insertar fila ID {row['id']}: {ex}") # Silenciado
                conn.rollback()
                continue
        
        conn.commit()
        return migrados, existentes, None

    except FileNotFoundError:
        return 0, 0, f"Error: El archivo {excel_file_path} no fue encontrado."
    except Exception as e:
        if conn:
            conn.rollback()
        return 0, 0, f"Ocurrió un error durante la migración de Excel a BD: {e}"

def buscar_y_procesar_reportes_pendientes(conn):
    """Busca reportes pendientes, los "envía" y actualiza su estado.
    Retorna (procesados_count, error_msg)
    """
    if not conn:
        return 0, "No hay conexión a la base de datos para procesar reportes."

    procesados_count = 0
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, cliente, contenido FROM reportes WHERE estado = 'pendiente'")
        reportes_pendientes = cursor.fetchall()

        if not reportes_pendientes:
            return 0, "No se encontraron reportes pendientes." # Considerar si esto es un error o un estado normal

        # print(f"\nProcesando {len(reportes_pendientes)} reportes pendientes...") # Silenciado
        for reporte in reportes_pendientes:
            reporte_id, cliente, contenido = reporte
            try:
                cursor.execute("UPDATE reportes SET estado = 'enviado' WHERE id = ?", (reporte_id,))
                cursor.execute("""
                    INSERT INTO log_envios (reporte_id, cliente, fecha_envio)
                    VALUES (?, ?, ?)
                """, (reporte_id, cliente, datetime.now().date())) # Usar .date() si solo se quiere la fecha
                
                conn.commit()
                # print(f"  Reporte ID: {reporte_id} marcado como enviado y logueado.") # Silenciado
                procesados_count += 1
            except pyodbc.Error as ex:
                # print(f"  Error al actualizar o loguear reporte ID {reporte_id}: {ex}") # Silenciado
                conn.rollback()

        return procesados_count, None

    except Exception as e:
        if conn:
            conn.rollback()
        return 0, f"Ocurrió un error al procesar reportes pendientes: {e}"

def get_ultimos_reportes_cargados(conn, limit=5):
    """Obtiene los últimos 'limit' reportes insertados desde la BD.
    Retorna (lista_de_reportes, error_msg)
    """
    if not conn:
        return [], "No hay conexión a la base de datos."
    try:
        cursor = conn.cursor()
        # Asumiendo que 'id' es autoincremental o que una fecha de inserción existe.
        # Si 'id' no refleja el orden de inserción, se necesitaría otra columna (ej. fecha_creacion).
        # Por ahora, ordenamos por 'id' descendente.
        query = """
            SELECT TOP (?) id, cliente, contenido, estado 
            FROM reportes 
            ORDER BY id DESC 
        """ # SQL Server usa TOP
        cursor.execute(query, limit)
        reportes = cursor.fetchall()
        # Convertir a lista de diccionarios para facilitar el uso si es necesario,
        # o mantener como lista de tuplas para el Treeview.
        # Columnas: id, cliente, contenido, estado
        return [list(row) for row in reportes], None # Treeview prefiere listas de valores
    except Exception as e:
        return [], f"Error al obtener últimos reportes: {e}"

def generar_informe_csv(conn):
    """Genera un archivo CSV con los logs de envío del día."""
    if not conn:
        # print("No hay conexión a la base de datos para generar el informe.") # Silenciado
        return "Error: Sin conexión a BD."

    try:
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
            return f"No se encontraron envíos registrados hoy ({hoy_inicio.strftime('%Y-%m-%d')})."
        
        df_logs.to_csv(CSV_REPORT_FILE, index=False, encoding='utf-8-sig')
        return f"Informe de envíos del día generado: {CSV_REPORT_FILE}"
    except Exception as e:
        return f"Ocurrió un error al generar el informe CSV: {e}"


class BotGUI:
    def __init__(self, master):
        self.master = master
        master.title("Bot de Gestión de Reportes")
        master.geometry("600x750")
        master.configure(bg='plum1') # <--- AÑADIR ESTA LÍNEA para color de fondo

        self.selected_excel_path = tk.StringVar()
        self.db_conn = None

        # Frame para selección de archivo
        frame_select = ttk.LabelFrame(master, text="Selección de Archivo", padding="10")
        frame_select.pack(padx=10, pady=5, fill="x")

        ttk.Button(frame_select, text="Seleccionar Excel", command=self.seleccionar_excel).pack(side=tk.LEFT, padx=5)
        self.excel_path_label = ttk.Label(frame_select, textvariable=self.selected_excel_path)
        self.excel_path_label.pack(side=tk.LEFT, padx=5, fill="x", expand=True)
        self.selected_excel_path.set("Ningún archivo seleccionado")

        # Frame para acciones
        frame_actions = ttk.LabelFrame(master, text="Acciones", padding="10")
        frame_actions.pack(padx=10, pady=5, fill="x")

        ttk.Button(frame_actions, text="Cargar Reportes", command=self.cargar_reportes).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_actions, text="Ver Últimos Reportes Cargados", command=self.ver_ultimos_reportes).pack(side=tk.LEFT, padx=5)

        # Frame para resumen/logs
        frame_summary = ttk.LabelFrame(master, text="Resumen de Operaciones", padding="10")
        frame_summary.pack(padx=10, pady=5, fill="both", expand=True)

        self.summary_text = tk.Text(frame_summary, height=8, wrap=tk.WORD, state=tk.DISABLED, bg='white', fg='black') # <--- MODIFICAR ESTA LÍNEA
        
        # Configurar tag para texto en negrita
        default_font_name = self.summary_text.cget("font") # Obtener el nombre de la fuente Tcl por defecto
        default_font_obj = tkFont.Font(font=default_font_name) # Crear un objeto Font a partir del nombre
        
        # Obtener las propiedades de la fuente actual
        family = default_font_obj.actual("family")
        size = default_font_obj.actual("size")
        
        # Configurar el tag "bold" usando la familia y tamaño actuales, pero con estilo "bold"
        self.summary_text.tag_configure("bold", font=(family, size, "bold"))
        
        self.summary_text.pack(fill="both", expand=True)
        
        # Frame para tabla de últimos reportes
        frame_table = ttk.LabelFrame(master, text="Últimos Reportes Cargados", padding="10")
        frame_table.pack(padx=10, pady=5, fill="both", expand=True)
        
        self.tree = ttk.Treeview(frame_table, columns=("ID", "Cliente", "Contenido", "Estado"), show="headings")
        self.tree.heading("ID", text="ID")
        self.tree.heading("Cliente", text="Cliente")
        self.tree.heading("Contenido", text="Contenido (extracto)")
        self.tree.heading("Estado", text="Estado")

        self.tree.column("ID", width=50, anchor=tk.W)
        self.tree.column("Cliente", width=150, anchor=tk.W)
        self.tree.column("Contenido", width=300, anchor=tk.W)
        self.tree.column("Estado", width=100, anchor=tk.W)
        
        self.tree.pack(fill="both", expand=True)

    def _log_separator(self):
        self.summary_text.config(state=tk.NORMAL)
        self.summary_text.insert(tk.END, "------------------------------------------\n")
        self.summary_text.see(tk.END)
        self.summary_text.config(state=tk.DISABLED)

    def _log_message(self, message_parts):
        self.summary_text.config(state=tk.NORMAL)
        self.summary_text.insert(tk.END, f"{datetime.now().strftime('%H:%M')} ") # Formato de hora HH:MM

        for part, style in message_parts:
            if style == "bold":
                self.summary_text.insert(tk.END, part, "bold")
            else:
                self.summary_text.insert(tk.END, part)
        
        self.summary_text.insert(tk.END, "\n") # Salto de línea al final del mensaje completo
        self.summary_text.see(tk.END)
        self.summary_text.config(state=tk.DISABLED)

    def seleccionar_excel(self):
        filepath = filedialog.askopenfilename(
            title="Seleccionar archivo Excel",
            filetypes=(("Archivos Excel", "*.xlsx *.xls"), ("Todos los archivos", "*.*"))
        )
        if filepath:
            self.selected_excel_path.set(filepath)
            # self._log_message(f"Archivo seleccionado: {filepath}") # Mensaje desactivado
        else:
            self.selected_excel_path.set("Ningún archivo seleccionado")

    def _get_db_conn(self):
        if self.db_conn and self.db_conn.closed == 0: # pyodbc connection check
             try:
                self.db_conn.execute("SELECT 1") # Check if connection is still alive
                return self.db_conn
             except pyodbc.Error:
                self.db_conn.close() # Close broken connection
                self.db_conn = None

        self.db_conn = crear_conexion_db()
        if not self.db_conn:
            self._log_message("Error: No se pudo conectar a la base de datos.")
            messagebox.showerror("Error de Conexión", "No se pudo establecer la conexión con la base de datos.")
        return self.db_conn

    def _close_db_conn(self):
        # Decidimos no cerrar la conexión inmediatamente para reutilizarla
        # Se cerrará al salir de la aplicación o si se detecta que está rota.
        pass
        # if self.db_conn:
        #     self.db_conn.close()
        #     self.db_conn = None
        #     self._log_message("Conexión a la base de datos cerrada.")

    def cargar_reportes(self):
        excel_path = self.selected_excel_path.get()
        if not excel_path or excel_path == "Ningún archivo seleccionado":
            messagebox.showwarning("Archivo no seleccionado", "Por favor, seleccione un archivo Excel primero.")
            return

        conn = self._get_db_conn()
        if not conn:
            return

        self._log_separator() # <--- AÑADIR ESTA LÍNEA PARA EL SEPARADOR

        self._log_message([("Iniciando carga desde:", "bold"), (f"\n{excel_path}", "normal")])
        
        migrados, existentes, error_migracion = migrar_excel_a_db(conn, excel_path)
        
        if error_migracion:
            self._log_message([("Error en migración: ", "normal"), (str(error_migracion), "normal")])
            messagebox.showerror("Error de Migración", f"Error durante la migración: {error_migracion}")
        else:
            self._log_message([("Migración completada:", "bold"), (f"\n{migrados} reportes nuevos insertados, {existentes} reportes ya existían.", "normal")])

        # Continuar con el procesamiento de pendientes independientemente del resultado de la migración,
        # a menos que la migración haya sido un fallo catastrófico (ya manejado por el return si conn es None).
        
        procesados, error_procesamiento = buscar_y_procesar_reportes_pendientes(conn)

        if error_procesamiento and error_procesamiento != "No se encontraron reportes pendientes.":
             self._log_message([("Error en procesamiento: ", "normal"), (str(error_procesamiento), "normal")])
             messagebox.showerror("Error de Procesamiento", f"Error durante el procesamiento de reportes: {error_procesamiento}")
        elif error_procesamiento == "No se encontraron reportes pendientes.":
            self._log_message([("Procesamiento:", "bold"), ("\nNo se encontraron reportes pendientes para enviar.", "normal")])
        else:
            self._log_message([("Proceso de envío de reportes completado:", "bold"), (f"\n{procesados} reportes fueron procesados y enviados (simulado).", "normal")])

        if not error_migracion and (not error_procesamiento or error_procesamiento == "No se encontraron reportes pendientes."):
            messagebox.showinfo("Proceso Completado", "Reportes cargados y procesados correctamente.")
        
        # Opcional: generar informe CSV automáticamente después de cargar
        # informe_msg = generar_informe_csv(conn)
        # self._log_message(informe_msg)

        # self._close_db_conn() # No cerramos aquí para reutilizar

    def ver_ultimos_reportes(self):
        conn = self._get_db_conn()
        if not conn:
            return

        # Limpiar tabla anterior
        for i in self.tree.get_children():
            self.tree.delete(i)

        reportes, error = get_ultimos_reportes_cargados(conn, limit=5)
        if error:
            self._log_message([("Error al ver reportes: ", "normal"), (str(error), "normal")])
            messagebox.showerror("Error", f"No se pudieron obtener los reportes: {error}")
        elif not reportes:
            self._log_message([("No hay reportes para mostrar.", "normal")])
            messagebox.showinfo("Información", "No se encontraron reportes recientes.")
        else:
            # self._log_message(f"Mostrando {len(reportes)} reportes recientes.") # Mensaje desactivado
            for reporte_data in reportes:
                # Asegurarse que reporte_data tiene 4 elementos
                # (id, cliente, contenido, estado)
                # Truncar contenido para visualización
                if len(reporte_data) > 2 and reporte_data[2] and len(reporte_data[2]) > 50:
                    reporte_data[2] = reporte_data[2][:50] + "..."
                self.tree.insert("", tk.END, values=reporte_data)
        
        # self._close_db_conn() # No cerramos aquí para reutilizar

    def on_closing(self):
        if self.db_conn:
            self.db_conn.close()
            # print("Conexión a BD cerrada al salir.") # Para depuración
        self.master.destroy()

# def main(): # La función main original ya no se usará de la misma forma
#     // ... existing code ...

if __name__ == '__main__':
    root = tk.Tk()
    app = BotGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing) # Manejar cierre de ventana
    root.mainloop()