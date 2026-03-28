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
    # k=3 está perfecto. Eliminamos el filtro de palabras manual que limitaba a MIA.
    docs_con_score = vector_db.similarity_search_with_score(tema, k=3)
    
    # Filtro de distancia: En Chroma/Nomic, un score menor a 0.5 - 0.6 suele ser muy buena coincidencia.
    contexto_valido = [doc.page_content for doc, score in docs_con_score if score < 0.8]
    
    if not contexto_valido:
        # Si no encuentra nada específico, le damos la Sección 12 y 13 que son el "cajón de sastre"
        # Hacemos una búsqueda forzada por metadatos o texto directo
        backup = vector_db.similarity_search("Seccion 12 Oficial de proteccion del buque", k=1)
        return backup[0].page_content if backup else "Criterio general Código PBIP Parte A."
        
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
    ruta = documento_obj.archivo.path
    
    # 1. Extracción y Normalización
    contenido_cliente = extraer_texto_pdf(ruta)
    contenido_cliente_limpio = " ".join(contenido_cliente.split())

    # 2. Búsqueda de Referencia Directa (Lo que el documento CITA)
    import re
    referencias = re.findall(r"(?i)(Parte [A|B]/?\s?\d+\.?\d*)", contenido_cliente_limpio)
    
    # 3. Consulta a Chroma enfocada SOLO en lo que el documento dice tratar
    # Si el documento dice "Ejercicios", buscamos "Ejercicios", no "Auditorías"
    contexto_legal = consultar_normativa(f"Requisitos específicos para {referencias[0] if referencias else 'Ejercicios y Prácticas PBIP'}")

    # 4. EL PROMPT DE AUDITORÍA OBJETIVA (Checklist)
    prompt = f"""
    Eres MIA, Auditora Técnica. Tu único trabajo es verificar si este papel cumple su función.
    
    NORMATIVA TÉCNICA:
    {contexto_legal}

    DOCUMENTO DEL CLIENTE:
    {contenido_cliente_limpio[:4000]}

    PROTOCOLO:
    1. ¿El documento identifica al buque PROTEUS (9247522)?
    2. ¿El contenido corresponde a la Base Legal que el propio documento cita? 
    3. REGLA DE ORO: Si es un PROGRAMA de ejercicios, solo verifica que tenga los ejercicios y fechas. NO pidas procedimientos de revisión, auditoría o firmas de terceros que no correspondan a la ejecución de ejercicios.
    4. Si tiene el buque, los ejercicios y la programación trimestral/anual: CUMPLE.

    RESPUESTA:
    🤖 *MIA INFORMA: AUDITORÍA TÉCNICA*
    📄 *Archivo:* {nombre_raw}
    🔍 *Análisis:* [Resumen seco: 'Se presenta programa de ejercicios para el PROTEUS con frecuencia trimestral según B/13.5']
    📜 *Base Legal:* [La que cite el documento, ej: Parte B/13.5]
    ✅/❌ *Dictamen:* [Cumple / No Cumple]
    """
    
    resultado_ia = consultar_ollama(prompt)
    enviar_whatsapp_mia(resultado_ia)
    return True

def enviar_whatsapp_mia(mensaje):
    url = "http://localhost:9000/enviar"
    payload = {"numero": "5215581073859", "mensaje": mensaje}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass