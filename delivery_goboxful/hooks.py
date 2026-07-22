# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Marca automáticamente la rama PRODUCTOS CONGELADOS como no transportable.

    La regla continúa siendo editable desde la categoría. La búsqueda es
    deliberadamente tolerante a mayúsculas y acentos en el nombre visible.
    """
    categories = env["product.category"].sudo().search([
        ("name", "ilike", "PRODUCTOS CONGELADOS"),
    ])
    if categories:
        categories.write({"goboxful_block_shipping": True})
        _logger.info(
            "Boxful: categorías congeladas marcadas automáticamente: %s",
            categories.mapped("complete_name"),
        )
