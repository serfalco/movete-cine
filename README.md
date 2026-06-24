# MoVeTe · Sistema de Cine

Genera la cartelera semanal de cine de La Plata para `movete.info`.

## Qué hace

- Scrapea cine tradicional desde El Día.
- Scrapea cine alternativo desde Agenda La Plata.
- Enriquece películas con TMDB cuando hay `TMDB_API_KEY`.
- Genera HTML estático semanal.

## Salida

```txt
cine/index.html
cine/AAAA-MM-DD/index.html
```

En el flujo completo, la salida se configura así:

```txt
MOVETE_CINE_OUT=../Movete-info/cine
```

## Correr local

```bash
pip install -r requirements.txt
python main.py
```

## Secrets

Opcional:

```txt
TMDB_API_KEY
```

No usa FTP. No usa Hostinger. No usa WordPress.
