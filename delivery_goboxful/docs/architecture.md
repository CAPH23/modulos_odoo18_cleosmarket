# Arquitectura

```text
sale.order
  └─ delivery.carrier (goboxful)
       ├─ goboxful.account (por compañía)
       ├─ goboxful.courier (clasificación mismo día / entrega programada, por transportista)
       └─ /courier/available -> lista de couriers; el cliente elige uno en el checkout

stock.picking
  ├─ opciones de courier
  ├─ botón Crear envío Boxful
  ├─ /shipment
  ├─ etiqueta ir.attachment
  └─ estado webhook / cron

portal /my/orders
  └─ endpoint JSON protegido por acceso estándar del portal
```

El estado comercial estándar de `sale.order` no se reemplaza. Los cambios de Boxful se almacenan como estado logístico para no alterar facturación, pagos ni movimientos de inventario.
