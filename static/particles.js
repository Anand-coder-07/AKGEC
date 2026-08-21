// Clean AKGEC Background - High Performance Subtle Gold Particles
(function () {
    const canvas = document.getElementById('bgCanvas');
    if (!canvas) return;

    // Check user preference for reduced motion
    const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) return;

    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) return;

    let w = 0, h = 0;
    const mouse = { x: null, y: null, radius: 180, radiusSq: 32400 };
    const particles = [];
    let animationId = null;
    let resizeTimeout = null;

    function resize() {
        w = canvas.width = window.innerWidth;
        h = canvas.height = window.innerHeight;
    }

    function onResize() {
        if (resizeTimeout) cancelAnimationFrame(resizeTimeout);
        resizeTimeout = requestAnimationFrame(() => {
            resize();
            initParticles();
        });
    }

    window.addEventListener('resize', onResize, { passive: true });
    resize();

    window.addEventListener('mousemove', e => {
        mouse.x = e.clientX;
        mouse.y = e.clientY;
    }, { passive: true });

    window.addEventListener('mouseout', () => {
        mouse.x = null;
        mouse.y = null;
    }, { passive: true });

    class Particle {
        constructor() {
            this.reset(true);
        }

        reset(initial = false) {
            this.x = initial ? Math.random() * w : (Math.random() > 0.5 ? Math.random() * w : (Math.random() > 0.5 ? 0 : w));
            this.y = initial ? Math.random() * h : Math.random() * h;
            this.baseX = this.x;
            this.baseY = this.y;
            this.size = Math.random() * 1.6 + 0.6;
            this.speed = Math.random() * 1.2 + 0.4;
            const alpha = (Math.random() * 0.35 + 0.25).toFixed(2);
            this.color = `rgba(212, 175, 55, ${alpha})`;
            this.angle = Math.random() * Math.PI * 2;
            this.angleSpeed = (Math.random() - 0.5) * 0.002;
            this.floatRadius = Math.random() * 10 + 3;
        }

        update() {
            this.angle += this.angleSpeed;
            const floatX = this.baseX + Math.cos(this.angle) * this.floatRadius;
            const floatY = this.baseY + Math.sin(this.angle) * this.floatRadius;

            if (mouse.x !== null) {
                const dx = mouse.x - this.x;
                const dy = mouse.y - this.y;
                const distSq = dx * dx + dy * dy;

                if (distSq < mouse.radiusSq && distSq > 0.01) {
                    const dist = Math.sqrt(distSq);
                    const force = (mouse.radius - dist) / mouse.radius;
                    this.x += (dx / dist) * force * this.speed * 1.1;
                    this.y += (dy / dist) * force * this.speed * 1.1;
                } else {
                    this.x += (floatX - this.x) * 0.03;
                    this.y += (floatY - this.y) * 0.03;
                }
            } else {
                this.x += (floatX - this.x) * 0.03;
                this.y += (floatY - this.y) * 0.03;
            }
        }

        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fillStyle = this.color;
            ctx.fill();
        }
    }

    function initParticles() {
        particles.length = 0;
        // Moderate particle density: max 120 on desktop, 50 on mobile
        const isMobile = w < 768;
        const maxParticles = isMobile ? 50 : 120;
        const calculated = Math.floor((w * h) / 14000);
        const count = Math.min(Math.max(calculated, 30), maxParticles);

        for (let i = 0; i < count; i++) {
            particles.push(new Particle());
        }
    }

    function drawCursorGlow() {
        if (mouse.x === null) return;
        const grad = ctx.createRadialGradient(mouse.x, mouse.y, 0, mouse.x, mouse.y, 140);
        grad.addColorStop(0, 'rgba(212, 175, 55, 0.07)');
        grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(mouse.x, mouse.y, 140, 0, Math.PI * 2);
        ctx.fill();
    }

    function drawConnections() {
        const len = particles.length;
        const maxDistSq = 9000; // 95 * 95

        ctx.lineWidth = 0.4;
        for (let i = 0; i < len; i++) {
            const p1 = particles[i];
            for (let j = i + 1; j < len; j++) {
                const p2 = particles[j];
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const distSq = dx * dx + dy * dy;

                if (distSq < maxDistSq) {
                    const dist = Math.sqrt(distSq);
                    const opacity = ((1 - dist / 95) * 0.14).toFixed(3);
                    ctx.strokeStyle = `rgba(212, 175, 55, ${opacity})`;
                    ctx.beginPath();
                    ctx.moveTo(p1.x, p1.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.stroke();
                }
            }
        }
    }

    function animate() {
        ctx.clearRect(0, 0, w, h);
        drawCursorGlow();

        const len = particles.length;
        for (let i = 0; i < len; i++) {
            particles[i].update();
            particles[i].draw();
        }

        drawConnections();
        animationId = requestAnimationFrame(animate);
    }

    initParticles();
    animate();

    // Pause animation when tab is not visible to save battery/CPU
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            if (animationId) cancelAnimationFrame(animationId);
        } else {
            animate();
        }
    });
})();
