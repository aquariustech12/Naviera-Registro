#!/usr/bin/env python3
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'naviera_registro.settings')
sys.path.insert(0, '/home/julian/Naviera-Registro')
django.setup()

from portal_cliente.mia_herramientas import buscar_pbip_hibrido, _detectar_estrategia

queries = [
    ("buques de carga arqueo bruto 500", "bm25"),
    ("nivel de protección 3 medidas buque", "rerank"),
    ("plan de protección del buque contenido mínimo", "rerank"),
    ("qué es una declaración de protección marítima", "bm25"),
    ("control de acceso instalación portuaria", "semantico"),
]

for q, esperado in queries:
    print(f"\n{'='*60}")
    print(f"🔍 '{q}'")
    estrategia = _detectar_estrategia(q)
    print(f"   Estrategia detectada: {estrategia} (esperado: {esperado}) {'✅' if estrategia == esperado else '❌'}")
    
    results = buscar_pbip_hibrido(q, k=3, estrategia='auto')
    for i, r in enumerate(results):
        meta = r['metadata']
        score = r.get('final_score', r.get('bm25_score', 0))
        print(f"   {i+1}. Parte {meta.get('parte','?')} | {meta.get('seccion','?')[:50]} | score={score:.3f}")
