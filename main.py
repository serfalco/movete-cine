"""Orquestador del sistema de cine de MoVeTe.

Genera la cartelera semanal jueves→miércoles y escribe:

- /index.html portada vigente de Cine
- /YYYY-MM-DD/index.html edición archivada

Ejemplo local:

python main.py --output ../Movete-info/cine
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import tmdb
from generar_html import generar
from scraper_agendalp_cine import scrapear_cine_alternativo
from scraper_eldia import scrapear_cine_tradicional


ALIAS_PATH = "alias.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera cartelera de cine para MoVeTe")
    parser.add_argument(
        "--output",
        default=os.environ.get("MOVETE_CINE_OUT", "../Movete-info/cine"),
        help="Carpeta de salida. Default: ../Movete-info/cine",
    )
    return parser.parse_args()


def _cargar_json(path: str | Path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def enriquecer_con_tmdb(tradicional: list[dict], cache_path: Path):
    """Adjunta a cada película un campo 'tmdb' con sus datos o None.

    Blindado: ante cualquier problema, la película queda sin datos
    y la página se genera igual con placeholder.
    """

    if not tmdb.disponible():
        print("[main] Sin TMDB_API_KEY: se usa placeholder en todos los pósters.", file=sys.stderr)
        return tradicional, []

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
        cache_path.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError as e:
        print(f"[main] No pude guardar caché de pósters: {e}", file=sys.stderr)

    print(
        f"[main] TMDb: {nuevos} títulos nuevos buscados, {len(no_encontrados)} sin match.",
        file=sys.stderr,
    )

    return tradicional, no_encontrados


def jueves_de_esta_semana(hoy: datetime | None = None) -> datetime:
    if hoy is None:
        hoy = datetime.now()
    delta = (hoy.weekday() - 3) % 7
    return (hoy - timedelta(days=delta)).replace(hour=0, minute=0, second=0, microsecond=0)


def main() -> None:
    args = parse_args()
    out = Path(args.output)
    jueves = jueves_de_esta_semana()
    slug = jueves.strftime("%Y-%m-%d")

    print(f"== MoVeTe Cine == semana del {jueves.date()}", file=sys.stderr)

    try:
        tradicional = scrapear_cine_tradicional()
    except Exception as e:  # noqa: BLE001
        print(f"[main] Pata tradicional falló: {e}", file=sys.stderr)
        tradicional = []

    try:
        alternativo = scrapear_cine_alternativo(desde=jueves, dias=7)
    except Exception as e:  # noqa: BLE001
        print(f"[main] Pata alternativa falló: {e}", file=sys.stderr)
        alternativo = []

    if not tradicional and not alternativo:
        print("[main] Ambas fuentes vacías. No se genera página.", file=sys.stderr)
        sys.exit(1)

    cache_path = out / "peliculas.json"
    tradicional, no_encontrados = enriquecer_con_tmdb(tradicional, cache_path)

    html = generar(tradicional, alternativo, jueves)

    slug_dir = out / slug
    slug_dir.mkdir(parents=True, exist_ok=True)

    (slug_dir / "index.html").write_text(html, encoding="utf-8")
    (out / "index.html").write_text(html, encoding="utf-8")

    print(f"[main] Generado: {slug_dir / 'index.html'}", file=sys.stderr)

    if no_encontrados:
        print("[main] --- Sin afiche/datos (revisá alias.json) ---", file=sys.stderr)
        for titulo in no_encontrados:
            print(f"[main] · {titulo}", file=sys.stderr)

    print(slug_dir / "index.html")


if __name__ == "__main__":
    main()
