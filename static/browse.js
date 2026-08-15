document.addEventListener('DOMContentLoaded', () => {
    const year = typeof CURRENT_YEAR !== 'undefined' ? CURRENT_YEAR : '';

    const semMapping = {
        '1st_year': [{ val: '1st_sem', label: '1st Semester' }, { val: '2nd_sem', label: '2nd Semester' }],
        '2nd_year': [{ val: '3rd_sem', label: '3rd Semester' }, { val: '4th_sem', label: '4th Semester' }],
        '3rd_year': [{ val: '5th_sem', label: '5th Semester' }, { val: '6th_sem', label: '6th Semester' }],
        '4th_year': [{ val: '7th_sem', label: '7th Semester' }, { val: '8th_sem', label: '8th Semester' }]
    };

    const sessions = [
        { val: '2025-26', label: '2025-26' },
        { val: '2024-25', label: '2024-25' },
        { val: '2023-24', label: '2023-24' },
        { val: '2022-23', label: '2022-23' },
        { val: '2021-22', label: '2021-22' }
    ];

    const typeMapping = [
        { val: 'st', label: 'ST Papers', icon: 'document-text', color: '#d4a017' },
        { val: 'put', label: 'PUT Papers', icon: 'school', color: '#c0392b' },
        { val: 'ut', label: 'UT Papers', icon: 'create', color: '#e8c547' }
    ];

    const allTypes = [
        ...typeMapping,
        { val: 'notes', label: 'Faculty Notes', icon: 'journal', color: '#8b1a1a' }
    ];

    const yearLabels = {
        '1st_year': '1st Year',
        '2nd_year': '2nd Year',
        '3rd_year': '3rd Year',
        '4th_year': '4th Year'
    };

    let isFacultyNotesMode = false;
    let fnSectionSelected = null;
    let path = [];

    const explorerView = document.getElementById('explorerView');
    const breadcrumb = document.getElementById('breadcrumb');
    const pageTitle = document.getElementById('pageTitle');
    const backBtn = document.getElementById('backBtn');

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    if (backBtn) {
        backBtn.addEventListener('click', () => {
            if (isFacultyNotesMode) {
                if (fnSectionSelected) {
                    fnSectionSelected = null;
                } else {
                    isFacultyNotesMode = false;
                }
            } else {
                if (path.length > 0) {
                    path.pop();
                }
            }
            render();
        });
    }

    function getLabel(id, list) {
        const item = list.find(i => i.val === id);
        return item ? item.label : id;
    }

    function renderBreadcrumbs() {
        let html = `<a href="/" class="crumb"><ion-icon name="home"></ion-icon> Home</a>`;
        html += `<span class="crumb" data-level="0">${yearLabels[year] || year}</span>`;

        if (isFacultyNotesMode) {
            html += `<span class="crumb" data-level="1">Faculty Notes</span>`;
            if (fnSectionSelected) {
                html += `<span class="crumb" data-level="2">${escapeHtml(fnSectionSelected)}</span>`;
            }
        } else {
            for (let i = 0; i < path.length; i++) {
                let label = path[i];
                if (i === 0) label = getLabel(path[i], semMapping[year] || []);
                else if (i === 1) label = getLabel(path[i], allTypes);
                else if (i === 2) label = path[i];
                html += `<span class="crumb" data-level="${i + 1}">${escapeHtml(label)}</span>`;
            }
        }

        breadcrumb.innerHTML = html;
        document.querySelectorAll('.crumb[data-level]').forEach(crumb => {
            crumb.addEventListener('click', () => {
                const level = parseInt(crumb.getAttribute('data-level'), 10);
                if (isFacultyNotesMode) {
                    if (level === 0) {
                        isFacultyNotesMode = false;
                        fnSectionSelected = null;
                        path = [];
                        render();
                    } else if (level === 1) {
                        fnSectionSelected = null;
                        render();
                    }
                } else {
                    if (level < path.length) {
                        path = path.slice(0, level);
                        render();
                    }
                }
            });
        });

        const crumbs = document.querySelectorAll('.crumb');
        if (crumbs.length > 0) {
            crumbs[crumbs.length - 1].classList.add('active');
        }
    }

    function folderHTML(id, label, iconName, iconColor, index) {
        const s = iconColor ? `style="color:${iconColor};"` : '';
        return `
            <div class="folder-item" data-id="${escapeHtml(id)}" style="--stagger:${index}" role="button" tabindex="0">
                <ion-icon name="${iconName}" class="item-icon" ${s}></ion-icon>
                <span class="item-name">${escapeHtml(label)}</span>
            </div>
        `;
    }

    function attachFolderListeners() {
        document.querySelectorAll('.folder-item').forEach(item => {
            const clickHandler = () => {
                path.push(item.getAttribute('data-id'));
                render();
            };
            item.addEventListener('click', clickHandler);
            item.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    clickHandler();
                }
            });
        });
    }

    function render() {
        renderBreadcrumbs();
        explorerView.innerHTML = '';

        if (backBtn) {
            if (isFacultyNotesMode || path.length > 0) {
                backBtn.style.display = 'flex';
            } else {
                backBtn.style.display = 'none';
            }
        }

        // --- Faculty Notes Mode ---
        if (isFacultyNotesMode) {
            if (!fnSectionSelected) {
                pageTitle.textContent = 'Faculty Notes';
                fetchFacultySections();
            } else {
                pageTitle.textContent = fnSectionSelected;
                fetchFacultyFiles(fnSectionSelected);
            }
            return;
        }

        // --- Normal (Papers) Mode ---
        const depth = path.length;

        // Level 0: Show semesters + Faculty Notes card
        if (depth === 0) {
            pageTitle.textContent = 'Select Category';
            const sems = semMapping[year] || [];
            sems.forEach((sem, i) => {
                explorerView.innerHTML += folderHTML(sem.val, sem.label, 'book-outline', '#d4a017', i);
            });

            const notesIdx = sems.length;
            const notesCard = `
                <div class="folder-item faculty-notes-card" data-id="__faculty_notes__" style="--stagger:${notesIdx}" role="button" tabindex="0">
                    <ion-icon name="journal-outline" class="item-icon" style="color:#8b1a1a;"></ion-icon>
                    <span class="item-name">Faculty Notes</span>
                </div>
            `;
            explorerView.innerHTML += notesCard;

            document.querySelectorAll('.folder-item').forEach(item => {
                const clickHandler = () => {
                    const id = item.getAttribute('data-id');
                    if (id === '__faculty_notes__') {
                        isFacultyNotesMode = true;
                        render();
                    } else {
                        path.push(id);
                        render();
                    }
                };
                item.addEventListener('click', clickHandler);
                item.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        clickHandler();
                    }
                });
            });
        }
        // Level 1: Select paper type (ST / PUT / UT)
        else if (depth === 1) {
            pageTitle.textContent = 'Select Paper Type';
            typeMapping.forEach((t, i) => {
                explorerView.innerHTML += folderHTML(t.val, t.label, t.icon, t.color, i);
            });
            attachFolderListeners();
        }
        // Level 2: Select session
        else if (depth === 2) {
            pageTitle.textContent = 'Select Academic Session';
            sessions.forEach((s, i) => {
                explorerView.innerHTML += folderHTML(s.val, s.label, 'calendar-outline', '#d4a017', i);
            });
            attachFolderListeners();
        }
        // Level 3: Show files
        else if (depth === 3) {
            pageTitle.textContent = 'Papers';
            fetchFiles();
        }
    }

    async function fetchFacultySections() {
        explorerView.innerHTML = `<div class="empty-state"><ion-icon name="hourglass-outline" class="spin"></ion-icon><p>Loading sections...</p></div>`;
        try {
            const res = await fetch(`/api/fn/sections?year=${encodeURIComponent(year)}`);
            const data = await res.json();
            if (!res.ok || data.error) {
                explorerView.innerHTML = `<div class="empty-state"><ion-icon name="alert-circle-outline" style="color:#f85149;"></ion-icon><p>${escapeHtml(data.error || 'Failed to load sections.')}</p></div>`;
                return;
            }
            const sections = data.sections || [];
            explorerView.innerHTML = '';
            if (sections.length === 0) {
                explorerView.innerHTML = `<div class="empty-state"><ion-icon name="folder-open-outline"></ion-icon><p>No sections available yet for ${yearLabels[year] || year}.</p></div>`;
                return;
            }
            sections.forEach((s, i) => {
                explorerView.innerHTML += folderHTML(s, s, 'folder-outline', '#d4a017', i);
            });

            document.querySelectorAll('.folder-item').forEach(item => {
                const clickHandler = () => {
                    fnSectionSelected = item.getAttribute('data-id');
                    render();
                };
                item.addEventListener('click', clickHandler);
                item.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        clickHandler();
                    }
                });
            });
        } catch (e) {
            explorerView.innerHTML = `<div class="empty-state"><ion-icon name="alert-circle-outline" style="color:#f85149;"></ion-icon><p>Connection error. Please try again.</p></div>`;
        }
    }

    function getFileIconDetails(fileName) {
        const ext = (fileName.split('.').pop() || '').toLowerCase();
        if (ext === 'pdf') {
            return { icon: 'document-text', color: '#f85149' };
        }
        if (['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)) {
            return { icon: 'image', color: '#58a6ff' };
        }
        if (['doc', 'docx'].includes(ext)) {
            return { icon: 'document-attach', color: '#2b7cd3' };
        }
        if (['ppt', 'pptx'].includes(ext)) {
            return { icon: 'easel', color: '#e8c547' };
        }
        return { icon: 'document', color: '#d4a017' };
    }

    async function fetchFacultyFiles(section) {
        explorerView.innerHTML = `<div class="empty-state"><ion-icon name="hourglass-outline" class="spin"></ion-icon><p>Loading files...</p></div>`;
        try {
            const res = await fetch(`/api/fn/files/${encodeURIComponent(year)}/${encodeURIComponent(section)}`);
            const data = await res.json();
            if (!res.ok || data.error) {
                explorerView.innerHTML = `<div class="empty-state"><ion-icon name="alert-circle-outline" style="color:#f85149;"></ion-icon><p>${escapeHtml(data.error || 'Failed to load files.')}</p></div>`;
                return;
            }
            const files = data.files || [];
            explorerView.innerHTML = '';
            if (files.length === 0) {
                explorerView.innerHTML = `<div class="empty-state"><ion-icon name="document-text-outline"></ion-icon><p>No files in this section yet.</p></div>`;
                return;
            }
            files.forEach((fileObj, idx) => {
                const fileName = fileObj.display_name;
                const fileId = fileObj.id;
                const iconDetails = getFileIconDetails(fileName);
                const safeName = escapeHtml(fileName);
                const encodedName = encodeURIComponent(fileName);

                explorerView.innerHTML += `
                    <div class="file-card" style="--stagger:${idx}">
                        <ion-icon name="${iconDetails.icon}" class="item-icon" style="color:${iconDetails.color};"></ion-icon>
                        <span class="item-name" title="${safeName}">${safeName}</span>
                        <div class="file-actions">
                            <a href="/view/${fileId}/${encodedName}" target="_blank" rel="noopener" class="file-btn btn-view">
                                <ion-icon name="eye-outline"></ion-icon> View
                            </a>
                            <a href="/download/${fileId}/${encodedName}" class="file-btn btn-download">
                                <ion-icon name="download-outline"></ion-icon> Download
                            </a>
                        </div>
                    </div>
                `;
            });
        } catch (e) {
            explorerView.innerHTML = `<div class="empty-state"><ion-icon name="alert-circle-outline" style="color:#f85149;"></ion-icon><p>Connection error. Please try again.</p></div>`;
        }
    }

    async function fetchFiles() {
        explorerView.innerHTML = `<div class="empty-state"><ion-icon name="hourglass-outline" class="spin"></ion-icon><p>Loading files...</p></div>`;
        const [sem, type, session] = path;

        try {
            const params = new URLSearchParams({ year, semester: sem, type, session });
            const res = await fetch(`/api/files?${params}`);
            const data = await res.json();

            if (!res.ok || data.error) {
                const errMsg = data.error || `Server error (${res.status})`;
                explorerView.innerHTML = `<div class="empty-state"><ion-icon name="alert-circle-outline" style="color:#f85149;"></ion-icon><p>${escapeHtml(errMsg)}</p></div>`;
                return;
            }

            const files = Array.isArray(data) ? data : [];
            explorerView.innerHTML = '';
            if (files.length === 0) {
                explorerView.innerHTML = `<div class="empty-state"><ion-icon name="document-text-outline"></ion-icon><p>No papers uploaded here yet.</p></div>`;
                return;
            }

            files.forEach((fileObj, idx) => {
                const fileName = fileObj.name;
                const fileId = fileObj.id;
                const iconDetails = getFileIconDetails(fileName);
                const safeName = escapeHtml(fileName);
                const encodedName = encodeURIComponent(fileName);

                explorerView.innerHTML += `
                    <div class="file-card" style="--stagger:${idx}">
                        <ion-icon name="${iconDetails.icon}" class="item-icon" style="color:${iconDetails.color};"></ion-icon>
                        <span class="item-name" title="${safeName}">${safeName}</span>
                        <div class="file-actions">
                            <a href="/view/${fileId}/${encodedName}" target="_blank" rel="noopener" class="file-btn btn-view">
                                <ion-icon name="eye-outline"></ion-icon> View
                            </a>
                            <a href="/download/${fileId}/${encodedName}" class="file-btn btn-download">
                                <ion-icon name="download-outline"></ion-icon> Download
                            </a>
                        </div>
                    </div>
                `;
            });
        } catch (e) {
            explorerView.innerHTML = `<div class="empty-state"><ion-icon name="alert-circle-outline" style="color:#f85149;"></ion-icon><p>Error loading files. Please try again.</p></div>`;
        }
    }

    render();
});
