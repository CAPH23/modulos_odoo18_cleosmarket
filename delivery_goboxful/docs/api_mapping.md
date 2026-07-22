# Mapeo API ↔ Odoo

| Boxful | Uso en Odoo |
|---|---|
| `POST /auth/v2/client` | Inicio de sesión de `goboxful.account` |
| `POST /auth/v2/refresh` | Renovación automática |
| `GET /auth/v2/me` | Probar conexión y obtener `clientId` |
| `GET /states` | Sincronizar `goboxful.state` y `goboxful.city` |
| `POST/PATCH /addresses` | Dirección única de recolección por compañía |
| `POST /quoter` | Identificar couriers `same-day` |
| `POST /courier/available` | Validar paquete, cobertura y tarifa real |
| `POST /shipment` | Crear guía manualmente desde `stock.picking` |
| `GET /shipment/{id}` | Sincronizar estado y enlaces |
| `GET /tracking/{number}` | Disponible para ampliaciones del tracking |
| `POST /client-webhook` | Registrar URL y secreto |
