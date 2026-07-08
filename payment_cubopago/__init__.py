# -*- coding: utf-8 -*-
# Part of the CuboPago payment module.
# Copyright 2026 Carlos Palacios
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file for full details.
from . import controllers
from . import models

try:
    from odoo.addons.payment import setup_provider, reset_payment_provider
except Exception:  # pragma: no cover
    setup_provider = reset_payment_provider = None


def post_init_hook(env):
    """Activate defaults for the CuboPago provider after installation."""
    if setup_provider:
        setup_provider(env, 'cubopago')
    env['payment.provider'].sudo()._cubopago_create_and_attach_payment_method()


def uninstall_hook(env):
    """Reset provider-specific configuration on uninstall."""
    if reset_payment_provider:
        reset_payment_provider(env, 'cubopago')
