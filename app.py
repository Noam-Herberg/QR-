import base64
import io
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import qrcode
from flask import Flask, render_template, request


app = Flask(__name__)

DEFAULT_UTM_VARIANTS = "\n".join(
    [
        "qr,offline",
        "poster,offline",
        "flyer,print",
    ]
)


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


def parse_utm_variants(raw_variants: str) -> list[dict[str, str]]:
    variants: list[dict[str, str]] = []

    for line in raw_variants.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        parts = [part.strip() for part in stripped.split(",")]
        if len(parts) != 2 or not all(parts):
            raise ValueError(
                "Each UTM variant must be on its own line as source,medium."
            )

        source, medium = parts
        variants.append(
            {
                "source": source,
                "medium": medium,
                "label": f"{source} / {medium}",
            }
        )

    if not variants:
        raise ValueError("Add at least one UTM variant to generate.")

    return variants


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
    error = None
    single_qr_image = None
    generate_utm_set = False
    generate_variant_qrs = False
    utm_campaign = ""
    utm_variants = DEFAULT_UTM_VARIANTS
    generated_variants: list[dict[str, str]] = []

    if request.method == "POST":
        url = normalize_url(request.form.get("url", ""))
        generate_utm_set = request.form.get("generate_utm_set") == "on"
        generate_variant_qrs = request.form.get("generate_variant_qrs") == "on"
        utm_campaign = request.form.get("utm_campaign", "").strip()
        utm_variants = request.form.get("utm_variants", DEFAULT_UTM_VARIANTS).strip()

        if not url:
            error = "Enter a link to convert."
        elif not is_valid_url(url):
            error = "Enter a valid http or https link."
        elif generate_utm_set and not utm_campaign:
            error = "Enter a campaign name to generate UTM links."
        else:
            if generate_utm_set:
                try:
                    variants = parse_utm_variants(utm_variants)
                except ValueError as exc:
                    error = str(exc)
                else:
                    for variant in variants:
                        tracked_url = build_tracked_url(
                            base_url=url,
                            utm_source=variant["source"],
                            utm_medium=variant["medium"],
                            utm_campaign=utm_campaign,
                        )
                        generated_variants.append(
                            {
                                **variant,
                                "url": tracked_url,
                                "qr_image": (
                                    generate_qr_base64(tracked_url)
                                    if generate_variant_qrs
                                    else ""
                                ),
                            }
                        )
            else:
                single_qr_image = generate_qr_base64(url)

    return render_template(
        "index.html",
        url=url,
        error=error,
        single_qr_image=single_qr_image,
        generate_utm_set=generate_utm_set,
        generate_variant_qrs=generate_variant_qrs,
        utm_campaign=utm_campaign,
        utm_variants=utm_variants,
        generated_variants=generated_variants,
    )


if __name__ == "__main__":
    app.run(debug=True)
