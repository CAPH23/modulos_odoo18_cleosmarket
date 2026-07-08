# -*- coding: utf-8 -*-
# Part of the CuboPago payment module.
# Copyright 2026 Carlos Palacios
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file for full details.

PROVIDER_CODE = 'cubopago'
PROVIDER_NAME = 'CuboPago'

# CuboPago links/transactions operate in USD.
SUPPORTED_CURRENCIES = {'USD'}

# Own payment method so we do not modify Odoo's shared 'card' method.
DEFAULT_PAYMENT_METHOD_CODES = {'cubopago'}

# NOTE: CuboPago does not publish fixed base URLs in its public documentation;
# the API base URL is provided per environment by CuboPago (contact center).
# These are sensible placeholders and MUST be confirmed/replaced by the merchant
# with the exact URLs delivered by CuboPago for SANDBOX and PRODUCTION.
DEFAULT_API_URL_TEST = 'https://sandbox.api.cubopago.com'
DEFAULT_API_URL_PROD = 'https://api.cubopago.com'

# API endpoints (relative to the configured base URL).
ENDPOINT_CREATE_LINK = '/api/v1/links/one-use'
ENDPOINT_TRANSACTION = '/api/v1/transactions/%s'

# Webhook / transaction statuses returned by CuboPago.
STATUS_APPROVED = {'succeeded', 'approved', 'paid', 'success', 'successful'}
STATUS_REJECTED = {'rejected', 'failed', 'declined', 'error'}
STATUS_CANCELLED = {'cancelled', 'canceled', 'voided', 'reversed', 'expired'}
STATUS_PENDING = {'pending', 'processing', 'created', 'in_progress', 'inprogress'}
