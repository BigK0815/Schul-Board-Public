const $ = id => document.getElementById(id);
const show = text => { $('status').textContent = text; };
async function api(path, method = 'GET', body) {
    const headers = {'X-CSRF-Token': document.body.dataset.csrf};
    if (body !== undefined && !(body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
        body = JSON.stringify(body);
    }
    const response = await fetch('/api/' + path, {method, headers, body});
    const data = await response.json();
    if (!response.ok) throw Error(data.error || 'Anfrage fehlgeschlagen.');
    return data;
}
if ($('login')) {
    $('login').onsubmit = async event => {
        event.preventDefault();
        try {
            await api('login', 'POST', {password: $('password').value});
            location.reload();
        } catch (error) { show(error.message); }
    };
} else {
    setupEditor();
}

function setupEditor() {
    const edit = $('edit');
    const handle = $('handle');
    const monitors = JSON.parse(document.body.dataset.monitors);
    const boxes = [...document.querySelectorAll('.target')];
    const clamp = (min, value, max) => Math.min(max, Math.max(min, value));
    const targets = () => boxes.filter(box => box.checked).map(box => Number(box.value));
    const selectedMonitors = () => $('allTargets').checked ? monitors : monitors.filter(item => targets().includes(item.id));
    function scalePreview() {
        const monitor = monitors.find(item => item.id === Number($('previewMonitor').value)) || monitors[0];
        const {board_width: width, board_height: height, info_width: info} = monitor;
        const full = $('mode').value === 'fullscreen';
        const panelWidth = full ? width : width * info / 100;
        const panelHeight = full ? height : height - clamp(54, height * .084, 90) - 2 * clamp(6, width * .008, 14);
        $('panelTitle').style.display = full ? 'none' : 'flex';
        Object.assign($('panel').style, {width: panelWidth + 'px', height: panelHeight + 'px'});
        Object.assign($('panelTitle').style, {height: clamp(30, height * .05, 50) + 'px',
                                             fontSize: clamp(12, width * .0135, 25) + 'px'});
        $('dimensions').textContent = width + ' × ' + height + (full ? ' · Vollbild' : ' · Infobreite ' + info + ' %');
        const scale = Math.min(1, $('stage').parentElement.clientWidth / (panelWidth + 32), 620 / panelHeight);
        Object.assign($('stage').style, {width: panelWidth * scale + 'px', height: panelHeight * scale + 'px'});
        $('panel').style.transform = 'scale(' + scale + ')';
    }

    function updateTargets() {
        const previous = $('previewMonitor').value;
        const available = selectedMonitors();
        $('previewMonitor').replaceChildren(...available.map(item => new Option(item.name, item.id)));
        if (available.some(item => String(item.id) === previous)) $('previewMonitor').value = previous;
        boxes.forEach(box => { box.disabled = $('allTargets').checked; });
        scalePreview();
        schedule();
    }
    window.addEventListener('resize', scalePreview);
    $('targets').onchange = updateTargets;
    $('mode').onchange = $('previewMonitor').onchange = () => { scalePreview(); schedule(); };

    let currentId = null, selectedImage = null, selection = null, timer, sequence = 0;
    const today = new Date().toLocaleDateString('sv-SE');
    let draft = 0;
    function reset() {
        draft++;
        currentId = null;
        $('allTargets').checked = true;
        $('mode').value = 'info';
        boxes.forEach(box => { box.checked = false; });
        updateTargets();
        $('heading').textContent = 'Neue Meldung';
        $('title').value = '';
        $('starts').value = $('ends').value = today;
        edit.innerHTML = '';
        selection = null;
        selectImage(null);
        schedule();
    }
    function html() {
        const copy = edit.cloneNode(true);
        copy.querySelectorAll('font').forEach(old => {
            const span = document.createElement('span');
            span.style.fontSize = old.dataset.size || '';
            span.style.fontFamily = old.face;
            span.style.color = old.color;
            span.append(...old.childNodes);
            old.replaceWith(span);
        });
        return copy.innerHTML;
    }
    function checkFit() {
        const preview = $('preview');
        const fits = preview.scrollHeight <= preview.clientHeight + 1 &&
                     preview.scrollWidth <= preview.clientWidth + 1;
        $('fit').textContent = fits ? '' : 'Die Meldung passt nicht vollständig in den Infoteil.';
        return fits;
    }
    async function updatePreview() {
        const revision = ++sequence;
        const result = await api('preview', 'POST', {html: html()});
        if (revision !== sequence) return false;
        $('preview').innerHTML = result.html;
        await Promise.all([...$('preview').querySelectorAll('img')].map(image => image.decode().catch(() => {})));
        return revision === sequence && checkFit();
    }
    function schedule() {
        clearTimeout(timer);
        ++sequence;
        timer = setTimeout(() => updatePreview().catch(error => show(error.message)), 160);
    }
    function applyFontSize() {
        edit.querySelectorAll('font[size="7"]').forEach(node => {
            node.dataset.size = $('size').value + 'px';
            node.style.fontSize = node.dataset.size;
            node.removeAttribute('size');
        });
    }
    edit.addEventListener('input', () => {
        applyFontSize();
        schedule();
    });
    edit.addEventListener('paste', event => {
        event.preventDefault();
        const clipboard = event.clipboardData;
        const image = [...clipboard.items]
            .find(item => item.kind === 'file' && item.type.startsWith('image/'))?.getAsFile();
        if (image) {
            insertImage(image);
            return;
        }
        document.execCommand('insertText', false, clipboard.getData('text/plain'));
        schedule();
    });
    edit.addEventListener('drop', event => event.preventDefault());
    document.addEventListener('selectionchange', () => {
        const value = getSelection();
        if (value.rangeCount && edit.contains(value.anchorNode) && edit.contains(value.focusNode))
            selection = value.getRangeAt(0).cloneRange();
    });
    function restore() {
        edit.focus();
        if (selection && edit.contains(selection.commonAncestorContainer)) {
            const value = getSelection();
            value.removeAllRanges();
            value.addRange(selection);
        }
    }
    function format(command, value = null) {
        restore();
        document.execCommand('styleWithCSS', false, command !== 'fontSize');
        document.execCommand(command, false, value);
        schedule();
    }
    document.querySelectorAll('[data-command]').forEach(button => {
        button.onmousedown = event => event.preventDefault();
        button.onclick = () => format(button.dataset.command);
    });
    $('family').onchange = () => format('fontName', $('family').value);
    $('color').onchange = () => format('foreColor', $('color').value);
    $('size').onchange = () => {
        restore();
        document.execCommand('styleWithCSS', false, false);
        document.execCommand('fontSize', false, '7');
        applyFontSize();
        schedule();
    };

    function positionHandle() {
        if (!selectedImage || !edit.contains(selectedImage)) { handle.hidden = true; return; }
        const image = selectedImage.getBoundingClientRect();
        const wrap = edit.parentElement.getBoundingClientRect();
        handle.hidden = image.bottom < wrap.top || image.bottom > wrap.bottom;
        handle.style.left = (image.right - wrap.left - 8) + 'px';
        handle.style.top = (image.bottom - wrap.top - 8) + 'px';
    }
    function selectImage(image) {
        selectedImage?.classList.remove('selected');
        selectedImage = image;
        selectedImage?.classList.add('selected');
        positionHandle();
    }
    edit.onclick = event => selectImage(event.target instanceof HTMLImageElement ? event.target : null);
    edit.onscroll = positionHandle;
    handle.onpointerdown = event => {
        event.preventDefault();
        if (!selectedImage) return;
        const image = selectedImage;
        const origin = event.clientX;
        const initial = image.clientWidth;
        const full = (image.parentElement === edit ? edit.clientWidth - 40 : image.parentElement.clientWidth);
        handle.setPointerCapture(event.pointerId);
        handle.onpointermove = move => {
            image.style.width = clamp(5, (initial + move.clientX - origin) * 100 / full, 100) + '%';
            positionHandle();
            schedule();
        };
        handle.onlostpointercapture = () => { handle.onpointermove = null; };
    };
    $('imageButton').onmousedown = event => event.preventDefault();
    $('imageButton').onclick = () => $('imageFile').click();
    $('imageFile').onchange = () => {
        const file = $('imageFile').files[0];
        $('imageFile').value = '';
        if (file) insertImage(file);
    };

    async function insertImage(file) {
        const insertion = selection?.cloneRange();
        const originalDraft = draft;
        const form = new FormData();
        form.append('image', file);
        try {
            const {src} = await api('image', 'POST', form);
            if (originalDraft !== draft) return;
            const existingImages = new Set(edit.querySelectorAll('img'));
            selection = insertion;
            restore();
            document.execCommand('insertHTML', false, '<img alt="" style="width:60%" src="' + src + '">');
            const image = [...edit.querySelectorAll('img')].find(item => !existingImages.has(item));
            if (image) {
                image.addEventListener('load', positionHandle, {once:true});
                selectImage(image);
            }
            schedule();
        } catch (error) { show(error.message); }
    }

    async function refreshList() {
        const rows = await api('announcements');
        $('list').replaceChildren(...rows.map(row => {
            const li = document.createElement('li'), text = document.createElement('span');
            text.textContent = row.title + ' · ' + row.starts + ' – ' + row.ends;
            const open = document.createElement('button'), remove = document.createElement('button');
            open.textContent = 'Bearbeiten';
            remove.textContent = 'Löschen';
            open.onclick = async () => {
                try {
                    const record = await api('announcements/' + row.id);
                    reset();
                    currentId = row.id;
                    $('heading').textContent = 'Meldung bearbeiten';
                    $('title').value = record.title;
                    $('starts').value = record.starts;
                    $('ends').value = record.ends;
                    edit.innerHTML = record.html;
                    $('mode').value = record.mode;
                    $('allTargets').checked = !record.targets.length;
                    boxes.forEach(box => { box.checked = record.targets.includes(Number(box.value)); });
                    updateTargets();
                    schedule();
                } catch (error) { show(error.message); }
            };
            remove.onclick = async () => {
                if (!confirm('Diese Meldung löschen?')) return;
                try {
                    await api('announcements/' + row.id, 'DELETE');
                    if (currentId === row.id) reset();
                    await refreshList();
                } catch (error) { show(error.message); }
            };
            li.append(text, open, remove);
            return li;
        }));
    }
    $('publish').onclick = async () => {
        $('publish').disabled = true;
        clearTimeout(timer);
        try {
            const available = selectedMonitors();
            if (!available.length) throw Error('Bitte mindestens einen Zielmonitor auswählen.');
            const original = $('previewMonitor').value;
            try {
                for (const item of available) {
                    $('previewMonitor').value = item.id;
                    scalePreview();
                    if (!await updatePreview()) throw Error('Die Meldung passt nicht vollständig auf ' + item.name + '.');
                }
            } finally {
                $('previewMonitor').value = original;
                scalePreview();
                schedule();
            }
            const path = currentId ? 'announcements/' + currentId : 'announcements';
            await api(path, currentId ? 'PUT' : 'POST', {
                targets: $('allTargets').checked ? [] : targets(), mode: $('mode').value,
                title: $('title').value, starts: $('starts').value, ends: $('ends').value, html: html(),
            });
            reset();
            await refreshList();
            show('Meldung gespeichert.');
        } catch (error) { show(error.message); }
        finally { $('publish').disabled = false; }
    };
    $('new').onclick = reset;
    $('logout').onclick = () => api('logout', 'POST').then(() => location.reload()).catch(error => show(error.message));
    reset();
    refreshList().catch(error => show(error.message));
}
