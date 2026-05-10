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

    const branchIcons = {
        'cse': { icon: 'laptop-outline', color: '#d4a017' },
        'cse_aiml': { icon: 'sparkles-outline', color: '#c0392b' },
        'cse_ds': { icon: 'analytics-outline', color: '#e8c547' },
        'cs': { icon: 'desktop-outline', color: '#d4a017' },
        'cse_hindi': { icon: 'language-outline', color: '#c0392b' },
        'aiml': { icon: 'bulb-outline', color: '#e8c547' },
        'it': { icon: 'globe-outline', color: '#d4a017' },
        'csit': { icon: 'code-slash-outline', color: '#c0392b' },
        'ece': { icon: 'radio-outline', color: '#e8c547' },
        'me': { icon: 'cog-outline', color: '#d4a017' },
        'eee': { icon: 'flash-outline', color: '#c0392b' },
        'ce': { icon: 'business-outline', color: '#e8c547' }
    };

    // Paper types only (no notes — notes is now a top-level section)
    const typeMapping = [
        { val: 'st', label: 'ST Papers', icon: 'document-text', color: '#d4a017' },
        { val: 'put', label: 'PUT Papers', icon: 'school', color: '#c0392b' },
        { val: 'ut', label: 'UT Papers', icon: 'create', color: '#e8c547' }
    ];

    // Full type list (used for breadcrumb labels)
    const allTypes = [
        ...typeMapping,
        { val: 'notes', label: 'Faculty Notes', icon: 'journal', color: '#8b1a1a' }
    ];

    const yearLabels = { '1st_year': '1st Year', '2nd_year': '2nd Year', '3rd_year': '3rd Year', '4th_year': '4th Year' };

    // Track whether we are in Faculty Notes mode
    let isFacultyNotesMode = false;
    let fnSectionSelected = null;
    let path = [];
    const explorerView = document.getElementById('explorerView');
    const breadcrumb = document.getElementById('breadcrumb');
    const pageTitle = document.getElementById('pageTitle');

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
                html += `<span class="crumb" data-level="2">${fnSectionSelected}</span>`;
            }
        } else {
            for (let i = 0; i < path.length; i++) {
                let label = path[i];
                if (i === 0) label = getLabel(path[i], semMapping[year]);
                else if (i === 1) label = getLabel(path[i], allTypes);
                else if (i === 2) label = path[i];
                html += `<span class="crumb" data-level="${i + 1}">${label}</span>`;
            }
        }

        breadcrumb.innerHTML = html;
        document.querySelectorAll('.crumb[data-level]').forEach(crumb => {
            crumb.addEventListener('click', () => {
                const level = parseInt(crumb.getAttribute('data-level'));
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
                    if (level < path.length) { path = path.slice(0, level); render(); }
                }
            });
        });
        const crumbs = document.querySelectorAll('.crumb');
        if (crumbs.length > 0) crumbs[crumbs.length - 1].classList.add('active');
    }

    function folderHTML(id, label, iconName, iconColor, index) {
        const s = iconColor ? `style="color:${iconColor};"` : '';
        return `<div class="folder-item" data-id="${id}" style="--stagger:${index}"><ion-icon name="${iconName}" class="item-icon" ${s}></ion-icon><span class="item-name">${label}</span></div>`;
    }

    function attachFolderListeners() {
        document.querySelectorAll('.folder-item').forEach(item => {
            item.addEventListener('click', () => { path.push(item.getAttribute('data-id')); render(); });
        });
    }

    function render() {
        renderBreadcrumbs();
        explorerView.innerHTML = '';

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

        // Level 0: Show semesters + Faculty Notes
        if (depth === 0) {
            pageTitle.textContent = 'Select Category';
            const sems = semMapping[year] || [];
            sems.forEach((sem, i) => {
                explorerView.innerHTML += folderHTML(sem.val, sem.label, 'book-outline', '#d4a017', i);
            });

            // Add Faculty Notes as a special card at the end
            const notesIdx = sems.length;
            const notesCard = `<div class="folder-item faculty-notes-card" data-id="__faculty_notes__" style="--stagger:${notesIdx}">
                <ion-icon name="journal-outline" class="item-icon" style="color:#8b1a1a;"></ion-icon>
                <span class="item-name">Faculty Notes</span>
            </div>`;
            explorerView.innerHTML += notesCard;

            // Attach listeners — special handling for Faculty Notes
            document.querySelectorAll('.folder-item').forEach(item => {
                item.addEventListener('click', () => {
                    const id = item.getAttribute('data-id');
                    if (id === '__faculty_notes__') {
                        isFacultyNotesMode = true;
                        render();
                    } else {
                        path.push(id);
                        render();
                    }
                });
            });
        }
        // Level 1: Select paper type (ST / PUT / UT only, no notes)
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

    // Fetch all sections (public — no admin key needed for browsing)
    async function fetchFacultySections() {
        explorerView.innerHTML = `<div class="empty-state"><ion-icon name="hourglass-outline" class="spin"></ion-icon>Loading sections...</div>`;
        try {
            const res = await fetch('/api/fn/sections');
            const data = await res.json();
            if (!res.ok || data.error) {
                explorerView.innerHTML = `<div class="empty-state"><ion-icon name="alert-circle-outline" style="color:#f85149;"></ion-icon><p>${data.error || 'Failed to load.'}</p></div>`;
                return;
            }
            const sections = data.sections || [];
            explorerView.innerHTML = '';
            if (sections.length === 0) {
                explorerView.innerHTML = `<div class="empty-state"><ion-icon name="folder-open-outline"></ion-icon><p>No sections available yet.</p></div>`;
                return;
            }
            sections.forEach((s, i) => {
                explorerView.innerHTML += folderHTML(s, s, 'folder-outline', '#d4a017', i);
            });
            document.querySelectorAll('.folder-item').forEach(item => {
                item.addEventListener('click', () => {
                    fnSectionSelected = item.getAttribute('data-id');
                    render();
                });
            });
        } catch (e) {
            explorerView.innerHTML = `<div class="empty-state"><ion-icon name="alert-circle-outline" style="color:#f85149;"></ion-icon><p>Connection error.</p></div>`;
        }
    }

    // Fetch files inside a section (public)
    async function fetchFacultyFiles(section) {
        explorerView.innerHTML = `<div class="empty-state"><ion-icon name="hourglass-outline" class="spin"></ion-icon>Loading files...</div>`;
        try {
            const res = await fetch(`/api/fn/files/${encodeURIComponent(section)}`);
            const data = await res.json();
            if (!res.ok || data.error) {
                explorerView.innerHTML = `<div class="empty-state"><ion-icon name="alert-circle-outline" style="color:#f85149;"></ion-icon><p>${data.error || 'Failed to load.'}</p></div>`;
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
                explorerView.innerHTML += `
                    <div class="file-card" style="--stagger:${idx}">
                        <ion-icon name="document-text" class="item-icon" style="color:#f85149;"></ion-icon>
                        <span class="item-name" title="${fileName}">${fileName}</span>
                        <div class="file-actions">
                            <a href="/view/${fileId}/${encodeURIComponent(fileName)}" target="_blank" class="file-btn btn-view">
                                <ion-icon name="eye-outline"></ion-icon> View
                            </a>
                            <a href="/download/${fileId}/${encodeURIComponent(fileName)}" class="file-btn btn-download">
                                <ion-icon name="download-outline"></ion-icon> Download
                            </a>
                        </div>
                    </div>
                `;
            });
        } catch (e) {
            explorerView.innerHTML = `<div class="empty-state"><ion-icon name="alert-circle-outline" style="color:#f85149;"></ion-icon><p>Connection error.</p></div>`;
        }
    }

    async function fetchFiles() {
        explorerView.innerHTML = `<div class="empty-state"><ion-icon name="hourglass-outline" class="spin"></ion-icon>Loading files...</div>`;
        let sem, type, session;

        [sem, type, session] = path;

        try {
            const params = new URLSearchParams({ year, semester: sem, type, session });
            // Note: branch parameter is omitted or empty
            const res = await fetch(`/api/files?${params}`);
            const data = await res.json();

            // Check if the API returned an error
            if (!res.ok || data.error) {
                const errMsg = data.error || `Server error (${res.status})`;
                explorerView.innerHTML = `<div class="empty-state"><ion-icon name="alert-circle-outline" style="color:#f85149;"></ion-icon><p>${errMsg}</p></div>`;
                return;
            }

            const files = data;

            explorerView.innerHTML = '';
            if (!files || files.length === 0) {
                explorerView.innerHTML = `<div class="empty-state"><ion-icon name="document-text-outline"></ion-icon><p>No papers uploaded here yet.</p></div>`;
                return;
            }

            files.forEach((fileObj, idx) => {
                const fileName = fileObj.name;
                const fileId = fileObj.id;
                const ext = fileName.split('.').pop().toLowerCase();
                const isPDF = ext === 'pdf';
                const isImage = ['png', 'jpg', 'jpeg', 'webp'].includes(ext);
                let iconName = isPDF ? 'document-text' : (isImage ? 'image' : 'document');
                let iconColor = isPDF ? '#f85149' : (isImage ? '#58a6ff' : '#d4a017');

                explorerView.innerHTML += `
                    <div class="file-card" style="--stagger:${idx}">
                        <ion-icon name="${iconName}" class="item-icon" style="color:${iconColor};"></ion-icon>
                        <span class="item-name" title="${fileName}">${fileName}</span>
                        <div class="file-actions">
                            <a href="/view/${fileId}/${encodeURIComponent(fileName)}" target="_blank" class="file-btn btn-view">
                                <ion-icon name="eye-outline"></ion-icon> View
                            </a>
                            <a href="/download/${fileId}/${encodeURIComponent(fileName)}" class="file-btn btn-download">
                                <ion-icon name="download-outline"></ion-icon> Download
                            </a>
                        </div>
                    </div>
                `;
            });
        } catch (e) {
            explorerView.innerHTML = `<div class="empty-state"><ion-icon name="alert-circle-outline" style="color:#f85149;"></ion-icon><p>Error loading files.</p></div>`;
        }
    }

    render();
});
