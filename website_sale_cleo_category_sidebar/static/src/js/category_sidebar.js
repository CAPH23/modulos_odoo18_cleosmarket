/** @odoo-module **/

(function () {
    'use strict';

    const STORAGE_KEY = 'cleo_shop_category_sidebar_collapsed_v4';

    function initSidebar(sidebar) {
        if (!sidebar || sidebar.dataset.cleoSidebarReady === '1') {
            return;
        }
        sidebar.dataset.cleoSidebarReady = '1';

        const toggle = sidebar.querySelector('[data-cleo-category-toggle]');
        if (!toggle) {
            return;
        }

        const setCollapsed = function (collapsed) {
            sidebar.classList.toggle('is-collapsed', collapsed);
            toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
            try {
                window.localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0');
            } catch (error) {}
        };

        try {
            setCollapsed(window.localStorage.getItem(STORAGE_KEY) === '1');
        } catch (error) {
            setCollapsed(false);
        }

        toggle.addEventListener('click', function () {
            setCollapsed(!sidebar.classList.contains('is-collapsed'));
        });
    }

    function boot() {
        document.querySelectorAll('[data-cleo-category-sidebar]').forEach(initSidebar);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
