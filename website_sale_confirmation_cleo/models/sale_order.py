# -*- coding: utf-8 -*-
from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def cleo_confirmation_invoice(self):
        """Return the first posted customer invoice related to the order."""
        self.ensure_one()
        invoices = self.invoice_ids.filtered(
            lambda move: move.state == 'posted' and move.move_type in ('out_invoice', 'out_refund')
        ).sorted(lambda move: move.date or move.create_date, reverse=True)
        return invoices[:1]

    def cleo_confirmation_invoice_pdf_url(self):
        """Return portal PDF URL for the posted invoice, or False if there is none."""
        self.ensure_one()
        invoice = self.cleo_confirmation_invoice()
        if not invoice:
            return False
        try:
            return invoice.get_portal_url(report_type='pdf', download=True)
        except Exception:
            return False

    def cleo_confirmation_order_url(self):
        """Return the portal URL for the sale order."""
        self.ensure_one()
        try:
            return self.get_portal_url()
        except Exception:
            return '/my/orders'

    def cleo_confirmation_last_transaction(self):
        """Return the transaction shown on the confirmation page, or an empty recordset."""
        self.ensure_one()
        try:
            tx = self.get_portal_last_transaction()
        except Exception:
            tx = self.transaction_ids.sorted(lambda t: t.id, reverse=True)[:1]
        return tx

    def cleo_confirmation_payment_label(self):
        """Return the latest payment provider label related to the order."""
        self.ensure_one()
        tx = self.cleo_confirmation_last_transaction()
        if tx and tx.provider_id:
            return tx.provider_id.name
        return 'Pago confirmado'

    def cleo_confirmation_payment_is_done(self):
        self.ensure_one()
        if self.invoice_ids.filtered(lambda move: move.payment_state in ('paid', 'in_payment')):
            return True
        txs = self.transaction_ids.filtered(lambda tx: tx.state == 'done')
        return bool(txs)

    # Códigos de proveedor que cobran con tarjeta al confirmar el pedido
    # (payment_wompi_sv, payment_cubopago). "Cobro contra entrega" (cleo_cod)
    # y "Pagar en el sitio" comparten el código genérico 'custom' de Odoo, así
    # que no se puede distinguir por código propio: se identifica el pago con
    # tarjeta por exclusión.
    CLEO_CARD_PROVIDER_CODES = ('wompi_sv', 'cubopago')

    def cleo_confirmation_is_cod_payment(self):
        """True cuando el pago todavía no se ha cobrado al confirmar el pedido
        ("Cobro contra entrega" en domicilio, o "Pagar en el sitio" al retirar
        en tienda), a diferencia de un pago con tarjeta ya procesado.
        """
        self.ensure_one()
        tx = self.cleo_confirmation_last_transaction()
        if not tx or not tx.provider_id:
            return False
        return tx.provider_id.code not in self.CLEO_CARD_PROVIDER_CODES

    def cleo_confirmation_is_pickup(self):
        """True cuando el método de entrega elegido es retiro en tienda."""
        self.ensure_one()
        return bool(self.carrier_id and self.carrier_id.delivery_type == 'in_store')

    def cleo_confirmation_main_message(self):
        """Mensaje principal del encabezado de confirmación.

        Depende solo del método de pago: si el pago ya se cobró (tarjeta), se
        confirma explícitamente; si es contra entrega/en sitio, el pago sigue
        pendiente y no debe decirse que "se procesó con éxito".
        """
        self.ensure_one()
        if self.cleo_confirmation_is_cod_payment():
            return 'Su pedido está en preparación.'
        return 'Su pago ha sido procesado con éxito y su pedido está en preparación.'

    def cleo_confirmation_payment_step_label(self):
        """Estado a mostrar en el paso "Pago confirmado"."""
        self.ensure_one()
        return 'Pendiente' if self.cleo_confirmation_is_cod_payment() else 'Completado'

    def cleo_confirmation_delivery_step_icon(self):
        """Ícono FontAwesome del paso "Listo para retiro o entrega"."""
        self.ensure_one()
        return 'fa-shopping-bag' if self.cleo_confirmation_is_pickup() else 'fa-motorcycle'

    def cleo_confirmation_delivery_step_title(self):
        """Título del paso "Listo para retiro o entrega"."""
        self.ensure_one()
        return 'Listo para retiro' if self.cleo_confirmation_is_pickup() else 'Entrega'

    def cleo_confirmation_delivery_step_status(self):
        """Estado del paso de entrega/retiro, tomado directamente de delivery_status."""
        self.ensure_one()
        return {
            False: 'Pendiente',
            'pending': 'Pendiente',
            'started': 'En progreso',
            'partial': 'En progreso',
            'full': 'Completado',
        }.get(self.delivery_status, 'Pendiente')

    def cleo_confirmation_preparation_text(self):
        """Texto del bloque "Estado de preparación", según el método de entrega."""
        self.ensure_one()
        if self.cleo_confirmation_is_pickup():
            return 'Te notificaremos cuando esté listo.'
        return 'Te notificaremos cuando el pedido sea enviado.'

    def cleo_confirmation_delivery_amount(self):
        self.ensure_one()
        delivery_lines = self.order_line.filtered(
            lambda line: not line.display_type and 'is_delivery' in line._fields and line.is_delivery
        )
        return sum(delivery_lines.mapped('price_total')) if delivery_lines else 0.0

    def cleo_confirmation_products_amount(self):
        self.ensure_one()
        return self.amount_total - self.cleo_confirmation_delivery_amount()

    def cleo_confirmation_product_line_count(self):
        self.ensure_one()
        product_lines = self.order_line.filtered(
            lambda line: not line.display_type
            and not ('is_delivery' in line._fields and line.is_delivery)
        )
        return len(product_lines)

    def cleo_confirmation_delivery_text(self):
        self.ensure_one()
        partner = self.partner_shipping_id or self.partner_invoice_id or self.partner_id
        if not partner:
            return ''
        parts = [
            partner.street,
            partner.street2,
            partner.city,
            partner.state_id.name,
            partner.country_id.name,
        ]
        return ', '.join([part for part in parts if part])

    def cleo_confirmation_is_delivered(self):
        self.ensure_one()
        return bool(self.picking_ids.filtered(lambda picking: picking.state == 'done'))
