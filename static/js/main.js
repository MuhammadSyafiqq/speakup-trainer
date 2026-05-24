// ============================================
// SPEAKUP - MAIN JAVASCRIPT
// ============================================

// Auto-close flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        document.querySelectorAll('.flash').forEach(el => {
            el.style.opacity = '0';
            el.style.transition = 'opacity 0.5s';
            setTimeout(() => el.remove(), 500);
        });
    }, 5000);

    // Animate aspect bars on result page
    animateAspectBars();
});

function animateAspectBars() {
    const fills = document.querySelectorAll('.aspect-fill');
    fills.forEach(el => {
        const target = el.style.width;
        el.style.width = '0';
        setTimeout(() => { el.style.width = target; }, 200);
    });
}

// ============================================
// MOBILE HAMBURGER MENU
// ============================================
(function () {
    function initHamburger() {
        const hamburger  = document.getElementById('hamburger-btn');
        const mobileNav  = document.getElementById('mobile-nav');
        const overlay    = document.getElementById('nav-overlay');
        const closeBtn   = document.getElementById('mobile-nav-close');

        if (!hamburger || !mobileNav || !overlay) return;

        function openMenu() {
            hamburger.classList.add('open');
            hamburger.setAttribute('aria-expanded', 'true');
            mobileNav.classList.add('open');
            overlay.classList.add('active');
            document.body.style.overflow = 'hidden';
        }

        function closeMenu() {
            hamburger.classList.remove('open');
            hamburger.setAttribute('aria-expanded', 'false');
            mobileNav.classList.remove('open');
            overlay.classList.remove('active');
            document.body.style.overflow = '';
        }

        function toggleMenu() {
            hamburger.classList.contains('open') ? closeMenu() : openMenu();
        }

        hamburger.addEventListener('click', toggleMenu);
        overlay.addEventListener('click', closeMenu);
        if (closeBtn) closeBtn.addEventListener('click', closeMenu);

        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeMenu();
        });

        // Close if window resizes to desktop
        window.addEventListener('resize', () => {
            if (window.innerWidth > 768) closeMenu();
        });

        // Close when a nav link is tapped
        mobileNav.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                // Small delay so route change feels intentional
                setTimeout(closeMenu, 80);
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initHamburger);
    } else {
        initHamburger();
    }
})();