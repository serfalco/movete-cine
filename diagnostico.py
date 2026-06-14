"""
diagnostico.py — Segunda pasada: medir si el meta description de El Día trae
la cartelera COMPLETA o truncada, y buscar dónde está la cartelera entera.
"""
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0"}

def L(t=""): print(t, flush=True)

# 1) Encontrar la guía vigente
SEC = "https://www.eldia.com/seccion/espectaculos"
r = requests.get(SEC, headers=HEADERS, timeout=25)
m = re.search(r'href="([^"]*guia-de-cines-espectaculos_[^"]*)"', r.text)
url = "https://www.eldia.com" + m.group(1) if m else None
L(f"Guía vigente: {url}")

r = requests.get(url, headers=HEADERS, timeout=25)
html = r.text
L(f"HTML total: {len(html)} bytes")
soup = BeautifulSoup(html, "html.parser")

L("")
L("=== LARGO DE CADA META ===")
for attrs in [{"name":"description"},{"property":"og:description"},{"name":"twitter:description"}]:
    tag = soup.find("meta", attrs=attrs)
    if tag and tag.get("content"):
        c = tag["content"]
        # contar cuantos cines y cuantas pelis (.-) hay en el meta
        cines = len(re.findall(r'\([^)]*(?:Te\.|N[º°])[^)]*\)', c))
        pelis = c.count('.-')
        L(f"{attrs}: {len(c)} chars | ~{cines} cines | {pelis} pelis (.-)")

L("")
L("=== ¿LA CARTELERA COMPLETA ESTÁ EN EL BODY? ===")
# Buscar todas las apariciones de salas conocidas en el HTML crudo
for sala in ["SAN MART", "CINEMA CITY", "OCHO", "PARADISO", "ROCHA", "SELECT", "ECOSELECT"]:
    n = html.upper().count(sala)
    if n:
        L(f"  '{sala}' aparece {n}x en el HTML")

# Contar cuantos '.-' hay en TODO el html (señal de cuantas pelis hay en total)
total_marcadores = html.count('.-')
L(f"  Total de marcadores '.-' en el HTML completo: {total_marcadores}")

L("")
L("=== ¿HAY UN JSON-LD O SCRIPT CON EL CUERPO? ===")
scripts = soup.find_all("script")
L(f"  scripts totales: {len(scripts)}")
for s in scripts:
    txt = s.string or ""
    if ".-" in txt and ("cast." in txt.lower() or "subt." in txt.lower()):
        L(f"  ¡script con cartelera! largo {len(txt)}")
        L("  muestra: " + re.sub(r'\s+',' ',txt[:300]))
        break

# Buscar el cuerpo del articulo (aunque este el muro)
L("")
L("=== CUERPO DEL ARTÍCULO (primeros 1500 chars de texto visible) ===")
art = soup.find("article") or soup.find("div", class_=re.compile("nota|article|cuerpo|content", re.I))
if art:
    t = re.sub(r'\s+',' ', art.get_text(' ', strip=True))
    L(f"  largo cuerpo: {len(t)} | marcadores .- : {t.count('.-')}")
    L("  " + t[:1500])
else:
    L("  no encontré <article>")
