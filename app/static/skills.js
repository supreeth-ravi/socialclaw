// SocialClaw — Skills Marketplace

let allSkills = [];
let installedSlugs = new Set();
let activeCategory = null;
let activeTab = 'catalog';
let modalSlug = null;

// ─── Boot ────────────────────────────────────────────────────────────────────

async function boot() {
    if (!getToken()) { window.location.href = '/auth'; return; }
    await loadCatalog();
    renderCategories();
    renderCatalog();
    renderInstalledCount();
}

// ─── Data fetching ────────────────────────────────────────────────────────────
// Uses apiFetch + getToken from common.js

async function api(path, opts = {}) {
    if (opts.body && typeof opts.body === 'object') opts.body = JSON.stringify(opts.body);
    const res = await apiFetch('/api' + path, opts);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

async function loadCatalog() {
    try {
        allSkills = await api('/skills');
        installedSlugs = new Set(allSkills.filter(s => s.installed).map(s => s.slug));
    } catch (e) {
        console.error('Failed to load skills:', e);
    }
}

// ─── Tab management ───────────────────────────────────────────────────────────

function switchTab(tab) {
    activeTab = tab;
    ['catalog', 'installed', 'browse'].forEach(t => {
        document.getElementById(`tab-${t}`).classList.toggle('active', t === tab);
        document.getElementById(`panel-${t}`).classList.toggle('hidden', t !== tab);
    });

    const searchFilter = document.getElementById('search-filter');
    const categoryChips = document.getElementById('category-chips');
    searchFilter.classList.toggle('hidden', tab === 'browse');
    categoryChips.classList.toggle('hidden', tab !== 'catalog');

    if (tab === 'installed') renderInstalled();
    if (tab === 'catalog') renderCatalog();
}

// ─── Category filter ──────────────────────────────────────────────────────────

function renderCategories() {
    const cats = [...new Set(allSkills.map(s => s.category).filter(Boolean))].sort();
    const container = document.getElementById('category-chips');
    container.innerHTML = `<button class="category-chip active" onclick="filterCategory(null, this)">All</button>`;
    cats.forEach(cat => {
        const btn = document.createElement('button');
        btn.className = 'category-chip';
        btn.textContent = cat;
        btn.onclick = () => filterCategory(cat, btn);
        container.appendChild(btn);
    });
}

function filterCategory(cat, el) {
    activeCategory = cat;
    document.querySelectorAll('.category-chip').forEach(b => b.classList.remove('active'));
    el.classList.add('active');
    renderCatalog();
}

// ─── Search ───────────────────────────────────────────────────────────────────

function handleSearch() {
    renderCatalog();
}

function filteredSkills() {
    const q = (document.getElementById('search-input')?.value || '').toLowerCase();
    return allSkills.filter(s => {
        if (activeCategory && s.category !== activeCategory) return false;
        if (q && !s.name.toLowerCase().includes(q) && !s.description.toLowerCase().includes(q)
               && !s.tags.join(' ').toLowerCase().includes(q)) return false;
        return true;
    });
}

// ─── Render catalog ───────────────────────────────────────────────────────────

function renderCatalog() {
    const skills = filteredSkills();
    const grid = document.getElementById('skills-grid');
    const empty = document.getElementById('catalog-empty');

    if (!skills.length) {
        grid.innerHTML = '';
        empty.classList.remove('hidden');
        return;
    }
    empty.classList.add('hidden');
    grid.innerHTML = skills.map(s => skillCardHTML(s)).join('');
}

function renderInstalled() {
    const installed = allSkills.filter(s => s.installed);
    const grid = document.getElementById('installed-grid');
    const empty = document.getElementById('installed-empty');

    if (!installed.length) {
        grid.innerHTML = '';
        empty.classList.remove('hidden');
        return;
    }
    empty.classList.add('hidden');
    grid.innerHTML = installed.map(s => skillCardHTML(s, true)).join('');
}

function skillCardHTML(skill, showToggle = false) {
    const isInstalled = installedSlugs.has(skill.slug);
    const tagPills = (skill.tags || []).slice(0, 3).map(t =>
        `<span class="tag-pill">${t}</span>`
    ).join('');

    const actionBtn = isInstalled
        ? `<button class="btn-installed text-xs" onclick="event.stopPropagation(); uninstallSkill('${skill.slug}', this)">✓ Installed</button>`
        : `<button class="btn-install text-xs" onclick="event.stopPropagation(); installSkill('${skill.slug}', this)">+ Install</button>`;

    const downloads = skill.downloads ? `<span class="text-xs text-muted">↓ ${skill.downloads.toLocaleString()}</span>` : '';

    return `
    <div class="skill-card ${isInstalled ? 'installed' : ''}" onclick="openModal('${skill.slug}')">
        <div class="flex items-start justify-between mb-3">
            <div class="flex items-center gap-3">
                <span class="text-3xl">${skill.icon || '🔧'}</span>
                <div>
                    <div class="font-semibold text-white text-sm leading-tight">${skill.name}</div>
                    <div class="text-xs text-muted mt-0.5">${skill.category || ''}</div>
                </div>
            </div>
            ${isInstalled ? '<span class="badge-installed">Active</span>' : ''}
        </div>
        <p class="text-xs text-gray-400 mb-3 leading-relaxed line-clamp-2">${skill.description}</p>
        <div class="flex flex-wrap gap-1 mb-3">${tagPills}</div>
        <div class="flex items-center justify-between mt-auto">
            ${downloads}
            ${actionBtn}
        </div>
    </div>`;
}

function renderInstalledCount() {
    const count = installedSlugs.size;
    document.getElementById('installed-count').textContent = count ? `${count} skill${count !== 1 ? 's' : ''} active` : '';
    document.getElementById('installed-badge').textContent = count || '';
}

// ─── Install / Uninstall ──────────────────────────────────────────────────────

async function installSkill(slug, btn) {
    btn.textContent = '...';
    btn.disabled = true;
    try {
        await api(`/skills/${encodeURIComponent(slug)}/install`, { method: 'POST' });
        installedSlugs.add(slug);
        const s = allSkills.find(x => x.slug === slug);
        if (s) s.installed = true;
        renderCatalog();
        renderInstalledCount();
        showToast(`✓ "${allSkills.find(x => x.slug === slug)?.name || slug}" installed`);
    } catch (e) {
        btn.textContent = '+ Install';
        btn.disabled = false;
        showToast('Failed to install skill', true);
    }
}

async function uninstallSkill(slug, btn) {
    btn.textContent = '...';
    btn.disabled = true;
    try {
        await api(`/skills/${encodeURIComponent(slug)}/install`, { method: 'DELETE' });
        installedSlugs.delete(slug);
        const s = allSkills.find(x => x.slug === slug);
        if (s) s.installed = false;
        if (activeTab === 'installed') renderInstalled();
        else renderCatalog();
        renderInstalledCount();
        showToast('Skill removed');
    } catch (e) {
        showToast('Failed to remove skill', true);
    }
}

// ─── Modal ────────────────────────────────────────────────────────────────────

async function openModal(slug) {
    modalSlug = slug;
    try {
        const skill = await api(`/skills/${encodeURIComponent(slug)}/detail`);
        const installed = installedSlugs.has(slug);

        document.getElementById('modal-icon').textContent = skill.icon || '🔧';
        document.getElementById('modal-name').textContent = skill.name;
        document.getElementById('modal-category').textContent = skill.category || '';
        document.getElementById('modal-downloads').textContent = skill.downloads ? `↓ ${skill.downloads.toLocaleString()}` : '';
        document.getElementById('modal-description').textContent = skill.description;
        document.getElementById('modal-content').textContent = skill.content || '(No preview available)';
        document.getElementById('modal-source-link').href = skill.readme_url || '#';

        const tagsEl = document.getElementById('modal-tags');
        tagsEl.innerHTML = (skill.tags || []).map(t => `<span class="tag-pill">${t}</span>`).join('');

        const btn = document.getElementById('modal-action-btn');
        btn.textContent = installed ? 'Uninstall' : 'Install Skill';
        btn.className = installed ? 'btn-installed px-6 py-2.5 text-sm' : 'btn-install px-6 py-2.5 text-sm';

        document.getElementById('skill-modal').classList.remove('hidden');
    } catch (e) {
        showToast('Failed to load skill details', true);
    }
}

function closeModal(e) {
    if (e.target === document.getElementById('skill-modal')) {
        document.getElementById('skill-modal').classList.add('hidden');
    }
}

async function handleModalAction() {
    if (!modalSlug) return;
    const installed = installedSlugs.has(modalSlug);
    const btn = document.getElementById('modal-action-btn');
    if (installed) {
        await uninstallSkill(modalSlug, btn);
    } else {
        await installSkill(modalSlug, btn);
    }
    document.getElementById('skill-modal').classList.add('hidden');
}

// ─── ClawhHub live browse ─────────────────────────────────────────────────────

async function searchClawhHub() {
    const q = document.getElementById('clawhub-search').value.trim();
    const loading = document.getElementById('clawhub-loading');
    const empty = document.getElementById('clawhub-empty');
    const results = document.getElementById('clawhub-results');

    loading.classList.remove('hidden');
    empty.classList.add('hidden');
    results.innerHTML = '';

    try {
        const data = await api(`/skills/browse/clawhub?q=${encodeURIComponent(q)}&limit=20`);
        loading.classList.add('hidden');

        if (!data.length) {
            empty.classList.remove('hidden');
            return;
        }

        results.innerHTML = data.map(s => clawhubCardHTML(s)).join('');
    } catch (e) {
        loading.classList.add('hidden');
        results.innerHTML = `<div class="empty-state col-span-3"><p class="text-red-400">Failed to search ClawhHub. GitHub API may be rate-limited.</p></div>`;
    }
}

function clawhubCardHTML(skill) {
    const inCatalog = skill.in_catalog;
    const isInstalled = installedSlugs.has(skill.slug);

    const btn = inCatalog
        ? (isInstalled
            ? `<button class="btn-installed text-xs" onclick="uninstallSkill('${skill.slug}', this)">✓ Installed</button>`
            : `<button class="btn-install text-xs" onclick="installSkill('${skill.slug}', this)">+ Install</button>`)
        : `<button class="btn-install text-xs" onclick="importAndInstall('${skill.slug}', '${skill.raw_url}', this)">Import & Install</button>`;

    return `
    <div class="skill-card">
        <div class="flex items-start justify-between mb-3">
            <div class="flex items-center gap-3">
                <span class="text-3xl">🔧</span>
                <div>
                    <div class="font-semibold text-white text-sm">${skill.name}</div>
                    <div class="text-xs text-muted font-mono mt-0.5">${skill.slug}</div>
                </div>
            </div>
        </div>
        <p class="text-xs text-gray-400 mb-3 leading-relaxed">${skill.description}</p>
        <div class="flex items-center justify-between">
            <a href="${skill.readme_url}" target="_blank" class="text-xs text-muted hover:text-primary">View on GitHub ↗</a>
            ${btn}
        </div>
    </div>`;
}

async function importAndInstall(slug, rawUrl, btn) {
    btn.textContent = 'Importing...';
    btn.disabled = true;
    try {
        await api('/skills/import/clawhub', {
            method: 'POST',
            body: JSON.stringify({ slug, raw_url: rawUrl }),
        });
        // Now install it
        await api(`/skills/${encodeURIComponent(slug)}/install`, { method: 'POST' });
        installedSlugs.add(slug);
        await loadCatalog();
        renderInstalledCount();
        btn.textContent = '✓ Installed';
        btn.className = 'btn-installed text-xs';
        btn.disabled = false;
        showToast(`Skill "${slug.split('/').pop()}" imported and installed`);
    } catch (e) {
        btn.textContent = 'Import & Install';
        btn.disabled = false;
        showToast('Failed to import skill', true);
    }
}

// ─── Toast ────────────────────────────────────────────────────────────────────

function showToast(msg, error = false) {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed; bottom: 24px; right: 24px; z-index: 100;
        background: ${error ? '#7f1d1d' : '#1a3a35'};
        border: 1px solid ${error ? '#f87171' : '#3bcfb6'};
        color: ${error ? '#fca5a5' : '#3bcfb6'};
        padding: 12px 18px; border-radius: 10px; font-size: 13px; font-weight: 500;
        animation: slideIn 0.2s ease;
    `;
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2800);
}

document.head.insertAdjacentHTML('beforeend', `
<style>
@keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.line-clamp-2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
</style>`);

// Script is at the bottom of <body> so DOM is already ready — call boot directly.
document.getElementById('clawhub-search')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') searchClawhHub();
});
boot();
