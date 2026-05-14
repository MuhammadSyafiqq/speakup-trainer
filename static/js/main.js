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
