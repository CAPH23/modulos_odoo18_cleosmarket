# -*- coding: utf-8 -*-

from odoo import _, models


class Website(models.Model):
    _inherit = "website"

    def _get_checkout_step_list(self):
        """Renombra los botones principales del checkout de Super Tienda Cleo.

        No se toca el texto cuando el botón del carrito redirige a iniciar
        sesión (`account_on_checkout == 'mandatory'`), para no pisar el flujo
        estándar de "Sign In".
        """
        steps = super()._get_checkout_step_list()

        for xmlids, step_vals in steps:
            if "website_sale.cart" in xmlids:
                if not step_vals.get("main_button_href", "").startswith("/web/login"):
                    step_vals["main_button"] = _("Proceder a comprar")
            elif "website_sale.checkout" in xmlids:
                step_vals["main_button"] = _("Confirmar Entrega")

        return steps
