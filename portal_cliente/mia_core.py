# portal_cliente/mia_core.py — VERSIÓN ESTABLE
import json
from typing import Optional

from .mia_memoria import obtener_contexto, guardar_mensaje
from .mia_herramientas import (
    consultar_ollama,
    herramienta_consultar_pbip,
    herramienta_consultar_estado,
    herramienta_reporte_global,
    enviar_whatsapp_jid,
    buscar_pbip_hibrido
)
from .mia_documentos import herramienta_analizar_documento


MAPA_PBIP = """ESTRUCTURA DEL CÓDIGO PBIP - MAPA DE CONSULTA:

PARTE A - BUQUES:
1. Introducción → Contexto general
2. Definiciones → Qué significa cada término (buque, PFSO, SSP, CSO, SSO, etc.)
3. Ámbito de aplicación → QUÉ buques están obligados (pasaje, carga ≥500 GT, perforación)
   ↳ 3.1: Lista obligatoria
   ↳ 3.2: Gobiernos deciden sobre buques NO listados (remolcadores, pesqueros, yates, etc.)
4. Responsabilidades de Gobiernos Contratantes → Qué debe hacer cada país
5. Declaración de Protección Marítima → Obligación de cada gobierno
6. Compañías → Responsabilidades de las navieras
7. Protección del buque → Medidas de seguridad del buque
8. Evaluación de la protección del buque → Cómo evaluar riesgos
9. Plan de protección del buque → Contenido mínimo obligatorio
10. Registros → Qué documentos guardar
11. Oficial de la compañía (CSO) → Designación y funciones
12. Oficial a bordo (SSO) → Funciones a bordo
13. Ejercicios y simulacros → Frecuencia y tipo
14. Control de acceso → Quién entra al buque
15. Seguridad de la carga → Protección de mercancías
16. Seguridad de la carga en contenedores → Sellos, inspección
17. Seguridad de los suministros → Combustible, víveres, repuestos
18. Seguridad de la tripulación → Verificación de marineros
19. Verificación y certificación → Cómo se expide el certificado ISPS

PARTE B - INSTALACIONES PORTUARIAS:
1. Introducción
2. Definiciones
3. Ámbito de aplicación → QUÉ instalaciones están obligadas
4. Responsabilidades de Gobiernos Contratantes
5. Declaración de Protección Marítima
6. Instalación portuaria → Responsabilidades
7. Evaluación de la protección
8. Plan de protección de la instalación portuaria
9. Plan de protección del buque (Parte B)
10. Registros
11. Oficial de la instalación portuaria (PFSO)
12. Ejercicios y simulacros
13. Control de acceso
14. Seguridad de la carga
15. Seguridad de los suministros
16. Plan de protección de la instalación portuaria (detalle)

REGLA DE ORO PARA CONSULTAS:
- Si preguntan "¿debe tener certificado?" → Ir a sección 3 (Parte A) o 3 (Parte B)
- Si preguntan "¿qué debe contener?" → Ir al Plan de protección (9A o 8B/16B)
- Si preguntan "¿quién es responsable?" → Ir a secciones 4, 6, 11, 12
- Si el tipo de buque NO está en 3.1 → Citar 3.2 (discreción del gobierno)
- Si preguntan sobre remolcadores, pesqueros, yates, auxiliares → NO están en 3.1, usar 3.2
"""


def procesar_input_mia(texto_usuario=None, documento_obj=None, numero_whatsapp=None, jid_remitente=None):
    """
    ÚNICO punto de entrada para MIA.
    """
    # 1. MEMORIA
    numero = numero_whatsapp or (jid_remitente.split('@')[0] if jid_remitente else "unknown")
    contexto = obtener_contexto(numero) if numero else []

    # 2. CLASIFICAR
    if documento_obj:
        intencion = "ANALISIS_DOCUMENTO"
        entidades = {"documento": getattr(documento_obj, 'nombre_documento', 'unknown')}
    else:
        intencion, entidades = _clasificar_intencion(texto_usuario or "", contexto)

    # 3. EJECUTAR
    respuesta = None
    if intencion == "ANALISIS_DOCUMENTO":
        if documento_obj is None:
            respuesta = _modo_conversacion(
                "El usuario mencionó documentos pero no adjuntó ninguno. "
                "Responde amablemente pidiendo que adjunte el archivo.", 
                contexto
            )
        else:
            try:
                herramienta_analizar_documento(documento_obj, jid_remitente)
                respuesta = None  # Ya notificó internamente
            except Exception as e:
                print(f"ERROR en analisis documento: {e}")
                import traceback
                traceback.print_exc()
                respuesta = "❌ Error analizando el documento. Revisa los logs."

    elif intencion == "CONSULTA_NORMATIVA":
        respuesta = _modo_consulta_pbip(texto_usuario, entidades, contexto)

    elif intencion == "CONSULTA_ESTADO":
        respuesta = _modo_consulta_estado(texto_usuario, entidades, contexto)

    elif intencion == "REPORTE_GLOBAL":
        respuesta = herramienta_reporte_global()

    else:
        respuesta = _modo_conversacion(texto_usuario, contexto)

    # 4. GUARDAR (solo para interacciones de texto, no documentos)
    if numero and texto_usuario and respuesta:
        try:
            guardar_mensaje(numero, "user", texto_usuario, intencion, entidades)
            guardar_mensaje(numero, "mia", respuesta, intencion, entidades)
        except Exception as e:
            print(f"ERROR guardando mensaje: {e}")

    return respuesta


def _clasificar_intencion(texto: str, contexto: list):
    """
    Clasificador híbrido. NUNCA devuelve ANALISIS_DOCUMENTO sin documento real.
    """
    texto_lower = texto.lower().strip()
    entidades = {}

    # DOCUMENTOS: Solo acciones explícitas de subir/analizar archivo
    doc_action_keywords = ["pdf", "archivo", "analiza", "revisa esto", "subí", "subi", "escaneo", "imagen", "adjunto", "envié", "envie"]
    if any(k in texto_lower for k in doc_action_keywords):
        return "CONVERSACION_GENERAL", entidades

    # Normativa PBIP
    pbip_keywords = ["pbip", "código", "codigo", "normativa", "artículo", "articulo", 
                     "omi", "reglamento", "ley", "circular", "resolución", "resolucion",
                     "control de acceso", "pfso", "opb", "sso", "csp", "isps",
                     "remolcador", "pesquero", "yate", "buque auxiliar", "certificado",
                     "obligatorio", "debe tener", "necesita", "aplica a"]
    if any(k in texto_lower for k in pbip_keywords):
        entidades["tema_pbip"] = texto
        return "CONSULTA_NORMATIVA", entidades

    # Estado / Reporte
    if texto_lower in ["estado", "reporte", "status"]:
        return "REPORTE_GLOBAL", entidades

    estado_keywords = ["cómo va", "como va", "progreso", "porcentaje", "falta", 
                       "completado", "expediente", "avance", "qué falta", "que falta",
                       "faltan documentos", "aun faltan", "aún faltan"]
    if any(k in texto_lower for k in estado_keywords):
        palabras = texto_lower.split()
        for i, palabra in enumerate(palabras):
            if palabra in ["buque", "naviera", "omi"]:
                entidades["tipo_busqueda"] = palabra
                if i + 1 < len(palabras):
                    entidades["termino"] = " ".join(palabras[i+1:])
        return "CONSULTA_ESTADO", entidades

    # Recordatorios
    if any(k in texto_lower for k in ["recordar", "recordatorio", "alerta", "notificar", "avisar"]):
        return "RECORDATORIO", entidades

    # Ayuda
    if any(k in texto_lower for k in ["ayuda", "help", "comandos", "qué puedes hacer", "que puedes hacer"]):
        return "AYUDA", entidades

    # FALLBACK: LLM
    return _clasificar_con_llm(texto, contexto)


def _clasificar_con_llm(texto: str, contexto: list):
    prompt = f"""Eres el clasificador de MIA. Clasifica el mensaje del auditor en UNA categoría:

CATEGORÍAS:
- CONSULTA_NORMATIVA: Pregunta sobre PBIP, OMI, regulaciones, normas marítimas, certificados, tipos de buques
- CONSULTA_ESTADO: Pregunta sobre navieras, buques, progreso, expedientes, documentos faltantes
- CONVERSACION_GENERAL: Saludos, despedidas, preguntas sobre MIA, chit-chat, frases cortas
- RECORDATORIO: Solicita alertas, recordatorios, notificaciones
- AYUDA: Pide menú de opciones o comandos disponibles

REGLAS IMPORTANTES:
- "faltan documentos" o "qué falta" → CONSULTA_ESTADO (no es análisis de documento)
- "subí un archivo" o "revisa este pdf" → CONVERSACION_GENERAL (el sistema detecta documentos por separado)
- Saludos simples → CONVERSACION_GENERAL

CONTEXTO RECIENTE:
{json.dumps(contexto[-3:], ensure_ascii=False, indent=2)}

MENSAJE: "{texto}"

Responde SOLO con un JSON:
{{"intencion": "CATEGORIA", "entidades": {{"tema": "tema detectado o null"}}}}"""

    respuesta = consultar_ollama(prompt, temperature=0.0, num_ctx=4096)

    try:
        respuesta = respuesta.strip()
        if respuesta.startswith('```json'): respuesta = respuesta[7:]
        if respuesta.endswith('```'): respuesta = respuesta[:-3]
        data = json.loads(respuesta)
        return data.get("intencion", "CONVERSACION_GENERAL"), data.get("entidades", {})
    except:
        return "CONVERSACION_GENERAL", {}


def _modo_consulta_pbip(pregunta: str, entidades: dict, contexto: list) -> str:
    tema = entidades.get("tema_pbip") or pregunta

    resultados = buscar_pbip_hibrido(tema, k=5, estrategia='auto')

    if not resultados:
        return f"🤖 *MIA*\n\nNo encontré información sobre '{tema}' en el código PBIP.\n\n💡 *Sugerencia:* Intenta con términos más específicos como \"control de acceso\", \"PFSO\", \"evaluación de riesgos\", etc."

    articulos_texto = []
    for r in resultados:
        meta = r['metadata']
        ref = f"Parte {meta.get('parte', '?')} | {meta.get('seccion', 'PBIP')}"
        contenido = r['text'][:1000] if len(r['text']) > 500 else r['text']
        articulos_texto.append(f"[{ref}]\n{contenido}")

    articulos_str = "\n---\n".join(articulos_texto)

    prompt = f"""{MAPA_PBIP}

ARTÍCULOS RECUPERADOS DE LA BASE DE DATOS:
{articulos_str}

PREGUNTA DEL AUDITOR:
{pregunta}

INSTRUCCIONES CRÍTICAS:
1. Usa el MAPA DE CONSULTA para saber qué secciones buscar y cómo interpretarlas
2. Si la pregunta es sobre obligatoriedad/certificación de un tipo de buque:
   - Primero verifica si está en la lista de la sección 3.1 (pasaje, carga ≥500 GT, perforación)
   - Si NO está (remolcadores, pesqueros, yates, auxiliares) → cita el párrafo 3.2 sobre discreción del gobierno
   - CONCLUSIÓN: No es obligatorio por el Código PBIP internacional, pero la autoridad marítima nacional puede exigirlo
3. Si la pregunta es sobre contenido de planes → busca en secciones 9A o 8B/16B
4. Si la pregunta es sobre responsabilidades → busca en secciones 4, 6, 11, 12
5. Responde en español, claro y conciso
6. Cita artículos específicos con referencia completa (Parte A/B, sección, párrafo si aplica)
7. Si la información no está en los artículos, dilo claramente PERO sugiere dónde buscar
8. Sé profesional pero cercano
9. Formato WhatsApp: usa *negritas* para énfasis

FORMATO DE RESPUESTA:
🤖 *MIA - CONSULTA PBIP*

📜 *Artículos consultados:*
[lista breve con referencias exactas]

💡 *Respuesta:*
[respuesta detallada, estructurada y fundamentada]

📌 *Referencias específicas:*
[citas exactas de artículos con números de párrafo si aplica]"""

    return consultar_ollama(prompt, temperature=0.2, num_ctx=16384)


def _modo_consulta_estado(pregunta: str, entidades: dict, contexto: list) -> str:
    tipo = entidades.get("tipo_busqueda")
    termino = entidades.get("termino")

    if not tipo and contexto:
        for msg in reversed(contexto):
            meta = msg.get("metadatos", {})
            if isinstance(meta, str):
                try: meta = json.loads(meta)
                except: meta = {}
            tipo = tipo or meta.get("tipo_busqueda")
            termino = termino or meta.get("termino")
            if tipo:
                break

    if tipo == "omi" and termino:
        datos = herramienta_consultar_estado(omi=termino.strip())
    elif tipo == "buque" and termino:
        datos = herramienta_consultar_estado(buque_nombre=termino.strip())
    elif tipo == "naviera" and termino:
        datos = herramienta_consultar_estado(naviera_nombre=termino.strip())
    else:
        datos = herramienta_reporte_global()

    prompt = f"""Eres MIA, asistente de auditoría. El auditor pregunta sobre estado de expedientes.

DATOS DEL SISTEMA:
{datos}

PREGUNTA: {pregunta}

Responde de forma natural y útil. Si los datos no responden exactamente la pregunta, indícalo y sugiere cómo obtener la información.

FORMATO:
🤖 *MIA - ESTADO*

{datos}

💡 *Análisis:*
[interpretación breve si aplica]"""

    return consultar_ollama(prompt, temperature=0.3, num_ctx=4096)


def _modo_conversacion(texto: str, contexto: list) -> str:
    prompt = f"""Eres MIA (Maritime Intelligence Assistant), el asistente personal de Julian, auditor experto en seguridad marítima y PBIP.

Eres profesional, eficiente, con sentido del humor marino. Conoces el código PBIP, la OMI, y el trabajo de auditoría portuaria.

CONTEXTO RECIENTE:
{json.dumps(contexto[-3:], ensure_ascii=False, indent=2)}

MENSAJE DEL AUDITOR:
{texto}

Responde de forma natural y breve y ÚNICAMENTE EN ESPAÑOL (WhatsApp). 

SI el mensaje es una pregunta sobre trabajo (PBIP, navieras, buques, documentos), ofrece ayuda específica.
SI es una conversación casual (saludos, chisme, humor), responde normal sin forzar el menú.

FORMATO:
🤖 *MIA*

[tu respuesta natural]

Solo añade el menú de opciones si el usuario preguntó explícitamente qué puedes hacer o parece perdido."""

    return consultar_ollama(prompt, temperature=0.4, num_ctx=4096)