import os
import requests
import PyPDF2
import io
# Dentro de agente_mia.py
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

# MIA ahora tiene memoria de largo plazo
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
CHROMA_PATH = os.path.join(BASE_DIR, "..", "scripts", "chroma_db")

embeddings = OllamaEmbeddings(model="nomic-embed-text")
vector_db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

def consultar_normativa(tema):
    # k=3 es suficiente, más es confundir a la IA
    docs_con_score = vector_db.similarity_search_with_score(tema, k=3)
    
    # Filtro de confianza: Si el score es muy alto (poca similitud en Chroma), lo ignoramos
    contexto_valido = []
    for doc, score in docs_con_score:
        # Solo aceptamos si hay coincidencia de palabras clave marítimas reales
        if any(word in doc.page_content.upper() for word in ["SSAS", "ALERTA", "PRUEBA", "PROTECCIÓN", "BUQUE"]):
            contexto_valido.append(doc.page_content)
    
    if not contexto_valido:
        return "No hay normativa específica para este equipo en la base de datos actual. Usa criterio general del Código PBIP Parte A, Sección 13."
        
    return "\n---\n".join(contexto_valido)

def extraer_texto_pdf(ruta_archivo):
    try:
        with open(ruta_archivo, 'rb') as f:
            lector = PyPDF2.PdfReader(f)
            texto = ""
            for pagina in lector.pages:
                texto += pagina.extract_text()
            return texto
    except Exception as e:
        return f"Error leyendo PDF: {e}"

def consultar_ollama(prompt):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen2.5:14b", # O el que tengas (llama3, etc)
        "prompt": prompt,
        "stream": False
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
        return r.json().get('response', 'No hubo respuesta de la IA')
    except Exception as e:
        return f"Error de IA: {e}"

def ejecutar_analisis_mia(documento_obj):
    nombre_raw = documento_obj.nombre_documento
    ruta = documento_obj.archivo.path # Necesitamos la ruta para leer el PDF
    
    # 1. LEER EL DOCUMENTO (Esta es la línea que faltaba)
    contenido_cliente = extraer_texto_pdf(ruta)
    
    # 2. MIA extrae el "Concepto Técnico" dinámicamente
    # Esto evita que busque "21 FORMATO..." y mejor busque "Prueba SSAS"
    query_ia = f"Extrae solo las 3 palabras clave principales de este nombre de documento: {nombre_raw}"
    tema_tecnico = consultar_ollama(query_ia).replace('"', '') 
    
    # 3. Busca en la memoria con el tema limpio
    try:
        contexto_legal = consultar_normativa(tema_tecnico)
    except Exception as e:
        contexto_legal = "No se pudo acceder a la base de datos técnica."
        print(f"Error en RAG: {e}")

    # 4. El Prompt de Auditoría
    prompt = f"""
    Eres MIA, auditora experta en el Código PBIP. 
    PROHIBIDO decir que la normativa no se relaciona. Todo documento que recibes ES PARTE de la seguridad marítima.

    CONTEXTO TÉCNICO:
    {contexto_legal}

    TEXTO A AUDITAR:
    {contenido_cliente[:3000]}

    INSTRUCCIONES DE AUDITORÍA (ESTRICTO):
    1. Tipo de documento: Identifícalo (ej. Certificado de Competencia).
    2. Extracción: Nombre del Titular, Folio y Vencimiento.
    3. Validación: Si el texto NO tiene folio o vencimiento, dictamina "NO CUMPLE" por falta de integridad documental.
    4. Formato de respuesta: Solo envía el reporte para WhatsApp, sin introducciones ni resúmenes extra.

    EJEMPLO DE SALIDA:
    🤖 *MIA INFORMA: AUDITORÍA TÉCNICA*
    📄 *Archivo:* [Nombre]
    🔍 *Análisis:* [Breve análisis técnico]
    ✅/❌ *Dictamen:* [Cumple/No Cumple]
    """
    
    # 5. Respuesta de Ollama
    resultado_ia = consultar_ollama(prompt)
    
    # 6. Reporte final
    reporte = (
        f"🤖 *MIA INFORMA: AUDITORÍA TÉCNICA*\n\n"
        f"📄 *Archivo:* {nombre_raw}\n"
        f"🔍 *Análisis:* {resultado_ia}\n"
    )
    
    enviar_whatsapp_mia(reporte)
    return True

def enviar_whatsapp_mia(mensaje):
    url = "http://localhost:9000/enviar"
    payload = {"numero": "5215581073859", "mensaje": mensaje}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass