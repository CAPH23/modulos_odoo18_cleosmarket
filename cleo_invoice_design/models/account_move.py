# -*- coding: utf-8 -*-
import re
import unicodedata

from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_print_cleo_purchase_document(self):
        """Print the Super Tienda Cleo letter-size purchase document."""
        return self.env.ref('cleo_invoice_design.action_report_cleo_invoice_letter').report_action(self)

    def action_print_cleo_invoice_ticket(self):
        """Print the Super Tienda Cleo 80mm ticket based on the invoice."""
        return self.env.ref('cleo_invoice_design.action_report_cleo_invoice_ticket').report_action(self)

    def preview_invoice(self):
        """Native 'Vista previa' button: open the Cleo comprobante directly.

        The standard implementation redirects to the generic portal invoice
        page, which is a separate HTML template account.report_invoice_document
        does not touch, so it still shows Odoo's stock layout. Customer
        invoices should preview the same report as the "Comprobante Cleo"
        button instead.
        """
        self.ensure_one()
        if self.move_type in ('out_invoice', 'out_receipt') and self.state == 'posted':
            return self.env.ref('cleo_invoice_design.action_report_cleo_invoice_letter').report_action(self)
        return super().preview_invoice()

    def _cleo_clear_standard_invoice_pdf_cache(self):
        """Clear cached standard invoice PDF before sending/printing.

        Odoo may keep a previously generated PDF in invoice_pdf_report_id.
        If that attachment was created before installing this module, the Send
        button could reuse the old standard invoice. Clearing the reference
        forces the wizard to generate a fresh PDF using the Cleo report.
        """
        if 'invoice_pdf_report_id' not in self._fields:
            return
        self.filtered(lambda move: move.invoice_pdf_report_id).sudo().write({
            'invoice_pdf_report_id': False,
        })

    def action_print_pdf(self):
        """Native Imprimir button: keep Odoo standard flow, but refresh cache.

        The standard invoice report template is overridden by this module, so
        calling Odoo's normal action produces the Cleo comprobante while keeping
        compatibility with the Send & Print wizard.
        """
        cleo_moves = self.filtered(lambda move: move.move_type in ('out_invoice', 'out_receipt', 'out_refund'))
        cleo_moves._cleo_clear_standard_invoice_pdf_cache()
        return super().action_print_pdf()

    def action_invoice_sent(self):
        """Native Enviar button: clear old cached invoice PDFs only.

        Do not force a custom report in the wizard. Odoo's standard invoice
        report is now visually replaced by the Cleo comprobante, which avoids
        duplicate attachments in the email composer.
        """
        cleo_moves = self.filtered(lambda move: move.move_type in ('out_invoice', 'out_receipt', 'out_refund'))
        cleo_moves._cleo_clear_standard_invoice_pdf_cache()
        return super().action_invoice_sent()

    def action_send_and_print(self):
        """Odoo 18 Send & Print flow: clear old cached invoice PDFs only."""
        cleo_moves = self.filtered(lambda move: move.move_type in ('out_invoice', 'out_receipt', 'out_refund'))
        cleo_moves._cleo_clear_standard_invoice_pdf_cache()
        return super().action_send_and_print()

    def _cleo_text(self, value):
        """Return report-safe text without mojibake-prone accents.

        Some wkhtmltopdf environments render UTF-8 text as Latin-1 and show
        characters such as Â or Ã. This helper normalizes dynamic text to a
        clean ASCII representation for Cleo PDF reports.
        """
        self.ensure_one()
        if value is None:
            return ''
        text = str(value)
        replacements = {
            'Ã¡': 'a', 'Ã©': 'e', 'Ã­': 'i', 'Ã³': 'o', 'Ãº': 'u',
            'Ã�': 'A', 'Ã‰': 'E', 'Ã�': 'I', 'Ã“': 'O', 'Ãš': 'U',
            'Ã±': 'n', 'Ã‘': 'N', 'Â': '', 'â€“': '-', 'â€”': '-',
            'â€œ': '"', 'â€': '"', 'â€˜': "'", 'â€™': "'",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
        return text.strip()

    def _cleo_ticket_money(self, amount):
        """Return a simple USD-style amount without non-breaking spaces.

        Odoo's monetary widget may render a non-breaking space between the
        currency symbol and amount. In some wkhtmltopdf environments that
        appears as an extra Â character, so the ticket uses this safe formatter.
        """
        self.ensure_one()
        symbol = self.currency_id.symbol or '$'
        try:
            value = float(amount or 0.0)
        except Exception:
            value = 0.0
        return '%s %.2f' % (symbol, value)


    def _cleo_ticket_qty(self, qty):
        """Return a compact quantity for the 80mm ticket."""
        self.ensure_one()
        try:
            value = float(qty or 0.0)
        except Exception:
            value = 0.0
        if value.is_integer():
            return str(int(value))
        return ('%.2f' % value).rstrip('0').rstrip('.')

    def _cleo_get_related_sale_order(self):
        """Return the sale order related to this invoice, when available.

        Some invoices generated from website sales in this installation may not
        keep visible invoice lines in invoice_line_ids. In that case the ticket
        uses the source sale order lines as fallback, usually identified by
        invoice_origin such as S00120.
        """
        self.ensure_one()
        SaleOrder = self.env['sale.order'].sudo()

        sale_order = SaleOrder.search([('invoice_ids', 'in', [self.id])], order='id desc', limit=1)
        if sale_order:
            return sale_order

        if self.invoice_origin:
            origin_parts = [part.strip() for part in re.split(r'[,;\s]+', self.invoice_origin or '') if part.strip()]
            if origin_parts:
                sale_order = SaleOrder.search([('name', 'in', origin_parts)], order='id desc', limit=1)
                if sale_order:
                    return sale_order

        return SaleOrder.browse()

    def _cleo_is_delivery_sale_line(self, line):
        """Return True if the sale line represents delivery cost."""
        if not line:
            return False
        if 'is_delivery' in line._fields and line.is_delivery:
            return True
        product = line.product_id
        if product and product.default_code and str(product.default_code).lower() in ('delivery', 'shipping'):
            return True
        text = '%s %s' % (line.name or '', product.display_name if product else '')
        text = text.lower()
        return any(word in text for word in ['delivery', 'envio', 'entrega domicilio', 'entrega estandar'])

    def _cleo_prepare_ticket_line(self, product, name, qty, price_unit, subtotal, total=None, description=None):
        return {
            'product': product,
            'name': name or (product.display_name if product else ''),
            'description': description or '',
            'qty': qty or 0.0,
            'price_unit': price_unit or 0.0,
            'subtotal': subtotal or 0.0,
            'total': total if total is not None else (subtotal or 0.0),
        }

    def _cleo_get_invoice_ticket_lines(self):
        """Return product lines for the Cleo 80mm invoice ticket.

        Priority:
        1) account.move.invoice_line_ids
        2) accounting move lines excluding receivable/payable
        3) source sale.order.order_line from invoice_origin/invoice_ids
        """
        self.ensure_one()
        result = []

        invoice_lines = self.invoice_line_ids.filtered(
            lambda line: not line.display_type and (line.product_id or line.name)
        )
        for line in invoice_lines:
            product_name = line.product_id.display_name if line.product_id else line.name
            description = ''
            if line.name and product_name and line.name.strip() != product_name.strip():
                description = line.name
            result.append(self._cleo_prepare_ticket_line(
                line.product_id,
                product_name,
                line.quantity,
                line.price_unit,
                line.price_subtotal,
                line.price_total,
                description,
            ))

        if result:
            return result

        accounting_lines = self.line_ids.filtered(
            lambda line: not line.display_type
            and (line.product_id or line.name)
            and line.account_id
            and line.account_id.account_type not in ('asset_receivable', 'liability_payable')
            and (line.quantity or line.price_subtotal or line.price_total)
        )
        for line in accounting_lines:
            product_name = line.product_id.display_name if line.product_id else line.name
            result.append(self._cleo_prepare_ticket_line(
                line.product_id,
                product_name,
                line.quantity,
                line.price_unit,
                line.price_subtotal,
                line.price_total,
                line.name if line.product_id and line.name != line.product_id.display_name else '',
            ))

        if result:
            return result

        sale_order = self._cleo_get_related_sale_order()
        if sale_order:
            for line in sale_order.order_line.sudo():
                if line.display_type or self._cleo_is_delivery_sale_line(line):
                    continue
                product_name = line.product_id.display_name if line.product_id else line.name
                description = ''
                if line.name and product_name and line.name.strip() != product_name.strip():
                    description = line.name
                result.append(self._cleo_prepare_ticket_line(
                    line.product_id,
                    product_name,
                    line.product_uom_qty,
                    line.price_unit,
                    line.price_subtotal,
                    line.price_total,
                    description,
                ))

        return result

    def _cleo_get_invoice_ticket_delivery_amount(self, sale_order=None):
        self.ensure_one()
        sale_order = sale_order or self._cleo_get_related_sale_order()
        if not sale_order:
            return 0.0
        if 'amount_delivery' in sale_order._fields and sale_order.amount_delivery:
            return sale_order.amount_delivery
        delivery_lines = sale_order.order_line.filtered(lambda line: self._cleo_is_delivery_sale_line(line))
        return sum(delivery_lines.mapped('price_total')) if delivery_lines else 0.0

    def _cleo_get_invoice_ticket_payment_method(self, sale_order=None):
        self.ensure_one()
        sale_order = sale_order or self._cleo_get_related_sale_order()

        if self.pos_payment_ids:
            methods = self.pos_payment_ids.mapped('payment_method_id.name')
            if methods:
                return ', '.join(dict.fromkeys(methods))

        if sale_order and 'transaction_ids' in sale_order._fields and sale_order.transaction_ids:
            transactions = sale_order.transaction_ids.sudo()
            preferred = transactions.filtered(lambda tx: tx.state in ('done', 'authorized', 'pending')) or transactions
            tx = preferred.sorted('id')[-1]
            provider_code = (tx.provider_code or '').lower()
            provider_name = tx.provider_id.display_name if tx.provider_id else ''
            method_name = tx.payment_method_id.display_name if tx.payment_method_id else ''
            if 'wompi' in provider_code or 'wompi' in provider_name.lower():
                return 'Tarjeta de credito o debito'
            return method_name or provider_name or 'Pago en linea'

        if self.matched_payment_ids:
            journals = self.matched_payment_ids.mapped('journal_id.name')
            if journals:
                return ', '.join(dict.fromkeys(journals))

        if self.payment_state == 'paid':
            return 'Pago registrado'
        return 'Pendiente de pago'

    def _cleo_get_invoice_ticket_delivery_method(self, sale_order=None):
        self.ensure_one()
        sale_order = sale_order or self._cleo_get_related_sale_order()
        if sale_order and sale_order.carrier_id:
            return sale_order.carrier_id.display_name
        if sale_order and 'amount_delivery' in sale_order._fields and sale_order.amount_delivery == 0:
            return 'Retiro en tienda o entrega segun pedido'
        if self.partner_shipping_id:
            return 'Entrega a domicilio'
        return 'Segun pedido'

    def _cleo_get_invoice_ticket_origin_label(self, sale_order=None):
        self.ensure_one()
        sale_order = sale_order or self._cleo_get_related_sale_order()
        if sale_order and sale_order.website_id:
            return 'Tienda en linea'
        if self.pos_order_ids:
            return 'Punto de venta'
        return 'Factura'

    def _cleo_get_invoice_ticket_amounts(self, ticket_lines=None, sale_order=None):
        self.ensure_one()
        sale_order = sale_order or self._cleo_get_related_sale_order()
        ticket_lines = ticket_lines if ticket_lines is not None else self._cleo_get_invoice_ticket_lines()
        delivery_amount = self._cleo_get_invoice_ticket_delivery_amount(sale_order)
        subtotal = sum(line.get('subtotal', 0.0) for line in ticket_lines) if ticket_lines else self.amount_untaxed
        tax_amount = self.amount_tax or (sale_order.amount_tax if sale_order else 0.0)
        total = self.amount_total or (sale_order.amount_total if sale_order else 0.0)
        paid = max(total - self.amount_residual, 0.0)
        return {
            'subtotal': subtotal,
            'tax': tax_amount,
            'delivery': delivery_amount,
            'total': total,
            'paid': paid,
        }

    def _cleo_get_invoice_ticket_context(self):
        self.ensure_one()
        sale_order = self._cleo_get_related_sale_order()
        lines = self._cleo_get_invoice_ticket_lines()
        return {
            'sale_order': sale_order,
            'lines': lines,
            'amounts': self._cleo_get_invoice_ticket_amounts(lines, sale_order),
            'payment_method': self._cleo_get_invoice_ticket_payment_method(sale_order),
            'delivery_method': self._cleo_get_invoice_ticket_delivery_method(sale_order),
            'origin_label': self._cleo_get_invoice_ticket_origin_label(sale_order),
            'reference': sale_order.name if sale_order else (self.invoice_origin or self.name),
            'is_paid': self.payment_state == 'paid',
        }
