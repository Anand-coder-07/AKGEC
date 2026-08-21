document.addEventListener('DOMContentLoaded', () => {
    let adminKey = '';
    let activeSection = null;
    let activeYear = '1st_year';

    const yearLabels = {
        '1st_year': '1st Year',
        '2nd_year': '2nd Year',
        '3rd_year': '3rd Year',
        '4th_year': '4th Year'
    };

    // --- Elements ---
    const authGate       = document.getElementById('authGate');
    const authKeyInput   = document.getElementById('authKeyInput');
    const authBtn        = document.getElementById('authBtn');
    const authStatus     = document.getElementById('authStatus');
    const mainPanel      = document.getElementById('mainPanel');

    const yearTabs       = document.getElementById('yearTabs');
    const newSectionName = document.getElementById('newSectionName');
    const createSectionBtn = document.getElementById('createSectionBtn');
    const createStatus   = document.getElementById('createStatus');
    const sectionsGrid   = document.getElementById('sectionsGrid');

    const filesPanel     = document.getElementById('filesPanel');
    const activeSectionLabel = document.getElementById('activeSectionLabel');
    const filesListContainer = document.getElementById('filesListContainer');
    const openUploadModalBtn = document.getElementById('openUploadModalBtn');

    const uploadModal    = document.getElementById('uploadModal');
    const closeModalBtn  = document.getElementById('closeModalBtn');
    const modalSectionName = document.getElementById('modalSectionName');
    const uploadFileForm = document.getElementById('uploadFileForm');
    const fileDisplayName = document.getElementById('fileDisplayName');
    const modalFileInput = document.getElementById('modalFileInput');
    const modalFileMsg   = document.getElementById('modalFileMsg');
    const modalDropArea  = document.getElementById('modalDropArea');
    const modalUploadBtn = document.getElementById('modalUploadBtn');
    const modalStatus    = document.getElementById('modalStatus');

    function escHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function showStatus(el, msg, type) {
        if (!el) return;
        el.textContent = msg;
        el.className = `status-msg ${type}`;
        setTimeout(() => {
            if (el.textContent === msg) {
                el.textContent = '';
                el.className = 'status-msg';
            }
        }, 4000);
    }

    // --- Auth Verification ---
    authBtn.addEventListener('click', async () => {
        const key = authKeyInput.value.trim();
        if (!key) {
            showStatus(authStatus, 'Please enter admin passcode.', 'error');
            return;
        }
        authBtn.disabled = true;
        authBtn.innerHTML = '<ion-icon name="sync-outline" class="spin"></ion-icon> <span>Verifying...</span>';

        try {
            const res = await fetch('/api/fn/verify', {
                method: 'POST',
                headers: { 'X-Admin-Key': key }
            });
            if (res.status === 401) {
                showStatus(authStatus, 'Invalid passcode.', 'error');
                return;
            }
            if (!res.ok) {
                showStatus(authStatus, 'Verification error.', 'error');
                return;
            }
            adminKey = key;
            authGate.style.display = 'none';
            mainPanel.style.display = 'block';
            renderYearTabs();
            loadSections();
        } catch (e) {
            showStatus(authStatus, 'Connection error.', 'error');
        } finally {
            authBtn.disabled = false;
            authBtn.innerHTML = '<span>Unlock</span><ion-icon name="arrow-forward-outline"></ion-icon>';
        }
    });

    authKeyInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') authBtn.click();
    });

    // --- Year Tabs ---
    function renderYearTabs() {
        yearTabs.innerHTML = '';
        Object.entries(yearLabels).forEach(([key, label]) => {
            const tab = document.createElement('button');
            tab.className = `year-tab ${key === activeYear ? 'active' : ''}`;
            tab.textContent = label;
            tab.dataset.year = key;
            tab.addEventListener('click', () => {
                activeYear = key;
                activeSection = null;
                filesPanel.style.display = 'none';
                renderYearTabs();
                loadSections();
            });
            yearTabs.appendChild(tab);
        });
    }

    // --- Create Section ---
    createSectionBtn.addEventListener('click', async () => {
        const name = newSectionName.value.trim();
        if (!name) {
            showStatus(createStatus, 'Enter a section name.', 'error');
            return;
        }
        createSectionBtn.disabled = true;

        try {
            const res = await fetch('/api/fn/sections', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Admin-Key': adminKey
                },
                body: JSON.stringify({ name, year: activeYear })
            });
            const data = await res.json();
            if (!res.ok) {
                showStatus(createStatus, data.error || 'Failed to create section.', 'error');
                return;
            }
            showStatus(createStatus, `Section "${name}" created in ${yearLabels[activeYear]}!`, 'success');
            newSectionName.value = '';
            loadSections();
        } catch (e) {
            showStatus(createStatus, 'Connection error.', 'error');
        } finally {
            createSectionBtn.disabled = false;
        }
    });

    newSectionName.addEventListener('keydown', e => {
        if (e.key === 'Enter') createSectionBtn.click();
    });

    // --- Load Sections ---
    async function loadSections() {
        sectionsGrid.innerHTML = `<div class="empty-state" style="grid-column:1/-1;"><ion-icon name="hourglass-outline" class="spin"></ion-icon><p>Loading sections...</p></div>`;
        try {
            const res = await fetch(`/api/fn/sections?year=${encodeURIComponent(activeYear)}`, {
                headers: { 'X-Admin-Key': adminKey }
            });
            const data = await res.json();
            if (!res.ok) {
                sectionsGrid.innerHTML = `<div class="empty-state" style="grid-column:1/-1;"><p>${escHtml(data.error || 'Failed to load sections.')}</p></div>`;
                return;
            }
            renderSections(data.sections || []);
        } catch (e) {
            sectionsGrid.innerHTML = `<div class="empty-state" style="grid-column:1/-1;"><p>Connection error.</p></div>`;
        }
    }

    function renderSections(sections) {
        if (sections.length === 0) {
            sectionsGrid.innerHTML = `<div class="empty-state" style="grid-column:1/-1;"><ion-icon name="folder-open-outline"></ion-icon><p>No sections in ${yearLabels[activeYear]} yet. Create one above!</p></div>`;
            return;
        }

        sectionsGrid.innerHTML = sections.map((s, i) => `
            <div class="section-card ${activeSection === s ? 'active' : ''}" data-section="${escHtml(s)}" style="--stagger:${i}">
                <button class="s-del" data-del="${escHtml(s)}" title="Delete section"><ion-icon name="trash-outline"></ion-icon></button>
                <ion-icon name="folder-outline" class="s-icon"></ion-icon>
                <div class="s-name">${escHtml(s)}</div>
                <div class="s-count">Click to manage files</div>
            </div>
        `).join('');

        sectionsGrid.querySelectorAll('.section-card').forEach(card => {
            card.addEventListener('click', (e) => {
                if (e.target.closest('.s-del')) return;
                const sec = card.getAttribute('data-section');
                selectSection(sec);
                sectionsGrid.querySelectorAll('.section-card').forEach(c => c.classList.remove('active'));
                card.classList.add('active');
            });
        });

        sectionsGrid.querySelectorAll('.s-del').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const sec = btn.getAttribute('data-del');
                if (!confirm(`Delete section "${sec}" and ALL its files from ${yearLabels[activeYear]}? This cannot be undone.`)) return;
                await deleteSection(sec);
            });
        });
    }

    async function deleteSection(section) {
        try {
            const res = await fetch(`/api/fn/sections/${encodeURIComponent(activeYear)}/${encodeURIComponent(section)}`, {
                method: 'DELETE',
                headers: { 'X-Admin-Key': adminKey }
            });
            const data = await res.json();
            if (!res.ok) {
                alert(data.error || 'Failed to delete section.');
                return;
            }
            if (activeSection === section) {
                activeSection = null;
                filesPanel.style.display = 'none';
            }
            loadSections();
        } catch (e) {
            alert('Connection error.');
        }
    }

    // --- Select Section ---
    function selectSection(section) {
        activeSection = section;
        activeSectionLabel.textContent = `${section} (${yearLabels[activeYear]})`;
        modalSectionName.textContent = `${section} (${yearLabels[activeYear]})`;
        filesPanel.style.display = 'block';
        loadFiles(section);
        filesPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    async function loadFiles(section) {
        filesListContainer.innerHTML = `<div class="empty-state"><ion-icon name="hourglass-outline" class="spin"></ion-icon><p>Loading files...</p></div>`;
        try {
            const res = await fetch(`/api/fn/files/${encodeURIComponent(activeYear)}/${encodeURIComponent(section)}`, {
                headers: { 'X-Admin-Key': adminKey }
            });
            const data = await res.json();
            if (!res.ok) {
                filesListContainer.innerHTML = `<div class="empty-state"><p>${escHtml(data.error || 'Failed to load files.')}</p></div>`;
                return;
            }
            renderFiles(data.files || []);
        } catch (e) {
            filesListContainer.innerHTML = `<div class="empty-state"><p>Connection error.</p></div>`;
        }
    }

    function renderFiles(files) {
        if (files.length === 0) {
            filesListContainer.innerHTML = `<div class="empty-state"><ion-icon name="document-text-outline"></ion-icon><p>No files yet. Click "Upload PDF" above.</p></div>`;
            return;
        }

        filesListContainer.innerHTML = files.map((f, i) => `
            <div class="file-row" style="--stagger:${i}">
                <ion-icon name="document-text" class="fr-icon"></ion-icon>
                <span class="fr-name">${escHtml(f.display_name)}</span>
                <div class="fr-actions">
                    <a href="/view/${f.id}/${encodeURIComponent(f.display_name)}" target="_blank" rel="noopener" class="file-btn btn-view">
                        <ion-icon name="eye-outline"></ion-icon> View
                    </a>
                    <a href="/download/${f.id}/${encodeURIComponent(f.display_name)}" class="file-btn btn-download">
                        <ion-icon name="download-outline"></ion-icon> Download
                    </a>
                    <button class="btn-sm btn-danger del-file-btn" data-id="${f.id}" data-name="${escHtml(f.display_name)}" title="Delete file">
                        <ion-icon name="trash-outline"></ion-icon>
                    </button>
                </div>
            </div>
        `).join('');

        filesListContainer.querySelectorAll('.del-file-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const id = btn.getAttribute('data-id');
                const name = btn.getAttribute('data-name');
                if (!confirm(`Delete "${name}"?`)) return;
                await deleteFile(id);
            });
        });
    }

    async function deleteFile(fileId) {
        try {
            const res = await fetch(`/api/fn/file/${fileId}`, {
                method: 'DELETE',
                headers: { 'X-Admin-Key': adminKey }
            });
            const data = await res.json();
            if (!res.ok) {
                alert(data.error || 'Failed to delete file.');
                return;
            }
            loadFiles(activeSection);
        } catch (e) {
            alert('Connection error.');
        }
    }

    // --- Upload Modal ---
    openUploadModalBtn.addEventListener('click', () => {
        uploadFileForm.reset();
        modalFileMsg.textContent = 'Drag & Drop or Click to choose PDF';
        modalDropArea.style.borderColor = 'rgba(255,255,255,0.15)';
        modalStatus.textContent = '';
        modalStatus.className = 'status-msg';
        uploadModal.classList.add('open');
    });

    closeModalBtn.addEventListener('click', () => uploadModal.classList.remove('open'));
    uploadModal.addEventListener('click', (e) => {
        if (e.target === uploadModal) uploadModal.classList.remove('open');
    });

    modalFileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            modalFileMsg.textContent = e.target.files[0].name;
            modalDropArea.style.borderColor = 'var(--accent-secondary)';
        } else {
            modalFileMsg.textContent = 'Drag & Drop or Click to choose PDF';
            modalDropArea.style.borderColor = 'rgba(255,255,255,0.15)';
        }
    });

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(ev =>
        modalDropArea.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); })
    );
    ['dragenter', 'dragover'].forEach(ev => modalDropArea.addEventListener(ev, () => modalDropArea.classList.add('dragover')));
    ['dragleave', 'drop'].forEach(ev => modalDropArea.addEventListener(ev, () => modalDropArea.classList.remove('dragover')));

    modalDropArea.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            modalFileInput.files = files;
            modalFileMsg.textContent = files[0].name;
            modalDropArea.style.borderColor = 'var(--accent-secondary)';
        }
    });

    uploadFileForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!activeSection) return;
        const displayName = fileDisplayName.value.trim();
        const file = modalFileInput.files[0];
        if (!displayName || !file) {
            showStatus(modalStatus, 'Please fill all required fields.', 'error');
            return;
        }

        modalUploadBtn.innerHTML = '<ion-icon name="sync-outline" class="spin"></ion-icon> <span>Uploading...</span>';
        modalUploadBtn.disabled = true;

        const formData = new FormData();
        formData.append('section', activeSection);
        formData.append('year', activeYear);
        formData.append('display_name', displayName);
        formData.append('file', file);
        formData.append('admin_key', adminKey);

        try {
            const res = await fetch('/api/fn/upload', {
                method: 'POST',
                headers: { 'X-Admin-Key': adminKey },
                body: formData
            });
            const data = await res.json();
            if (res.ok && data.success) {
                showStatus(modalStatus, 'Uploaded successfully! 🚀', 'success');
                uploadFileForm.reset();
                modalFileMsg.textContent = 'Drag & Drop or Click to choose PDF';
                modalDropArea.style.borderColor = 'rgba(255,255,255,0.15)';
                loadFiles(activeSection);
                setTimeout(() => uploadModal.classList.remove('open'), 1200);
            } else {
                showStatus(modalStatus, data.error || 'Upload failed.', 'error');
            }
        } catch (err) {
            showStatus(modalStatus, 'Connection error.', 'error');
        } finally {
            modalUploadBtn.innerHTML = '<span>Upload</span><ion-icon name="arrow-forward-outline"></ion-icon>';
            modalUploadBtn.disabled = false;
        }
    });
});
