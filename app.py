import base64
import io
import sqlite3
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import qrcode
from flask import Flask, abort, redirect, render_template, request, url_for


app = Flask(__name__)
DATABASE_PATH = Path(__file__).with_name("analytics.db")


def get_db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    connection = get_db_connection()
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS tracked_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            destination_url TEXT NOT NULL,
            utm_source TEXT NOT NULL,
            utm_medium TEXT NOT NULL,
            utm_campaign TEXT NOT NULL,
            visit_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()
    connection.close()


init_db()


def normalize_url(raw_url: str) -> str:
    value = raw_url.strip()
    if not value:
        return ""

    parsed = urlparse(value)
    if not parsed.scheme:
        value = f"https://{value}"

    return value


def is_valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def build_tracked_url(
    base_url: str,
    utm_source: str,
    utm_medium: str,
    utm_campaign: str,
) -> str:
    parsed = urlparse(base_url)
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))

    query_params.update(
        {
            "utm_source": utm_source.strip(),
            "utm_medium": utm_medium.strip(),
            "utm_campaign": utm_campaign.strip(),
        }
    )

    return urlunparse(parsed._replace(query=urlencode(query_params)))


def create_tracked_link(
    destination_url: str,
    utm_source: str,
    utm_medium: str,
    utm_campaign: str,
) -> int:
    connection = get_db_connection()
    cursor = connection.execute(
        """
        INSERT INTO tracked_links (destination_url, utm_source, utm_medium, utm_campaign)
        VALUES (?, ?, ?, ?)
        """,
        (destination_url, utm_source, utm_medium, utm_campaign),
    )
    connection.commit()
    tracked_link_id = cursor.lastrowid
    connection.close()
    return tracked_link_id


def fetch_tracked_links():
    connection = get_db_connection()
    rows = connection.execute(
        """
        SELECT id, destination_url, utm_source, utm_medium, utm_campaign, visit_count, created_at
        FROM tracked_links
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()
    connection.close()
    return rows


def fetch_tracked_link(link_id: int):
    connection = get_db_connection()
    row = connection.execute(
        """
        SELECT id, destination_url, utm_source, utm_medium, utm_campaign, visit_count, created_at
        FROM tracked_links
        WHERE id = ?
        """,
        (link_id,),
    ).fetchone()
    connection.close()
    return row


def increment_visit_count(link_id: int) -> None:
    connection = get_db_connection()
    connection.execute(
        "UPDATE tracked_links SET visit_count = visit_count + 1 WHERE id = ?",
        (link_id,),
    )
    connection.commit()
    connection.close()


def generate_qr_base64(url: str) -> str:
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    return base64.b64encode(buffer.getvalue()).decode("ascii")


@app.route("/", methods=["GET", "POST"])
def index():
    url = ""
    final_url = ""
    qr_target_url = ""
    qr_image = None
    error = None
    utm_enabled = False
    utm_source = "qr"
    utm_medium = "offline"
    utm_campaign = ""

    if request.method == "POST":
        url = normalize_url(request.form.get("url", ""))
        utm_enabled = request.form.get("utm_enabled") == "on"
        utm_source = request.form.get("utm_source", "qr").strip() or "qr"
        utm_medium = request.form.get("utm_medium", "offline").strip() or "offline"
        utm_campaign = request.form.get("utm_campaign", "").strip()

        if not url:
            error = "Enter a link to convert."
        elif not is_valid_url(url):
            error = "Enter a valid http or https link."
        elif utm_enabled and not utm_campaign:
            error = "Enter a campaign name when UTM tracking is enabled."
        else:
            final_url = url
            qr_target_url = final_url

            if utm_enabled:
                final_url = build_tracked_url(
                    base_url=url,
                    utm_source=utm_source,
                    utm_medium=utm_medium,
                    utm_campaign=utm_campaign,
                )

            if not is_valid_url(final_url):
                error = "Enter a valid http or https link."
            else:
                if utm_enabled:
                    tracked_link_id = create_tracked_link(
                        destination_url=final_url,
                        utm_source=utm_source,
                        utm_medium=utm_medium,
                        utm_campaign=utm_campaign,
                    )
                    qr_target_url = url_for("redirect_tracked_link", link_id=tracked_link_id, _external=True)

                qr_image = generate_qr_base64(qr_target_url)

    return render_template(
        "index.html",
        url=url,
        final_url=final_url,
        qr_target_url=qr_target_url,
        qr_image=qr_image,
        error=error,
        utm_enabled=utm_enabled,
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
    )


@app.route("/analytics")
def analytics():
    tracked_links = fetch_tracked_links()
    return render_template("analytics.html", tracked_links=tracked_links)


@app.route("/r/<int:link_id>")
def redirect_tracked_link(link_id: int):
    tracked_link = fetch_tracked_link(link_id)
    if tracked_link is None:
        abort(404)

    increment_visit_count(link_id)
    return redirect(tracked_link["destination_url"], code=302)


if __name__ == "__main__":
    app.run(debug=True)
