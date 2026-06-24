"""Generador HTML de Cine para MoVeTe."""

from __future__ import annotations

import html
from collections import defaultdict
from datetime import datetime, timedelta

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
POSTER_PLACEHOLDER = "/assets/img/cine-placeholder.jpg"


def esc(valor: object) -> str:
    return html.escape(str(valor or ""), quote=True)


def rango_texto(jueves: datetime) -> str:
    fin = jueves + timedelta(days=6)
    if jueves.month == fin.month:
        return f"{jueves.day} al {fin.day} de {MESES[fin.month - 1]}"
    return f"{jueves.day} de {MESES[jueves.month - 1]} al {fin.day} de {MESES[fin.month - 1]}"


def meta_badges(idioma: str, formato: str) -> str:
    badges = []
    if idioma:
        idi = "Subtitulada" if idioma.lower().startswith("subt") else "Castellano"
        badges.append(f'<span class="pill">{esc(idi)}</span>')
    if formato:
        badges.append(f'<span class="pill">{esc(formato)}</span>')
    return "".join(badges)


def ficha_extra(info: dict | None) -> str:
    if not info:
        return ""

    partes = []

    if info.get("anio"):
        partes.append(str(info["anio"]))

    if info.get("duracion"):
        try:
            partes.append(f"{int(info['duracion'])} min")
        except (TypeError, ValueError):
            pass

    if info.get("generos"):
        partes.append(" · ".join(info["generos"]))

    if not partes:
        return ""

    return f'<p class="event-meta">{esc(" · ".join(partes))}</p>'


def sinopsis_html(info: dict | None) -> str:
    if info and info.get("sinopsis"):
        return f'<p>{esc(info["sinopsis"])}</p>'
    return ""


def poster_url(info: dict | None) -> str:
    if info and info.get("poster"):
        return esc(info["poster"])
    return POSTER_PLACEHOLDER


def bloque_tradicional(cines: list[dict]) -> str:
    if not cines:
        return '<p class="empty">Esta semana no hay cartelera comercial disponible.</p>'

    bloques = []

    for cine in cines:
        peliculas = []

        for peli in cine.get("peliculas", []):
            info = peli.get("tmdb")
            horarios = peli.get("horarios", [])
            horarios_html = "".join(f"<li>{esc(h)}</li>" for h in horarios)

            peliculas.append(
                f"""
                <article class="movie-card">
                  <img class="movie-poster" src="{poster_url(info)}" alt="Afiche de {esc(peli.get('titulo'))}" loading="lazy">
                  <div>
                    <h3>{esc(peli.get('titulo'))}</h3>
                    {ficha_extra(info)}
                    <div class="pill-row">{meta_badges(peli.get('idioma', ''), peli.get('formato', ''))}</div>
                    {sinopsis_html(info)}
                    <ul class="times">{horarios_html}</ul>
                  </div>
                </article>
                """
            )

        bloques.append(
            f"""
            <section class="day-block">
              <h2>{esc(cine.get('cine'))}</h2>
              <p class="event-meta">{esc(cine.get('direccion'))}</p>
              <div class="movie-list">
                {''.join(peliculas)}
              </div>
            </section>
            """
        )

    return "\n".join(bloques)


def bloque_alternativo(funciones: list[dict]) -> str:
    if not funciones:
        return '<p class="empty">Esta semana no hay funciones alternativas cargadas.</p>'

    por_fecha: dict[str, list[dict]] = defaultdict(list)

    for funcion in funciones:
        por_fecha[funcion.get("fecha", "")].append(funcion)

    bloques = []

    for fecha in sorted(por_fecha):
        try:
            d = datetime.strptime(fecha, "%Y-%m-%d")
            dia_label = f"{DIAS[d.weekday()]} {d.day} {MESES[d.month - 1]}"
        except ValueError:
            dia_label = fecha

        cards = []

        for funcion in sorted(por_fecha[fecha], key=lambda x: x.get("hora", "")):
            cards.append(
                f"""
                <article class="event-card">
                  <p class="event-date">{esc(funcion.get('hora'))} hs</p>
                  <h3>{esc(funcion.get('titulo'))}</h3>
                  <p class="event-meta">{esc(funcion.get('espacio'))}</p>
                  <p class="pill">Cine alternativo</p>
                </article>
                """
            )

        bloques.append(
            f"""
            <section class="day-block">
              <h2>{esc(dia_label)}</h2>
              <div class="grid cards">
                {''.join(cards)}
              </div>
            </section>
            """
        )

    return "\n".join(bloques)


def generar(cines_tradicional: list[dict], funciones_alternativo: list[dict], jueves: datetime) -> str:
    rango = rango_texto(jueves)
    fecha_iso = jueves.strftime("%Y-%m-%d")
    trad = bloque_tradicional(cines_tradicional)
    alt = bloque_alternativo(funciones_alternativo)

    total_peliculas = sum(len(c.get("peliculas", [])) for c in cines_tradicional)
    total_alt = len(funciones_alternativo)

    return f"""<!doctype html>
<html lang="es-AR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cartelera de cine en La Plata · Semana del {esc(rango)} · MoVeTe</title>
  <meta name="description" content="Cartelera de cine en La Plata. Cine tradicional y cine alternativo. Edición semanal del {esc(rango)}.">
  <link rel="stylesheet" href="/assets/css/movete.css">
</head>

<body>
  <header class="site-header">
    <a class="brand" href="/">MoVeTe<span>●</span></a>
    <nav>
      <a href="/cine/">Cine</a>
      <a href="/en-vivo/">En vivo</a>
    </nav>
  </header>

  <main>
    <section class="hero compact">
      <p class="eyebrow">Cine · Edición {esc(fecha_iso)}</p>
      <h1>Cartelera de cine en La Plata</h1>
      <p class="lead">Cada semana, todo el cine de la ciudad.</p>
      <div class="actions">
        <a class="button" href="#cine-tradicional">Cine tradicional</a>
        <a class="button secondary" href="#cine-alternativo">Cine alternativo</a>
      </div>
    </section>

    <section class="card edition-summary">
      <p class="tag">En esta edición</p>
      <h2>{total_peliculas} películas en salas tradicionales y {total_alt} funciones en salas alternativas.</h2>
      <p>MoVeTe · Cartelera Cultural del Gran La Plata · Edición {esc(fecha_iso)}</p>
    </section>

    <section id="cine-tradicional" class="section">
      <p class="eyebrow">Cartelera comercial</p>
      <h2>Cine tradicional</h2>
      <p>Salas comerciales de La Plata. Confirmá siempre el horario con el cine antes de salir.</p>
      {trad}
    </section>

    <section id="cine-alternativo" class="section">
      <p class="eyebrow">Cineclubes y espacios culturales</p>
      <h2>Cine alternativo</h2>
      <p>Ciclos, funciones especiales, INCAA, proyecciones y cineclubes.</p>
      {alt}
    </section>

    <section class="ad-box">
      <p class="ad-label">Espacio promocional</p>
      <h2>Tres Empanadas Comedia</h2>
      <p>Stand up en La Plata. Shows a la gorra, todos los viernes.</p>
      <a class="button small" href="https://tresempanadas.com.ar/reservas">Reservar</a>
    </section>

    <section class="card">
      <p class="tag">También en MoVeTe</p>
      <h2>Agenda de espectáculos en La Plata</h2>
      <p>Teatro, música, stand up, danza y eventos en vivo de la semana.</p>
      <a href="/en-vivo/">Ver En Vivo →</a>
    </section>
  </main>

  <footer class="site-footer">
    <p>MoVeTe · Cine y agenda cultural del Gran La Plata · Edición {esc(fecha_iso)}</p>
    <p>Información de películas y afiches: The Movie Database (TMDb). Este producto usa la API de TMDb pero no está avalado ni certificado por TMDb.</p>
  </footer>
</body>
</html>
"""
