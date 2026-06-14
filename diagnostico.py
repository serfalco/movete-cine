"""
diagnostico.py — Corre una vez en GitHub Actions para ver QUÉ reciben los
scrapers desde la IP de GitHub. No genera nada; solo imprime al log.
"""
import re
import requests
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
}

def línea(t=""): print(t, flush=True)

línea("=" * 60)
línea("DIAGNÓSTICO 1 · EL DÍA — sección espectáculos")
línea("=" * 60)
SECCION = "https://www.eldia.com/seccion/espectaculos"
try:
    r = requests.get(SECCION, headers=HEADERS, timeout=20)
    línea(f"status: {r.status_code}  | bytes: {len(r.text)}")
    # ¿hay links a la guía?
    links = re.findall(r'href="([^"]*guia-de-cines-espectaculos_[^"]*)"', r.text)
    línea(f"links a guía de cines encontrados: {len(links)}")
    for l in links[:3]:
        línea(f"   -> {l}")
    if not links:
        línea("  (no se hallaron links; muestro un fragmento del HTML)")
        línea(r.text[:800])
except Exception as e:
    línea(f"ERROR: {e}")

línea("")
línea("=" * 60)
línea("DIAGNÓSTICO 2 · EL DÍA — una nota de guía conocida")
línea("=" * 60)
# Probamos una URL de guía conocida directamente
URL_GUIA = "https://www.eldia.com/espectaculos/guia-de-cines-espectaculos_1781327428"
try:
    r = requests.get(URL_GUIA, headers=HEADERS, timeout=20)
    línea(f"status: {r.status_code}  | bytes: {len(r.text)}")
    txt = r.text
    # señales de muro de pago
    muro = any(s in txt.lower() for s in
               ["suscrib", "iniciar sesión", "artículos por mes", "registrarse"])
    línea(f"¿señales de muro/login?: {muro}")
    # ¿aparece algún cine conocido?
    for cine in ["CINEMA SAN MARTÍN", "CINEMA CITY", "SAN MARTÍN", "Cinema"]:
        if cine.lower() in txt.lower():
            línea(f"  contiene '{cine}': SÍ")
    # mostrar dónde aparece 'cast.' (señal de cartelera)
    idx = txt.lower().find("cast.")
    if idx >= 0:
        línea("  fragmento alrededor de la cartelera:")
        línea("  " + re.sub(r"\s+", " ", txt[idx-200:idx+200]))
    else:
        línea("  NO aparece 'cast.' — quizá la cartelera no está en el HTML servido")
        línea("  primeros 600 chars del body:")
        línea("  " + re.sub(r"\s+", " ", txt[:600]))
except Exception as e:
    línea(f"ERROR: {e}")

línea("")
línea("=" * 60)
línea("DIAGNÓSTICO 3 · AGENDA LA PLATA — un día con cine")
línea("=" * 60)
# Un día futuro cercano (mañana) para asegurar contenido
manana = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
URL_AG = f"https://agendalaplata.ar/genda/?fecha={manana}&filtro=cine"
línea(f"URL: {URL_AG}")
try:
    r = requests.get(URL_AG, headers=HEADERS, timeout=20)
    línea(f"status: {r.status_code}  | bytes: {len(r.text)}")
    txt = r.text
    línea(f"¿contiene la palabra 'Cine'?: {'Cine' in txt}")
    línea(f"¿contiene 'hs |'?: {'hs |' in txt or 'hs  |' in txt}")
    # ¿es app vacía cargada por JS?
    línea(f"¿contiene '<script'?: {txt.lower().count('<script')} scripts")
    línea("  primeros 600 chars:")
    línea("  " + re.sub(r"\s+", " ", txt[:600]))
except Exception as e:
    línea(f"ERROR: {e}")

línea("")
línea("FIN DIAGNÓSTICO")
