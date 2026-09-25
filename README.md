# Cable installation analysis

Streamlit app for cable-pull planning and tracking on site. It joins a **Progressliste** (status) Excel with a **CaTra Kabelliste**, then filters, exports, and charts progress. An optional **workforce hours** Excel powers headcount and productivity views.

## Requirements

- Python 3.10+
- Progressliste + CaTra Kabelliste (`.xlsx`) for cable pages
- Workforce hours Excel (optional) for Workforce and weekly Progress hours

```bash
pip install -r requirements.txt
```

## Run locally

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501).

Uploads live in the sidebar under **Data files**. Cable data and workforce data are cached in a local SQLite DB under `data/` so you do not need to re-upload every session. Use **Clear cable data** / **Clear workforce data** to reset.

## Pages

| Page | What it does |
|------|----------------|
| **All cables** | Shared filters, live length total, copy lists (pulled / started), CaTra + Kurzliste export |
| **Stopped cables** | Cables with a stop date, grouped by Endsegment, remaining meters, exports |
| **Stütze / Bahn szűrő** | Paste Stütze numbers (`;`), unique-only, AND/OR on pathway, CaTra / Kurzliste |
| **Cable ID export** | Paste cable IDs (`;` or newlines); `5012.1` = `5012,1`; dedupe; combined export |
| **Workforce** | Daily headcount by position, growth charts, date range, m/person and m/hour when cable data is loaded (`H` = holiday) |
| **Nyomvonal-csoportok** | Pathway groups (~90% path match), exports |
| **Progress** | Daily / weekly (KW) pulled meters; work hours on weekly chart when workforce is loaded |
| **Hossz kalkulátor** | Partial pull length from pathway segments + A/E allowances; highlight overlap with already pulled path |
| **Hogyan működik** | Short in-app guide with links to each page |

Shared sidebar filters (Gerät, pull status, thickness, category, stop Stütze) apply across the cable pages.

### Exports

- **CaTra (húzókártya):** multi-row pull card with pathway layout  
- **Kurzliste:** one row per cable including pathway  

## Tests

```bash
pytest
```

## Deploy (Streamlit Community Cloud)

Point the app at `app.py` on the branch you want to publish (typically `main`). Set secrets / env in the Cloud dashboard if you enable password protection later (`APP_PASSWORD`; see `.env.example`).

## Project layout

```
app.py              # navigation + uploads
views/              # one module per page
src/                # parse, join, filters, export, progress, workforce, store
tests/              # pytest suite
data/               # local SQLite cache (gitignored)
.streamlit/         # theme / server config
```
