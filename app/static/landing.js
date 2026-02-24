// AI Social — Landing page logic

// ── Particle Network Background ────────────────
function initNetworkBg() {
    const canvas = document.getElementById('net-bg');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    let w, h;
    const particles = [];
    const COUNT = 70;
    const LINK_DIST = 180;

    function resize() {
        w = canvas.width = window.innerWidth;
        h = canvas.height = window.innerHeight;
    }

    function createParticles() {
        particles.length = 0;
        for (let i = 0; i < COUNT; i++) {
            particles.push({
                x: Math.random() * w,
                y: Math.random() * h,
                vx: (Math.random() - 0.5) * 0.25,
                vy: (Math.random() - 0.5) * 0.25,
                r: Math.random() * 1.8 + 0.6,
            });
        }
    }

    function draw() {
        ctx.clearRect(0, 0, w, h);

        // Draw links
        for (let i = 0; i < COUNT; i++) {
            for (let j = i + 1; j < COUNT; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < LINK_DIST) {
                    const alpha = 0.12 * (1 - dist / LINK_DIST);
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(59,207,182,${alpha})`;
                    ctx.lineWidth = 1;
                    ctx.stroke();
                }
            }
        }

        // Draw particles
        for (const p of particles) {
            p.x += p.vx;
            p.y += p.vy;
            if (p.x < 0) p.x = w;
            if (p.x > w) p.x = 0;
            if (p.y < 0) p.y = h;
            if (p.y > h) p.y = 0;

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(59,207,182,0.45)';
            ctx.fill();
        }

        requestAnimationFrame(draw);
    }

    resize();
    createParticles();
    draw();

    window.addEventListener('resize', () => {
        resize();
        // Keep existing particles, they'll naturally redistribute
    });
}

// ── Handle Input + Glow Logic ──────────────────
const handleInput = document.getElementById('handle-input');
const handleStatus = document.getElementById('handle-status');
const continueBtn = document.getElementById('continue-btn');
const handleGroup = document.getElementById('handle-group');

let checkTimeout = null;
let currentHandle = '';

function setGlow(type) {
    if (!handleGroup) return;
    handleGroup.classList.remove('glow-focus', 'glow-available', 'glow-taken');
    if (type) handleGroup.classList.add(type);
}

// If already logged in, redirect to app
(async function checkAuth() {
    const token = getToken();
    if (!token) return;
    try {
        const resp = await fetch(`${API}/auth/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (resp.ok) {
            window.location.href = '/app';
        }
    } catch {}
})();

handleInput.addEventListener('focus', () => {
    if (!handleGroup.classList.contains('glow-available') && !handleGroup.classList.contains('glow-taken')) {
        setGlow('glow-focus');
    }
});

handleInput.addEventListener('blur', () => {
    if (handleGroup.classList.contains('glow-focus')) {
        setGlow(null);
    }
});

handleInput.addEventListener('input', () => {
    const raw = handleInput.value.replace(/[^a-zA-Z0-9_]/g, '');
    handleInput.value = raw;
    currentHandle = raw.toLowerCase();

    continueBtn.disabled = true;
    handleStatus.textContent = '';
    handleStatus.className = 'text-sm h-5 mt-3 transition-opacity duration-300';
    setGlow('glow-focus');

    if (checkTimeout) clearTimeout(checkTimeout);

    if (raw.length < 3) {
        if (raw.length > 0) {
            handleStatus.textContent = 'At least 3 characters';
            handleStatus.className = 'text-sm h-5 mt-3 transition-opacity duration-300 text-yellow-400';
        }
        return;
    }

    if (!/^[a-zA-Z]/.test(raw)) {
        handleStatus.textContent = 'Must start with a letter';
        handleStatus.className = 'text-sm h-5 mt-3 transition-opacity duration-300 text-red-400';
        setGlow('glow-taken');
        return;
    }

    handleStatus.textContent = 'Checking...';
    handleStatus.className = 'text-sm h-5 mt-3 transition-opacity duration-300 text-muted';

    checkTimeout = setTimeout(async () => {
        try {
            const resp = await fetch(`${API}/auth/check-handle`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ handle: currentHandle }),
            });
            const data = await resp.json();
            if (handleInput.value.toLowerCase() !== currentHandle) return; // stale

            if (data.available) {
                handleStatus.textContent = 'Available!';
                handleStatus.className = 'text-sm h-5 mt-3 transition-opacity duration-300 text-green-400';
                continueBtn.disabled = false;
                setGlow('glow-available');
            } else {
                handleStatus.textContent = data.reason || 'Already taken';
                handleStatus.className = 'text-sm h-5 mt-3 transition-opacity duration-300 text-red-400';
                continueBtn.disabled = true;
                setGlow('glow-taken');
            }
        } catch {
            handleStatus.textContent = 'Could not check availability';
            handleStatus.className = 'text-sm h-5 mt-3 transition-opacity duration-300 text-red-400';
            setGlow('glow-taken');
        }
    }, 400);
});

continueBtn.addEventListener('click', () => {
    if (!currentHandle || continueBtn.disabled) return;
    window.location.href = `/auth?handle=${encodeURIComponent(currentHandle)}`;
});

// Allow pressing Enter
handleInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !continueBtn.disabled) {
        continueBtn.click();
    }
});

handleInput.focus();

// ── Init ────────────────────────────────────────
initNetworkBg();
