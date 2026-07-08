Changelog
=========

18.0.1.0.0
----------

* Primera versión: encabezado personalizado.

18.0.1.1.0
----------

* Se agrega el hero principal de la página Home.
* Se mantiene el rediseño del encabezado.
* Se corrige el SCSS del buscador usando ``width: 330px`` y ``max-width: 32vw`` para evitar errores de unidades incompatibles.

18.0.1.6.0
----------

* Reescritura completa de la página "Sobre Nosotros" (plantilla y estilos).
* La maquetación ahora usa el grid de Bootstrap 5 de Odoo: se eliminan las
  columnas con anchos mínimos fijos (``minmax(420px/620px)``) que provocaban
  desbordamiento horizontal y el recorte del contenido.
* Encabezados centrados con subrayado amarillo, acentos manuscritos con la
  fuente Caveat (con respaldo Georgia), conectores punteados en la línea de
  tiempo y en los pasos de compra, e insignias con icono circular, fieles al
  diseño de referencia.
* Se agrega el logotipo de Super Tienda Cleo al hero de la página.
* Decoraciones laterales de productos reposicionadas y visibles solo en
  pantallas anchas (≥1400px) para no interferir con el contenido.
* Limpieza: se eliminan los respaldos ``mi_modulo.scss.save*`` generados por nano.

18.0.1.7.0
----------

* La plantilla de "Sobre Nosotros" se renombra a ``cleosmarket_about_page_v8``
  y el controlador apunta a ella. Esto deja sin efecto la copia interna
  (copy-on-write) que el constructor web de Odoo creó al editar la página y
  que impedía ver las actualizaciones del módulo (causa raíz del problema).
* La maquetación ya NO depende de Bootstrap: se incorpora una rejilla propia
  con CSS Grid (columnas ``minmax(0, 1fr)``, imposible de desbordar) con
  breakpoints para celular, tablet y laptop.
* Nuevas ilustraciones propias en estilo flat (SVG vectorial, ligeras y
  nítidas en cualquier resolución) dentro de ``static/src/img/about/``:
  familia con carrito, persona sembrando y 4 tiras decorativas de alimentos.
  Se eliminan las imágenes PNG anteriores de esa carpeta.
* Se omite el logotipo de Super Tienda Cleo en la página, según lo solicitado.
* Vista previa local ``preview_sobre_nosotros.html`` regenerada y verificada
  en 1440px (laptop), 820px (tablet) y 390px (celular).
