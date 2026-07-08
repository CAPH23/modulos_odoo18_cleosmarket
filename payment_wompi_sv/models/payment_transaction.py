# -*- coding: utf-8 -*-
import json
import logging
import pprint

from odoo import _, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment_wompi_sv import const

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    wompi_sv_id_enlace = fields.Char(string='Wompi ID Enlace', readonly=True, copy=False)
    wompi_sv_id_transaccion = fields.Char(string='Wompi ID Transacción', readonly=True, copy=False)
    wompi_sv_return_hash = fields.Char(string='Wompi Hash Retorno', readonly=True, copy=False, groups='base.group_system')
    wompi_sv_webhook_hash = fields.Char(string='Wompi Hash Webhook', readonly=True, copy=False, groups='base.group_system')
    wompi_sv_last_payload = fields.Text(string='Último payload enviado a Wompi', readonly=True, copy=False, groups='base.group_system')
    wompi_sv_last_notification = fields.Text(string='Última notificación Wompi', readonly=True, copy=False, groups='base.group_system')
    wompi_sv_validation_source = fields.Char(string='Fuente validación Wompi', readonly=True, copy=False)

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != const.PROVIDER_CODE:
            return res

        self.ensure_one()
        if not self.reference:
            raise ValidationError(_('Wompi: la transacción no tiene referencia.'))
        if not self.amount or self.amount <= 0:
            raise ValidationError(_('Wompi: el monto debe ser mayor que cero.'))

        payload = self._wompi_sv_build_payment_link_payload()
        self.provider_id._wompi_sv_log('info', 'Wompi payload para %s:\n%s', self.reference, pprint.pformat(payload))

        response = self.provider_id._wompi_sv_make_request(
            const.API_PAYMENT_LINK_ENDPOINT,
            payload=payload,
            method='POST',
            reference=self.reference,
        )

        url_enlace = response.get('urlEnlace') or response.get('urlEnlaceLargo')
        if not url_enlace:
            _logger.error('Wompi no devolvió urlEnlace. Respuesta: %s', response)
            raise ValidationError(_('Wompi: no se recibió URL de pago.'))

        self.write({
            'provider_reference': str(response.get('idEnlace') or ''),
            'wompi_sv_id_enlace': str(response.get('idEnlace') or ''),
            'wompi_sv_last_payload': json.dumps(payload, ensure_ascii=False, indent=2),
        })
        return {'api_url': url_enlace}

    def _wompi_sv_build_payment_link_payload(self):
        self.ensure_one()
        provider = self.provider_id
        base_url = provider._wompi_sv_get_base_url()
        order = self.sale_order_ids[:1] if 'sale_order_ids' in self._fields else self.env['sale.order']
        payment_title = self._wompi_sv_format_payment_title(order)

        payload = {
            'identificadorEnlaceComercio': self.reference,
            'monto': float(self.amount),
            'nombreProducto': payment_title,
            'formaPago': self._wompi_sv_build_payment_methods(),
            'configuracion': self._wompi_sv_build_configuration(base_url),
            'limitesDeUso': self._wompi_sv_build_usage_limits(),
        }

        if provider.wompi_sv_send_product_info:
            payload['infoProducto'] = self._wompi_sv_build_product_info(order)

        if provider.wompi_sv_allow_installments and provider.wompi_sv_max_installments and provider.wompi_sv_max_installments > 0:
            payload['cantidadMaximaCuotas'] = int(provider.wompi_sv_max_installments)

        if provider.wompi_sv_card_group_id:
            payload['idGrupoTarjetas'] = provider.wompi_sv_card_group_id.strip()

        return payload

    def _wompi_sv_format_payment_title(self, order):
        provider = self.provider_id
        template = provider.wompi_sv_payment_title or 'Pedido {reference} - Super Tienda Cleo'
        order_name = order.name if order else self.reference
        try:
            return template.format(
                reference=self.reference,
                order_name=order_name,
                amount='%.2f' % self.amount,
                currency=self.currency_id.name,
            )[:120]
        except Exception:
            return ('Pedido %s - Super Tienda Cleo' % self.reference)[:120]

    def _wompi_sv_build_payment_methods(self):
        provider = self.provider_id
        return {
            'permitirTarjetaCreditoDebido': bool(provider.wompi_sv_allow_card),
            'permitirPagoConPuntoAgricola': bool(provider.wompi_sv_allow_points),
            'permitirPagoEnCuotasAgricola': bool(provider.wompi_sv_allow_installments),
            'permitirPagoEnBitcoin': bool(provider.wompi_sv_allow_bitcoin),
            'permitePagoQuickPay': bool(provider.wompi_sv_allow_quickpay),
        }

    def _wompi_sv_build_configuration(self, base_url):
        provider = self.provider_id
        config = {
            'urlRedirect': '%s/payment/wompi_sv/return' % base_url,
            'urlRetorno': '%s/shop/payment' % base_url,
            'urlWebhook': '%s/payment/wompi_sv/webhook' % base_url,
            'esMontoEditable': bool(provider.wompi_sv_allow_amount_edit),
            'esCantidadEditable': bool(provider.wompi_sv_allow_quantity_edit),
            'cantidadPorDefecto': max(int(provider.wompi_sv_default_quantity or 1), 1),
            'duracionInterfazIntentoMinutos': max(int(provider.wompi_sv_payment_link_duration_minutes or 30), 1),
            'notificarTransaccionCliente': bool(provider.wompi_sv_notify_customer),
        }
        if provider.wompi_sv_notification_emails:
            config['emailsNotificacion'] = provider.wompi_sv_notification_emails.strip()
        return config

    def _wompi_sv_build_usage_limits(self):
        provider = self.provider_id
        return {
            'cantidadMaximaPagosExitosos': max(int(provider.wompi_sv_max_successful_payments or 1), 1),
            'cantidadMaximaPagosFallidos': max(int(provider.wompi_sv_max_failed_attempts or 0), 0),
        }

    def _wompi_sv_build_product_info(self, order):
        provider = self.provider_id
        description = self._wompi_sv_build_description(order)
        return {
            'descripcionProducto': description[:900],
            'urlImagenProducto': provider._wompi_sv_get_public_banner_url(),
        }

    def _wompi_sv_build_description(self, order):
        provider = self.provider_id
        lines = [
            'Compra en línea Super Tienda Cleo',
            'Pedido: %s' % self.reference,
        ]
        if order:
            valid_lines = order.order_line.filtered(lambda line: not line.display_type)
            product_qty = sum(valid_lines.mapped('product_uom_qty'))
            lines.append('Productos: %s producto(s)' % int(product_qty))
        lines.append('Total: %s %.2f' % (self.currency_id.name, self.amount))

        if order and provider.wompi_sv_include_order_lines:
            max_lines = max(int(provider.wompi_sv_max_order_lines or 0), 0)
            valid_lines = order.order_line.filtered(lambda line: not line.display_type)
            if max_lines and valid_lines:
                lines.append('')
                lines.append('Resumen de productos:')
                for line in valid_lines[:max_lines]:
                    clean_name = str(line.name or line.product_id.display_name or '').replace('\n', ' ').strip()
                    qty = line.product_uom_qty
                    lines.append('- %s x %s' % (self._wompi_sv_format_qty(qty), clean_name[:75]))
                if len(valid_lines) > max_lines:
                    lines.append('- y otros productos del pedido')

        if provider.wompi_sv_description_footer:
            lines.append('')
            lines.extend(str(provider.wompi_sv_description_footer).splitlines())
        return '\n'.join(lines)

    def _wompi_sv_format_qty(self, qty):
        if qty == int(qty):
            return str(int(qty))
        return ('%.2f' % qty).rstrip('0').rstrip('.')

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        if provider_code != const.PROVIDER_CODE:
            return super()._get_tx_from_notification_data(provider_code, notification_data)

        reference = self._wompi_sv_extract_reference(notification_data)
        if not reference:
            raise ValidationError(_('Wompi: no se recibió referencia de la transacción.'))

        tx = self.search([('reference', '=', reference), ('provider_code', '=', const.PROVIDER_CODE)], limit=1)
        if not tx:
            raise ValidationError(_('Wompi: no se encontró la transacción con referencia %s.', reference))
        return tx

    def _process_notification_data(self, notification_data):
        if self.provider_code != const.PROVIDER_CODE:
            return super()._process_notification_data(notification_data)

        super()._process_notification_data(notification_data)
        self.ensure_one()
        self.provider_id._wompi_sv_log('info', 'Procesando notificación Wompi (%s) para %s:\n%s', notification_data.get('_wompi_sv_source'), self.reference, pprint.pformat(notification_data))

        write_vals = {
            'wompi_sv_last_notification': json.dumps(notification_data, ensure_ascii=False, indent=2, default=str),
            'wompi_sv_validation_source': notification_data.get('_wompi_sv_source') or '',
        }
        if notification_data.get('hash'):
            write_vals['wompi_sv_return_hash'] = notification_data.get('hash')
        if notification_data.get('_wompi_sv_webhook_hash'):
            write_vals['wompi_sv_webhook_hash'] = notification_data.get('_wompi_sv_webhook_hash')

        wompi_tx_id = self._wompi_sv_extract_transaction_id(notification_data)
        wompi_link_id = self._wompi_sv_extract_link_id(notification_data)
        if wompi_tx_id:
            write_vals['wompi_sv_id_transaccion'] = str(wompi_tx_id)
            write_vals['provider_reference'] = str(wompi_tx_id)
        if wompi_link_id:
            write_vals['wompi_sv_id_enlace'] = str(wompi_link_id)
        self.write(write_vals)

        resultado = self._wompi_sv_extract_result(notification_data)
        es_aprobada = self._wompi_sv_extract_approved_flag(notification_data)

        if not resultado and es_aprobada is None and wompi_tx_id:
            api_data = self._wompi_sv_fetch_transaction_by_id(wompi_tx_id)
            if api_data:
                self.provider_id._wompi_sv_log('info', 'Wompi consulta por idTransaccion %s para %s:\n%s', wompi_tx_id, self.reference, pprint.pformat(api_data))
                notification_data = self._wompi_sv_merge_notification_data(notification_data, api_data)
                resultado = self._wompi_sv_extract_result(notification_data)
                es_aprobada = self._wompi_sv_extract_approved_flag(notification_data)
                self.write({'wompi_sv_last_notification': json.dumps(notification_data, ensure_ascii=False, indent=2, default=str)})

        amount_received = self._wompi_sv_extract_amount(notification_data)
        if amount_received is not None:
            try:
                amount_received = float(amount_received)
            except (TypeError, ValueError):
                amount_received = None

        if amount_received is not None and self.currency_id.compare_amounts(amount_received, self.amount) != 0:
            _logger.warning('Wompi: discrepancia de monto para %s. Esperado %s, recibido %s.', self.reference, self.amount, amount_received)
            self._set_error(_('Wompi: el monto recibido (%s) no coincide con el monto esperado (%s).', amount_received, self.amount))
            return

        aprobado = self._wompi_sv_is_approved(resultado, es_aprobada)
        pendiente = self._wompi_sv_is_pending(resultado)
        cancelado = self._wompi_sv_is_cancelled(resultado)

        if aprobado:
            _logger.info('Wompi: transacción aprobada para %s.', self.reference)
            self._wompi_sv_mark_done_and_confirm_order()
            return
        if pendiente:
            _logger.info('Wompi: transacción pendiente para %s.', self.reference)
            self._set_pending()
            return
        if cancelado:
            _logger.info('Wompi: transacción cancelada para %s.', self.reference)
            self._set_canceled(state_message=_('Wompi: la transacción fue cancelada (resultado: %s).', resultado))
            return
        if resultado:
            _logger.warning('Wompi: transacción rechazada/error para %s. Resultado: %s', self.reference, resultado)
            self._set_error(_('Wompi: la transacción fue rechazada o no aprobada (resultado: %s).', resultado))
            return

        _logger.warning('Wompi: notificación sin resultado para %s. Datos:\n%s', self.reference, pprint.pformat(notification_data))
        self._set_pending()

    def _wompi_sv_mark_done_and_confirm_order(self):
        if self.state != 'done':
            self._set_done()
        if 'sale_order_ids' in self._fields:
            for order in self.sale_order_ids:
                if order.state in ('draft', 'sent'):
                    _logger.info('Wompi: confirmando orden %s relacionada con transacción %s.', order.name, self.reference)
                    order.action_confirm()

    def _wompi_sv_fetch_transaction_by_id(self, wompi_tx_id):
        if not wompi_tx_id:
            return {}
        try:
            return self.provider_id._wompi_sv_make_request(
                const.API_TRANSACTION_ENDPOINT % wompi_tx_id,
                method='GET',
                reference=self.reference,
            )
        except Exception:
            _logger.exception('Wompi: no se pudo consultar TransaccionCompra/%s para %s.', wompi_tx_id, self.reference)
            return {}

    def _wompi_sv_merge_notification_data(self, notification_data, api_data):
        merged = dict(notification_data or {})
        for key, value in (api_data or {}).items():
            if key not in merged or merged.get(key) in (None, '', False):
                merged[key] = value
        merged['_wompi_sv_api_data'] = api_data
        return merged

    def _wompi_sv_extract_reference(self, data):
        enlace = self._wompi_sv_get_value(data, 'EnlacePago', 'enlacePago') or {}
        return (
            self._wompi_sv_get_value(data, 'identificadorEnlaceComercio', 'IdentificadorEnlaceComercio')
            or self._wompi_sv_get_value(enlace, 'identificadorEnlaceComercio', 'IdentificadorEnlaceComercio')
            or self._wompi_sv_get_value(data, 'idExterno', 'IdExterno')
            or self._wompi_sv_get_value(data, 'reference', 'Referencia')
        )

    def _wompi_sv_extract_transaction_id(self, data):
        return self._wompi_sv_get_value(data, 'idTransaccion', 'IdTransaccion', 'idTransaccionCompra', 'IdTransaccionCompra')

    def _wompi_sv_extract_link_id(self, data):
        enlace = self._wompi_sv_get_value(data, 'EnlacePago', 'enlacePago') or {}
        return self._wompi_sv_get_value(data, 'idEnlace', 'IdEnlace') or self._wompi_sv_get_value(enlace, 'idEnlace', 'IdEnlace')

    def _wompi_sv_extract_result(self, data):
        return self._wompi_sv_get_value(data, 'resultadoTransaccion', 'ResultadoTransaccion', 'estado', 'Estado', 'mensaje', 'Mensaje')

    def _wompi_sv_extract_amount(self, data):
        return self._wompi_sv_get_value(data, 'monto', 'Monto', 'montoOriginal', 'MontoOriginal')

    def _wompi_sv_extract_approved_flag(self, data):
        value = self._wompi_sv_get_value(data, 'esAprobada', 'EsAprobada', 'aprobada', 'Aprobada')
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        value_str = str(value).strip().lower()
        if value_str in ('true', '1', 'si', 'sí', 'yes'):
            return True
        if value_str in ('false', '0', 'no'):
            return False
        return None

    def _wompi_sv_get_value(self, data, *keys):
        if not isinstance(data, dict):
            return None
        for key in keys:
            if key in data:
                return data[key]
        lower_map = {str(k).lower(): v for k, v in data.items()}
        for key in keys:
            value = lower_map.get(str(key).lower())
            if value is not None:
                return value
        return None

    def _wompi_sv_is_approved(self, resultado, es_aprobada=None):
        if es_aprobada is True:
            return True
        if resultado is None:
            return False
        value = str(resultado).strip().lower()
        approved_values = {'exitosaaprobada', 'aprobada', 'aprobado', 'approved', 'success', 'successful', 'paid', 'pagada', 'pagado', 'done'}
        return value in approved_values

    def _wompi_sv_is_pending(self, resultado):
        if resultado is None:
            return False
        value = str(resultado).strip().lower()
        return value in {'pendiente', 'pending', 'enproceso', 'en proceso', 'procesando', 'processing'}

    def _wompi_sv_is_cancelled(self, resultado):
        if resultado is None:
            return False
        value = str(resultado).strip().lower()
        return value in {'cancelada', 'cancelado', 'cancelled', 'canceled', 'anulada', 'anulado', 'void', 'reversed', 'rechazada', 'rechazado'}
