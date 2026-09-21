# Cable installation analysis

Password-protected Streamlit app for the Progressliste and CaTra Kabelliste.

## Run

```bash
pip install streamlit pandas openpyxl python-dotenv
streamlit run app.py
```

Default password is `cable2026`. Override it with `APP_PASSWORD` in a `.env` file (see `.env.example`).

## Pages

- **All cables:** stackable filters (device, pulled, thin/thick, Cat1–Cat5) and a live total length.
- **Stopped cables:** cables with a stop date, grouped by Endsegment, with remaining unpulled meters and total cable length.
