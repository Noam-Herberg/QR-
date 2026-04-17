# QR-

Simple Python tool with a web page for converting pasted links into QR codes, with optional UTM tracking fields and a basic analytics view for tracked links.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Then open `http://127.0.0.1:5000` in your browser.

## Analytics

When UTM tracking is enabled, the QR code points to a local redirect route first. That route counts visits and then sends the visitor to the final destination URL. View the totals on the analytics page linked from the top of the app.
