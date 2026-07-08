/** @odoo-module **/

import paymentPostProcessing from '@payment/js/post_processing';

paymentPostProcessing.include({
    /**
     * Cobro contra entrega transactions remain pending until the customer pays on delivery.
     * Treat 'pending' as a final frontend state so the checkout can redirect to the status page.
     *
     * @override method from `@payment/js/post_processing`
     * @param {string} providerCode - The code of the provider handling the transaction.
     */
    _getFinalStates(providerCode) {
        const finalStates = this._super(...arguments);
        if (providerCode === 'cleo_cod') {
            finalStates.add('pending');
        }
        return finalStates;
    }
});
