# portal_cliente/extractores.py
import pdfplumber
import re
from datetime import datetime

def extraer_formulario_cotizacion(ruta_pdf: str) -> dict:
    """
    Extrae datos estructurados del FGMP-FC-01 de manera flexible.
    """
    datos = {
        'nombre_buque': '',
        'tipo_buque': '',
        'omi': '',
        'razon_social': '',
        'rfc': '',
        'domicilio': {},
        'telefono': '',
        'ubicacion_buque': '',
        'representante_legal': {},
        'opip': {},
        'ocpm': {},
        'opb': {},
        'capitan': {},
        'servicios_solicitados': [],
        'requerimientos': {},
        'fecha_solicitud': datetime.now().strftime('%d/%m/%Y'),
    }
    
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            texto_completo = ""
            for page in pdf.pages:
                texto_completo += page.extract_text() or ""
    except Exception as e:
        print(f"❌ Error al abrir PDF en extractor: {e}")
        return datos

    # Si el PDF viene en blanco o es un escaneo plano sin texto
    if len(texto_completo.strip()) < 50:
        print("⚠️ El PDF no contiene texto suficiente. Posible estructura de imagen pura.")
        return datos

    # --- ESTRATEGIA DE BÚSQUEDA ROBUSTA (LÍNEA POR LÍNEA / PALABRAS CLAVE) ---
    lineas = [linea.strip() for linea in texto_completo.split('\n') if linea.strip()]
    
    # 1. Extracción de OMI (Suele ser un patrón numérico de 7 dígitos estándar)
    omi_match = re.search(r'(?:OMI|IMO)\s*:?\s*([0-9\-]{7,})', texto_completo, re.IGNORECASE)
    if omi_match:
        datos['omi'] = omi_match.group(1).strip()

    # 2. Extracción de RFC
    rfc_match = re.search(r'([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,3})', texto_completo, re.IGNORECASE)
    if rfc_match:
        datos['rfc'] = rfc_match.group(1).upper().strip()

    # 3. Caídas de respaldo dinámicas si fallan los regex principales
    for i, linea in enumerate(lineas):
        # Buscar Nombre del Buque
        if 'nombre' in linea.lower() and ('buque' in linea.lower() or 'artefacto' in linea.lower()):
            # Intentar tomar la línea actual quitando la etiqueta o la línea siguiente
            datos['nombre_buque'] = linea.split(':')[-1].strip() if ':' in linea else (lineas[i+1] if i+1 < len(lineas) else '')
        
        # Buscar Razón Social
        if 'razón social' in linea.lower() or 'razon social' in linea.lower() or 'giro' in linea.lower():
            datos['razon_social'] = linea.split(':')[-1].strip() if ':' in linea else (lineas[i+1] if i+1 < len(lineas) else '')

        # Buscar Teléfono
        if 'teléfono' in linea.lower() or 'telefono' in linea.lower():
            tel_match = re.search(r'([\d\s\-\(\)\+]{10,})', linea)
            if tel_match:
                datos['telefono'] = tel_match.group(1).strip()

    # Limpieza de seguridad en caso de capturar etiquetas
    for k, v in datos.items():
        if isinstance(v, str) and (':' in v or len(v) > 120):
            datos[k] = v.split(':')[-1].strip()[:60]

    # Intentar sacar tipo_buque
    if datos['nombre_buque']:
        partes = datos['nombre_buque'].split(',')
        datos['tipo_buque'] = partes[-1].strip() if len(partes) > 1 else "No especificado"

    return datos