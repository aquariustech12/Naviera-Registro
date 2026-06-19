# portal_cliente/validadores.py

import re
from dataclasses import dataclass
from typing import List

from .tarifario import RANGO_KEYWORDS  # ← CORREGIDO: faltaba este import


@dataclass
class ValidacionFormulario:
    ok: bool
    errores: List[str]
    datos: dict


def validar_formulario_cotizacion(texto_pdf: str) -> ValidacionFormulario:
    """
    Valida que el FGMP-FC-01 tenga los campos mínimos necesarios.
    Si falta algo, MIA rechaza el documento y avisa.
    """
    errores = []
    datos   = {}

    # === NOMBRE Y TIPO DE BUQUE ===
    match_buque = re.search(
        r'Nombre y tipo de artefacto naval.*?No\.\s*OMI\s+(.*?)(?=DATOS|$)',
        texto_pdf, re.DOTALL | re.IGNORECASE
    )
    if not match_buque or not match_buque.group(1).strip():
        errores.append("❌ Falta NOMBRE Y TIPO DE BUQUE")
        datos['nombre_buque'] = ''
        datos['tipo_buque']   = ''
    else:
        texto_buque = match_buque.group(1).strip()
        datos['nombre_buque'] = texto_buque
        partes = [p.strip() for p in texto_buque.split(',') if p.strip()]
        if len(partes) >= 2:
            datos['tipo_buque'] = partes[-1]
        else:
            palabras = texto_buque.split()
            for i, palabra in enumerate(palabras):
                if any(kw in palabra.lower() for kw in [k for v in RANGO_KEYWORDS.values() for k in v]):
                    datos['tipo_buque']   = ' '.join(palabras[i:])
                    datos['nombre_buque'] = ' '.join(palabras[:i])
                    break
            else:
                datos['tipo_buque']   = texto_buque
                datos['nombre_buque'] = texto_buque

    # === NO. OMI ===
    match_omi = re.search(r'No\.\s*OMI\s+([A-Z0-9\-]{3,})', texto_pdf, re.IGNORECASE)
    if not match_omi:
        errores.append("❌ Falta NO. OMI")
        datos['omi'] = ''
    else:
        datos['omi'] = match_omi.group(1).strip()

    # === RAZÓN SOCIAL ===
    match_rs = re.search(
        r'Razón Social y Giro.*?compañía.*?buque\.\s+(.*?)(?=RFC|$)',
        texto_pdf, re.DOTALL | re.IGNORECASE
    )
    if not match_rs or not match_rs.group(1).strip():
        errores.append("❌ Falta RAZÓN SOCIAL")
        datos['razon_social'] = ''
    else:
        datos['razon_social'] = match_rs.group(1).strip()

    # === RFC ===
    match_rfc = re.search(
        r'RFC de la compañía\.\s+([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,3})',
        texto_pdf, re.IGNORECASE
    )
    if not match_rfc:
        errores.append("❌ Falta RFC")
        datos['rfc'] = ''
    else:
        datos['rfc'] = match_rfc.group(1).strip()

    # === DOMICILIO ===
    match_calle  = re.search(r'Calle y Número\s+(.*?)(?=Ciudad|$)',  texto_pdf, re.DOTALL)
    match_ciudad = re.search(r'Ciudad y Estado\s+(.*?)(?=Municipio|$)', texto_pdf, re.DOTALL)
    if not match_calle or not match_ciudad:
        errores.append("❌ Falta DOMICILIO FISCAL completo")

    # === TELÉFONO ===
    match_tel = re.search(r'Teléfono\s+([\d\s\-\(\)\+]{7,})', texto_pdf)
    if not match_tel:
        errores.append("❌ Falta TELÉFONO")
        datos['telefono'] = ''
    else:
        datos['telefono'] = match_tel.group(1).strip()

    # === LOCALIZACIÓN DEL BUQUE ===
    match_loc = re.search(
        r'Localización del artefacto naval.*?Puerto, Ciudad y Estado\s+(.*?)(?=Representante|$)',
        texto_pdf, re.DOTALL | re.IGNORECASE
    )
    if not match_loc or not match_loc.group(1).strip():
        errores.append("❌ Falta LOCALIZACIÓN DEL BUQUE")
        datos['ubicacion_buque'] = ''
    else:
        datos['ubicacion_buque'] = match_loc.group(1).strip()

    # === REPRESENTANTE LEGAL ===
    match_rep = re.search(
        r'Representante legal.*?Nombre\s+(.*?)(?=Teléfono|$)',
        texto_pdf, re.DOTALL | re.IGNORECASE
    )
    if not match_rep or not match_rep.group(1).strip():
        errores.append("❌ Falta REPRESENTANTE LEGAL")

    # === SERVICIOS SOLICITADOS ===
    match_serv = re.search(
        r'Servicios solicitados:\s+(.*?)(?=Nombre y tipo|$)',
        texto_pdf, re.DOTALL | re.IGNORECASE
    )
    servicio_texto = match_serv.group(1).strip() if match_serv else ''

    if not servicio_texto or servicio_texto.lower() in ['', 'n/a', 'na', 'ninguno']:
        errores.append("❌ Falta SERVICIO SOLICITADO (Verificación Inicial, Renovación, Evaluación, etc.)")
        datos['servicio_solicitado'] = ''
    else:
        datos['servicio_solicitado'] = servicio_texto
        # Detectar si pusieron tipo de buque en lugar del servicio (error frecuente)
        tiene_tipo_buque = any(
            kw in servicio_texto.lower()
            for kw in [k for v in RANGO_KEYWORDS.values() for k in v]
        )
        tiene_servicio = any(
            sv in servicio_texto.lower()
            for sv in ['verificación', 'evaluación', 'renovación', 'inspección', 'auditoría', 'certificación']
        )
        if tiene_tipo_buque and not tiene_servicio:
            errores.append(
                f"⚠️ En SERVICIOS SOLICITADOS parece haber puesto el TIPO DE BUQUE "
                f"('{servicio_texto}') en lugar del servicio. Corregir."
            )

    # === REQUERIMIENTOS DE INGRESO ===
    match_epp = re.search(r'Ropa y EPP\.\s+(.*?)(?=Documentación|$)', texto_pdf, re.DOTALL)
    if not match_epp or not match_epp.group(1).strip():
        errores.append("❌ Falta ROPA Y EPP")

    return ValidacionFormulario(
        ok=len(errores) == 0,
        errores=errores,
        datos=datos
    )
