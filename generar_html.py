"""
generar_html.py — Generador de la página de cine de MoVeTe
Toma cine tradicional (El Día) + cine alternativo (AgendaLP) y arma una
página HTML autónoma y archivable con el diseño del tema MoVeTe.

Salida: cine/AAAA-MM-DD.html  (la fecha es el jueves de inicio de la semana)
"""

import html
import locale
from datetime import datetime, timedelta

# Placeholder único para esta versión (solo texto, sin pósters)
POSTER = "https://movete.info/wp-content/uploads/2026/05/cine-placeholder.jpg"

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _esc(t):
    return html.escape(t or "", quote=True)


def _rango_texto(jueves):
    """'18 al 24 de junio' o '30 de junio al 6 de julio'."""
    fin = jueves + timedelta(days=6)
    if jueves.month == fin.month:
        return f"{jueves.day} al {fin.day} de {MESES[fin.month - 1]}"
    return (f"{jueves.day} de {MESES[jueves.month - 1]} "
            f"al {fin.day} de {MESES[fin.month - 1]}")


def _meta_badge(idioma, formato):
    """Devuelve los <span> de meta de una película tradicional."""
    spans = []
    if idioma:
        idi = "Subtitulada" if idioma.lower().startswith("subt") else "Castellano"
        spans.append(f'<span class="idioma">{_esc(idi)}</span>')
    if formato:
        spans.append(f'<span class="formato">'
                     f'<span class="movete-pelicula-badge">{_esc(formato)}</span></span>')
    return "".join(spans)


def _ficha_extra(info):
    """Línea de año · duración · género, solo con lo que TMDb haya traído."""
    if not info:
        return ""
    partes = []
    if info.get("anio"):
        partes.append(_esc(str(info["anio"])))
    if info.get("duracion"):
        partes.append(f"{int(info['duracion'])} min")
    if info.get("generos"):
        partes.append(_esc(" · ".join(info["generos"])))
    if not partes:
        return ""
    return f'<p class="movete-pelicula-ficha">{" · ".join(partes)}</p>'


def _sinopsis_html(info):
    if info and info.get("sinopsis"):
        return f'<p class="movete-pelicula-sinopsis">{_esc(info["sinopsis"])}</p>'
    return ""


def _bloque_tradicional(cines):
    if not cines:
        return ('<p class="movete-cine-vacio">Esta semana no hay cartelera '
                'comercial disponible.</p>')
    out = []
    for c in cines:
        pelis = []
        for p in c["peliculas"]:
            funciones = "".join(f"<li>{_esc(h)}</li>" for h in p["horarios"])
            meta = _meta_badge(p.get("idioma", ""), p.get("formato", ""))

            # Datos TMDb que main.py adjuntó a la película (o None).
            info = p.get("tmdb")
            poster = (info or {}).get("poster") or POSTER
            ficha = _ficha_extra(info)
            sinopsis = _sinopsis_html(info)

            pelis.append(f"""
      <article class="movete-pelicula">
        <img class="movete-pelicula-poster" src="{poster}" loading="lazy"
             alt="Afiche de {_esc(p['titulo'])}">
        <div class="movete-pelicula-info">
          <h4 class="movete-pelicula-titulo">{_esc(p['titulo'])}</h4>
          {ficha}
          <p class="movete-pelicula-meta">{meta}</p>
          {sinopsis}
          <ul class="movete-pelicula-funciones">{funciones}</ul>
        </div>
      </article>""")
        out.append(f"""
  <section class="movete-cine">
    <h3 class="movete-cine-title">{_esc(c['cine'])}</h3>
    <p class="movete-cine-direccion">{_esc(c['direccion'])}</p>
    <div class="movete-pelicula-grid">{''.join(pelis)}
    </div>
  </section>""")
    return "".join(out)


def _bloque_alternativo(funciones):
    if not funciones:
        return ('<p class="movete-cine-vacio">Esta semana no hay funciones '
                'alternativas cargadas.</p>')
    # Agrupar por fecha para que se lea como agenda
    por_fecha = {}
    for f in funciones:
        por_fecha.setdefault(f["fecha"], []).append(f)

    out = []
    for fecha in sorted(por_fecha):
        try:
            d = datetime.strptime(fecha, "%Y-%m-%d")
            dia_label = f"{_DIAS[d.weekday()]} {d.day}"
        except ValueError:
            dia_label = fecha
        items = []
        for f in sorted(por_fecha[fecha], key=lambda x: x["hora"]):
            items.append(f"""
      <article class="movete-event-item movete-event-item--alt">
        <div class="movete-event-date">
          <span class="hora">{_esc(f['hora'])}</span>
        </div>
        <div>
          <div class="movete-event-title">{_esc(f['titulo'])}</div>
          <div class="movete-event-meta">{_esc(f['espacio'])}</div>
        </div>
      </article>""")
        out.append(f"""
  <div class="movete-alt-dia">
    <h3 class="movete-alt-fecha">{dia_label}</h3>
    {''.join(items)}
  </div>""")
    return "".join(out)


_DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def generar(cines_tradicional, funciones_alternativo, jueves):
    rango = _rango_texto(jueves)
    fecha_iso = jueves.strftime("%Y-%m-%d")
    titulo_pag = f"Cine en La Plata · semana del {rango}"

    trad = _bloque_tradicional(cines_tradicional)
    alt = _bloque_alternativo(funciones_alternativo)

    return f"""<!DOCTYPE html>
<html lang="es-AR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(titulo_pag)} | MoVeTe</title>
<meta name="description" content="Cartelera de cine en La Plata, semana del {rango}. Cine tradicional y alternativo: salas comerciales, ciclos, INCAA y cine-clubes.">
<link rel="canonical" href="https://movete.info/cine/{fecha_iso}.html">
<meta property="og:title" content="{_esc(titulo_pag)}">
<meta property="og:description" content="Cartelera completa de cine en La Plata: comercial y alternativo.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://movete.info/cine/{fecha_iso}.html">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,400;0,700;0,900;1,400;1,700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
{_CSS}
</style>
</head>
<body>

<header class="movete-mini-header">
  <a href="https://movete.info" class="movete-logo">MoVeTe<span class="movete-logo-dot"></span></a>
  <nav class="movete-mini-nav">
    <a href="https://movete.info">Agenda</a>
    <a href="https://movete.info/cine/" aria-current="page">Cine</a>
  </nav>
</header>

<section class="movete-cine-page-header">
  <p class="eyebrow">🎬 Cartelera</p>
  <h1>Cine en <span class="highlight">La Plata</span></h1>
  <p>Semana del {rango}</p>
</section>

<main class="movete-cartelera">

  <div class="movete-cine-switch">
    <a href="#tradicional" class="activo">Cine tradicional</a>
    <a href="#alternativo">Cine alternativo</a>
  </div>

  <section id="tradicional" class="movete-cine-grupo">
    <header class="movete-grupo-head">
      <h2>Cine tradicional</h2>
      <p>Las salas comerciales de la ciudad</p>
    </header>
    {trad}
  </section>

  <section id="alternativo" class="movete-cine-grupo">
    <header class="movete-grupo-head">
      <h2>Cine alternativo</h2>
      <p>Ciclos, INCAA, cine-clubes y funciones especiales</p>
    </header>
    <div class="movete-alt-lista">
      {alt}
    </div>
  </section>

</main>

<footer class="movete-foot">
  <p>© {jueves.year} MoVeTe · Agenda Cultural del Gran La Plata</p>
  <p class="movete-foot-fuente">Cartelera tradicional: diario El Día · Cine alternativo: Agenda La Plata. Los horarios pueden cambiar; confirmá en la sala.</p>
  <p class="movete-foot-fuente">Información de películas y afiches: <a href="https://www.themoviedb.org" rel="noopener">The Movie Database (TMDb)</a>. Este producto usa la API de TMDb pero no está avalado ni certificado por TMDb.</p>
</footer>

</body>
</html>"""


# ----------------------------------------------------------------------------
# CSS — portado del tema MoVeTe (style.css) + adaptaciones para página estática
# ----------------------------------------------------------------------------
_CSS = """
:root{
  --ink:#0e0d10; --paper:#f5f1e8; --accent:#ff5128; --accent2:#e8c547;
  --muted:rgba(14,13,16,0.45); --border:rgba(14,13,16,0.12);
  --cat-cine:#3b1f2b; --cat-teatro:#7b5ea7; --cat-musica:#2e86ab;
  --ff-serif:'Fraunces',Georgia,serif; --ff-mono:'JetBrains Mono','Courier New',monospace;
  --r:4px; --shadow:0 2px 12px rgba(14,13,16,0.10);
}
*,*::before,*::after{box-sizing:border-box;}
body{background:var(--paper);color:var(--ink);font-family:var(--ff-mono);
  font-size:15px;line-height:1.6;margin:0;-webkit-font-smoothing:antialiased;}
h1,h2,h3,h4{font-family:var(--ff-serif);font-weight:900;line-height:1.08;
  letter-spacing:-0.02em;}
a{color:inherit;}

/* Header compacto */
.movete-mini-header{background:var(--ink);display:flex;align-items:center;
  justify-content:space-between;padding:14px 24px;position:sticky;top:0;z-index:100;}
.movete-logo{color:var(--paper);font-family:var(--ff-serif);font-size:24px;
  font-weight:900;letter-spacing:-0.03em;text-decoration:none;display:inline-flex;
  align-items:center;gap:3px;}
.movete-logo-dot{width:8px;height:8px;background:var(--accent);border-radius:50%;
  display:inline-block;}
.movete-mini-nav a{color:rgba(245,241,232,0.7);font-size:12px;font-weight:700;
  text-transform:uppercase;letter-spacing:0.1em;text-decoration:none;margin-left:18px;}
.movete-mini-nav a[aria-current="page"]{color:var(--accent);}

/* Header de página */
.movete-cine-page-header{background:var(--ink);color:var(--paper);
  padding:64px 24px 48px;text-align:center;border-bottom:3px solid var(--accent);}
.movete-cine-page-header .eyebrow{font-family:var(--ff-mono);font-size:11px;
  text-transform:uppercase;letter-spacing:0.2em;color:rgba(245,241,232,0.5);margin:0 0 12px;}
.movete-cine-page-header h1{font-size:clamp(40px,8vw,80px);color:var(--paper);margin:0 0 10px;}
.movete-cine-page-header h1 .highlight{color:var(--accent);font-style:italic;}
.movete-cine-page-header p{font-family:var(--ff-mono);font-size:12px;
  text-transform:uppercase;letter-spacing:0.15em;color:rgba(245,241,232,0.55);margin:0;}

.movete-cartelera{max-width:1100px;margin:0 auto;padding:40px 24px 80px;}

/* Switch tradicional/alternativo */
.movete-cine-switch{display:flex;gap:8px;justify-content:center;margin-bottom:48px;
  flex-wrap:wrap;}
.movete-cine-switch a{font-family:var(--ff-mono);font-size:12px;font-weight:700;
  text-transform:uppercase;letter-spacing:0.08em;padding:10px 20px;
  border:1px solid var(--border);border-radius:999px;text-decoration:none;
  color:var(--ink);transition:all .15s ease;}
.movete-cine-switch a:hover,.movete-cine-switch a.activo{background:var(--ink);
  color:var(--paper);border-color:var(--ink);}

/* Cabecera de cada grupo */
.movete-cine-grupo{margin-bottom:64px;scroll-margin-top:80px;}
.movete-grupo-head{margin-bottom:32px;border-bottom:2px solid var(--ink);
  padding-bottom:12px;}
.movete-grupo-head h2{font-size:clamp(28px,5vw,44px);margin:0;}
.movete-grupo-head p{font-family:var(--ff-mono);font-size:12px;color:var(--muted);
  text-transform:uppercase;letter-spacing:0.1em;margin:6px 0 0;}

/* --- Cine tradicional (cartelera) --- */
.movete-cine{margin-bottom:48px;}
.movete-cine-title{font-size:clamp(24px,4vw,36px);margin:0 0 4px;}
.movete-cine-direccion{font-family:var(--ff-mono);font-size:11px;
  text-transform:uppercase;letter-spacing:0.12em;color:var(--muted);margin:0 0 24px;}
.movete-pelicula-grid{display:flex;flex-direction:column;gap:16px;}
.movete-pelicula{display:grid;grid-template-columns:90px 1fr;gap:18px;
  align-items:start;padding:18px;background:#fff;border-radius:var(--r);
  border:1px solid var(--border);box-shadow:var(--shadow);}
.movete-pelicula-poster{width:90px;height:135px;object-fit:cover;border-radius:2px;
  display:block;background:var(--cat-cine);}
.movete-pelicula-info{display:flex;flex-direction:column;gap:8px;}
.movete-pelicula-titulo{font-family:var(--ff-serif);font-size:20px;font-weight:700;
  margin:0;line-height:1.2;}
.movete-pelicula-ficha{font-family:var(--ff-mono);font-size:11px;color:var(--muted);
  margin:0;letter-spacing:0.03em;}
.movete-pelicula-meta{font-family:var(--ff-mono);font-size:11px;color:var(--muted);
  text-transform:uppercase;letter-spacing:0.06em;margin:0;display:flex;gap:10px;
  flex-wrap:wrap;align-items:center;}
.movete-pelicula-sinopsis{font-size:14px;line-height:1.5;margin:0;
  color:rgba(14,13,16,0.72);max-width:60ch;}
.movete-pelicula-badge{display:inline-block;font-family:var(--ff-mono);font-size:9px;
  font-weight:700;text-transform:uppercase;letter-spacing:0.1em;padding:2px 7px;
  border-radius:2px;border:1px solid var(--accent);color:var(--accent);}
.movete-pelicula-funciones{list-style:none;padding:0;margin:4px 0 0;display:flex;
  flex-wrap:wrap;gap:8px;}
.movete-pelicula-funciones li{background:var(--ink);color:var(--paper);
  font-family:var(--ff-mono);font-size:13px;font-weight:700;padding:5px 12px;
  border-radius:2px;letter-spacing:0.05em;}

/* --- Cine alternativo (agenda) --- */
.movete-alt-dia{margin-bottom:36px;}
.movete-alt-fecha{font-family:var(--ff-mono);font-size:13px;font-weight:700;
  text-transform:uppercase;letter-spacing:0.12em;color:var(--accent);
  border-bottom:1px solid var(--border);padding-bottom:8px;margin:0 0 8px;}
.movete-event-item{display:grid;grid-template-columns:70px 1fr;gap:18px;
  align-items:start;padding:16px 0;border-bottom:1px solid var(--border);}
.movete-event-item .hora{font-family:var(--ff-mono);font-size:20px;font-weight:700;
  display:block;line-height:1;}
.movete-event-title{font-family:var(--ff-serif);font-size:19px;font-weight:700;
  line-height:1.2;margin:0 0 4px;}
.movete-event-meta{font-family:var(--ff-mono);font-size:11px;color:var(--muted);
  text-transform:uppercase;letter-spacing:0.08em;}

.movete-cine-vacio{font-family:var(--ff-mono);font-size:13px;color:var(--muted);
  padding:24px 0;}

/* Footer */
.movete-foot{background:var(--ink);color:rgba(245,241,232,0.6);
  font-family:var(--ff-mono);font-size:11px;text-transform:uppercase;
  letter-spacing:0.08em;text-align:center;padding:32px 24px;}
.movete-foot p{margin:0 0 8px;}
.movete-foot-fuente{text-transform:none;letter-spacing:0;font-size:10px;
  color:rgba(245,241,232,0.4);max-width:600px;margin:8px auto 0;}

@media(max-width:768px){
  .movete-pelicula{grid-template-columns:64px 1fr;gap:12px;padding:14px;}
  .movete-pelicula-poster{width:64px;height:96px;}
  .movete-pelicula-titulo{font-size:16px;}
  .movete-cartelera{padding:32px 16px 60px;}
}
"""
