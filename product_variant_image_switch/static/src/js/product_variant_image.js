odoo.define('product_variant_image_switch.product_variant_image', function (require) {
  'use strict';

  const publicWidget = require('web.public.widget');

  publicWidget.registry.ProductVariantImage = publicWidget.Widget.extend({
    selector: '.product_detail',
    events: {
      'change select[name="product_id"]': '_onVariantChange',
    },

    start: function () {
      const $script = document.getElementById('variant_images_json');
      this.variantImages = $script ? JSON.parse($script.textContent) : {};
      return this._super.apply(this, arguments);
    },

    _onVariantChange: function (ev) {
      const variantId = ev.target.value;
      const newImage = this.variantImages[variantId];
      if (newImage) {
        const $img = document.querySelector('.carousel .carousel-item.active img');
        if ($img) {
          $img.src = 'data:image/png;base64,' + newImage;
        }
      }
    },
  });
});
