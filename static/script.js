document.addEventListener('DOMContentLoaded', () => {
    // --- Data Definition ---
    const semMapping = {
        '1st_year': [{ val: '1st_sem', label: '1st Semester' }, { val: '2nd_sem', label: '2nd Semester' }],
        '2nd_year': [{ val: '3rd_sem', label: '3rd Semester' }, { val: '4th_sem', label: '4th Semester' }],
        '3rd_year': [{ val: '5th_sem', label: '5th Semester' }, { val: '6th_sem', label: '6th Semester' }],
        '4th_year': [{ val: '7th_sem', label: '7th Semester' }, { val: '8th_sem', label: '8th Semester' }]
    };

    const branches = [
        { val: 'cse', label: 'CSE' },
        { val: 'cse_aiml', label: 'CSE (AI & ML)' },
        { val: 'cse_ds', label: 'CSE (Data Science)' },
        { val: 'cs', label: 'Computer Science' },
        { val: 'cse_hindi', label: 'CSE (Hindi)' },
        { val: 'aiml', label: 'AI & Machine Learning' },
        { val: 'it', label: 'Information Technology' },
        { val: 'csit', label: 'CS & IT' },
        { val: 'ece', label: 'ECE' },
        { val: 'me', label: 'Mechanical' },
        { val: 'eee', label: 'Electrical & Electronics' },
        { val: 'ce', label: 'Civil' }
    ];

    const typeMapping = [
        { val: 'st', label: 'ST Papers' },
        { val: 'put', label: 'PUT Papers' },
        { val: 'ut', label: 'UT Papers' },
        { val: 'notes', label: 'Faculty Notes' }
    ];

    // --- Upload Form Logic ---
    const yearSelect = document.getElementById('yearSelect');
    const branchGroup = document.getElementById('branchGroup');
    const branchSelect = document.getElementById('branchSelect');
    const semSelect = document.getElementById('semSelect');
    const fileInput = document.getElementById('fileInput');
    const fileMsg = document.querySelector('.file-msg');
    const dropArea = document.getElementById('fileDropArea');
    const uploadForm = document.getElementById('uploadForm');
    const uploadBtn = document.getElementById('uploadBtn');
    const statusMsg = document.getElementById('uploadStatus');

    yearSelect.addEventListener('change', (e) => {
        const year = e.target.value;
        const sems = semMapping[year];

        semSelect.innerHTML = '<option value="" disabled selected>Select Sem</option>';
        sems.forEach(sem => {
            semSelect.innerHTML += `<option value="${sem.val}">${sem.label}</option>`;
        });
        semSelect.disabled = false;

        // Show/hide branch dropdown
        if (year === '1st_year') {
            branchGroup.style.display = 'none';
            branchSelect.removeAttribute('required');
            branchSelect.value = '';
        } else {
            branchGroup.style.display = 'flex';
            branchSelect.setAttribute('required', 'true');
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            fileMsg.textContent = e.target.files[0].name;
            fileMsg.style.color = 'var(--text-primary)';
            dropArea.style.borderColor = 'var(--accent-secondary)';
        } else {
            fileMsg.textContent = 'Drag & Drop or Click to choose file';
            fileMsg.style.color = 'var(--text-secondary)';
            dropArea.style.borderColor = 'rgba(255,255,255,0.2)';
        }
    });

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => dropArea.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); }));
    ['dragenter', 'dragover'].forEach(evt => dropArea.addEventListener(evt, () => dropArea.classList.add('dragover')));
    ['dragleave', 'drop'].forEach(evt => dropArea.addEventListener(evt, () => dropArea.classList.remove('dragover')));

    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(uploadForm);

        uploadBtn.innerHTML = '<ion-icon name="sync-outline" class="spin"></ion-icon> <span>Uploading...</span>';
        uploadBtn.disabled = true;

        try {
            const response = await fetch('/upload', { method: 'POST', body: formData });
            const result = await response.json();

            if (response.ok) {
                statusMsg.textContent = 'Upload Successful! 🚀';
                statusMsg.className = 'status-msg success';
                uploadForm.reset();
                semSelect.innerHTML = '<option value="" disabled selected>Select Sem</option>';
                semSelect.disabled = true;
                branchGroup.style.display = 'none';
                branchSelect.removeAttribute('required');
                fileMsg.textContent = 'Drag & Drop or Click to choose file';
                fileMsg.style.color = 'var(--text-secondary)';
                dropArea.style.borderColor = 'rgba(255,255,255,0.2)';
            } else {
                statusMsg.textContent = result.error || 'Upload failed.';
                statusMsg.className = 'status-msg error';
            }
        } catch (error) {
            statusMsg.textContent = 'Connection error.';
            statusMsg.className = 'status-msg error';
        } finally {
            uploadBtn.innerHTML = '<span>Upload Now</span><ion-icon name="arrow-forward-outline"></ion-icon>';
            uploadBtn.disabled = false;
            setTimeout(() => { statusMsg.textContent = ''; }, 5000);
        }
    });

    // --- File Explorer Logic ---
    // Navigation path differs by year:
    // 1st year: [year, sem, type]
    // Others:   [year, branch, sem, type]
    let currentPath = [];
    const breadcrumb = document.getElementById('breadcrumb');
    const explorerView = document.getElementById('explorerView');

    const yearData = [
        { id: '1st_year', label: '1st Year' },
        { id: '2nd_year', label: '2nd Year' },
        { id: '3rd_year', label: '3rd Year' },
        { id: '4th_year', label: '4th Year' }
    ];

    function getLabel(id, list) {
        const item = list.find(i => i.id === id || i.val === id);
        return item ? (item.label || item.id) : id;
    }

    function renderBreadcrumbs() {
        let html = `<span class="crumb" data-level="0"><ion-icon name="home"></ion-icon> Home</span>`;
        const selectedYear = currentPath[0];
        const is1stYear = selectedYear === '1st_year';

        for (let i = 0; i < currentPath.length; i++) {
            let label = currentPath[i];
            if (i === 0) label = getLabel(currentPath[i], yearData);
            else if (!is1stYear && i === 1) label = getLabel(currentPath[i], branches);
            else {
                // semester or type
                const semIdx = is1stYear ? 1 : 2;
                const typeIdx = is1stYear ? 2 : 3;
                if (i === semIdx) label = getLabel(currentPath[i], semMapping[selectedYear]);
                if (i === typeIdx) label = getLabel(currentPath[i], typeMapping);
            }
            html += `<span class="crumb" data-level="${i + 1}">${label}</span>`;
        }

        breadcrumb.innerHTML = html;

        document.querySelectorAll('.crumb').forEach(crumb => {
            crumb.addEventListener('click', () => {
                const level = parseInt(crumb.getAttribute('data-level'));
                if (level < currentPath.length) {
                    currentPath = currentPath.slice(0, level);
                    renderExplorer();
                }
            });
        });

        const crumbs = document.querySelectorAll('.crumb');
        if (crumbs.length > 0) crumbs[crumbs.length - 1].classList.add('active');
    }

    function renderExplorer() {
        renderBreadcrumbs();
        explorerView.innerHTML = '';
        const depth = currentPath.length;
        const selectedYear = currentPath[0];
        const is1stYear = selectedYear === '1st_year';

        if (depth === 0) {
            // Show Years
            yearData.forEach(year => {
                explorerView.innerHTML += folderHTML(year.id, year.label, 'folder');
            });
            attachFolderListeners();
        }
        else if (depth === 1 && !is1stYear) {
            // Show Branches with relevant icons & colors
            const branchIcons = {
                'cse': { icon: 'laptop-outline', color: '#58a6ff' },
                'cse_aiml': { icon: 'sparkles-outline', color: '#ff7b72' },
                'cse_ds': { icon: 'analytics-outline', color: '#79c0ff' },
                'cs': { icon: 'desktop-outline', color: '#d2a8ff' },
                'cse_hindi': { icon: 'language-outline', color: '#f0883e' },
                'aiml': { icon: 'bulb-outline', color: '#e3b341' },
                'it': { icon: 'globe-outline', color: '#3fb950' },
                'csit': { icon: 'code-slash-outline', color: '#a5d6ff' },
                'ece': { icon: 'radio-outline', color: '#f0883e' },
                'me': { icon: 'cog-outline', color: '#8b949e' },
                'eee': { icon: 'flash-outline', color: '#e3b341' },
                'ce': { icon: 'business-outline', color: '#d2a8ff' }
            };
            branches.forEach(b => {
                const bi = branchIcons[b.val] || { icon: 'folder', color: '#e3b341' };
                explorerView.innerHTML += folderHTML(b.val, b.label, bi.icon, bi.color);
            });
            attachFolderListeners();
        }
        else if ((depth === 1 && is1stYear) || (depth === 2 && !is1stYear)) {
            // Show Semesters
            const sems = semMapping[selectedYear];
            sems.forEach(sem => {
                explorerView.innerHTML += folderHTML(sem.val, sem.label, 'folder');
            });
            attachFolderListeners();
        }
        else if ((depth === 2 && is1stYear) || (depth === 3 && !is1stYear)) {
            // Show Types
            typeMapping.forEach(type => {
                let iconName = 'book';
                if (type.val === 'notes') iconName = 'journal';
                if (type.val === 'put') iconName = 'school';
                if (type.val === 'st') iconName = 'document-text';
                if (type.val === 'ut') iconName = 'create';
                explorerView.innerHTML += folderHTML(type.val, type.label, iconName, '#58a6ff');
            });
            attachFolderListeners();
        }
        else {
            // Show Files from API
            fetchFiles();
        }
    }

    function folderHTML(id, label, iconName, iconColor) {
        const style = iconColor ? `style="color:${iconColor};"` : '';
        return `
            <div class="folder-item" data-id="${id}">
                <ion-icon name="${iconName}" class="item-icon" ${style}></ion-icon>
                <span class="item-name">${label}</span>
            </div>
        `;
    }

    function attachFolderListeners() {
        document.querySelectorAll('.folder-item').forEach(item => {
            item.addEventListener('click', () => {
                currentPath.push(item.getAttribute('data-id'));
                renderExplorer();
            });
        });
    }

    async function fetchFiles() {
        explorerView.innerHTML = `<div class="empty-state"><ion-icon name="hourglass-outline" class="spin"></ion-icon>Loading files...</div>`;
        const selectedYear = currentPath[0];
        const is1stYear = selectedYear === '1st_year';

        let year, branch, sem, type, downloadBase;

        if (is1stYear) {
            [year, sem, type] = currentPath;
            branch = '';
            downloadBase = `${year}/${sem}/${type}`;
        } else {
            [year, branch, sem, type] = currentPath;
            downloadBase = `${year}/${branch}/${sem}/${type}`;
        }

        try {
            const params = new URLSearchParams({ year, semester: sem, type });
            if (branch) params.append('branch', branch);
            const res = await fetch(`/api/files?${params}`);
            const files = await res.json();

            explorerView.innerHTML = '';
            if (!files || files.length === 0) {
                explorerView.innerHTML = `
                    <div class="empty-state">
                        <ion-icon name="document-text-outline"></ion-icon>
                        <p>No papers found in this folder yet.</p>
                    </div>`;
                return;
            }

            files.forEach(file => {
                const ext = file.split('.').pop().toLowerCase();
                let iconName = 'document-text';
                let iconClass = 'item-icon';
                if (['png', 'jpg', 'jpeg', 'webp'].includes(ext)) {
                    iconName = 'image';
                    iconClass += ' image-icon';
                }
                explorerView.innerHTML += `
                    <a href="/uploads/${downloadBase}/${file}" target="_blank" class="file-item">
                        <ion-icon name="${iconName}" class="${iconClass}"></ion-icon>
                        <span class="item-name" title="${file}">${file}</span>
                    </a>
                `;
            });
        } catch (e) {
            explorerView.innerHTML = `<div class="empty-state"><ion-icon name="alert-circle-outline" style="color:#f85149;"></ion-icon><p>Error loading files.</p></div>`;
        }
    }

    // Init
    renderExplorer();

    // --- Interactive Background (Particles) ---
    const canvas = document.getElementById('bgCanvas');
    if (canvas) {
        const ctx = canvas.getContext('2d');
        let w, h;
        const particles = [];
        const mouse = { x: undefined, y: undefined, radius: 150 };

        window.addEventListener('mousemove', (e) => {
            mouse.x = e.x;
            mouse.y = e.y;
        });

        window.addEventListener('mouseout', () => {
            mouse.x = undefined;
            mouse.y = undefined;
        });

        function initCanvas() {
            w = canvas.width = window.innerWidth;
            h = canvas.height = window.innerHeight;
        }

        class Particle {
            constructor() {
                this.x = Math.random() * w;
                this.y = Math.random() * h;
                this.size = Math.random() * 2 + 1;
                this.baseX = this.x;
                this.baseY = this.y;
                this.density = (Math.random() * 30) + 1;
                this.color = `rgba(${Math.random() > 0.5 ? '121, 40, 202' : '255, 0, 128'}, 0.8)`;
            }

            draw() {
                ctx.fillStyle = this.color;
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
                ctx.closePath();
                ctx.fill();
            }

            update() {
                if (mouse.x != null) {
                    let dx = mouse.x - this.x;
                    let dy = mouse.y - this.y;
                    let distance = Math.sqrt(dx * dx + dy * dy);
                    let forceDirectionX = dx / distance;
                    let forceDirectionY = dy / distance;
                    let force = (mouse.radius - distance) / mouse.radius;

                    if (distance < mouse.radius) {
                        this.x -= forceDirectionX * force * this.density;
                        this.y -= forceDirectionY * force * this.density;
                    } else {
                        if (this.x !== this.baseX) this.x -= (this.x - this.baseX) / 10;
                        if (this.y !== this.baseY) this.y -= (this.y - this.baseY) / 10;
                    }
                } else {
                    if (this.x !== this.baseX) this.x -= (this.x - this.baseX) / 10;
                    if (this.y !== this.baseY) this.y -= (this.y - this.baseY) / 10;
                }
            }
        }

        function initParticles() {
            particles.length = 0;
            let numParticles = (w * h) / 7000;
            for (let i = 0; i < numParticles; i++) {
                particles.push(new Particle());
            }
        }

        function animate() {
            ctx.clearRect(0, 0, w, h);
            for (let i = 0; i < particles.length; i++) {
                particles[i].update();
                particles[i].draw();

                for (let j = i; j < particles.length; j++) {
                    let dx = particles[i].x - particles[j].x;
                    let dy = particles[i].y - particles[j].y;
                    let dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist < 100) {
                        ctx.beginPath();
                        ctx.strokeStyle = `rgba(121, 40, 202, ${0.8 - dist / 100})`;
                        ctx.lineWidth = 0.5;
                        ctx.moveTo(particles[i].x, particles[i].y);
                        ctx.lineTo(particles[j].x, particles[j].y);
                        ctx.stroke();
                        ctx.closePath();
                    }
                }
            }
            requestAnimationFrame(animate);
        }

        window.addEventListener('resize', () => {
            initCanvas();
            initParticles();
        });

        initCanvas();
        initParticles();
        animate();
    }
});
