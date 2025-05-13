from flask import Blueprint, render_template, request, redirect, url_for, jsonify # Añadir jsonify
from flask_login import login_required, current_user
from db_utils import get_all_reports

views_bp = Blueprint('views', __name__, template_folder='templates')

@views_bp.route('/dashboard')
@login_required
def dashboard():
    search_term = request.args.get('search', '')
    # La carga inicial de reportes se hace aquí para el renderizado completo de la página
    if search_term:
        reports = get_all_reports(search_term=search_term)
    else:
        reports = get_all_reports()
    
    return render_template('dashboard.html', reports=reports, search_term=search_term)

@views_bp.route('/_get_reports_table') # Nueva ruta para AJAX
@login_required
def get_reports_table_ajax():
    search_term = request.args.get('search', '') # Mantenemos la capacidad de búsqueda para la actualización
    if search_term:
        reports = get_all_reports(search_term=search_term)
    else:
        reports = get_all_reports()
    
    # Renderizamos solo la plantilla parcial de la tabla
    return render_template('_report_table.html', reports=reports, search_term=search_term)

# Podrías añadir más vistas aquí si es necesario, por ejemplo, para ver detalles de un reporte