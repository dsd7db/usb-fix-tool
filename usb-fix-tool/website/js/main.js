// Tiny helper to mark the active nav link based on the current path.
(function () {
    const path = window.location.pathname.split('/').pop() || 'index.html';
    document.querySelectorAll('.nav-links a').forEach(a => {
        const href = a.getAttribute('href');
        if (!href) return;
        const target = href.split('/').pop();
        if (target === path || (path === '' && target === 'index.html')) {
            a.classList.add('active');
        }
    });
})();
