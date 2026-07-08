# -*- coding: utf-8 -*-
import json
import re

from odoo import api, models


class AccountMoveSendWizard(models.TransientModel):
    _inherit = 'account.move.send.wizard'

    @api.model
    def default_get(self, fields_list):
        """Remove duplicate old invoice PDFs and keep the Cleo comprobante only.

        In Odoo 18 the Send & Print wizard can show two PDFs:
        1) an old cached standard attachment, usually named INV_YYYY_00000.pdf
        2) the freshly generated invoice PDF, usually named "pdf de la factura_..."

        Super Tienda Cleo wants to keep only the new comprobante and rename it
        as Comprobante_de_compra_INV_YYYY_00000.pdf.
        """
        moves = self._cleo_get_active_moves_from_context()
        if moves:
            moves._cleo_clear_standard_invoice_pdf_cache()
            moves._cleo_delete_old_standard_invoice_attachments()

        res = super().default_get(fields_list)

        for key in ('mail_attachments_widget', 'attachments_widget'):
            if key in res and res.get(key):
                res[key] = self._cleo_clean_and_rename_invoice_pdf_attachments(res[key], moves)

        return res

    @api.onchange('pdf_report_id', 'mail_template_id', 'sending_method_checkboxes')
    def _onchange_cleo_clean_attachments(self):
        """Keep the attachments widget clean after Odoo recomputes it."""
        moves = self._cleo_get_active_moves_from_context()
        for wizard in self:
            for key in ('mail_attachments_widget', 'attachments_widget'):
                if key in wizard._fields and wizard[key]:
                    wizard[key] = wizard._cleo_clean_and_rename_invoice_pdf_attachments(wizard[key], moves)

    def _cleo_get_active_moves_from_context(self):
        active_ids = self.env.context.get('active_ids') or self.env.context.get('active_id')
        if not active_ids:
            return self.env['account.move'].browse()
        if isinstance(active_ids, int):
            active_ids = [active_ids]
        return self.env['account.move'].sudo().browse(active_ids).exists()

    def _cleo_invoice_pdf_filename(self, moves=None):
        move = (moves[:1] if moves else self.env['account.move'].browse())
        if move:
            clean_name = (move.name or 'Documento').replace('/', '_').replace(' ', '_')
        else:
            clean_name = 'Documento'
        clean_name = re.sub(r'[^A-Za-z0-9_.-]+', '_', clean_name).strip('_') or 'Documento'
        return 'Comprobante_de_compra_%s.pdf' % clean_name

    def _cleo_parse_attachment_widget(self, widget_value):
        original_is_string = isinstance(widget_value, str)
        try:
            rows = json.loads(widget_value) if original_is_string else widget_value
        except Exception:
            return None, original_is_string
        if not isinstance(rows, list):
            return None, original_is_string
        return rows, original_is_string

    def _cleo_row_name(self, row):
        if not isinstance(row, dict):
            return ''
        return (row.get('name') or row.get('filename') or row.get('display_name') or '').strip()

    def _cleo_set_row_name(self, row, new_name):
        if not isinstance(row, dict):
            return row
        for key in ('name', 'filename', 'display_name'):
            if key in row:
                row[key] = new_name
        if not any(key in row for key in ('name', 'filename', 'display_name')):
            row['name'] = new_name
        return row

    def _cleo_is_pdf_row(self, row):
        name = self._cleo_row_name(row).lower()
        mimetype = ''
        if isinstance(row, dict):
            mimetype = (row.get('mimetype') or row.get('mimetype_name') or '').lower()
        return name.endswith('.pdf') or mimetype == 'application/pdf'

    def _cleo_is_old_standard_invoice_pdf(self, row, moves=None):
        """Detect the old default attachment like INV_2025_00023.pdf."""
        name = self._cleo_row_name(row)
        if not name:
            return False
        lower = name.lower()
        if not lower.endswith('.pdf'):
            return False
        if 'comprobante' in lower or 'pdf de la factura' in lower or 'cleo' in lower:
            return False

        candidates = []
        if moves:
            for move in moves:
                if move.name:
                    candidates.append(move.name.replace('/', '_').replace(' ', '_').lower() + '.pdf')
        candidates += [
            r'inv_\d{4}_\d+\.pdf$',
            r'fact_\d{4}_\d+\.pdf$',
        ]
        normalized = lower.replace('-', '_')
        if normalized in candidates:
            return True
        return any(re.search(pattern, normalized) for pattern in candidates if pattern.startswith('inv_') or pattern.startswith('fact_'))

    def _cleo_is_preferred_invoice_pdf(self, row):
        name = self._cleo_row_name(row).lower()
        return name.endswith('.pdf') and (
            'pdf de la factura' in name or
            'comprobante' in name or
            'cleo' in name
        )

    def _cleo_clean_and_rename_invoice_pdf_attachments(self, widget_value, moves=None):
        rows, original_is_string = self._cleo_parse_attachment_widget(widget_value)
        if rows is None:
            return widget_value

        desired_name = self._cleo_invoice_pdf_filename(moves)

        preferred_rows = []
        old_standard_rows = []
        other_rows = []

        for row in rows:
            if self._cleo_is_pdf_row(row):
                if self._cleo_is_old_standard_invoice_pdf(row, moves):
                    old_standard_rows.append(row)
                    continue
                if self._cleo_is_preferred_invoice_pdf(row):
                    preferred_rows.append(row)
                    continue
            other_rows.append(row)

        cleaned = []
        kept_invoice_pdf = False

        # Keep exactly one Cleo/new invoice PDF, renamed as requested.
        if preferred_rows:
            row = preferred_rows[0]
            cleaned.append(self._cleo_set_row_name(row, desired_name))
            kept_invoice_pdf = True
        elif not preferred_rows and not old_standard_rows:
            # No invoice PDF detected. Preserve non-old rows only.
            kept_invoice_pdf = False

        # Preserve non-invoice attachments. If Odoo adds another invoice PDF not
        # recognized by name, keep only the first PDF to prevent duplicates.
        for row in other_rows:
            if self._cleo_is_pdf_row(row):
                name = self._cleo_row_name(row).lower()
                looks_invoice = any(token in name for token in ('invoice', 'factura', 'inv_', 'comprobante'))
                if looks_invoice:
                    if kept_invoice_pdf:
                        continue
                    cleaned.append(self._cleo_set_row_name(row, desired_name))
                    kept_invoice_pdf = True
                    continue
            cleaned.append(row)

        return json.dumps(cleaned) if original_is_string else cleaned
