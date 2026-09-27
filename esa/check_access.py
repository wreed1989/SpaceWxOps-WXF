#!/usr/bin/env python3
"""Read-only ESA M2M/product diagnostics. Standard library; no secrets in reports.

Secrets: ESAID and ESASECRET, supplied only to the GitHub Actions process.
No data/imagery, token responses, credentials, or cookies are written to disk.
This is an access/response-format check, not a forecast freshness/skill test.
"""
from __future__ import annotations

import html
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

TOKEN_URL = "https://sso.s2p.esa.int/realms/swe/protocol/openid-connect/token"
SIDC = "https://esa-swe-services-sidc-be.content.swe.s2p.esa.int/prod/API/index.php"
CONNECT = "https://connect-tool-ssa-esa-irap-omp-eu.content.swe.s2p.esa.int"
AUTH_HOSTS = {
    "swe.ssa.esa.int": "swe_hapiserver",
    "esa-swe-services-sidc-be.content.swe.s2p.esa.int": "swe_contentproxy",
    "connect-tool-ssa-esa-irap-omp-eu.content.swe.s2p.esa.int": "swe_contentproxy",
    "www-h-esc-org.content.swe.s2p.esa.int": "swe_contentproxy",
}
PUBLIC_HOSTS = {"sso.kso.ac.at", "a-effort.academyofathens.gr", "connect-tool.irap.omp.eu"}
ALLOWED_SCOPES = {"swe_hapiserver", "swe_contentproxy"}
MAX_BYTES = 8_000_000


class SafeError(Exception):
    """Only constant, non-sensitive error codes may be passed to this exception."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes


def exchange(url: str, *, form: dict[str, str] | None = None,
             bearer: str | None = None, scope: str | None = None) -> Response:
    """TLS verification stays on. Credentials never follow redirects."""
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" or u.username or u.password or u.port not in (None, 443) or u.fragment:
        raise SafeError("unsafe_url")
    if form is not None:
        if url != TOKEN_URL or bearer:
            raise SafeError("unsafe_token_destination")
    elif u.hostname not in set(AUTH_HOSTS) | PUBLIC_HOSTS:
        raise SafeError("unapproved_host")
    if bearer and (scope not in ALLOWED_SCOPES or AUTH_HOSTS.get(u.hostname) != scope):
        raise SafeError("token_audience_mismatch")
    headers = {"User-Agent": "SpaceWxOps-ESA-AccessCheck/1.0", "Accept": "*/*"}
    if bearer:
        headers["Authorization"] = "Bearer " + bearer
    body = None
    if form is not None:
        body = urllib.parse.urlencode(form).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=headers)
    opener = urllib.request.build_opener(NoRedirect())
    try:
        try:
            r = opener.open(req, timeout=25)
        except urllib.error.HTTPError as e:
            r = e  # Inspect status only; never print the HTTPError/request/body.
        with r:
            limit = 128_000 if form is not None else MAX_BYTES
            data = r.read(limit + 1)
            if len(data) > limit:
                raise SafeError("response_too_large")
            return Response(r.code, {k.lower(): v for k, v in r.headers.items()}, data)
    except (socket.timeout, TimeoutError):
        raise SafeError("timeout") from None
    except urllib.error.URLError as e:
        if isinstance(e.reason, socket.gaierror):
            raise SafeError("dns_failure") from None
        if isinstance(e.reason, ssl.SSLError):
            raise SafeError("tls_failure") from None
        raise SafeError("network_failure") from None
    except (OSError, ValueError):
        raise SafeError("transport_failure") from None


def mask(value: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true" and value:
        value = value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print("::add-mask::" + value, flush=True)


class M2M:
    def __init__(self, client: str, secret: str):
        self.client = client
        self.secret = secret
        self.tokens: dict[str, tuple[str, float]] = {}
        self.failures: dict[str, str] = {}
        mask(client)
        mask(secret)

    def token(self, scope: str) -> str:
        if scope not in ALLOWED_SCOPES:
            raise SafeError("unapproved_scope")
        if not self.client or not self.secret:
            raise SafeError("missing_repository_secret")
        if scope in self.failures:
            raise SafeError(self.failures[scope])
        cached = self.tokens.get(scope)
        if cached and time.monotonic() + 30 < cached[1]:
            return cached[0]
        try:
            r = exchange(TOKEN_URL, form={"client_id": self.client, "client_secret": self.secret,
                        "grant_type": "client_credentials", "scope": scope})
        except SafeError as e:
            self.failures[scope] = str(e)
            raise
        try:
            data = json.loads(r.body)
        except (ValueError, UnicodeError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        if r.status != 200:
            error = data.get("error")
            code = error if error in {"invalid_client", "invalid_scope", "unauthorized_client", "access_denied"} else "token_http_" + str(r.status)
            self.failures[scope] = code
            raise SafeError(code)
        token = data.get("access_token")
        if not isinstance(token, str) or not token or "\r" in token or "\n" in token or data.get("token_type", "").lower() != "bearer":
            raise SafeError("invalid_token_response")
        try:
            lifetime = float(data.get("expires_in", 0))
            if not 30 < lifetime <= 172800:
                raise ValueError()
        except (ValueError, TypeError):
            raise SafeError("invalid_token_expiry") from None
        mask(token)
        self.tokens[scope] = (token, time.monotonic() + lifetime)
        return token


def clean_field(value: str) -> str | None:
    """Record field names, not values; constrain even the diagnostic schema."""
    return value if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:-]{0,47}", value) else None


def shape(value: object) -> dict:
    if isinstance(value, dict):
        result = {"root_type": "object", "keys": sorted(filter(None, (clean_field(str(k)) for k in value)))[:35]}
        for key, item in value.items():
            key = clean_field(str(key))
            if key and isinstance(item, list):
                result["list_field"] = key
                result["record_count"] = len(item)
                if item and isinstance(item[0], dict):
                    result["record_keys"] = sorted(filter(None, (clean_field(str(k)) for k in item[0])))[:35]
                break
        return result
    if isinstance(value, list):
        result = {"root_type": "array", "record_count": len(value)}
        if value and isinstance(value[0], dict):
            result["record_keys"] = sorted(filter(None, (clean_field(str(k)) for k in value[0])))[:35]
        return result
    return {"root_type": type(value).__name__}


def inspect_response(r: Response, expected: str) -> dict:
    """A login page and an EUHFORIA landing page are not numerical products."""
    result = {"http_status": r.status, "bytes": len(r.body)}
    if 300 <= r.status < 400:
        location = urllib.parse.urlsplit(html.unescape(r.headers.get("location", "")))
        result["status"] = "redirect_not_followed"
        if location.scheme == "https" and location.hostname == "sso.s2p.esa.int":
            result["status"] = "login_redirect"
            scope = urllib.parse.parse_qs(location.query).get("client_id", [""])[0]
            if scope in ALLOWED_SCOPES:
                result["required_scope"] = scope
        return result
    if r.status != 200:
        return {**result, "status": "http_" + str(r.status)}
    if not r.body.strip():
        return {**result, "status": "empty_response"}
    raw = r.body.lstrip()
    text = r.body.decode("utf-8", errors="replace")
    lower = text[:100000].lower()
    is_html = "text/html" in r.headers.get("content-type", "").lower() or bool(re.search(r"<(?:!doctype\s+html|html)(?:\s|>)", lower[:2000]))
    if is_html:
        status = "html_instead_of_product"
        if any(x in lower for x in ('type="password"', "openid-connect/auth", 'id="kc-form-login"')):
            status = "login_page"
        elif expected == "provider_page":
            status = "provider_page_only"
        return {**result, "status": status}
    if expected in {"json", "hapi"}:
        try:
            value = json.loads(r.body)
        except (ValueError, UnicodeError):
            return {**result, "status": "invalid_json"}
        if not isinstance(value, (list, dict)):
            return {**result, "status": "unexpected_json_root"}
        if expected == "hapi":
            status = value.get("status", {}) if isinstance(value, dict) else {}
            if not isinstance(status, dict) or status.get("code") != 1200:
                return {**result, "status": "hapi_not_ok"}
        elif isinstance(value, dict) and (value.get("error") or value.get("errors")):
            return {**result, "status": "provider_error_json"}
        return {**result, "status": "readable_json", "schema": shape(value)}
    if expected in {"xml", "svg"} or (expected == "map" and (raw.startswith(b"<") or b"<svg" in raw[:1024])):
        if b"<!DOCTYPE" in r.body.upper() or b"<!ENTITY" in r.body.upper():
            return {**result, "status": "xml_dtd_rejected"}
        try:
            root = ET.fromstring(r.body)
        except ET.ParseError:
            return {**result, "status": "invalid_xml"}
        tag = root.tag.split("}")[-1]
        if tag.lower() in {"html", "error"}:
            return {**result, "status": "unexpected_xml_root"}
        if expected in {"svg", "map"} and tag != "svg":
            return {**result, "status": "not_svg"}
        names = sorted({t for el in root.iter() if (t := clean_field(el.tag.split("}")[-1]))})[:45]
        attrs = sorted({t for el in root.iter() for key in el.attrib if (t := clean_field(key.split("}")[-1]))})[:35]
        return {**result, "status": "readable_svg" if tag == "svg" else "readable_xml", "schema": {"root": clean_field(tag), "element_names": names, "attribute_names": attrs}}
    if expected in {"map", "image"}:
        if raw.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a")):
            return {**result, "status": "image_signature_received"}
        return {**result, "status": "not_an_image"}
    if expected == "kso":
        candidate = text.strip().strip('"')
        try:
            url = urllib.parse.urlsplit(candidate)
            valid = url.scheme == "https" and url.hostname == "sso.kso.ac.at" and not url.username and not url.password
        except ValueError:
            valid = False
        if valid:
            return {**result, "status": "image_url_received"}
        try:
            value = json.loads(r.body)
            return {**result, "status": "readable_json", "schema": shape(value)} if isinstance(value, (dict, list)) else {**result, "status": "unexpected_image_index"}
        except (ValueError, UnicodeError):
            return {**result, "status": "unexpected_image_index"}
    return {**result, "status": "unexpected_response"}


def targets(now: datetime) -> list[tuple[str, str, str, str | None]]:
    # Most recently completed six-hour slot, not a fixed year or historical example.
    now = now.astimezone(timezone.utc)
    cycle = now.replace(hour=(now.hour // 6) * 6, minute=0, second=0, microsecond=0)
    stamp = cycle.strftime("%Y%m%dT%H%M%S")
    conn_path = f"/api_creation/EARTH/ADAPT/SCTIME/{stamp}/?frame=on&connectivity=on&background=euv193"
    return [
        ("HAPI Capabilities", "https://swe.ssa.esa.int/hapi/capabilities", "hapi", "swe_hapiserver"),
        ("HAPI Catalog", "https://swe.ssa.esa.int/hapi/catalog", "hapi", "swe_hapiserver"),
        ("SIDC Coronal Holes", SIDC + "?component=latest&pc=S126&psc=a&type=ch", "json", "swe_contentproxy"),
        ("SIDC Coronal-Hole Runs", SIDC + "?component=latest&pc=S126&psc=a&type=run", "json", "swe_contentproxy"),
        ("SIDC Flare Forecast", SIDC + "?component=latest&pc=S109&psc=b", "xml", "swe_contentproxy"),
        ("SIDC Solarmap", SIDC + "?component=latest&pc=S101&psc=c&images_sun=AIA193&coronal_holes_sidc=1&regions_noaa_region=1&features_width=1024", "svg", "swe_contentproxy"),
        ("Magnetic Connectivity ESA", CONNECT + conn_path, "map", "swe_contentproxy"),
        ("Magnetic Connectivity Direct", "https://connect-tool.irap.omp.eu" + conn_path, "map", None),
        ("EUHFORIA Provider View", "https://www-h-esc-org.content.swe.s2p.esa.int/h101g/", "provider_page", "swe_contentproxy"),
        ("KSO H-Alpha", "https://sso.kso.ac.at/prod/API/index.php?component=latest&pc=S107&psc=a&type=hc", "kso", None),
        ("A-EFFort", "https://a-effort.academyofathens.gr/prod/api/index.php?component=latest&pc=S124", "xml", None),
    ]


def run(client: M2M) -> dict:
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "purpose": "Access and response format only; no freshness/forecast validation or deployment",
              "secrets_present": {"ESAID": bool(client.client), "ESASECRET": bool(client.secret)},
              "authentication": [], "products": []}
    for scope in sorted(ALLOWED_SCOPES):
        try:
            client.token(scope)
            report["authentication"].append({"scope": scope, "status": "token_issued"})
        except SafeError as e:
            report["authentication"].append({"scope": scope, "status": str(e)})
    for name, url, expected, scope in targets(datetime.now(timezone.utc)):
        entry = {"name": name, "endpoint": url, "scope": scope or "public_request"}
        try:
            token = client.token(scope) if scope else None
            result = inspect_response(exchange(url, bearer=token, scope=scope), expected)
        except SafeError as e:
            result = {"status": str(e)}
        report["products"].append({**entry, **result})
    return report


def main() -> int:
    client = M2M(os.environ.get("ESAID", ""), os.environ.get("ESASECRET", ""))
    report = run(client)
    # Defense in depth: literal credential/token redaction applies to every output.
    serialized = json.dumps(report, indent=2, ensure_ascii=True)
    for secret in [client.client, client.secret] + [v[0] for v in client.tokens.values()]:
        if secret:
            serialized = serialized.replace(secret, "[REDACTED]").replace(json.dumps(secret)[1:-1], "[REDACTED]")
    report = json.loads(serialized)
    out = Path(os.environ.get("ESA_REPORT_DIR", "esa-access-report"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "esa_access_report.json").write_text(serialized + "\n", encoding="utf-8")
    rows = ["# ESA M2M Access Check", "", "No credentials, tokens, cookies or provider payloads are included.", "",
            "This tests access/format, not current forecast availability or a running dashboard integration.", "",
            "| Check | Result |", "| --- | --- |"]
    for key, present in report["secrets_present"].items():
        rows.append(f"| Repository secret {key} | {'Present' if present else 'Missing'} |")
    for result in report["authentication"]:
        rows.append(f"| Token: {result['scope']} | {result['status']} |")
    for result in report["products"]:
        rows.append(f"| {result['name']} | {result['status']} |")
    text = "\n".join(rows) + "\n"
    (out / "esa_access_report.md").write_text(text, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text)
    print(text, flush=True)
    if any(x["status"] != "token_issued" for x in report["authentication"]):
        return 1
    good = {"readable_json", "readable_xml", "readable_svg", "image_signature_received", "image_url_received", "provider_page_only"}
    # Red workflow means one or more transports still need attention, not necessarily bad credentials.
    return 0 if all(x["status"] in good for x in report["products"]) else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print("ESA check stopped due to an internal error. No raw exception or credentials were logged.")
        sys.exit(3)
