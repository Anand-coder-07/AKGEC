document.addEventListener('DOMContentLoaded', () => {
    const year = typeof CURRENT_YEAR !== 'undefined' ? CURRENT_YEAR : '';
    const is1stYear = year === '1st_year';

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

    const typeMapping = [
        { val: 'st', label: 'ST Papers', icon: 'document-text', color: '#d4a017' },
        { val: 'put', label: 'PUT Papers', icon: 'school', color: '#c0392b' },
        { val: 'ut', label: 'UT Papers', icon: 'create', color: '#e8c547' },
        { val: 'notes', label: 'Faculty Notes', icon: 'journal', color: '#8b1a1a' }
    ];

    const yearLabels = { '1st_year': '1st Year', '2nd_year': '2nd Year', '3rd_year': '3rd Year', '4th_year': '4th Year' };

    // Navigation order:
    // 1st year: [sem, type, session]  → then files
    // Others:   [branch, sem, type, session] → then files
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

        const semIdx = is1stYear ? 0 : 1;
        const typeIdx = is1stYear ? 1 : 2;
        const sessionIdx = is1stYear ? 2 : 3;

        for (let i = 0; i < path.length; i++) {
            let label = path[i];
            if (!is1stYear && i === 0) label = getLabel(path[i], branches);
            else if (i === semIdx) label = getLabel(path[i], semMapping[year]);
            else if (i === typeIdx) label = getLabel(path[i], typeMapping);
            else if (i === sessionIdx) label = path[i]; // session is already readable
            html += `<span class="crumb" data-level="${i + 1}">${label}</span>`;
        }

        breadcrumb.innerHTML = html;
        document.querySelectorAll('.crumb[data-level]').forEach(crumb => {
            crumb.addEventListener('click', () => {
                const level = parseInt(crumb.getAttribute('data-level'));
                if (level < path.length) { path = path.slice(0, level); render(); }
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

    // Levels:
    // 1st year: 0=sem, 1=type, 2=session, 3=files
    // Others:   0=branch, 1=sem, 2=type, 3=session, 4=files
    function render() {
        renderBreadcrumbs();
        explorerView.innerHTML = '';
        const depth = path.length;

        const branchLevel = is1stYear ? -1 : 0;
        const semLevel = is1stYear ? 0 : 1;
        const typeLevel = is1stYear ? 1 : 2;
        const sessionLevel = is1stYear ? 2 : 3;
        const fileLevel = is1stYear ? 3 : 4;

        if (!is1stYear && depth === branchLevel) {
            // This won't trigger since branchLevel=0 and depth starts at 0
        }

        if (!is1stYear && depth === 0) {
            pageTitle.textContent = `${yearLabels[year]} – Select Branch`;
            branches.forEach((b, i) => {
                const bi = branchIcons[b.val] || { icon: 'folder', color: '#d4a017' };
                explorerView.innerHTML += folderHTML(b.val, b.label, bi.icon, bi.color, i);
            });
            attachFolderListeners();
        }
        else if (depth === semLevel) {
            pageTitle.textContent = 'Select Semester';
            semMapping[year].forEach((sem, i) => {
                explorerView.innerHTML += folderHTML(sem.val, sem.label, 'book-outline', '#d4a017', i);
            });
            attachFolderListeners();
        }
        else if (depth === typeLevel) {
            pageTitle.textContent = 'Select Material Type';
            typeMapping.forEach((t, i) => {
                explorerView.innerHTML += folderHTML(t.val, t.label, t.icon, t.color, i);
            });
            attachFolderListeners();
        }
        else if (depth === sessionLevel) {
            pageTitle.textContent = 'Select Academic Session';
            sessions.forEach((s, i) => {
                explorerView.innerHTML += folderHTML(s.val, s.label, 'calendar-outline', '#d4a017', i);
            });
            attachFolderListeners();
        }
        else if (depth === fileLevel) {
            pageTitle.textContent = 'Papers & Notes';
            fetchFiles();
        }
    }

    async function fetchFiles() {
        explorerView.innerHTML = `<div class="empty-state"><ion-icon name="hourglass-outline" class="spin"></ion-icon>Loading files...</div>`;
        let branch = '', sem, type, session, downloadBase;

        if (is1stYear) {
            [sem, type, session] = path;
            downloadBase = `${year}/${sem}/${type}/${session}`;
        } else {
            [branch, sem, type, session] = path;
            downloadBase = `${year}/${branch}/${sem}/${type}/${session}`;
        }

        try {
            const params = new URLSearchParams({ year, semester: sem, type, session });
            if (branch) params.append('branch', branch);
            const res = await fetch(`/api/files?${params}`);
            const files = await res.json();

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
