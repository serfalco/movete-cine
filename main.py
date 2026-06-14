"""
main.py — Orquestador del sistema de cine de MoVeTe.
Corre los jueves: junta cine tradicional (El Día) + alternativo (AgendaLP),
genera la página de la semana y la guarda en cine/AAAA-MM-DD.html

Principio rector: si una pata falla, la otra sigue. La página sale igual.
"""

import os
import sys
from datetime import datetime, timedelta

from scraper_eldia import scrapear_cine_tradicional
from scraper_agendalp_cine import scrapear_cine_alternativo
from generar_html import generar


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

    html = generar(tradicional, alternativo, jueves)

    os.makedirs("cine", exist_ok=True)
    salida = os.path.join("cine", f"{jueves.strftime('%Y-%m-%d')}.html")
    with open(salida, "w", encoding="utf-8") as f:
        f.write(html)

    # También actualizamos cine/index.html -> redirige a la última
    with open(os.path.join("cine", "index.html"), "w", encoding="utf-8") as f:
        f.write(_redirect(jueves.strftime('%Y-%m-%d')))

    print(f"[main] Generado: {salida}", file=sys.stderr)
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
