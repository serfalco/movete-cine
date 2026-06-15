"""
main.py — Orquestador del sistema de cine de MoVeTe.
Corre los jueves: junta cine tradicional (El Día) + alternativo (AgendaLP),
genera la página de la semana y la guarda en cine/AAAA-MM-DD.html

Principio rector: si una pata falla, la otra sigue. La página sale igual.
"""

import os
import sys
import json
from datetime import datetime, timedelta

from scraper_eldia import scrapear_cine_tradicional
from scraper_agendalp_cine import scrapear_cine_alternativo
from generar_html import generar
import tmdb

CACHE_PATH = "cine/peliculas.json"
ALIAS_PATH = "alias.json"


def _cargar_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def enriquecer_con_tmdb(tradicional):
    """Adjunta a cada película un campo 'tmdb' con sus datos (o None).

    Usa caché (peliculas.json) para no re-buscar títulos ya conocidos, y
    alias.json para los títulos que TMDb tiene con otro nombre.

    BLINDADO: ante cualquier problema, la película queda sin 'tmdb' y la
    página se genera igual (cae al placeholder).
    """
    if not tmdb.disponible():
        print("[main] Sin TMDB_API_KEY: se usa placeholder en todos los pósters.",
              file=sys.stderr)
        return tradicional, []

    cache = _cargar_json(CACHE_PATH, {})
    alias = _cargar_json(ALIAS_PATH, {})
    no_encontrados = []
    nuevos = 0

    for cine in tradicional:
        for peli in cine["peliculas"]:
            titulo = peli["titulo"]
            clave = tmdb.limpiar_titulo(titulo)

            if clave in cache:
                peli["tmdb"] = cache[clave]  # puede ser dict o None
                continue

            info = tmdb.buscar_pelicula(titulo, alias=alias)
            cache[clave] = info            # cacheamos también los None
            peli["tmdb"] = info
            nuevos += 1
            if info is None:
                no_encontrados.append(clave)

    # Guardar caché actualizado
    try:
        os.makedirs("cine", exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)
    except OSError as e:
        print(f"[main] No pude guardar caché de pósters: {e}", file=sys.stderr)

    print(f"[main] TMDb: {nuevos} títulos nuevos buscados, "
          f"{len(no_encontrados)} sin match.", file=sys.stderr)
    return tradicional, no_encontrados


def jueves_de_esta_semana(hoy=None):
    """Devuelve el jueves de la semana actual (o el de hoy si es jueves)."""
    if hoy is None:
        hoy = datetime.now()
    # weekday(): lunes=0 ... jueves=3
    delta = (hoy.weekday() - 3) % 7
    return (hoy - timedelta(days=delta)).replace(
        hour=0, minute=0, second=0, microsecond=0)


def main():
    jueves = jueves_de_esta_semana()
    print(f"== MoVeTe Cine == semana del {jueves.date()}", file=sys.stderr)

    # Pata A: cine tradicional (El Día). Si falla, lista vacía.
    try:
        tradicional = scrapear_cine_tradicional()
    except Exception as e:
        print(f"[main] Pata tradicional falló: {e}", file=sys.stderr)
        tradicional = []

    # Pata C: cine alternativo (AgendaLP), jueves -> miércoles (7 días).
    try:
        alternativo = scrapear_cine_alternativo(desde=jueves, dias=7)
    except Exception as e:
        print(f"[main] Pata alternativa falló: {e}", file=sys.stderr)
        alternativo = []

    # Si las dos patas fallan del todo, no pisamos una página vieja buena.
    if not tradicional and not alternativo:
        print("[main] Ambas fuentes vacías. No se genera página.", file=sys.stderr)
        sys.exit(1)

    # Enriquecer cine tradicional con TMDb (póster, sinopsis, año, duración,
    # género). Blindado: si falla, cada película cae al placeholder.
    tradicional, no_encontrados = enriquecer_con_tmdb(tradicional)

    html = generar(tradicional, alternativo, jueves)

    os.makedirs("cine", exist_ok=True)
    salida = os.path.join("cine", f"{jueves.strftime('%Y-%m-%d')}.html")
    with open(salida, "w", encoding="utf-8") as f:
        f.write(html)

    # También actualizamos cine/index.html -> redirige a la última
    with open(os.path.join("cine", "index.html"), "w", encoding="utf-8") as f:
        f.write(_redirect(jueves.strftime('%Y-%m-%d')))

    print(f"[main] Generado: {salida}", file=sys.stderr)

    # Reporte capa 4: títulos sin match en TMDb, para agregar a alias.json.
    if no_encontrados:
        print("[main] --- Sin afiche/datos (revisá alias.json) ---",
              file=sys.stderr)
        for t in no_encontrados:
            print(f"[main]   · {t}", file=sys.stderr)

    print(salida)


def _redirect(fecha_iso):
    destino = f"/cine/{fecha_iso}.html"
    return (f'<!DOCTYPE html><html lang="es-AR"><head><meta charset="UTF-8">'
            f'<meta http-equiv="refresh" content="0; url={destino}">'
            f'<link rel="canonical" href="https://movete.info{destino}">'
            f'<title>Cine en La Plata · MoVeTe</title></head>'
            f'<body>Redirigiendo a la <a href="{destino}">cartelera de esta semana</a>.</body></html>')


if __name__ == "__main__":
    main()
