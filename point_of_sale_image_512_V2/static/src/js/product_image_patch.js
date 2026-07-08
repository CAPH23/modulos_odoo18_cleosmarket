/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductProduct } from "@point_of_sale/app/models/product_product";

patch(ProductProduct.prototype, {
    getImageUrl() {
        if (this.image_512) {
            return `/web/image?model=product.product&field=image_512&id=${this.id}&unique=${this.write_date}`;
        } else if (this.image_256) {
            return `/web/image?model=product.product&field=image_256&id=${this.id}&unique=${this.write_date}`;
        } else if (this.image_128) {
            return `/web/image?model=product.product&field=image_128&id=${this.id}&unique=${this.write_date}`;
        }
        return "";
    },
/**    getTemplateImageUrl() {
        const url = this.image_512
        ? `/web/image?model=product.template&field=image_512&id=${this.raw.product_tmpl_id}&unique=${this.write_date}`
        : `/web/image?model=product.template&field=image_128&id=${this.raw.product_tmpl_id}&unique=${this.write_date}`;
        console.log("getTemplateImageUrl está usando:",this.image_512);  //  aquí va la variable
        if (this.image_512) {
            return `/web/image?model=product.template&field=image_512&id=${this.raw.product_tmpl_id}&unique=${this.write_date}`;
        } else if (this.image_256) {
            return `/web/image?model=product.template&field=image_256&id=${this.raw.product_tmpl_id}&unique=${this.write_date}`;
        } else if (this.image_128) {
            return `/web/image?model=product.template&field=image_128&id=${this.raw.product_tmpl_id}&unique=${this.write_date}`;
        }
        return "";
    },**/
    getTemplateImageUrl() {
        const url = `/web/image?model=product.template&field=image_512&id=${this.raw.product_tmpl_id}&unique=${this.write_date}`;
        return url;
    },
});
