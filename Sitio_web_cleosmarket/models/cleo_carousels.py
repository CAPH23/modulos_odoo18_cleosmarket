# -*- coding: utf-8 -*-

from odoo import api, fields, models


class CleoWebsiteHelper(models.AbstractModel):
    _name = "cleo.website.helper"
    _description = "Super Tienda Cleo Website Helper"

    @api.model
    def get_best_seller_products(self, limit=20, days=60):
        """
        Devuelve productos más vendidos en los últimos X días.

        Criterio:
        - Incluye ventas de cualquier medio:
            * Ventas normales / sitio web: sale.order.line
            * Punto de venta: pos.order.line
        - Solo productos publicados en eCommerce.
        - Ordena por cantidad vendida de mayor a menor.
        - Agrupa por product.template para evitar duplicados por variantes.
        """

        ProductTemplate = self.env["product.template"].sudo()
        ProductProduct = self.env["product.product"].sudo()

        date_limit = fields.Datetime.subtract(fields.Datetime.now(), days=days)

        template_qty = {}

        def add_sold_qty(product_id, sold_qty):
            if not product_id or not sold_qty:
                return

            product_variant = ProductProduct.browse(product_id).exists()

            if not product_variant:
                return

            product_template = product_variant.product_tmpl_id

            if not product_template:
                return

            # Solo productos publicados en comercio electrónico
            if not product_template.website_published:
                return

            template_qty[product_template.id] = template_qty.get(product_template.id, 0.0) + sold_qty

        # ============================================================
        # 1. Ventas normales y ventas del sitio web
        #    Modelo: sale.order.line
        # ============================================================
        SaleOrderLine = self.env["sale.order.line"].sudo()

        sale_domain = [
            ("order_id.state", "in", ["sale", "done"]),
            ("order_id.date_order", ">=", date_limit),
            ("display_type", "=", False),
            ("product_id", "!=", False),
            ("product_uom_qty", ">", 0),
            ("product_id.product_tmpl_id.website_published", "=", True),
        ]

        sale_groups = SaleOrderLine.read_group(
            domain=sale_domain,
            fields=["product_uom_qty:sum", "product_id"],
            groupby=["product_id"],
            lazy=False,
        )

        for group in sale_groups:
            product_data = group.get("product_id")
            if not product_data:
                continue

            product_id = product_data[0]
            sold_qty = group.get("product_uom_qty") or 0.0

            add_sold_qty(product_id, sold_qty)

        # ============================================================
        # 2. Ventas de Punto de Venta
        #    Modelo: pos.order.line
        # ============================================================
        if "pos.order.line" in self.env.registry:
            PosOrderLine = self.env["pos.order.line"].sudo()

            pos_domain = [
                ("order_id.state", "in", ["paid", "done", "invoiced"]),
                ("order_id.date_order", ">=", date_limit),
                ("product_id", "!=", False),
                ("qty", ">", 0),
                ("product_id.product_tmpl_id.website_published", "=", True),
            ]

            pos_groups = PosOrderLine.read_group(
                domain=pos_domain,
                fields=["qty:sum", "product_id"],
                groupby=["product_id"],
                lazy=False,
            )

            for group in pos_groups:
                product_data = group.get("product_id")
                if not product_data:
                    continue

                product_id = product_data[0]
                sold_qty = group.get("qty") or 0.0

                add_sold_qty(product_id, sold_qty)

        if not template_qty:
            return ProductTemplate.browse([])

        templates = ProductTemplate.browse(list(template_qty.keys()))

        template_names = {
            template.id: template.name or ""
            for template in templates
        }

        ordered_template_ids = sorted(
            template_qty.keys(),
            key=lambda template_id: (
                -template_qty[template_id],
                template_names.get(template_id, ""),
            ),
        )

        return ProductTemplate.browse(ordered_template_ids[:limit])
