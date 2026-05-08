document.addEventListener('DOMContentLoaded', () => {
    const semMapping = {
        '1st_year': [{ val: '1st_sem', label: '1st Semester' }, { val: '2nd_sem', label: '2nd Semester' }],
        '2nd_year': [{ val: '3rd_sem', label: '3rd Semester' }, { val: '4th_sem', label: '4th Semester' }],
        '3rd_year': [{ val: '5th_sem', label: '5th Semester' }, { val: '6th_sem', label: '6th Semester' }],
        '4th_year': [{ val: '7th_sem', label: '7th Semester' }, { val: '8th_sem', label: '8th Semester' }]
    };

    const yearSelect = document.getElementById('yearSelect');
    const branchGroup = document.getElementById('branchGroup');
    const branchSelect = document.getElementById('branchSelect');
    const semSelect = document.getElementById('semSelect');
    const typeSelect = document.getElementById('typeSelect');
    const sessionGroup = document.getElementById('sessionGroup');
    const semGroup = document.getElementById('semGroup');
    const sessionSelect = document.getElementById('sessionSelect');
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
        sems.forEach(s => { semSelect.innerHTML += `<option value="${s.val}">${s.label}</option>`; });
        semSelect.disabled = false;

        branchGroup.style.display = 'none';
        branchSelect.removeAttribute('required');
        branchSelect.value = '';
    });

    typeSelect.addEventListener('change', (e) => {
        if (e.target.value === 'notes') {
            sessionGroup.style.display = 'none';
            semGroup.style.display = 'none';
            sessionSelect.removeAttribute('required');
            semSelect.removeAttribute('required');
        } else {
            sessionGroup.style.display = 'flex';
            semGroup.style.display = 'flex';
            sessionSelect.setAttribute('required', 'required');
            if (yearSelect.value) {
                semSelect.setAttribute('required', 'required');
            }
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) { fileMsg.textContent = e.target.files[0].name; dropArea.style.borderColor = 'var(--accent-secondary)'; }
        else { fileMsg.textContent = 'Drag & Drop or Click to choose file'; dropArea.style.borderColor = 'rgba(255,255,255,0.15)'; }
    });

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(e => dropArea.addEventListener(e, ev => { ev.preventDefault(); ev.stopPropagation(); }));
    ['dragenter', 'dragover'].forEach(e => dropArea.addEventListener(e, () => dropArea.classList.add('dragover')));
    ['dragleave', 'drop'].forEach(e => dropArea.addEventListener(e, () => dropArea.classList.remove('dragover')));

    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(uploadForm);
        uploadBtn.innerHTML = '<ion-icon name="sync-outline" class="spin"></ion-icon> <span>Uploading...</span>';
        uploadBtn.disabled = true;
        try {
            const res = await fetch('/upload', { method: 'POST', body: formData });
            const result = await res.json();
            if (res.ok) {
                statusMsg.textContent = 'Upload Successful! 🚀'; statusMsg.className = 'status-msg success';
                uploadForm.reset(); semSelect.innerHTML = '<option value="" disabled selected>Select Sem</option>';
                semSelect.disabled = true; branchGroup.style.display = 'none'; branchSelect.removeAttribute('required');
                sessionGroup.style.display = 'flex'; semGroup.style.display = 'flex';
                sessionSelect.setAttribute('required', 'required');
                fileMsg.textContent = 'Drag & Drop or Click to choose file'; dropArea.style.borderColor = 'rgba(255,255,255,0.15)';
            } else { statusMsg.textContent = result.error || 'Upload failed.'; statusMsg.className = 'status-msg error'; }
        } catch (err) { statusMsg.textContent = 'Connection error.'; statusMsg.className = 'status-msg error'; }
        finally {
            uploadBtn.innerHTML = '<span>Upload Now</span><ion-icon name="arrow-forward-outline"></ion-icon>';
            uploadBtn.disabled = false; setTimeout(() => { statusMsg.textContent = ''; }, 5000);
        }
    });
});
