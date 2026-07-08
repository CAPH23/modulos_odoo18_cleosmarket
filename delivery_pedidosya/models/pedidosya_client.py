# -*- coding: utf-8 -*-
"""Cliente HTTP para PedidosYa Courier API v3.

Dos implementaciones con la MISMA interfaz pública:

- ``PedidosYaClient``      → cliente real (requests) contra courier-api.pedidosya.com.
                             Queda listo el manejo de token (45 min de vida, caché en
                             el carrier, reintento ante 401). El endpoint de generación
                             de token NO figura en el OpenAPI v3; se configura en el
                             carrier cuando PedidosYa entregue las credenciales.
- ``PedidosYaMockClient``  → cliente simulado. Devuelve respuestas con la misma forma
                             que los esquemas del spec (EstimationShippingResponse,
                             ShippingResponseConfirmed, TrackingResponse, etc.) para
                             poder desarrollar y probar el checkout sin credenciales.

Interfaz pública común:
    estimate(payload)                      -> dict (EstimationShippingResponse)
    confirm_estimate(estimate_id, offer_id)-> dict (ShippingResponseConfirmed)
    get_shipping(shipping_id)              -> dict (ShippingOrderResponse)
    get_tracking(shipping_id)              -> dict (TrackingResponse)
    cancel_shipping(shipping_id, reason)   -> dict
"""

import json
import logging
import math
import random
import time
from datetime import datetime, timedelta, timezone

import requests

from odoo import _, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

COURIER_API_URL = "https://courier-api.pedidosya.com"
TOKEN_LIFETIME_SECONDS = 45 * 60          # la doc indica 45 minutos de vigencia
TOKEN_SAFETY_MARGIN_SECONDS = 120         # renovamos 2 min antes de expirar
REQUEST_TIMEOUT = 20                      # segundos


def _utcnow_iso(delta_minutes=0):
    dt = datetime.now(timezone.utc) + timedelta(minutes=delta_minutes)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


class PedidosYaError(UserError):
    """Error de negocio devuelto por la API de PedidosYa."""


# ---------------------------------------------------------------------------
# Cliente REAL
# ---------------------------------------------------------------------------
class PedidosYaClient(object):

    def __init__(self, carrier):
        self.carrier = carrier
        self.base_url = COURIER_API_URL
        self.session = requests.Session()

    # -- logging -----------------------------------------------------------
    def _log(self, title, payload):
        """Usa el logger de depuración estándar de delivery.carrier."""
        if self.carrier.debug_logging:
            try:
                self.carrier.log_xml(json.dumps(payload, indent=2, default=str), title)
            except Exception:  # nunca romper el flujo por un log
                _logger.exception("PedidosYa: fallo registrando log de depuración")

    # -- token -------------------------------------------------------------
    def _get_token(self, force_refresh=False):
        carrier = self.carrier.sudo()
        now = fields.Datetime.now()
        if (not force_refresh and carrier.pedidosya_token
                and carrier.pedidosya_token_expiration
                and carrier.pedidosya_token_expiration > now):
            return carrier.pedidosya_token

        if not carrier.pedidosya_auth_url:
            raise PedidosYaError(_(
                "PedidosYa: falta configurar la URL de autenticación (endpoint de "
                "generación de token). Esta URL la entrega PedidosYa junto con las "
                "credenciales; ver https://developers.pedidosya.com/courier-doc/first-steps"
            ))
        if not (carrier.pedidosya_client_id and carrier.pedidosya_client_secret
                and carrier.pedidosya_user and carrier.pedidosya_password):
            raise PedidosYaError(_(
                "PedidosYa: credenciales incompletas en el método de envío "
                "(ClientID, ClientSecret, Usuario y Contraseña son obligatorios)."
            ))

        payload = {
            'client_id': carrier.pedidosya_client_id,
            'client_secret': carrier.pedidosya_client_secret,
            'username': carrier.pedidosya_user,
            'password': carrier.pedidosya_password,
        }
        self._log('pedidosya_token_request', {'url': carrier.pedidosya_auth_url,
                                              'client_id': payload['client_id']})
        try:
            resp = self.session.post(carrier.pedidosya_auth_url, json=payload,
                                     timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            raise PedidosYaError(_("PedidosYa: no se pudo contactar el servicio de "
                                   "autenticación (%s)") % exc) from exc

        if resp.status_code == 429:
            raise PedidosYaError(_(
                "PedidosYa: límite de solicitudes de token excedido; el acceso queda "
                "bloqueado ~10 minutos. El token dura 45 min, no lo regeneres antes."
            ))
        if resp.status_code >= 400:
            raise PedidosYaError(_("PedidosYa: error %(code)s al generar token: %(body)s",
                                   code=resp.status_code, body=resp.text[:500]))

        data = resp.json() if resp.content else {}
        token = (data.get('access_token') or data.get('token')
                 or (resp.text.strip() if resp.text and not resp.text.startswith('{') else None))
        if not token:
            raise PedidosYaError(_("PedidosYa: respuesta de token no reconocida: %s")
                                 % resp.text[:500])
        expires_in = int(data.get('expires_in') or TOKEN_LIFETIME_SECONDS)
        expiration = now + timedelta(seconds=max(60, expires_in - TOKEN_SAFETY_MARGIN_SECONDS))
        carrier.write({
            'pedidosya_token': token,
            'pedidosya_token_expiration': expiration,
        })
        return token

    # -- request genérico ----------------------------------------------------
    def _request(self, method, path, payload=None, params=None, _retry=True):
        url = self.base_url + path
        headers = {
            'Authorization': self._get_token(),
            'Content-Type': 'application/json',
        }
        self._log('pedidosya_request %s %s' % (method, path),
                  {'params': params, 'payload': payload})
        try:
            resp = self.session.request(
                method, url, json=payload, params=params,
                headers=headers, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            raise PedidosYaError(_("PedidosYa: error de red llamando a %(path)s: %(err)s",
                                   path=path, err=exc)) from exc

        # Token vencido/ inválido → refrescar una sola vez y reintentar
        if resp.status_code == 401 and _retry:
            self._get_token(force_refresh=True)
            return self._request(method, path, payload=payload, params=params, _retry=False)

        body = {}
        if resp.content:
            try:
                body = resp.json()
            except ValueError:
                body = {'raw': resp.text[:1000]}
        self._log('pedidosya_response %s %s (%s)' % (method, path, resp.status_code), body)

        if resp.status_code >= 400:
            message = body.get('message') or body.get('messages') or resp.text[:500]
            code = body.get('code') or resp.status_code
            raise PedidosYaError(_("PedidosYa [%(code)s]: %(msg)s", code=code, msg=message))
        return body

    # -- interfaz pública ----------------------------------------------------
    def estimate(self, payload):
        return self._request('POST', '/v3/shippings/estimates', payload=payload)

    def confirm_estimate(self, estimate_id, delivery_offer_id=None):
        payload = {}
        if delivery_offer_id:
            payload['deliveryOfferId'] = delivery_offer_id
        return self._request(
            'POST', '/v3/shippings/estimates/%s/confirm' % estimate_id, payload=payload)

    def get_shipping(self, shipping_id):
        return self._request('GET', '/v3/shippings/%s' % shipping_id)

    def get_tracking(self, shipping_id):
        return self._request('GET', '/v3/shippings/%s/tracking' % shipping_id)

    def cancel_shipping(self, shipping_id, reason):
        return self._request('POST', '/v3/shippings/%s/cancel' % shipping_id,
                             payload={'reasonText': (reason or 'Cancelado desde Odoo')[:255]})

    def set_webhooks_configuration(self, config):
        return self._request('PUT', '/v3/webhooks-configuration', payload=config)

    def get_webhooks_configuration(self):
        return self._request('GET', '/v3/webhooks-configuration')


# ---------------------------------------------------------------------------
# Cliente SIMULADO
# ---------------------------------------------------------------------------
class PedidosYaMockClient(object):
    """Simula la Courier API v3 sin salir del servidor.

    - Precio = base + (precio_km * distancia). La distancia se calcula con
      Haversine entre las coordenadas de los waypoints; si faltan coordenadas
      se asume DEFAULT_DISTANCE_KM.
    - El estado del envío "avanza" solo con el paso del tiempo: el shippingId
      lleva embebido su epoch de creación, así el refresco de estado y el cron
      se pueden probar de punta a punta.
    """

    DEFAULT_DISTANCE_KM = 5.0
    # minutos transcurridos → estado simulado
    STATUS_TIMELINE = [
        (2, 'CONFIRMED'),
        (4, 'IN_PROGRESS'),
        (6, 'NEAR_PICKUP'),
        (8, 'PICKED_UP'),
        (10, 'NEAR_DROPOFF'),
    ]

    def __init__(self, carrier):
        self.carrier = carrier

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def _haversine_km(lat1, lon1, lat2, lon2):
        radius = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (math.sin(d_lat / 2) ** 2
             + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
             * math.sin(d_lon / 2) ** 2)
        return radius * 2 * math.asin(math.sqrt(a))

    def _distance_km(self, waypoints):
        coords = []
        for wp in waypoints:
            lat, lon = wp.get('latitude'), wp.get('longitude')
            if lat and lon:
                coords.append((lat, lon))
        if len(coords) == 2:
            return max(0.5, self._haversine_km(*coords[0], *coords[1]))
        return self.DEFAULT_DISTANCE_KM

    def _price(self, distance_km):
        base = self.carrier.pedidosya_sim_base_price or 3.0
        per_km = self.carrier.pedidosya_sim_km_price or 0.5
        subtotal = round(base + per_km * distance_km, 2)
        taxes = round(subtotal * 0.13, 2)   # IVA El Salvador 13% (solo simulación)
        return subtotal, taxes, round(subtotal + taxes, 2)

    @staticmethod
    def _new_id():
        # epoch embebido al inicio → permite simular la progresión de estados
        return '%d%04d' % (int(time.time()), random.randint(0, 9999))

    @classmethod
    def _status_for(cls, shipping_id):
        try:
            created = int(str(shipping_id)[:10])
        except (ValueError, TypeError):
            return 'CONFIRMED'
        elapsed_min = (time.time() - created) / 60.0
        for limit, status in cls.STATUS_TIMELINE:
            if elapsed_min < limit:
                return status
        return 'COMPLETED'

    # -- interfaz pública ------------------------------------------------------
    def estimate(self, payload):
        distance_km = self._distance_km(payload.get('waypoints', []))
        subtotal, taxes, total = self._price(distance_km)
        estimate_id = self._new_id()
        driving_min = max(5, int(distance_km * 4))
        return {
            'estimateId': estimate_id,
            'referenceId': payload.get('referenceId'),
            'isTest': True,
            'items': payload.get('items', []),
            'waypoints': payload.get('waypoints', []),
            'deliveryOffers': [{
                'deliveryOfferId': 'mock-%s' % estimate_id,
                'deliveryMode': 'EXPRESS',
                'estimatedPickUpTime': _utcnow_iso(15),
                'estimatedDrivingTime': driving_min,
                'deliveryTimeFrom': _utcnow_iso(15 + driving_min),
                'deliveryTimeTo': _utcnow_iso(35 + driving_min),
                'confirmationTimeLimit': _utcnow_iso(15),
                'pricing': {
                    'subtotal': subtotal,
                    'taxes': taxes,
                    'total': total,
                    'currency': 'USD',
                },
            }],
            'route': {'distance': int(distance_km * 1000)},
        }

    def confirm_estimate(self, estimate_id, delivery_offer_id=None):
        shipping_id = self._new_id()
        return {
            'estimateId': estimate_id,
            'shippingId': shipping_id,
            'confirmationCode': 'MOCK-%s' % str(shipping_id)[-6:],
            'isTest': True,
            'status': 'CONFIRMED',
            'proofOfDelivery': False,
            'shareLocationUrl':
                'https://example-courier-web.pedidosya.com/tracking/%s' % shipping_id,
        }

    def get_shipping(self, shipping_id):
        return {
            'shippingId': shipping_id,
            'status': self._status_for(shipping_id),
            'isTest': True,
        }

    def get_tracking(self, shipping_id):
        return {
            'latitude': 13.4833 + random.uniform(-0.01, 0.01),   # San Miguel aprox.
            'longitude': -88.1833 + random.uniform(-0.01, 0.01),
            'deliveryName': 'Rider Simulado',
            'estimatedPickUpTime': _utcnow_iso(5),
            'estimatedDropOffTime': _utcnow_iso(25),
            'deliveryTransport': 'Motorbike',
        }

    def cancel_shipping(self, shipping_id, reason):
        return {
            'shippingId': shipping_id,
            'status': 'CANCELLED',
            'reasonText': reason,
        }

    def set_webhooks_configuration(self, config):
        # En modo simulado no hay API que llamar: se acepta la configuración
        # tal cual para poder probar el endpoint local con curl.
        return dict(config, result='ok-mock')

    def get_webhooks_configuration(self):
        return {'webhooks': [], 'result': 'ok-mock'}
