# portal_cliente/mia_core.py
import json
from typing import Optional

from .mia_memoria import obtener_contexto, guardar_mensaje
from .mia_herramientas import (
    consultar_ollama,
    herramienta_consultar_pbip,
    herramienta_consultar_estado,
    herramienta_reporte_global,
    enviar_whatsapp_jid
)
from .mia_documentos import herramienta_analizar_documento


def procesar_input_mia(texto_usuario=None, documento_obj=None, numero_whatsapp=None, jid_remitente=None):
    """
    ÚNICO punto de entrada para MIA.
    Desde views.py (portal), webhook (WhatsApp), o scheduler (cron).
    """
    
    # 1. MEMORIA
    numero = numero_whatsapp or (jid_remitente.split('@')[0] if jid_remitente else "unknown")
    contexto = obtener_contexto(numero) if numero else []
    
    # 2. CLASIFICAR
    if documento_obj:
        intencion = "ANALISIS_DOCUMENTO"
        entidades = {"documento": documento_obj.nombre_documento}
    else:
        intencion, entidades = _clasificar_intencion(texto_usuario or "", contexto)
    
    # 3. EJECUTAR
    if intencion == "ANALISIS_DOCUMENTO":
        # El analisis es async, pero capturamos errores
        try:
            respuesta = herramienta_analizar_documento(documento_obj, jid_remitente)
        except Exception as e:
            print(f"ERROR en analisis documento: {e}")
            import traceback
            print(traceback.format_exc())
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
    if numero and texto_usuario:
        guardar_mensaje(numero, "user", texto_usuario, intencion, entidades)
        if respuesta:
            guardar_mensaje(numero, "mia", respuesta, intencion, entidades)
    
    return respuesta


def _clasificar_intencion(texto: str, contexto: list):
    """
    Clasificador híbrido: keywords rápidas + LLM para ambigüedades.
    Devuelve: (intencion_str, entidades_dict)
    """
    texto_lower = texto.lower().strip()
    entidades = {}
    
    # --- REGLAS RÁPIDAS (90% de casos) ---
    
    # Documentos
    if any(k in texto_lower for k in ["documento", "pdf", "archivo", "analiza", "revisa esto", "subí", "subi"]):
        return "ANALISIS_DOCUMENTO", entidades
    
    # Normativa PBIP
    pbip_keywords = ["pbip", "código", "codigo", "normativa", "artículo", "articulo", 
                     "omi", "reglamento", "ley", "circular", "resolución", "resolucion",
                     "control de acceso", "pfso", "opb", "sso", "csp", "isps"]
    if any(k in texto_lower for k in pbip_keywords):
        # Extraer tema específico
        entidades["tema_pbip"] = texto
        return "CONSULTA_NORMATIVA", entidades
    
    # Estado / Reporte
    if texto_lower in ["estado", "reporte", "status"]:
        return "REPORTE_GLOBAL", entidades
    
    estado_keywords = ["cómo va", "como va", "progreso", "porcentaje", "falta", 
                       "completado", "expediente", "avance"]
    if any(k in texto_lower for k in estado_keywords):
        # Extraer entidades
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
    
    # Ayuda / Comandos
    if any(k in texto_lower for k in ["ayuda", "help", "comandos", "qué puedes hacer", "que puedes hacer"]):
        return "AYUDA", entidades
    
    # --- FALLBACK: LLM para casos ambiguos ---
    return _clasificar_con_llm(texto, contexto)


def _clasificar_con_llm(texto: str, contexto: list):
    prompt = f"""Eres el clasificador de MIA. Clasifica el mensaje del auditor en UNA categoría:

CATEGORÍAS:
- CONSULTA_NORMATIVA: Pregunta sobre PBIP, OMI, regulaciones, normas marítimas
- CONSULTA_ESTADO: Pregunta sobre navieras, buques, progreso, expedientes
- CONVERSACION_GENERAL: Saludos, despedidas, preguntas sobre MIA, chit-chat
- RECORDATORIO: Solicita alertas, recordatorios, notificaciones

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
    
    # Consultar Chroma
    articulos = herramienta_consultar_pbip(tema, k=5)
    
    if "No encontré" in articulos:
        return f"🤖 *MIA*\n\nNo encontré información sobre '{tema}' en el código PBIP.\n\n💡 *Sugerencia:* Intenta con términos más específicos como \"control de acceso\", \"PFSO\", \"evaluación de riesgos\", etc."
    
    # Generar respuesta con LLM
    prompt = f"""Eres MIA, experto en Código PBIP. Responde basándote EXCLUSIVAMENTE en estos artículos oficiales:

{articulos}

PREGUNTA DEL AUDITOR:
{pregunta}

INSTRUCCIONES:
1. Responde en español, claro y conciso
2. Cita los artículos específicos con su referencia completa
3. Si la información no está en los artículos, dilo claramente
4. Sé profesional pero cercano
5. Formato WhatsApp: usa *negritas* para énfasis

FORMATO DE RESPUESTA:
🤖 *MIA - CONSULTA PBIP*

📜 *Artículos consultados:*
[lista breve]

💡 *Respuesta:*
[respuesta detallada y estructurada]

📌 *Referencias específicas:*
[citas exactas de artículos]"""
    
    return consultar_ollama(prompt, temperature=0.3)


def _modo_consulta_estado(pregunta: str, entidades: dict, contexto: list) -> str:
    tipo = entidades.get("tipo_busqueda")
    termino = entidades.get("termino")
    
    # Si no extrajo entidades, intentar del contexto previo
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
    
    # Ejecutar consulta
    if tipo == "omi" and termino:
        datos = herramienta_consultar_estado(omi=termino.strip())
    elif tipo == "buque" and termino:
        datos = herramienta_consultar_estado(buque_nombre=termino.strip())
    elif tipo == "naviera" and termino:
        datos = herramienta_consultar_estado(naviera_nombre=termino.strip())
    else:
        # Sin entidades claras, reporte global
        datos = herramienta_reporte_global()
    
    # Generar respuesta natural con LLM
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
    
    return consultar_ollama(prompt, temperature=0.3)

def _modo_conversacion(texto: str, contexto: list) -> str:
    prompt = f"""Eres MIA (Maritime Intelligence Assistant), el asistente personal de Julian, auditor experto en seguridad marítima y PBIP.

Eres profesional, eficiente, con sentido del humor marino. Conoces el código PBIP, la OMI, y el trabajo de auditoría portuaria.

CONTEXTO RECIENTE:
{json.dumps(contexto[-3:], ensure_ascii=False, indent=2)}

MENSAJE DEL AUDITOR:
{texto}

Responde de forma natural y breve (WhatsApp). 

SI el mensaje es una pregunta sobre trabajo (PBIP, navieras, buques, documentos), ofrece ayuda específica.
SI es una conversación casual (saludos, chisme, humor), responde normal sin forzar el menú.

FORMATO:
🤖 *MIA*

[tu respuesta natural]

Solo añade el menú de opciones si el usuario preguntó explícitamente qué puedes hacer o parece perdido."""
    
    return consultar_ollama(prompt, temperature=0.7)
