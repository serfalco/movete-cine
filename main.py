"""Orquestador del sistema de cine de MoVeTe.

Junta cine tradicional (El Día) + alternativo (AgendaLP), genera la página de la
semana y la guarda en una salida estática compatible con Movete-info.

Salida por defecto:
  cine/AAAA-MM-DD/index.html
  cine/index.html

En CI se puede configurar con:
  MOVETE_CINE_OUT=../Movete-info/cine
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

import tmdb
from generar_html import generar
from scraper_agendalp_cine import scrapear_cine_alternativo
from scraper_eldia import scrapear_cine_tradicional

ALIAS_PATH = "alias.json"


def _out_dir() -> Path:
    return Path(os.environ.get("MOVETE_CINE_OUT", "cine"))


def _cache_path() -> Path:
    return _out_dir() / "peliculas.json"


def _cargar_json(path: str | Path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def enriquecer_con_tmdb(tradicional):
    """Adjunta a cada película un campo 'tmdb' con sus datos o None.

    Blindado: ante cualquier problema, la película queda sin datos y la página se
    genera igual con placeholder.
    """
    if not tmdb.disponible():
        print("[main] Sin TMDB_API_KEY: se usa placeholder en todos los pósters.", file=sys.stderr)
        return tradicional, []

    cache_path = _cache_path()
    cache = _cargar_json(cache_path, {})
    alias = _cargar_json(ALIAS_PATH, {})
    no_encontrados = []
    nuevos = 0

    for cine in tradicional:
        for peli in cine.get("peliculas", []):
            titulo = peli.get("titulo", "")
            clave = tmdb.limpiar_titulo(titulo)
            if clave in cache:
                peli["tmdb"] = cache[clave]
                continue
            info = tmdb.buscar_pelicula(titulo, alias=alias)
            cache[clave] = info
            peli["tmdb"] = info
            nuevos += 1
            if info is None:
                no_encontrados.append(clave)

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    except OSError as exc:
        print(f"[main] No pude guardar caché de pósters: {exc}", file=sys.stderr)

    print(
        f"[main] TMDb: {nuevos} títulos nuevos buscados, {len(no_encontrados)} sin match.",
        file=sys.stderr,
    )
    return tradicional, no_encontrados


def jueves_de_esta_semana(hoy: datetime | None = None) -> datetime:
    """Devuelve el jueves de la semana actual."""
    hoy = hoy or datetime.now()
    delta = (hoy.weekday() - 3) % 7  # lunes=0, jueves=3
    return (hoy - timedelta(days=delta)).replace(hour=0, minute=0, second=0, microsecond=0)


def main() -> None:
    jueves = jueves_de_esta_semana()
    slug = jueves.strftime("%Y-%m-%d")
    out_dir = _out_dir()

    print(f"== MoVeTe Cine == semana del {jueves.date()}", file=sys.stderr)

    try:
        tradicional = scrapear_cine_tradicional()
    except Exception as exc:  # noqa: BLE001
        print(f"[main] Pata tradicional falló: {exc}", file=sys.stderr)
        tradicional = []

    try:
        alternativo = scrapear_cine_alternativo(desde=jueves, dias=7)
    except Exception as exc:  # noqa: BLE001
        print(f"[main] Pata alternativa falló: {exc}", file=sys.stderr)
        alternativo = []

    if not tradicional and not alternativo:
        print("[main] Ambas fuentes vacías. No se genera página.", file=sys.stderr)
        sys.exit(1)

    tradicional, no_encontrados = enriquecer_con_tmdb(tradicional)
    html = generar(tradicional, alternativo, jueves)

    edicion_dir = out_dir / slug
    edicion_dir.mkdir(parents=True, exist_ok=True)
    salida = edicion_dir / "index.html"
    salida.write_text(html, encoding="utf-8")

    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(salida, out_dir / "index.html")

    print(f"[main] Generado: {salida}", file=sys.stderr)

    if no_encontrados:
        print("[main] --- Sin afiche/datos (revisá alias.json) ---", file=sys.stderr)
        for titulo in no_encontrados:
            print(f"[main] · {titulo}", file=sys.stderr)

    print(salida)


if __name__ == "__main__":
    main()
