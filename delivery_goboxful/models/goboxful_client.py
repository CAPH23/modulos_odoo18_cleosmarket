# -*- coding: utf-8 -*-
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import requests

from odoo import _, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {
    "password", "apipassword", "accesstoken", "refreshToken", "refresh_token",
    "authorization", "secret", "clientsecret", "client_secret",
}


class GoBoxfulApiError(UserError):
    """Error controlado devuelto por Boxful o por la conexión HTTP."""


class GoBoxfulClient:
    def __init__(self, account):
        self.account = account.sudo()
        self.env = self.account.env
        self.base_url = (self.account.api_url or "https://api.goboxful.com").rstrip("/") + "/"
        self.timeout = max(int(self.account.request_timeout or 25), 5)
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Odoo-18-CleosMarket-Boxful/1.0",
        })

    # ------------------------------------------------------------------
    # Autenticación JWT
    # ------------------------------------------------------------------
    def _token_is_valid(self):
        expires = self.account.access_token_expires_at
        if not (self.account.access_token and expires):
            return False
        return fields.Datetime.to_datetime(expires) > fields.Datetime.now() + timedelta(seconds=120)

    def _refresh_is_valid(self):
        expires = self.account.refresh_token_expires_at
        if not (self.account.refresh_token and expires):
            return False
        return fields.Datetime.to_datetime(expires) > fields.Datetime.now() + timedelta(seconds=300)

    @staticmethod
    def _epoch_to_datetime(value):
        if not value:
            return False
        try:
            value = float(value)
            if value > 10_000_000_000:  # algunos servicios usan milisegundos
                value /= 1000.0
            return datetime.fromtimestamp(value, tz=timezone.utc).replace(tzinfo=None)
        except (TypeError, ValueError, OverflowError):
            return False

    def _save_tokens(self, payload):
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        access = data.get("accessToken") or data.get("access_token")
        refresh = data.get("refreshToken") or data.get("refresh_token")
        if not access:
            if data.get("active") is False:
                raise GoBoxfulApiError(_("La cuenta Boxful existe, pero todavía no está activa."))
            raise GoBoxfulApiError(_("Boxful no devolvió un accessToken."))
        vals = {
            "access_token": access,
            "access_token_expires_at": self._epoch_to_datetime(
                data.get("accessTokenExpiresAt") or data.get("access_token_expires_at")
            ) or fields.Datetime.now() + timedelta(minutes=13),
        }
        if refresh:
            vals.update({
                "refresh_token": refresh,
                "refresh_token_expires_at": self._epoch_to_datetime(
                    data.get("refreshTokenExpiresAt") or data.get("refresh_token_expires_at")
                ) or fields.Datetime.now() + timedelta(days=29),
            })
        self.account.write(vals)
        self.account.invalidate_recordset()
        return access

    def authenticate(self):
        if not (self.account.api_email and self.account.api_password):
            raise GoBoxfulApiError(_("Configure el correo y la contraseña Boxful."))
        response = self._raw_request(
            "POST", "/auth/v2/client",
            json_body={"email": self.account.api_email, "password": self.account.api_password},
            auth=False,
        )
        return self._save_tokens(response)

    def refresh_tokens(self):
        if not self._refresh_is_valid():
            return self.authenticate()
        response = self._raw_request(
            "POST", "/auth/v2/refresh",
            json_body={"refreshToken": self.account.refresh_token},
            auth=False,
        )
        return self._save_tokens(response)

    def ensure_token(self):
        if self._token_is_valid():
            return self.account.access_token

        # El refresh token rota. El bloqueo evita que dos workers lo consuman
        # al mismo tiempo y uno de ellos deje persistido un token inválido.
        self.env.cr.execute(
            "SELECT id FROM goboxful_account WHERE id = %s FOR UPDATE",
            [self.account.id],
        )
        self.account.invalidate_recordset([
            "access_token", "access_token_expires_at",
            "refresh_token", "refresh_token_expires_at",
        ])
        if self._token_is_valid():
            return self.account.access_token
        try:
            return self.refresh_tokens()
        except Exception:
            _logger.info("Boxful: falló el refresh; se intentará autenticación completa", exc_info=True)
            return self.authenticate()

    # ------------------------------------------------------------------
    # HTTP / logs
    # ------------------------------------------------------------------
    @staticmethod
    def _sanitize(value):
        if isinstance(value, dict):
            clean = {}
            for key, item in value.items():
                normalized = str(key).replace("-", "").replace("_", "").lower()
                if key in SENSITIVE_KEYS or normalized in {
                    "password", "apipassword", "accesstoken", "refreshtoken",
                    "authorization", "secret", "clientsecret",
                }:
                    clean[key] = "***"
                else:
                    clean[key] = GoBoxfulClient._sanitize(item)
            return clean
        if isinstance(value, list):
            return [GoBoxfulClient._sanitize(item) for item in value]
        return value

    @staticmethod
    def _json_dump(value):
        try:
            return json.dumps(value, ensure_ascii=False, default=str, indent=2)[:100000]
        except Exception:
            return str(value)[:100000]

    def _log(self, method, endpoint, started, status, success, request_body,
             response_body=None, error_message=None, res_model=None, res_id=None):
        try:
            self.env["goboxful.api.log"].sudo().create({
                "company_id": self.account.company_id.id,
                "account_id": self.account.id,
                "method": method,
                "endpoint": endpoint,
                "http_status": int(status or 0),
                "duration_ms": int((time.monotonic() - started) * 1000),
                "success": success,
                "request_body": self._json_dump(self._sanitize(request_body or {}))
                    if self.account.log_payloads else False,
                "response_body": self._json_dump(self._sanitize(response_body or {}))
                    if self.account.log_payloads else False,
                "error_message": (error_message or "")[:5000],
                "res_model": res_model,
                "res_id": res_id or 0,
            })
        except Exception:
            _logger.warning("No se pudo guardar el log técnico Boxful", exc_info=True)

    def _raw_request(self, method, endpoint, json_body=None, params=None, auth=True,
                     binary=False, res_model=None, res_id=None):
        method = method.upper()
        url = urljoin(self.base_url, endpoint.lstrip("/"))
        headers = {}
        if auth:
            headers["Authorization"] = "Bearer %s" % self.ensure_token()
        started = time.monotonic()
        status = 0
        response_payload = None
        try:
            response = self.session.request(
                method, url, json=json_body, params=params, headers=headers,
                timeout=(8, self.timeout), allow_redirects=False,
            )
            status = response.status_code
            content_type = (response.headers.get("Content-Type") or "").lower()
            if binary:
                if not 200 <= status < 300:
                    text = response.text[:2000]
                    raise GoBoxfulApiError(_("Boxful respondió HTTP %(status)s: %(message)s",
                                                status=status, message=text))
                self._log(method, endpoint, started, status, True, json_body,
                          {"content_type": content_type, "bytes": len(response.content)},
                          res_model=res_model, res_id=res_id)
                return response.content, content_type
            try:
                response_payload = response.json() if response.content else {}
            except ValueError:
                response_payload = {"raw": response.text[:10000]}
            if status == 401 and auth:
                # Un único reintento con token recién renovado.
                self.account.write({"access_token": False, "access_token_expires_at": False})
                headers["Authorization"] = "Bearer %s" % self.ensure_token()
                response = self.session.request(
                    method, url, json=json_body, params=params, headers=headers,
                    timeout=(8, self.timeout), allow_redirects=False,
                )
                status = response.status_code
                try:
                    response_payload = response.json() if response.content else {}
                except ValueError:
                    response_payload = {"raw": response.text[:10000]}
            if not 200 <= status < 300:
                message = self._extract_error(response_payload) or response.reason
                raise GoBoxfulApiError(_("Boxful respondió HTTP %(status)s: %(message)s",
                                            status=status, message=message))
            self._log(method, endpoint, started, status, True, json_body,
                      response_payload, res_model=res_model, res_id=res_id)
            return response_payload or {}
        except GoBoxfulApiError as exc:
            self._log(method, endpoint, started, status, False, json_body,
                      response_payload, str(exc), res_model, res_id)
            raise
        except requests.Timeout as exc:
            message = _("La solicitud a Boxful excedió el tiempo de espera.")
            self._log(method, endpoint, started, status, False, json_body,
                      response_payload, message, res_model, res_id)
            raise GoBoxfulApiError(message) from exc
        except requests.RequestException as exc:
            message = _("No fue posible comunicarse con Boxful: %s") % str(exc)
            self._log(method, endpoint, started, status, False, json_body,
                      response_payload, message, res_model, res_id)
            raise GoBoxfulApiError(message) from exc

    @staticmethod
    def _extract_error(payload):
        if not isinstance(payload, dict):
            return str(payload or "")
        for key in ("message", "error", "errorMessage", "detail", "description"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, list) and value:
                return "; ".join(str(item) for item in value)
            if isinstance(value, dict):
                return GoBoxfulClient._extract_error(value)
        errors = payload.get("errors")
        if errors:
            return GoBoxfulClient._json_dump(errors)[:1000]
        return False

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------
    def get_me(self):
        return self._raw_request("GET", "/auth/v2/me")

    def get_states(self):
        return self._raw_request("GET", "/states")

    def get_addresses(self):
        return self._raw_request("GET", "/addresses")

    def create_address(self, payload):
        return self._raw_request("POST", "/addresses", json_body=payload)

    def update_address(self, address_id, payload):
        return self._raw_request("PATCH", "/addresses/%s" % address_id, json_body=payload)

    def quote(self, payload, res_model=None, res_id=None):
        return self._raw_request("POST", "/quoter", json_body=payload,
                                 res_model=res_model, res_id=res_id)

    def available_couriers(self, payload, res_model=None, res_id=None):
        return self._raw_request("POST", "/courier/available", json_body=payload,
                                 res_model=res_model, res_id=res_id)

    def create_shipment(self, payload, res_model=None, res_id=None):
        if self.account.mode == "test" and not self.account.test_allow_real_shipments:
            raise GoBoxfulApiError(_(
                "La creación real de envíos está bloqueada en modo pruebas. "
                "Active la autorización solamente después de confirmarlo con Boxful."
            ))
        return self._raw_request("POST", "/shipment", json_body=payload,
                                 res_model=res_model, res_id=res_id)

    def get_shipment(self, shipment_id, res_model=None, res_id=None):
        return self._raw_request("GET", "/shipment/%s" % shipment_id,
                                 res_model=res_model, res_id=res_id)

    def track(self, shipment_number, res_model=None, res_id=None):
        # El endpoint está documentado como público; primero se usa sin bearer
        # para no depender de la sesión si el envío ya existe.
        return self._raw_request("GET", "/tracking/%s" % shipment_number,
                                 auth=False, res_model=res_model, res_id=res_id)

    def register_webhook(self, payload):
        return self._raw_request("POST", "/client-webhook", json_body=payload)

    def download_label(self, url, res_model=None, res_id=None):
        parsed = urlparse(url)
        allowed = {
            host.strip().lower()
            for host in (self.account.allowed_label_hosts or "").splitlines()
            if host.strip()
        }
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not hostname or not any(
            hostname == host or hostname.endswith("." + host) for host in allowed
        ):
            raise GoBoxfulApiError(_("La URL de la etiqueta no pertenece a un host Boxful permitido."))
        started = time.monotonic()
        try:
            response = self.session.get(url, timeout=(8, self.timeout), allow_redirects=False)
            if not 200 <= response.status_code < 300:
                raise GoBoxfulApiError(_("No se pudo descargar la etiqueta (HTTP %s).") % response.status_code)
            if len(response.content) > 15 * 1024 * 1024:
                raise GoBoxfulApiError(_("La etiqueta supera el tamaño máximo permitido de 15 MB."))
            content_type = (response.headers.get("Content-Type") or "").lower()
            if "pdf" not in content_type and not response.content.startswith(b"%PDF-"):
                raise GoBoxfulApiError(_("Boxful no devolvió un archivo PDF válido para la etiqueta."))
            self._log("GET", "label", started, response.status_code, True,
                      {"url_host": hostname}, {"bytes": len(response.content)},
                      res_model=res_model, res_id=res_id)
            return response.content, response.headers.get("Content-Type") or "application/pdf"
        except requests.RequestException as exc:
            raise GoBoxfulApiError(_("No se pudo descargar la etiqueta: %s") % exc) from exc


class GoBoxfulMockClient(GoBoxfulClient):
    """Simulador determinista: nunca realiza tráfico externo."""

    MOCK_STATES = [
        {
            "id": "sv-ss", "name": "San Salvador",
            "Cities": [
                {"id": "sv-ss-san-salvador", "name": "San Salvador"},
                {"id": "sv-ss-panchimalco", "name": "Panchimalco"},
                {"id": "sv-ss-mejicanos", "name": "Mejicanos"},
            ],
        },
        {
            "id": "sv-ll", "name": "La Libertad",
            "Cities": [
                {"id": "sv-ll-santa-tecla", "name": "Santa Tecla"},
                {"id": "sv-ll-antiguo-cuscatlan", "name": "Antiguo Cuscatlán"},
            ],
        },
    ]

    def get_me(self):
        return {"jwtPayload": {"clientId": "mock-cleosmarket", "active": True}}

    def get_states(self):
        return {"states": self.MOCK_STATES}

    def get_addresses(self):
        return {"addresses": []}

    def create_address(self, payload):
        return {"address": dict(payload, id="mock-pickup-%s" % self.account.company_id.id)}

    def update_address(self, address_id, payload):
        return {"address": dict(payload, id=address_id)}

    def quote(self, payload, res_model=None, res_id=None):
        return {"couriers": [
            {"courierId": "mock-flash", "courierName": "Boxful Flash", "deliveryType": "same-day"},
            {"courierId": "mock-economy", "courierName": "Boxful Economy", "deliveryType": "next-day"},
        ]}

    def available_couriers(self, payload, res_model=None, res_id=None):
        packages = payload.get("packages") or payload.get("parcels") or []
        weight = sum(float(item.get("weight") or 0.0) for item in packages) or 1.0
        return {"couriers": [
            {
                "courierId": "mock-flash",
                "courierName": "Boxful Flash",
                "price": round(3.25 + weight * 0.18, 2),
                "codCommissionPercentage": 0.02,
                "estimatedDelivery": fields.Date.to_string(fields.Date.context_today(self.account)),
                "deliveryType": "same-day",
            },
            {
                "courierId": "mock-express",
                "courierName": "Courier Express Demo",
                "price": round(4.20 + weight * 0.12, 2),
                "codCommission": 0.0,
                "estimatedDelivery": fields.Date.to_string(fields.Date.context_today(self.account)),
                "deliveryType": "same-day",
            },
        ]}

    def create_shipment(self, payload, res_model=None, res_id=None):
        stamp = int(time.time())
        number = "MOCK-%s-%s" % (self.account.company_id.id, stamp)
        return {"shipmentData": {
            "id": "mock-shipment-%s" % stamp,
            "shipmentNumber": number,
            "status": -1,
            "statusDescription": "Creado en sistema",
            "courierId": payload.get("courierId"),
            "courierName": payload.get("courierName") or "Boxful Flash",
            "trackingUrl": "https://app.goboxful.com/tracking/%s" % number,
            "labelUrl": "mock://label/%s" % number,
        }}

    def get_shipment(self, shipment_id, res_model=None, res_id=None):
        return {"shipmentData": {"id": shipment_id, "status": 1,
                                  "statusDescription": "Registrado"}}

    def track(self, shipment_number, res_model=None, res_id=None):
        return {"shipmentNumber": shipment_number, "status": 1,
                "statusDescription": "Registrado"}

    def register_webhook(self, payload):
        return {"webhook": {"active": True, "url": payload.get("webhook")}}

    def download_label(self, url, res_model=None, res_id=None):
        label = url.rsplit("/", 1)[-1] if url else "MOCK"
        text = ("Etiqueta Boxful simulada - %s" % label).replace("(", "[").replace(")", "]")
        stream = ("BT /F1 16 Tf 72 720 Td (%s) Tj ET" % text).encode("latin-1", "replace")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
        pdf = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for index, obj in enumerate(objects, start=1):
            offsets.append(len(pdf))
            pdf.extend(("%d 0 obj\n" % index).encode())
            pdf.extend(obj + b"\nendobj\n")
        xref = len(pdf)
        pdf.extend(("xref\n0 %d\n" % (len(objects) + 1)).encode())
        pdf.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf.extend(("%010d 00000 n \n" % offset).encode())
        pdf.extend(("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" %
                    (len(objects) + 1, xref)).encode())
        return bytes(pdf), "application/pdf"
