# QR-

Simple Flask tool for generating QR codes from links.

It supports two modes:

- Single QR generation for one direct link
- UTM batch generation for one base link, with an optional QR code for each generated UTM URL

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
