// Clean AKGEC Background - Subtle gold particles, attract to cursor
(function () {
    const canvas = document.getElementById('bgCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let w, h;
    const mouse = { x: null, y: null, radius: 200 };
    const particles = [];

    function resize() { w = canvas.width = window.innerWidth; h = canvas.height = window.innerHeight; }
    window.addEventListener('resize', () => { resize(); initParticles(); });
    resize();

    window.addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });
    window.addEventListener('mouseout', () => { mouse.x = null; mouse.y = null; });

    class Particle {
        constructor() {
            this.x = Math.random() * w;
            this.y = Math.random() * h;
            this.baseX = this.x;
            this.baseY = this.y;
            this.size = Math.random() * 1.8 + 0.5;
            this.speed = Math.random() * 1.5 + 0.5;
            // Clean single gold tone
            const alpha = Math.random() * 0.4 + 0.3;
            this.color = `rgba(212, 175, 55, ${alpha})`;
            this.glowColor = `rgba(212, 175, 55, 0.03)`;
            this.angle = Math.random() * Math.PI * 2;
            this.angleSpeed = (Math.random() - 0.5) * 0.003;
            this.floatRadius = Math.random() * 12 + 3;
        }
        update() {
            this.angle += this.angleSpeed;
            let floatX = this.baseX + Math.cos(this.angle) * this.floatRadius;
            let floatY = this.baseY + Math.sin(this.angle) * this.floatRadius;

            if (mouse.x != null) {
                let dx = mouse.x - this.x, dy = mouse.y - this.y;
                let dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < mouse.radius) {
                    let force = (mouse.radius - dist) / mouse.radius;
                    this.x += (dx / dist) * force * this.speed * 1.2;
                    this.y += (dy / dist) * force * this.speed * 1.2;
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
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size * 3, 0, Math.PI * 2);
            ctx.fillStyle = this.glowColor;
            ctx.fill();
        }
    }

    function initParticles() {
        particles.length = 0;
        let count = Math.min(Math.floor((w * h) / 6000), 300);
        for (let i = 0; i < count; i++) particles.push(new Particle());
    }

    function drawCursorGlow() {
        if (mouse.x == null) return;
        const grad = ctx.createRadialGradient(mouse.x, mouse.y, 0, mouse.x, mouse.y, 160);
        grad.addColorStop(0, 'rgba(212, 175, 55, 0.08)');
        grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(mouse.x, mouse.y, 160, 0, Math.PI * 2);
        ctx.fill();
    }

    function drawConnections() {
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                let dx = particles[i].x - particles[j].x, dy = particles[i].y - particles[j].y;
                let dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 100) {
                    ctx.beginPath();
                    ctx.strokeStyle = `rgba(212, 175, 55, ${(1 - dist / 100) * 0.15})`;
                    ctx.lineWidth = 0.4;
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.stroke();
                }
            }
        }
    }

    function animate() {
        ctx.clearRect(0, 0, w, h);
        drawCursorGlow();
        particles.forEach(p => { p.update(); p.draw(); });
        drawConnections();
        requestAnimationFrame(animate);
    }

    initParticles();
    animate();
})();
