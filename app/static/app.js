// SocialClaw — Main App UI
// Auth-aware, multi-page, per-user agent

let currentUser = null;
let currentSessionId = null;
let isStreaming = false;
let lastToolCallKey = null;
let lastFinalizedText = '';
let toolEventCounter = 0;
let replayEvents = [];
let replayIndex = 0;
let isReplaying = false;
let replayTimer = null;
let currentThinkingBlock = null;
let thinkingEventQueue = [];
let currentTurnContainer = null;
let currentTurnAssistant = null;
let currentResponseText = '';
let pendingToolCards = [];
let pendingAgentExchanges = [];
let activeStreamTimer = null;
let narrationBuffer = '';
let lastSseEventType = '';
let hadToolCallInTurn = false;
let responsePhaseActive = false;
let lastToolResponseSeen = false;

function renderMarkdown(text) {
    return marked.parse(text || '', { breaks: true });
}

// ─── Chat Layout State ──────────────────────────────────────────
let sessionsOpen = false;
let agentsSidebarOpen = false;
let chatIsEmpty = true;
let sessionAgents = {};  // { name: { status, messageCount, color, ... } }
let sessionEdges = [];   // [{ from, to, status, color }]

// ─── Tool Display Labels ────────────────────────────────────────
const TOOL_LABELS = {
    send_message_to_contact: { icon: '\u{1F4AC}', label: (args) => `Asking ${args?.contact_name || args?.name || 'contact'} for help` },
    get_my_contacts:         { icon: '\u{1F4CB}', label: () => 'Looking up my contacts' },
    search_contacts_by_tag:  { icon: '\u{1F50D}', label: (args) => `Searching for ${args?.tag || 'matching'} contacts` },
    get_merchant_contacts:   { icon: '\u{1F3EA}', label: () => 'Checking available merchants' },
    get_friend_contacts:     { icon: '\u{1F465}', label: () => 'Looking up friends' },
    ping_contact:            { icon: '\u{1F4E1}', label: (args) => `Checking if ${args?.contact_name || args?.name || 'contact'} is online` },
    discover_agent:          { icon: '\u{1F50E}', label: () => 'Discovering a new agent' },
    add_contact:             { icon: '\u{2795}', label: (args) => `Adding ${args?.name || 'new contact'}` },
    remove_contact:          { icon: '\u{2796}', label: (args) => `Removing ${args?.name || 'contact'}` },
    get_my_history:          { icon: '\u{1F9E0}', label: () => 'Recalling past experiences' },
    add_memory:              { icon: '\u{1F4DD}', label: () => 'Saving memory' },
    check_inbox:             { icon: '\u{1F4E8}', label: () => 'Checking inbox for new messages' },
    get_active_tasks:        { icon: '\u{1F4CB}', label: () => 'Checking background tasks' },
    schedule_task:           { icon: '\u{23F0}', label: (args) => `Scheduling: ${args?.intent?.slice(0, 30) || 'task'}` },
};

// ─── Agent Color System ─────────────────────────────────────────
const AGENT_COLORS = [
    { name: 'cyan',    text: '#22d3ee', bg: 'rgba(34,211,238,0.1)',  border: 'rgba(34,211,238,0.2)',  dot: '#22d3ee' },
    { name: 'emerald', text: '#34d399', bg: 'rgba(52,211,153,0.1)',  border: 'rgba(52,211,153,0.2)',  dot: '#34d399' },
    { name: 'amber',   text: '#fbbf24', bg: 'rgba(251,191,36,0.1)', border: 'rgba(251,191,36,0.2)',  dot: '#fbbf24' },
    { name: 'rose',    text: '#fb7185', bg: 'rgba(251,113,133,0.1)', border: 'rgba(251,113,133,0.2)', dot: '#fb7185' },
    { name: 'violet',  text: '#a78bfa', bg: 'rgba(167,139,250,0.1)', border: 'rgba(167,139,250,0.2)', dot: '#a78bfa' },
    { name: 'teal',    text: '#2dd4bf', bg: 'rgba(45,212,191,0.1)',  border: 'rgba(45,212,191,0.2)',  dot: '#2dd4bf' },
];
const USER_COLOR = { text: '#6366f1', bg: '#6366f1', border: '#6366f1' };

// Per-context color maps (reset per chat session / inbox conversation)
let _chatColorMap = {};
let _chatColorIdx = 0;
let _inboxColorMap = {};
let _inboxColorIdx = 0;

function getParticipantColor(name, colorMap, idxRef) {
    if (!name) name = 'agent';
    const key = name.toLowerCase();
    if (colorMap[key]) return colorMap[key];
    const color = AGENT_COLORS[idxRef.val % AGENT_COLORS.length];
    idxRef.val++;
    colorMap[key] = color;
    return color;
}

// Wrapper objects so we can pass index by reference
let _chatIdx = { val: 0 };
let _inboxIdx = { val: 0 };

function getChatColor(name) {
    return getParticipantColor(name, _chatColorMap, _chatIdx);
}

function getInboxColor(name) {
    return getParticipantColor(name, _inboxColorMap, _inboxIdx);
}

function resetChatColors() {
    _chatColorMap = {};
    _chatIdx = { val: 0 };
}

function resetInboxColors() {
    _inboxColorMap = {};
    _inboxIdx = { val: 0 };
}

function createColoredAvatar(name, color, size) {
    const initial = (name || '?')[0].toUpperCase();
    const sizeClass = size === 'sm' ? 'agent-avatar-sm' : 'agent-avatar-md';
    const div = document.createElement('div');
    div.className = `agent-avatar ${sizeClass}`;
    div.style.backgroundColor = color.bg;
    div.style.border = `1.5px solid ${color.border}`;
    div.style.color = color.text;
    div.textContent = initial;
    return div;
}

function createColoredBubble(name, message, color, isExchange) {
    const wrapper = document.createElement('div');
    wrapper.className = 'flex items-start gap-2.5 animate-float-in';

    const avatar = createColoredAvatar(name, color, isExchange ? 'sm' : 'md');
    wrapper.appendChild(avatar);

    const content = document.createElement('div');
    content.className = 'max-w-lg';

    const label = document.createElement('div');
    label.className = 'text-xs font-medium mb-1';
    label.style.color = color.text;
    label.textContent = name || 'Agent';
    content.appendChild(label);

    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble-colored px-4 py-2.5 text-sm text-gray-200';
    bubble.style.backgroundColor = color.bg;
    bubble.style.borderColor = color.border;
    const span = document.createElement('span');
    span.className = 'bubble-content';
    if (message) {
        span.innerHTML = renderMarkdown(message);
        span.classList.add('markdown-body');
    }
    bubble.appendChild(span);
    content.appendChild(bubble);

    wrapper.appendChild(content);
    return wrapper;
}

function createUserBubble(text) {
    const div = document.createElement('div');
    div.className = 'flex justify-end animate-float-in';
    div.innerHTML = `<div class="bubble-user px-4 py-2.5 max-w-lg text-sm whitespace-pre-wrap">${escHtml(text)}</div>`;
    return div;
}

function createTypingIndicator(name, color) {
    const wrapper = document.createElement('div');
    wrapper.className = 'typing-indicator animate-float-in';
    wrapper.id = 'loading-indicator';

    const avatar = createColoredAvatar(name, color, 'md');
    wrapper.appendChild(avatar);

    const dots = document.createElement('div');
    dots.className = 'typing-indicator-dots';
    dots.style.backgroundColor = color.bg;
    dots.style.borderColor = color.border;
    for (let i = 1; i <= 3; i++) {
        const dot = document.createElement('span');
        dot.className = `typing-dot-${i}`;
        dot.style.backgroundColor = color.dot;
        dots.appendChild(dot);
    }
    wrapper.appendChild(dots);
    return wrapper;
}

// ─── DOM refs ───────────────────────────────────────────────────
const newChatBtn = document.getElementById('new-chat-btn');
const newChatHeaderBtn = document.getElementById('new-chat-header-btn');
const sessionsList = document.getElementById('sessions-list');
const chatSessionTitle = document.getElementById('chat-session-title');
const chatMessages = document.getElementById('chat-messages');
const chatReasoning = document.getElementById('chat-reasoning');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const chatFormCentered = document.getElementById('chat-form-centered');
const chatInputCentered = document.getElementById('chat-input-centered');
const sendBtnCentered = document.getElementById('send-btn-centered');
const sessionsOverlay = document.getElementById('sessions-overlay');
const sessionsPanel = document.getElementById('sessions-panel');
const sessionsToggleBtn = document.getElementById('sessions-toggle-btn');
const agentsToggleBtn = document.getElementById('agents-toggle-btn');
const agentsSidebar = document.getElementById('agents-sidebar');
const agentsSidebarList = document.getElementById('agents-sidebar-list');
const agentsSidebarStats = document.getElementById('agents-sidebar-stats');
const agentsNetworkViz = document.getElementById('agents-network-viz');
const chatEmptyState = document.getElementById('chat-empty-state');
const chatActiveState = document.getElementById('chat-active-state');
const chatTabChat = document.getElementById('chat-tab-chat');
const chatTabReasoning = document.getElementById('chat-tab-reasoning');
let currentChatTab = 'chat';
const replayPlayBtn = document.getElementById('replay-play-btn');
const replayStepBtn = document.getElementById('replay-step-btn');
const replayResetBtn = document.getElementById('replay-reset-btn');
const replayRange = document.getElementById('replay-range');
const replayLabel = document.getElementById('replay-label');

const inviteModal = document.getElementById('invite-modal');
const inviteUrl = document.getElementById('invite-url');
const inviteCancel = document.getElementById('invite-cancel');
const inviteConfirm = document.getElementById('invite-confirm');
const inviteError = document.getElementById('invite-error');

const agentCardModal = document.getElementById('agent-card-modal');
const agentCardClose = document.getElementById('agent-card-close');
const agentCardTitle = document.getElementById('agent-card-title');
const agentCardLoading = document.getElementById('agent-card-loading');
const agentCardError = document.getElementById('agent-card-error');
const agentCardContent = document.getElementById('agent-card-content');

const inboxTabMessages = document.getElementById('inbox-tab-messages');
const inboxTabTasks = document.getElementById('inbox-tab-tasks');
const inboxMessagesPane = document.getElementById('inbox-messages-pane');
const inboxTasksPane = document.getElementById('inbox-tasks-pane');
const inboxSidebar = document.getElementById('inbox-sidebar');

// ─── Sidebar Toggles ────────────────────────────────────────────
function toggleSessionsSidebar(forceState) {
    if (!sessionsPanel || !sessionsOverlay) return;
    sessionsOpen = forceState !== undefined ? forceState : !sessionsOpen;
    if (sessionsOpen) {
        sessionsPanel.classList.add('sessions-sidebar--open');
        sessionsOverlay.classList.remove('hidden');
    } else {
        sessionsPanel.classList.remove('sessions-sidebar--open');
        sessionsOverlay.classList.add('hidden');
    }
}

function toggleAgentsSidebar(forceState) {
    agentsSidebarOpen = forceState !== undefined ? forceState : !agentsSidebarOpen;
    if (agentsSidebarOpen) {
        agentsSidebar.classList.add('agents-sidebar--open');
        agentsSidebar.classList.remove('agents-sidebar--closed');
    } else {
        agentsSidebar.classList.remove('agents-sidebar--open');
        agentsSidebar.classList.add('agents-sidebar--closed');
    }
}

if (sessionsToggleBtn) sessionsToggleBtn.addEventListener('click', () => toggleSessionsSidebar());
if (sessionsOverlay) sessionsOverlay.addEventListener('click', () => toggleSessionsSidebar(false));
agentsToggleBtn.addEventListener('click', () => toggleAgentsSidebar());

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        if (sessionsOpen) toggleSessionsSidebar(false);
        if (agentsSidebarOpen) toggleAgentsSidebar(false);
    }
});

// ─── Empty / Active State Management ────────────────────────────
function showEmptyState() {
    chatIsEmpty = true;
    chatEmptyState.classList.remove('hidden');
    chatActiveState.classList.add('hidden');
    chatInputCentered.disabled = false;
    sendBtnCentered.disabled = false;
    chatInput.disabled = true;
    sendBtn.disabled = true;
    toggleAgentsSidebar(false);
}

function showActiveState() {
    chatIsEmpty = false;
    chatEmptyState.classList.add('hidden');
    chatActiveState.classList.remove('hidden');
    chatInput.disabled = false;
    sendBtn.disabled = false;
    document.getElementById('bg-task-btn').disabled = false;
    setChatTab(currentChatTab);
    chatInput.focus();
}

function setChatTab(tab) {
    currentChatTab = tab;
    if (chatTabChat) chatTabChat.classList.toggle('active', tab === 'chat');
    if (chatTabReasoning) chatTabReasoning.classList.toggle('active', tab === 'reasoning');
    if (chatMessages) chatMessages.classList.toggle('hidden', tab !== 'chat');
    if (chatReasoning) chatReasoning.classList.toggle('hidden', tab !== 'reasoning');
    scrollToBottom(getActiveChatContainer());
}

function getActiveChatContainer() {
    return currentChatTab === 'reasoning' ? chatReasoning : chatMessages;
}

if (chatTabChat) {
    chatTabChat.addEventListener('click', () => setChatTab('chat'));
}
if (chatTabReasoning) {
    chatTabReasoning.addEventListener('click', () => setChatTab('reasoning'));
}

function setReplayMode(enabled) {
    isReplaying = enabled;
    if (enabled) {
        chatInput.disabled = true;
        sendBtn.disabled = true;
        chatInputCentered.disabled = true;
        sendBtnCentered.disabled = true;
        document.body.classList.add('replay-mode');
    } else {
        chatInput.disabled = false;
        sendBtn.disabled = false;
        chatInputCentered.disabled = false;
        sendBtnCentered.disabled = false;
        document.body.classList.remove('replay-mode');
    }
    if (replayPlayBtn) replayPlayBtn.textContent = enabled ? 'Pause' : 'Play';
}

function updateReplayControls() {
    if (!replayRange || !replayLabel) return;
    replayRange.max = String(replayEvents.length);
    replayRange.value = String(replayIndex);
    replayLabel.textContent = `${replayIndex} / ${replayEvents.length}`;
}

function clearChatThreads() {
    chatMessages.innerHTML = '';
    chatReasoning.innerHTML = '';
    lastToolCallKey = null;
    lastFinalizedText = '';
    toolEventCounter = 0;
    currentThinkingBlock = null;
    thinkingEventQueue = [];
    currentTurnContainer = null;
    currentTurnAssistant = null;
    currentResponseText = '';
    pendingToolCards = [];
    pendingAgentExchanges = [];
    if (activeStreamTimer) {
        clearInterval(activeStreamTimer);
        activeStreamTimer = null;
    }
    narrationBuffer = '';
    lastSseEventType = '';
    hadToolCallInTurn = false;
    responsePhaseActive = false;
    lastToolResponseSeen = false;
}

function renderReplayEvent(evt) {
    if (!evt) return;
    if (evt.type === 'user') {
        appendUserBubble(evt.text);
    } else if (evt.type === 'assistant') {
        appendAgentBubble(evt.text, evt.author);
    } else if (evt.type === 'tool_call') {
        appendToolActivity(evt.payload, chatReasoning);
        trackAgentFromToolCall(evt.payload);
    } else if (evt.type === 'tool_response') {
        completeToolActivity(evt.payload, chatReasoning);
        trackAgentResponse(evt.payload);
    }
}

function renderReplayToIndex(idx) {
    clearChatThreads();
    resetChatColors();
    resetSessionAgents();
    const chatFrag = document.createDocumentFragment();
    const reasoningFrag = document.createDocumentFragment();

    for (let i = 0; i < idx; i++) {
        const evt = replayEvents[i];
        if (!evt) continue;
        if (evt.type === 'user') {
            const { turn, assistantWrap } = createTurnContainer();
            currentTurnContainer = turn;
            currentTurnAssistant = assistantWrap;
            turn.insertBefore(createUserBubble(evt.text), assistantWrap);
            const thinkingBlock = createThinkingBlock();
            turn.insertBefore(thinkingBlock, assistantWrap);
            currentThinkingBlock = thinkingBlock;
            chatFrag.appendChild(turn);
        } else if (evt.type === 'assistant') {
            const name = (evt.author && evt.author !== 'agent') ? evt.author : (currentUser?.handle || 'Agent');
            const color = getChatColor(name);
            const bubble = createColoredBubble(name, evt.text, color, false);
            if (currentTurnAssistant) {
                currentTurnAssistant.appendChild(bubble);
            } else {
                chatFrag.appendChild(bubble);
            }
        } else if (evt.type === 'tool_call') {
            appendToolActivity(evt.payload, reasoningFrag);
            trackAgentFromToolCall(evt.payload);
        } else if (evt.type === 'tool_response') {
            completeToolActivity(evt.payload, reasoningFrag);
            trackAgentResponse(evt.payload);
        }
    }

    chatMessages.appendChild(chatFrag);
    chatReasoning.appendChild(reasoningFrag);
    scrollToBottom(getActiveChatContainer());
}

function startReplay() {
    if (replayEvents.length === 0) return;
    setReplayMode(true);
    if (replayTimer) clearInterval(replayTimer);
    replayTimer = setInterval(() => {
        if (replayIndex >= replayEvents.length) {
            pauseReplay();
            return;
        }
        replayIndex += 1;
        updateReplayControls();
        renderReplayToIndex(replayIndex);
    }, 600);
}

function pauseReplay() {
    setReplayMode(false);
    if (replayTimer) clearInterval(replayTimer);
    replayTimer = null;
}

function resetReplay() {
    replayIndex = replayEvents.length;
    updateReplayControls();
    renderReplayToIndex(replayIndex);
    pauseReplay();
}

if (replayPlayBtn) {
    replayPlayBtn.addEventListener('click', () => {
        if (isReplaying) pauseReplay();
        else startReplay();
    });
}
if (replayStepBtn) {
    replayStepBtn.addEventListener('click', () => {
        pauseReplay();
        replayIndex = Math.min(replayIndex + 1, replayEvents.length);
        updateReplayControls();
        renderReplayToIndex(replayIndex);
    });
}
if (replayResetBtn) {
    replayResetBtn.addEventListener('click', () => {
        replayIndex = 0;
        updateReplayControls();
        renderReplayToIndex(replayIndex);
    });
}
if (replayRange) {
    replayRange.addEventListener('input', () => {
        pauseReplay();
        replayIndex = Number(replayRange.value);
        updateReplayControls();
        renderReplayToIndex(replayIndex);
    });
}

// ─── Agent Tracking System ──────────────────────────────────────
function trackAgentFromToolCall(payload) {
    if (payload.name !== 'send_message_to_contact') return;
    const args = payload.args || {};
    const contactName = args.contact_name || args.name || 'contact';
    const color = getChatColor(contactName);

    if (!sessionAgents[contactName]) {
        sessionAgents[contactName] = { status: 'responding', messageCount: 0, color };
    } else {
        sessionAgents[contactName].status = 'responding';
    }

    sessionEdges.push({
        from: currentUser?.handle || 'You',
        to: contactName,
        status: 'active',
        color,
    });

    renderAgentsSidebar();
    // Auto-open agents sidebar on first agent contact
    if (Object.keys(sessionAgents).length === 1 && !agentsSidebarOpen) {
        toggleAgentsSidebar(true);
    }
}

function trackAgentResponse(payload) {
    // Find the agent currently in "responding" state
    for (const [name, agent] of Object.entries(sessionAgents)) {
        if (agent.status === 'responding') {
            agent.status = 'responded';
            agent.messageCount = (agent.messageCount || 0) + 1;
            sessionEdges.push({
                from: name,
                to: currentUser?.handle || 'You',
                status: 'done',
                color: agent.color,
            });
            break;
        }
    }
    renderAgentsSidebar();
}

function resetSessionAgents() {
    sessionAgents = {};
    sessionEdges = [];
    agentsSidebarList.innerHTML = '';
    agentsNetworkViz.innerHTML = '';
    agentsSidebarStats.textContent = '';
    toggleAgentsSidebar(false);
}

function renderAgentsSidebar() {
    agentsSidebarList.innerHTML = '';
    const agents = Object.entries(sessionAgents);

    for (const [name, agent] of agents) {
        const card = document.createElement('div');
        card.className = 'agent-card';
        if (agent.status === 'responding') card.className += ' agent-card--responding';
        else if (agent.status === 'responded') {
            card.className += ' agent-card--responded';
            card.style.setProperty('--agent-color-border', agent.color.border);
            card.style.setProperty('--agent-color-bg', agent.color.bg);
        }

        const header = document.createElement('div');
        header.className = 'flex items-center gap-2';

        const avatar = createColoredAvatar(name, agent.color, 'sm');
        header.appendChild(avatar);

        const nameEl = document.createElement('span');
        nameEl.className = 'text-sm font-medium flex-1 truncate';
        nameEl.style.color = agent.color.text;
        nameEl.textContent = name;
        header.appendChild(nameEl);

        const dot = document.createElement('span');
        dot.className = 'agent-status-dot';
        if (agent.status === 'responding') dot.className += ' agent-status-dot--responding';
        else if (agent.status === 'responded') dot.className += ' agent-status-dot--responded';
        header.appendChild(dot);

        card.appendChild(header);

        // Stats row
        const stats = document.createElement('div');
        stats.className = 'flex items-center justify-between text-xs text-muted';
        const statusText = agent.status === 'responding' ? 'Responding...' : agent.status === 'responded' ? 'Responded' : 'Idle';
        stats.innerHTML = `<span>${escHtml(statusText)}</span><span>${agent.messageCount || 0} msg${(agent.messageCount || 0) !== 1 ? 's' : ''}</span>`;
        card.appendChild(stats);

        card.addEventListener('click', () => focusAgentInReasoning(name));
        agentsSidebarList.appendChild(card);
    }

    // Update stats
    const total = agents.length;
    const responding = agents.filter(([, a]) => a.status === 'responding').length;
    agentsSidebarStats.textContent = total > 0
        ? `${total} agent${total !== 1 ? 's' : ''} contacted${responding > 0 ? ` · ${responding} active` : ''}`
        : '';

    renderNetworkVisualization();
}

function renderNetworkVisualization() {
    agentsNetworkViz.innerHTML = '';
    const agents = Object.entries(sessionAgents);
    if (agents.length === 0) return;

    const svgNS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('class', 'network-viz-svg');
    svg.setAttribute('viewBox', '0 0 240 120');

    const centerX = 120, centerY = 60, radius = 42;

    // Arrow marker
    const defs = document.createElementNS(svgNS, 'defs');
    const marker = document.createElementNS(svgNS, 'marker');
    marker.setAttribute('id', 'arrow');
    marker.setAttribute('markerWidth', '6');
    marker.setAttribute('markerHeight', '6');
    marker.setAttribute('refX', '5');
    marker.setAttribute('refY', '3');
    marker.setAttribute('orient', 'auto');
    const arrowPath = document.createElementNS(svgNS, 'path');
    arrowPath.setAttribute('d', 'M0,0 L6,3 L0,6 Z');
    arrowPath.setAttribute('fill', '#6b7280');
    marker.appendChild(arrowPath);
    defs.appendChild(marker);
    svg.appendChild(defs);

    // Precompute positions
    const positions = {};
    agents.forEach(([name], i) => {
        const angle = (2 * Math.PI * i / agents.length) - Math.PI / 2;
        positions[name] = {
            x: centerX + radius * Math.cos(angle),
            y: centerY + radius * Math.sin(angle),
        };
    });

    // Draw directional edges (from sessionEdges)
    sessionEdges.forEach((edge) => {
        const from = edge.from === (currentUser?.handle || 'You') ? { x: centerX, y: centerY } : positions[edge.from];
        const to = edge.to === (currentUser?.handle || 'You') ? { x: centerX, y: centerY } : positions[edge.to];
        if (!from || !to) return;
        const line = document.createElementNS(svgNS, 'line');
        line.setAttribute('x1', from.x);
        line.setAttribute('y1', from.y);
        line.setAttribute('x2', to.x);
        line.setAttribute('y2', to.y);
        line.setAttribute('class', edge.status === 'active' ? 'network-line network-line--active' : 'network-line network-line--done');
        line.setAttribute('marker-end', 'url(#arrow)');
        if (edge.color) line.style.stroke = edge.color.dot;
        svg.appendChild(line);
    });

    // Center node (personal agent)
    const center = document.createElementNS(svgNS, 'circle');
    center.setAttribute('cx', centerX);
    center.setAttribute('cy', centerY);
    center.setAttribute('r', 10);
    center.setAttribute('class', 'network-node-center');
    svg.appendChild(center);

    const centerLabel = document.createElementNS(svgNS, 'text');
    centerLabel.setAttribute('x', centerX);
    centerLabel.setAttribute('y', centerY + 3);
    centerLabel.setAttribute('class', 'network-label');
    centerLabel.style.fill = 'white';
    centerLabel.style.fontSize = '8px';
    centerLabel.textContent = 'You';
    svg.appendChild(centerLabel);

    // Agent nodes
    agents.forEach(([name, agent], i) => {
        const angle = (2 * Math.PI * i / agents.length) - Math.PI / 2;
        const x = centerX + radius * Math.cos(angle);
        const y = centerY + radius * Math.sin(angle);

        const node = document.createElementNS(svgNS, 'circle');
        node.setAttribute('cx', x);
        node.setAttribute('cy', y);
        node.setAttribute('r', 7);
        node.setAttribute('fill', agent.color.dot);
        node.setAttribute('class', 'network-node-agent');
        node.style.setProperty('--node-glow', `${agent.color.dot}66`);
        svg.appendChild(node);

        const label = document.createElementNS(svgNS, 'text');
        label.setAttribute('x', x);
        label.setAttribute('y', y + 16);
        label.setAttribute('class', 'network-label');
        label.textContent = name.length > 10 ? name.slice(0, 9) + '…' : name;
        svg.appendChild(label);
    });

    agentsNetworkViz.appendChild(svg);
}

function focusAgentInReasoning(agentName) {
    setChatTab('reasoning');
    const items = chatReasoning.querySelectorAll(`[data-agent="${agentName}"]`);
    if (items.length === 0) return;
    items[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
    items.forEach((el) => {
        el.classList.add('reasoning-highlight');
        setTimeout(() => el.classList.remove('reasoning-highlight'), 1200);
    });
}

// ─── Auth Init ──────────────────────────────────────────────────
async function initAuth() {
    const token = getToken();
    if (!token) { window.location.href = '/'; return false; }
    try {
        const resp = await apiFetch(`${API}/auth/me`);
        if (!resp.ok) { logout(); return false; }
        currentUser = await resp.json();
        // Update localStorage with fresh user data
        localStorage.setItem('user', JSON.stringify(currentUser));
        return true;
    } catch {
        logout();
        return false;
    }
}

// ─── Navigation ─────────────────────────────────────────────────
const appLayout = document.getElementById('app-layout');
const onboardingScreen = document.getElementById('page-onboarding');

function showPage(page) {
    if (page === 'onboarding') {
        // Full-screen onboarding — hide app layout entirely
        appLayout.classList.add('hidden');
        onboardingScreen.classList.remove('hidden');
        return;
    }
    // Normal app pages — show app layout, hide onboarding
    onboardingScreen.classList.add('hidden');
    appLayout.classList.remove('hidden');

    document.querySelectorAll('#app-layout .page').forEach(p => p.classList.add('hidden'));
    const target = document.getElementById(`page-${page}`);
    if (target) target.classList.remove('hidden');

    document.querySelectorAll('.nav-item[data-page]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.page === page);
    });

    // Keep notification polling active across pages so nav badges stay fresh.
    startInboxPolling();
}

document.querySelectorAll('.nav-item[data-page]').forEach(btn => {
    btn.addEventListener('click', () => {
        const page = btn.dataset.page;
        showPage(page);
        if (page === 'contacts') loadContactsPage();
        if (page === 'settings') loadSettings();
        if (page === 'inbox') loadInboxPage();
        if (page === 'memory') loadMemoryPage();
        if (page === 'feed') loadFeedPage();
        if (page === 'integrations') loadIntegrationsPage();
    });
});

document.getElementById('logout-btn').addEventListener('click', logout);
const profileMenuBtn = document.getElementById('nav-profile-toggle');
const profileMenu = document.getElementById('profile-menu');
if (profileMenuBtn && profileMenu) {
    const closeProfileMenu = () => {
        profileMenu.classList.add('hidden');
        profileMenuBtn.setAttribute('aria-expanded', 'false');
    };
    const toggleProfileMenu = () => {
        profileMenu.classList.toggle('hidden');
        profileMenuBtn.setAttribute('aria-expanded', profileMenu.classList.contains('hidden') ? 'false' : 'true');
    };
    profileMenuBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        toggleProfileMenu();
    });
    profileMenuBtn.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        toggleProfileMenu();
    });
    document.addEventListener('click', (event) => {
        if (profileMenu.classList.contains('hidden')) return;
        if (profileMenu.contains(event.target)) return;
        if (profileMenuBtn.contains(event.target)) return;
        closeProfileMenu();
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closeProfileMenu();
    });
}
document.querySelectorAll('.profile-item[data-page]').forEach(item => {
    item.addEventListener('click', () => {
        const page = item.dataset.page;
        if (!page) return;
        showPage(page);
        if (page === 'memory') loadMemoryPage();
        if (page === 'feed') loadFeedPage();
        if (page === 'settings') loadSettings();
        if (page === 'integrations') loadIntegrationsPage();
        profileMenu.classList.add('hidden');
        profileMenuBtn?.setAttribute('aria-expanded', 'false');
    });
});

// ─── Init ───────────────────────────────────────────────────────
async function init() {
    const ok = await initAuth();
    if (!ok) return;

    // Populate nav
    const navAvatar = document.getElementById('nav-avatar');
    const navHandle = document.getElementById('nav-handle');
    navAvatar.textContent = (currentUser.display_name || currentUser.handle)[0].toUpperCase();
    navHandle.textContent = `@${currentUser.handle}`;
    seedTaskSeenIfMissing();

    // Check onboarding
    if (!currentUser.is_onboarded) {
        showPage('onboarding');
        await loadOnboarding();
        return;
    }

    // Load chat
    showPage('inbox');
    const sessions = await loadSessions();
    if (sessions.length > 0) {
        await selectSession(sessions[0].id, sessions[0].title);
    } else {
        const resp = await apiFetch(`${API}/sessions`, {
            method: 'POST',
            body: JSON.stringify({}),
        });
        const session = await resp.json();
        await loadSessions();
        await selectSession(session.id, session.title);
    }

    // Start polling for inbox badges
    startInboxPolling();
}

// ─── Utilities ──────────────────────────────────────────────────
function formatHistoryTime(ts) {
    if (!ts) return '';
    const date = new Date(ts);
    if (Number.isNaN(date.getTime())) return ts;
    return date.toLocaleString();
}

// ─── Feed ─────────────────────────────────────────────────────────

const FEED_TYPE_COLORS = {
    purchase: '#34d399', recommendation: '#22d3ee', review: '#fb7185',
    research: '#60a5fa', inquiry: '#c084fc', note: '#a78bfa',
    preference: '#f0c27b', contact_exchange: '#2dd4bf', reshare: '#fbbf24',
};

let _feedLastCreatedAt = '';
let _feedCurrentSort = 'new';

async function loadFeedPage() {
    _feedLastCreatedAt = '';
    _feedCurrentSort = 'new';
    // Reset active tab
    document.querySelectorAll('.feed-tab').forEach(t => t.classList.toggle('active', t.dataset.sort === 'new'));
    // Load stats, agents, and posts in parallel
    const [statsResp, agentsResp, postsResp] = await Promise.all([
        apiFetch(`${API}/feed/stats`),
        apiFetch(`${API}/feed/recent-agents?limit=8`),
        apiFetch(`${API}/feed/?limit=20&sort=new`),
    ]);
    const stats = await statsResp.json();
    const agents = await agentsResp.json();
    const posts = await postsResp.json();
    renderFeedStats(stats);
    renderRecentAgents(agents);
    renderFeed(posts, false);
}

function renderFeedStats(s) {
    document.getElementById('feed-stat-agents').textContent = _fmtStatNum(s.agents || 0);
    document.getElementById('feed-stat-posts').textContent = _fmtStatNum(s.posts || 0);
    document.getElementById('feed-stat-comments').textContent = _fmtStatNum(s.comments || 0);
    document.getElementById('feed-stat-reactions').textContent = _fmtStatNum(s.reactions || 0);
}

function _fmtStatNum(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'K';
    return String(n);
}

function renderRecentAgents(agents) {
    const strip = document.getElementById('feed-agents-strip');
    const list = document.getElementById('feed-agents-list');
    if (!agents || agents.length === 0) { strip.classList.add('hidden'); return; }
    strip.classList.remove('hidden');
    list.innerHTML = '';
    const colors = ['#34d399','#22d3ee','#fb7185','#60a5fa','#c084fc','#f0c27b','#fbbf24','#2dd4bf'];
    agents.forEach((a, i) => {
        const color = colors[i % colors.length];
        const init = (a.author_display || a.author_handle || '?')[0].toUpperCase();
        const div = document.createElement('div');
        div.className = 'feed-agent-card';
        div.innerHTML = `
            <div class="feed-agent-av" style="background:${color}20;color:${color};border:2px solid ${color}">${init}</div>
            <div class="feed-agent-name">${escapeHtml(a.author_display || a.author_handle)}</div>
            <div class="feed-agent-time">${formatTimeAgo(a.last_post)}</div>
        `;
        list.appendChild(div);
    });
}

async function loadFeedSorted(sort) {
    _feedCurrentSort = sort;
    _feedLastCreatedAt = '';
    document.querySelectorAll('.feed-tab').forEach(t => t.classList.toggle('active', t.dataset.sort === sort));
    const resp = await apiFetch(`${API}/feed/?limit=20&sort=${sort}`);
    const posts = await resp.json();
    renderFeed(posts, false);
}

async function loadMoreFeed() {
    if (!_feedLastCreatedAt) return;
    const resp = await apiFetch(`${API}/feed/?limit=20&sort=${_feedCurrentSort}&before=${encodeURIComponent(_feedLastCreatedAt)}`);
    const posts = await resp.json();
    renderFeed(posts, true);
}

function _fmtCount(n) {
    if (!n) return '';
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    return String(n);
}

function renderFeed(posts, append) {
    const list = document.getElementById('feed-list');
    const empty = document.getElementById('feed-empty');
    const loadMore = document.getElementById('feed-load-more');

    if (!append) list.innerHTML = '';

    if (!posts || posts.length === 0) {
        if (!append) { empty.classList.remove('hidden'); loadMore.classList.add('hidden'); }
        else { loadMore.classList.add('hidden'); }
        return;
    }
    empty.classList.add('hidden');

    for (const p of posts) {
        const el = document.createElement('div');
        el.className = 'feed-post';
        el.dataset.postId = p.id;

        const typeColor = FEED_TYPE_COLORS[p.type] || '#a78bfa';
        const displayName = p.author_display || p.author_handle || '?';
        const initial = displayName[0].toUpperCase();
        const timeAgo = formatTimeAgo(p.created_at);

        // Reshare context
        let ctxHtml = '';
        if (p.type === 'reshare') {
            ctxHtml = `<div class="fp-context"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>${escapeHtml(displayName)} reshared</div>`;
        }

        // Content
        let contentHtml;
        try { contentHtml = typeof marked !== 'undefined' ? marked.parse(p.content) : escapeHtml(p.content); }
        catch { contentHtml = escapeHtml(p.content); }

        // Detail chips
        const det = p.details || {};
        const detKeys = Object.keys(det).filter(k => !['original_author','original_type'].includes(k) && det[k]);
        const detHtml = detKeys.length ? `<div class="fp-details">${detKeys.map(k => `<span class="fp-chip">${escapeHtml(k)}: ${escapeHtml(String(det[k]))}</span>`).join('')}</div>` : '';

        // Quote-tweet
        let qtHtml = '';
        if (p.type === 'reshare' && p.original_post) {
            const o = p.original_post;
            const oc = FEED_TYPE_COLORS[o.type] || '#a78bfa';
            const oi = (o.author_display || o.author_handle || '?')[0].toUpperCase();
            let oContent;
            try { oContent = typeof marked !== 'undefined' ? marked.parse(o.content) : escapeHtml(o.content); }
            catch { oContent = escapeHtml(o.content); }
            qtHtml = `<div class="fp-quote"><div class="fp-quote-head"><div class="fp-quote-av" style="background:${oc}18;color:${oc}">${oi}</div><b>${escapeHtml(o.author_display || o.author_handle)}</b><span class="fp-muted">@${escapeHtml(o.author_handle)} · ${formatTimeAgo(o.created_at)}</span></div><div class="fp-quote-body">${oContent}</div></div>`;
        }

        // Counts
        const rx = p.reactions || {};
        const likes = rx.like || 0;
        const interesting = rx.interesting || 0;
        const helpful = rx.helpful || 0;
        const comments = p.comment_count || 0;

        el.innerHTML = `
            ${ctxHtml}
            <div class="fp-row">
                <div class="fp-av" style="background:${typeColor}12;color:${typeColor}">${initial}</div>
                <div class="fp-body">
                    <div class="fp-head">
                        <div class="fp-names">
                            <span class="fp-name">${escapeHtml(displayName)}</span>
                            <span class="fp-handle">@${escapeHtml(p.author_handle)}</span>
                        </div>
                        <span class="fp-time">${timeAgo}</span>
                    </div>
                    <div class="fp-type" style="color:${typeColor}">${p.type}</div>
                    <div class="fp-content">${contentHtml}</div>
                    ${detHtml}
                    ${qtHtml}
                    <div class="fp-actions">
                        <button class="fp-act fp-act-comment" data-post-id="${p.id}">
                            <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                            <span>${_fmtCount(comments)}</span>
                        </button>
                        <button class="fp-act fp-act-reshare">
                            <svg viewBox="0 0 24 24"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
                            <span></span>
                        </button>
                        <button class="fp-act fp-act-like ${likes ? 'active' : ''}">
                            <svg viewBox="0 0 24 24" ${likes ? 'fill="currentColor"' : ''}><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
                            <span>${_fmtCount(likes)}</span>
                        </button>
                        <button class="fp-act fp-act-bulb ${interesting ? 'active' : ''}">
                            <svg viewBox="0 0 24 24" ${interesting ? 'fill="currentColor"' : ''}><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 1 1 7.072 0l-.548.547A3.374 3.374 0 0 0 14 18.469V19a2 2 0 1 1-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
                            <span>${_fmtCount(interesting)}</span>
                        </button>
                        <button class="fp-act fp-act-check ${helpful ? 'active' : ''}">
                            <svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
                            <span>${_fmtCount(helpful)}</span>
                        </button>
                    </div>
                    <div class="fp-expand-zone" data-post-id="${p.id}"></div>
                </div>
            </div>
        `;
        list.appendChild(el);
        _feedLastCreatedAt = p.created_at;
    }

    loadMore.classList.toggle('hidden', posts.length < 20);
}

function formatTimeAgo(dateStr) {
    try {
        const d = new Date(dateStr + (dateStr.includes('Z') || dateStr.includes('+') ? '' : 'Z'));
        const s = Math.floor((Date.now() - d) / 1000);
        if (s < 60) return 'now';
        if (s < 3600) return `${Math.floor(s / 60)}m`;
        if (s < 86400) return `${Math.floor(s / 3600)}h`;
        if (s < 604800) return `${Math.floor(s / 86400)}d`;
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    } catch { return dateStr; }
}

function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str || '';
    return d.innerHTML;
}

// ─── Expandable post: inline comments ───────────────────────────

async function toggleFeedExpand(postId) {
    const zone = document.querySelector(`.fp-expand-zone[data-post-id="${postId}"]`);
    if (!zone) return;

    // Toggle off
    if (zone.classList.contains('expanded')) {
        zone.classList.remove('expanded');
        zone.innerHTML = '';
        return;
    }

    // Collapse any other open post
    document.querySelectorAll('.fp-expand-zone.expanded').forEach(z => {
        z.classList.remove('expanded');
        z.innerHTML = '';
    });

    zone.classList.add('expanded');
    zone.innerHTML = '<div class="fp-expand-loading"><div class="fp-spinner"></div></div>';

    const resp = await apiFetch(`${API}/feed/${postId}/comments`);
    const comments = await resp.json();

    if (!comments || comments.length === 0) {
        zone.innerHTML = '<div class="fp-expand-empty">No replies yet</div>';
        return;
    }

    zone.innerHTML = '';
    renderInlineComments(comments, zone, 0);
}

function renderInlineComments(clist, container, depth) {
    for (const c of clist) {
        const row = document.createElement('div');
        row.className = 'fp-reply' + (depth > 0 ? ' fp-reply-nested' : '');
        const init = (c.author_display || c.author_handle || '?')[0].toUpperCase();
        row.innerHTML = `
            <div class="fp-reply-av">${init}</div>
            <div class="fp-reply-body">
                <div class="fp-reply-head">
                    <b>${escapeHtml(c.author_display || c.author_handle)}</b>
                    <span class="fp-muted">@${escapeHtml(c.author_handle)} · ${formatTimeAgo(c.created_at)}</span>
                </div>
                <div class="fp-reply-text">${escapeHtml(c.content)}</div>
            </div>
        `;
        container.appendChild(row);
        if (c.replies && c.replies.length > 0) {
            const nested = document.createElement('div');
            nested.className = 'fp-reply-thread';
            renderInlineComments(c.replies, nested, depth + 1);
            container.appendChild(nested);
        }
    }
}

// ─── Feed event delegation ──────────────────────────────────────

document.getElementById('feed-load-more-btn')?.addEventListener('click', loadMoreFeed);

// Feed filter tabs
document.querySelectorAll('.feed-tab[data-sort]').forEach(tab => {
    tab.addEventListener('click', () => loadFeedSorted(tab.dataset.sort));
});

document.addEventListener('click', (e) => {
    // Comment button or click on the post body area
    const commentBtn = e.target.closest('.fp-act-comment');
    if (commentBtn) {
        toggleFeedExpand(commentBtn.dataset.postId);
        return;
    }
    // Clicking on the post content area also expands
    const post = e.target.closest('.feed-post');
    if (post && !e.target.closest('.fp-act') && !e.target.closest('.fp-quote') && !e.target.closest('.fp-expand-zone') && !e.target.closest('a')) {
        toggleFeedExpand(post.dataset.postId);
    }
});

// ─── Integrations Page ──────────────────────────────────────────

let _integrationApps = [];
let _integrationSearchTimer = null;

async function loadIntegrationsPage() {
    loadMssqlStatus();

    const list = document.getElementById('integrations-list');
    const empty = document.getElementById('integrations-empty');
    const loading = document.getElementById('integrations-loading');
    const search = document.getElementById('integrations-search');

    list.innerHTML = '';
    empty.classList.add('hidden');
    loading.classList.remove('hidden');
    if (search) search.value = '';

    try {
        const resp = await apiFetch(`${API}/integrations/apps`);
        if (!resp.ok) throw new Error('Failed to load');
        const data = await resp.json();
        _integrationApps = Array.isArray(data) ? data : (data.items || []);
        renderIntegrations(_integrationApps);
    } catch (e) {
        list.innerHTML = '';
        empty.querySelector('p').textContent = 'Could not load integrations. Check your COMPOSIO_API_KEY.';
        empty.classList.remove('hidden');
    } finally {
        loading.classList.add('hidden');
    }
}

function renderIntegrations(apps) {
    const list = document.getElementById('integrations-list');
    const empty = document.getElementById('integrations-empty');
    list.innerHTML = '';
    if (!apps || apps.length === 0) {
        empty.classList.remove('hidden');
        return;
    }
    empty.classList.add('hidden');
    for (const app of apps) {
        const card = document.createElement('div');
        card.className = 'integration-card';
        const logoUrl = app.logo || '';
        const name = app.displayName || app.name || app.key || '';
        const desc = (app.description || '').slice(0, 120) + ((app.description || '').length > 120 ? '...' : '');
        const categories = app.categories || [];
        const meta = app.meta || {};
        const actionsCount = meta.actionsCount || 0;
        card.innerHTML = `
            <div class="flex items-center gap-3">
                ${logoUrl ? `<img src="${logoUrl}" alt="" class="w-8 h-8 rounded-lg bg-surface border border-border object-contain">` : ''}
                <div class="integration-name">${escHtml(name)}</div>
            </div>
            <div class="integration-desc">${escHtml(desc)}</div>
            <div class="flex flex-wrap gap-1">
                ${categories.slice(0, 3).map(c => `<span class="integration-category-badge">${escHtml(c)}</span>`).join('')}
                ${actionsCount ? `<span class="integration-category-badge">${actionsCount} actions</span>` : ''}
            </div>
        `;
        card.addEventListener('click', () => openIntegrationDetail(app));
        list.appendChild(card);
    }
}

function filterIntegrations(query) {
    if (!query) {
        renderIntegrations(_integrationApps);
        return;
    }
    const q = query.toLowerCase();
    const filtered = _integrationApps.filter(app => {
        const name = (app.displayName || app.name || app.key || '').toLowerCase();
        const desc = (app.description || '').toLowerCase();
        const cats = (app.categories || []).join(' ').toLowerCase();
        return name.includes(q) || desc.includes(q) || cats.includes(q);
    });
    renderIntegrations(filtered);
}

// ─── MS SQL Connector ──────────────────────────────────────────

async function loadMssqlStatus() {
    try {
        const resp = await apiFetch(`${API}/integrations/mssql/config`);
        if (!resp.ok) return;
        const cfg = await resp.json();
        const badge = document.getElementById('mssql-status-badge');
        if (!badge) return;
        if (cfg.configured) {
            badge.textContent = 'Connected';
            badge.className = 'text-xs px-2 py-0.5 rounded-full bg-green-900/40 border border-green-700/50 text-green-400 shrink-0';
        } else {
            badge.textContent = 'Not connected';
            badge.className = 'text-xs px-2 py-0.5 rounded-full bg-surface border border-border text-muted shrink-0';
        }
    } catch (_) {}
}

async function openMssqlModal() {
    const modal = document.getElementById('mssql-modal');
    document.getElementById('mssql-test-result').classList.add('hidden');
    document.getElementById('mssql-remove-btn').classList.add('hidden');
    try {
        const resp = await apiFetch(`${API}/integrations/mssql/config`);
        if (resp.ok) {
            const cfg = await resp.json();
            if (cfg.configured) {
                document.getElementById('mssql-server').value = cfg.server || '';
                document.getElementById('mssql-port').value = cfg.port || 1433;
                document.getElementById('mssql-database').value = cfg.database || '';
                document.getElementById('mssql-username').value = cfg.username || '';
                document.getElementById('mssql-password').value = cfg.password || '';
                document.getElementById('mssql-remove-btn').classList.remove('hidden');
            } else {
                document.getElementById('mssql-server').value = '';
                document.getElementById('mssql-port').value = 1433;
                document.getElementById('mssql-database').value = '';
                document.getElementById('mssql-username').value = '';
                document.getElementById('mssql-password').value = '';
            }
        }
    } catch (_) {}
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function closeMssqlModal() {
    const modal = document.getElementById('mssql-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

async function saveMssqlConfig() {
    const btn = document.getElementById('mssql-save-btn');
    const orig = btn.textContent;
    btn.textContent = 'Saving...';
    btn.disabled = true;
    try {
        const body = {
            server: document.getElementById('mssql-server').value.trim(),
            port: parseInt(document.getElementById('mssql-port').value) || 1433,
            database: document.getElementById('mssql-database').value.trim(),
            username: document.getElementById('mssql-username').value.trim(),
            password: document.getElementById('mssql-password').value,
        };
        const resp = await apiFetch(`${API}/integrations/mssql/config`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await resp.json();
        if (resp.ok && data.ok) {
            _showMssqlResult('Configuration saved.', true);
            document.getElementById('mssql-remove-btn').classList.remove('hidden');
            loadMssqlStatus();
        } else {
            _showMssqlResult(data.error || 'Failed to save.', false);
        }
    } catch (e) {
        _showMssqlResult('Network error.', false);
    } finally {
        btn.textContent = orig;
        btn.disabled = false;
    }
}

async function testMssqlConnection() {
    const btn = document.getElementById('mssql-test-btn');
    const orig = btn.textContent;
    btn.textContent = 'Testing...';
    btn.disabled = true;
    try {
        const body = {
            server: document.getElementById('mssql-server').value.trim(),
            port: parseInt(document.getElementById('mssql-port').value) || 1433,
            database: document.getElementById('mssql-database').value.trim(),
            username: document.getElementById('mssql-username').value.trim(),
            password: document.getElementById('mssql-password').value,
        };
        const resp = await apiFetch(`${API}/integrations/mssql/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await resp.json();
        if (data.ok) {
            _showMssqlResult('✓ ' + data.message, true);
        } else {
            _showMssqlResult('✗ ' + (data.error || 'Connection failed'), false);
        }
    } catch (e) {
        _showMssqlResult('Network error.', false);
    } finally {
        btn.textContent = orig;
        btn.disabled = false;
    }
}

async function removeMssqlConfig() {
    if (!confirm('Remove MS SQL configuration?')) return;
    try {
        await apiFetch(`${API}/integrations/mssql/config`, { method: 'DELETE' });
        closeMssqlModal();
        loadMssqlStatus();
    } catch (_) {}
}

function _showMssqlResult(msg, success) {
    const el = document.getElementById('mssql-test-result');
    el.textContent = msg;
    el.className = `mt-4 p-3 rounded-lg text-sm ${success
        ? 'bg-green-900/30 border border-green-700/40 text-green-300'
        : 'bg-red-900/30 border border-red-700/40 text-red-300'}`;
    el.classList.remove('hidden');
}

async function openIntegrationDetail(app) {
    const modal = document.getElementById('integration-detail-modal');
    const logo = document.getElementById('integration-detail-logo');
    const name = document.getElementById('integration-detail-name');
    const desc = document.getElementById('integration-detail-desc');
    const cats = document.getElementById('integration-detail-categories');
    const auth = document.getElementById('integration-detail-auth');
    const authSection = document.getElementById('integration-detail-auth-section');
    const actions = document.getElementById('integration-detail-actions');
    const actionsLoading = document.getElementById('integration-detail-actions-loading');

    name.textContent = app.displayName || app.name || app.key || '';
    desc.textContent = app.description || '';
    if (app.logo) {
        logo.src = app.logo;
        logo.classList.remove('hidden');
    } else {
        logo.classList.add('hidden');
    }

    cats.innerHTML = '';
    (app.categories || []).forEach(c => {
        const badge = document.createElement('span');
        badge.className = 'integration-category-badge';
        badge.textContent = c;
        cats.appendChild(badge);
    });

    // Auth — from list data we may not have schemes yet, populate from no_auth flag for now
    authSection.classList.add('hidden');
    auth.innerHTML = '';

    // Show modal
    modal.classList.remove('hidden');
    modal.style.display = 'flex';

    // Load detail (includes auth_schemes and meta)
    actions.innerHTML = '';
    actionsLoading.classList.remove('hidden');
    try {
        const slug = app.key || app.name;
        const resp = await apiFetch(`${API}/integrations/apps/${encodeURIComponent(slug)}`);
        if (resp.ok) {
            const detail = await resp.json();

            // Populate auth schemes from detail
            const authSchemes = detail.auth_schemes || [];
            if (authSchemes.length > 0) {
                authSection.classList.remove('hidden');
                auth.innerHTML = '';
                authSchemes.forEach(s => {
                    const badge = document.createElement('span');
                    badge.className = 'integration-auth-badge';
                    badge.textContent = s.auth_mode || s.mode || 'Unknown';
                    auth.appendChild(badge);
                });
            } else if (detail.no_auth) {
                authSection.classList.remove('hidden');
                auth.innerHTML = '<span class="integration-auth-badge">No Auth</span>';
            }

            // Show action/trigger counts + test connectors
            actions.innerHTML = '';
            const meta = detail.meta || {};
            const actionsCount = meta.actionsCount || 0;
            const triggersCount = meta.triggersCount || 0;
            const testConnectors = detail.testConnectors || [];

            if (actionsCount > 0 || triggersCount > 0) {
                const summary = document.createElement('div');
                summary.className = 'integration-action-item';
                summary.innerHTML = `
                    <div class="text-sm text-white font-medium">Capabilities</div>
                    <div class="text-xs text-muted">${actionsCount} actions, ${triggersCount} triggers available</div>
                `;
                actions.appendChild(summary);
            }

            if (testConnectors.length > 0) {
                testConnectors.forEach(tc => {
                    const item = document.createElement('div');
                    item.className = 'integration-action-item';
                    item.innerHTML = `
                        <div class="text-sm text-white font-medium">${escHtml(tc.name || tc.id || '')}</div>
                        <div class="text-xs text-muted">Auth: ${escHtml(tc.authScheme || 'N/A')}</div>
                    `;
                    actions.appendChild(item);
                });
            }

            if (actionsCount === 0 && triggersCount === 0 && testConnectors.length === 0) {
                actions.innerHTML = '<div class="text-sm text-muted">No actions available.</div>';
            }
        } else {
            actions.innerHTML = '<div class="text-sm text-muted">Could not load details.</div>';
        }
    } catch {
        actions.innerHTML = '<div class="text-sm text-muted">Could not load details.</div>';
    } finally {
        actionsLoading.classList.add('hidden');
    }
}

function closeIntegrationModal() {
    const modal = document.getElementById('integration-detail-modal');
    modal.classList.add('hidden');
    modal.style.display = '';
}

// Integration modal close handlers
document.getElementById('integration-detail-close')?.addEventListener('click', closeIntegrationModal);
document.getElementById('integration-detail-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'integration-detail-modal') closeIntegrationModal();
});

// Integration search
const _intSearch = document.getElementById('integrations-search');
if (_intSearch) {
    _intSearch.addEventListener('input', () => {
        const q = _intSearch.value.trim();
        if (_integrationSearchTimer) clearTimeout(_integrationSearchTimer);
        _integrationSearchTimer = setTimeout(() => filterIntegrations(q), 200);
    });
}

// ─── Memory Page ────────────────────────────────────────────────
const memoryList = document.getElementById('memory-list');
const memoryEmpty = document.getElementById('memory-empty');
const memorySearch = document.getElementById('memory-search');
const memoryFilterType = document.getElementById('memory-filter-type');
const memoryFilterVisibility = document.getElementById('memory-filter-visibility');
let memorySearchTimer = null;

const MEMORY_TYPE_COLORS = {
    note: '#a78bfa',
    preference: '#f0c27b',
    purchase: '#34d399',
    recommendation: '#22d3ee',
    review: '#fb7185',
    research: '#60a5fa',
    inquiry: '#c084fc',
};

function renderMemory(entries) {
    memoryList.innerHTML = '';
    if (!entries || entries.length === 0) {
        memoryEmpty.classList.remove('hidden');
        return;
    }
    memoryEmpty.classList.add('hidden');
    for (const entry of entries) {
        const typeColor = MEMORY_TYPE_COLORS[entry.type] || '#a78bfa';
        const visClass = entry.visibility === 'sharable' ? 'sharable' : 'personal';
        const div = document.createElement('div');
        div.className = 'memory-card';
        div.dataset.id = entry.id;
        div.innerHTML = `
            <div class="memory-card-header">
                <span class="memory-type" style="color:${typeColor};border-color:${typeColor}33;background:${typeColor}18">${escHtml(entry.type)}</span>
                <span class="memory-visibility ${visClass}">${escHtml(entry.visibility)}</span>
            </div>
            <div class="memory-summary">${escHtml(entry.summary || '')}</div>
            ${entry.sentiment && entry.sentiment !== 'neutral'
                ? `<div class="memory-sentiment">${escHtml(entry.sentiment)}</div>`
                : ''}
            ${entry.contacts_involved && entry.contacts_involved.length
                ? `<div class="memory-contacts">${entry.contacts_involved.map(c => `<span>${escHtml(c)}</span>`).join('')}</div>`
                : ''}
            ${entry.details && entry.details.source_url
                ? `<div class="memory-source">from URL</div>`
                : ''}
            <div class="memory-card-footer">
                <span class="memory-time">${escHtml(formatHistoryTime(entry.timestamp))}</span>
                <span class="memory-actions">
                    <button class="memory-edit-action" data-id="${entry.id}">Edit</button>
                    <button class="memory-delete-action" data-id="${entry.id}">Delete</button>
                </span>
            </div>
        `;
        memoryList.appendChild(div);
    }

    // Wire edit/delete buttons
    memoryList.querySelectorAll('.memory-edit-action').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const id = btn.dataset.id;
            const card = btn.closest('.memory-card');
            const entry = entries.find(en => String(en.id) === id);
            if (!entry) return;
            openMemoryEditModal(entry);
        });
    });
    memoryList.querySelectorAll('.memory-delete-action').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const id = btn.dataset.id;
            if (!confirm('Delete this memory?')) return;
            await apiFetch(`${API}/history/${id}`, { method: 'DELETE' });
            await loadMemoryPage();
        });
    });
}

async function loadMemoryPage() {
    const q = memorySearch ? memorySearch.value.trim() : '';
    const type = memoryFilterType ? memoryFilterType.value : '';
    const vis = memoryFilterVisibility ? memoryFilterVisibility.value : '';
    let url = `${API}/history?`;
    if (q) url += `q=${encodeURIComponent(q)}&`;
    if (type) url += `type=${encodeURIComponent(type)}&`;
    if (vis) url += `visibility=${encodeURIComponent(vis)}&`;
    const resp = await apiFetch(url);
    const entries = await resp.json();
    renderMemory(entries);
}

// Filter change handlers
if (memoryFilterType) {
    memoryFilterType.addEventListener('change', () => loadMemoryPage());
}
if (memoryFilterVisibility) {
    memoryFilterVisibility.addEventListener('change', () => loadMemoryPage());
}
if (memorySearch) {
    memorySearch.addEventListener('input', () => {
        if (memorySearchTimer) clearTimeout(memorySearchTimer);
        memorySearchTimer = setTimeout(() => loadMemoryPage(), 250);
    });
}

// ─── Memory Add Modal ───────────────────────────────────────────
function openMemoryModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) { modal.classList.remove('hidden'); modal.style.display = 'flex'; }
}
function closeMemoryModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) { modal.classList.add('hidden'); modal.style.display = ''; }
}

const memoryAddBtn = document.getElementById('memory-add-btn');
const memoryAddSave = document.getElementById('memory-add-save');
const memoryAddCancel = document.getElementById('memory-add-cancel');
if (memoryAddBtn) {
    memoryAddBtn.addEventListener('click', () => {
        document.getElementById('memory-add-summary').value = '';
        document.getElementById('memory-add-type').value = 'note';
        document.getElementById('memory-add-visibility').value = 'personal';
        document.getElementById('memory-add-sentiment').value = 'neutral';
        document.getElementById('memory-add-error').classList.add('hidden');
        openMemoryModal('memory-add-modal');
    });
}
if (memoryAddCancel) {
    memoryAddCancel.addEventListener('click', () => closeMemoryModal('memory-add-modal'));
}
if (memoryAddSave) {
    memoryAddSave.addEventListener('click', async () => {
        const summary = document.getElementById('memory-add-summary').value.trim();
        if (!summary) {
            const err = document.getElementById('memory-add-error');
            err.textContent = 'Please enter a summary.';
            err.classList.remove('hidden');
            return;
        }
        memoryAddSave.disabled = true;
        try {
            await apiFetch(`${API}/history`, {
                method: 'POST',
                body: JSON.stringify({
                    summary,
                    type: document.getElementById('memory-add-type').value,
                    visibility: document.getElementById('memory-add-visibility').value,
                    sentiment: document.getElementById('memory-add-sentiment').value,
                }),
            });
            closeMemoryModal('memory-add-modal');
            await loadMemoryPage();
        } catch (e) {
            const err = document.getElementById('memory-add-error');
            err.textContent = 'Failed to save memory.';
            err.classList.remove('hidden');
        } finally {
            memoryAddSave.disabled = false;
        }
    });
}

// ─── Memory Edit Modal ──────────────────────────────────────────
function openMemoryEditModal(entry) {
    document.getElementById('memory-edit-id').value = entry.id;
    document.getElementById('memory-edit-summary').value = entry.summary || '';
    document.getElementById('memory-edit-type').value = entry.type || 'note';
    document.getElementById('memory-edit-visibility').value = entry.visibility || 'personal';
    document.getElementById('memory-edit-error').classList.add('hidden');
    openMemoryModal('memory-edit-modal');
}
const memoryEditCancel = document.getElementById('memory-edit-cancel');
const memoryEditSave = document.getElementById('memory-edit-save');
if (memoryEditCancel) {
    memoryEditCancel.addEventListener('click', () => closeMemoryModal('memory-edit-modal'));
}
if (memoryEditSave) {
    memoryEditSave.addEventListener('click', async () => {
        const id = document.getElementById('memory-edit-id').value;
        const body = {
            summary: document.getElementById('memory-edit-summary').value.trim(),
            type: document.getElementById('memory-edit-type').value,
            visibility: document.getElementById('memory-edit-visibility').value,
        };
        if (!body.summary) {
            const err = document.getElementById('memory-edit-error');
            err.textContent = 'Summary cannot be empty.';
            err.classList.remove('hidden');
            return;
        }
        memoryEditSave.disabled = true;
        try {
            await apiFetch(`${API}/history/${id}`, {
                method: 'PATCH',
                body: JSON.stringify(body),
            });
            closeMemoryModal('memory-edit-modal');
            await loadMemoryPage();
        } catch (e) {
            const err = document.getElementById('memory-edit-error');
            err.textContent = 'Failed to update memory.';
            err.classList.remove('hidden');
        } finally {
            memoryEditSave.disabled = false;
        }
    });
}

// ─── Memory URL Extract Modal ───────────────────────────────────
const memoryExtractBtn = document.getElementById('memory-extract-btn');
const memoryUrlCancel = document.getElementById('memory-url-cancel');
const memoryUrlExtract = document.getElementById('memory-url-extract');
if (memoryExtractBtn) {
    memoryExtractBtn.addEventListener('click', () => {
        document.getElementById('memory-url-input').value = '';
        document.getElementById('memory-url-context').value = '';
        document.getElementById('memory-url-error').classList.add('hidden');
        document.getElementById('memory-url-status').classList.add('hidden');
        openMemoryModal('memory-url-modal');
    });
}
if (memoryUrlCancel) {
    memoryUrlCancel.addEventListener('click', () => closeMemoryModal('memory-url-modal'));
}
if (memoryUrlExtract) {
    memoryUrlExtract.addEventListener('click', async () => {
        const url = document.getElementById('memory-url-input').value.trim();
        if (!url) {
            const err = document.getElementById('memory-url-error');
            err.textContent = 'Please enter a URL.';
            err.classList.remove('hidden');
            return;
        }
        memoryUrlExtract.disabled = true;
        document.getElementById('memory-url-error').classList.add('hidden');
        document.getElementById('memory-url-status').classList.remove('hidden');
        try {
            const resp = await apiFetch(`${API}/history/extract-url`, {
                method: 'POST',
                body: JSON.stringify({
                    url,
                    context: document.getElementById('memory-url-context').value.trim(),
                }),
            });
            const data = await resp.json();
            document.getElementById('memory-url-status').textContent = `Extracted ${data.count} facts!`;
            setTimeout(() => {
                closeMemoryModal('memory-url-modal');
                loadMemoryPage();
            }, 1000);
        } catch (e) {
            document.getElementById('memory-url-status').classList.add('hidden');
            const err = document.getElementById('memory-url-error');
            err.textContent = 'Failed to extract facts from URL.';
            err.classList.remove('hidden');
        } finally {
            memoryUrlExtract.disabled = false;
        }
    });
}

// ─── Sessions ───────────────────────────────────────────────────
async function loadSessions() {
    const resp = await apiFetch(`${API}/sessions`);
    const sessions = await resp.json();
    sessionsList.innerHTML = '';
    if (sessions.length === 0) {
        sessionsList.innerHTML = '<div class="text-xs text-muted px-3 py-2">No sessions yet</div>';
        return sessions;
    }
    for (const s of sessions) {
        const div = document.createElement('div');
        div.className = `session-item px-3 py-2 rounded-lg text-sm flex items-center justify-between group ${s.id === currentSessionId ? 'active' : ''}`;
        div.innerHTML = `
            <span class="truncate flex-1">${escHtml(s.title)}</span>
            <button class="delete-session opacity-0 group-hover:opacity-100 text-muted hover:text-red-400 ml-2 text-xs" data-id="${s.id}">&times;</button>
        `;
        div.addEventListener('click', (e) => {
            if (e.target.classList.contains('delete-session')) return;
            selectSession(s.id, s.title);
        });
        div.querySelector('.delete-session').addEventListener('click', async (e) => {
            e.stopPropagation();
            await apiFetch(`${API}/sessions/${s.id}`, { method: 'DELETE' });
            if (currentSessionId === s.id) {
                currentSessionId = null;
                chatMessages.innerHTML = '';
                chatSessionTitle.textContent = '';
                showEmptyState();
                resetSessionAgents();
            }
            await loadSessions();
        });
        sessionsList.appendChild(div);
    }
    return sessions;
}

async function selectSession(id, title) {
    showPage('chat');
    currentSessionId = id;
    chatSessionTitle.textContent = title || 'Chat';

    lastToolCallKey = null;
    lastFinalizedText = '';
    resetChatColors();
    resetSessionAgents();
    pendingToolCards = [];
    pendingAgentExchanges = [];

    const resp = await apiFetch(`${API}/sessions/${id}`);
    const session = await resp.json();
    chatMessages.innerHTML = '';
    chatReasoning.innerHTML = '';
    replayEvents = [];
    replayIndex = 0;
    toolEventCounter = 0;
    currentTurnContainer = null;
    currentTurnAssistant = null;
    currentThinkingBlock = null;
    setChatTab('chat');

    const messages = session.messages || [];
    if (messages.length === 0) {
        showEmptyState();
    } else {
        showActiveState();
        for (const msg of messages) {
            if (msg.role === 'user') {
                appendUserBubble(msg.content);
                replayEvents.push({ type: 'user', text: msg.content });
            } else if (msg.role === 'assistant') {
                try {
                    const meta = JSON.parse(msg.metadata_json);
                    if (meta.type === 'function_call') {
                        appendToolActivity(meta, chatReasoning);
                        trackAgentFromToolCall(meta);
                        replayEvents.push({ type: 'tool_call', payload: meta });
                    } else if (meta.type === 'function_response') {
                        completeToolActivity(meta, chatReasoning);
                        trackAgentResponse(meta);
                        replayEvents.push({ type: 'tool_response', payload: meta });
                    } else {
                        appendAgentBubble(msg.content, msg.author);
                        replayEvents.push({ type: 'assistant', text: msg.content, author: msg.author });
                    }
                } catch {
                    appendAgentBubble(msg.content, msg.author);
                    replayEvents.push({ type: 'assistant', text: msg.content, author: msg.author });
                }
            }
        }
        scrollToBottom(chatMessages);
        scrollToBottom(chatReasoning);
        replayIndex = replayEvents.length;
        updateReplayControls();
    }

    // Close sessions sidebar after selection
    toggleSessionsSidebar(false);
    await loadSessions();
}

async function createNewChat() {
    const sessions = await loadSessions();
    for (const s of sessions) {
        if ((s.title || '') === 'New Chat') {
            const resp = await apiFetch(`${API}/sessions/${s.id}`);
            const full = await resp.json();
            if ((full.messages || []).length === 0) {
                await selectSession(s.id, s.title);
                return;
            }
        }
    }
    const resp = await apiFetch(`${API}/sessions`, {
        method: 'POST',
        body: JSON.stringify({}),
    });
    const session = await resp.json();
    await loadSessions();
    await selectSession(session.id, session.title);
}

newChatBtn.addEventListener('click', createNewChat);
newChatHeaderBtn.addEventListener('click', createNewChat);

// ─── Chat ───────────────────────────────────────────────────────
async function sendChatMessage(message) {
    if (!message || !currentSessionId || isStreaming) return;

    lastToolCallKey = null;
    lastFinalizedText = '';
    appendUserBubble(message);
    replayEvents.push({ type: 'user', text: message });
    scrollToBottom();

    isStreaming = true;
    sendBtn.disabled = true;
    chatInput.disabled = true;

    const agentName = currentUser?.handle || 'Agent';
    const agentColor = getChatColor(agentName);
    const loadingEl = createTypingIndicator(agentName, agentColor);
    if (currentTurnAssistant) {
        currentTurnAssistant.appendChild(loadingEl);
    } else {
        chatMessages.appendChild(loadingEl);
    }
    scrollToBottom(chatMessages);

    try {
        const token = getToken();
        const resp = await fetch(`${API}/chat/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify({ session_id: currentSessionId, message }),
        });

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let loadingRemoved = false;
        currentResponseText = '';
        let currentAgentBubble = null;
        narrationBuffer = '';
        lastSseEventType = '';
        hadToolCallInTurn = false;
        responsePhaseActive = false;
        lastToolResponseSeen = false;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const jsonStr = line.slice(6).trim();
                if (!jsonStr) continue;

                let payload;
                try { payload = JSON.parse(jsonStr); } catch { continue; }

                if (!loadingRemoved) {
                    const el = document.getElementById('loading-indicator');
                    if (el) el.remove();
                    loadingRemoved = true;
                }

                if (payload.type === 'text') {
                    if (payload.partial) {
                        // Partial = streaming delta — accumulate chunks
                        if (hadToolCallInTurn && !lastToolResponseSeen) {
                            narrationBuffer += payload.content || '';
                        } else {
                            currentResponseText += payload.content || '';
                        }
                    } else {
                        // Non-partial = complete final text — use as-is
                        if (hadToolCallInTurn && !lastToolResponseSeen) {
                            narrationBuffer = payload.content || narrationBuffer;
                        } else {
                            currentResponseText = payload.content || currentResponseText;
                        }
                    }
                } else if (payload.type === 'function_call') {
                    const created = appendToolActivity(payload, chatReasoning);
                    hadToolCallInTurn = true;
                    lastToolResponseSeen = false;
                    if (narrationBuffer) {
                        if (created) attachNarrationToAction(created, narrationBuffer);
                        else attachNarrationToLastAction(narrationBuffer);
                        narrationBuffer = '';
                    }
                    trackAgentFromToolCall(payload);
                    replayEvents.push({ type: 'tool_call', payload });
                } else if (payload.type === 'function_response') {
                    completeToolActivity(payload, chatReasoning);
                    lastToolResponseSeen = true;
                    trackAgentResponse(payload);
                    replayEvents.push({ type: 'tool_response', payload });
                } else if (payload.type === 'done') {
                    if (narrationBuffer) {
                        attachNarrationToLastAction(narrationBuffer);
                        narrationBuffer = '';
                    }
                    if (currentResponseText) {
                        if (!currentAgentBubble) {
                            currentAgentBubble = createAgentBubble(payload.author);
                        }
                        let finalText = currentResponseText;
                        if (hadToolCallInTurn && lastToolResponseSeen) {
                            const parts = currentResponseText
                                .split(/\n\s*\n/)
                                .map(p => p.trim())
                                .filter(Boolean);
                            if (parts.length > 1) {
                                const reasoningText = parts.slice(0, -1).join('\n\n');
                                attachNarrationToLastAction(reasoningText);
                                finalText = parts[parts.length - 1];
                            }
                        }
                        streamTextToBubble(currentAgentBubble, finalText, () => {
                            replayEvents.push({ type: 'assistant', text: finalText, author: payload.author });
                        });
                    }
                    currentResponseText = '';
                    responsePhaseActive = false;
                    lastToolResponseSeen = false;
                    finalizeThinkingBlock();
                    currentThinkingBlock = null;
                }
                lastSseEventType = payload.type;
                if (payload.type === 'function_call' || payload.type === 'function_response') {
                    scrollToBottom(chatReasoning);
                } else {
                    scrollToBottom(chatMessages);
                }
            }
        }
    } catch (err) {
        const el = document.getElementById('loading-indicator');
        if (el) el.remove();
        appendSystemMessage('Connection error: ' + err.message);
    }

    isStreaming = false;
    sendBtn.disabled = false;
    chatInput.disabled = false;
    chatInput.focus();
    await loadSessions();
    replayIndex = replayEvents.length;
    updateReplayControls();
}

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;
    chatInput.value = '';
    await sendChatMessage(message);
});

chatFormCentered.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = chatInputCentered.value.trim();
    if (!message) return;
    chatInputCentered.value = '';
    autoResizeTextarea(chatInputCentered);
    showActiveState();
    await sendChatMessage(message);
});

// Welcome prompt chips
document.querySelectorAll('.welcome-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
        const prompt = chip.getAttribute('data-prompt') || '';
        if (!prompt) return;
        chatInputCentered.value = prompt;
        autoResizeTextarea(chatInputCentered);
        sendBtnCentered.disabled = false;
        chatInputCentered.focus();
    });
});

const welcomeIntegrationsBtn = document.getElementById('welcome-integrations-btn');
if (welcomeIntegrationsBtn) {
    welcomeIntegrationsBtn.addEventListener('click', () => {
        showPage('integrations');
    });
}

function autoResizeTextarea(el) {
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
}

if (chatInputCentered) {
    chatInputCentered.addEventListener('input', () => autoResizeTextarea(chatInputCentered));
    chatInputCentered.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatFormCentered.dispatchEvent(new Event('submit', { cancelable: true }));
        }
    });
}

// ─── Bubble Renderers ───────────────────────────────────────────
function createThinkingBlock() {
    const block = document.createElement('div');
    block.className = 'chat-thinking-card collapsed hidden';
    block.dataset.thinkingId = `thinking-${currentSessionId || 'session'}-${toolEventCounter}`;
    block.dataset.pendingCount = '0';
    block.innerHTML = `
        <button class="thinking-header" type="button" aria-expanded="false">
            <div class="thinking-title-row">
                <div class="thinking-title">Reviewed 0 actions</div>
                <div class="thinking-caret">▾</div>
            </div>
            <div class="thinking-subtitle">Tool calls and agent interactions</div>
            <div class="thinking-status-row">
                <span class="thinking-status">Idle</span>
                <span class="thinking-spinner"></span>
            </div>
        </button>
        <div class="thinking-body hidden">
            <div class="thinking-empty">No actions yet.</div>
            <div class="thinking-timeline"></div>
        </div>
    `;
    const toggle = block.querySelector('.thinking-header');
    const body = block.querySelector('.thinking-body');
    const caret = block.querySelector('.thinking-caret');
    const timeline = block.querySelector('.thinking-timeline');
    const empty = block.querySelector('.thinking-empty');
    toggle.addEventListener('click', () => {
        const isCollapsed = block.classList.toggle('collapsed');
        if (body) body.classList.toggle('hidden', !isCollapsed ? false : true);
        if (caret) caret.textContent = isCollapsed ? '▾' : '▴';
        toggle.setAttribute('aria-expanded', String(!isCollapsed));
        if (!isCollapsed && empty && empty.dataset.hasItems === 'true') {
            empty.classList.add('hidden');
        }
        if (timeline) timeline.classList.toggle('hidden', isCollapsed);
    });
    return block;
}

function createTurnContainer() {
    const turn = document.createElement('div');
    turn.className = 'chat-turn';
    const assistantWrap = document.createElement('div');
    assistantWrap.className = 'chat-turn-assistant';
    turn.appendChild(assistantWrap);
    return { turn, assistantWrap };
}

function appendUserBubble(text) {
    const { turn, assistantWrap } = createTurnContainer();
    currentTurnContainer = turn;
    currentTurnAssistant = assistantWrap;
    turn.insertBefore(createUserBubble(text), assistantWrap);
    const thinkingBlock = createThinkingBlock();
    turn.insertBefore(thinkingBlock, assistantWrap);
    currentThinkingBlock = thinkingBlock;
    chatMessages.appendChild(turn);
    scrollToBottom(chatMessages);
}

function createAgentBubble(author) {
    const name = (author && author !== 'agent') ? author : (currentUser?.handle || 'Agent');
    const color = getChatColor(name);
    const bubble = createColoredBubble(name, null, color, false);
    if (currentTurnAssistant) {
        currentTurnAssistant.appendChild(bubble);
    }
    return bubble;
}

function appendAgentBubble(text, author) {
    if (!text) return;
    const name = (author && author !== 'agent') ? author : (currentUser?.handle || 'Agent');
    const color = getChatColor(name);
    const bubble = createColoredBubble(name, text, color, false);
    if (currentTurnAssistant) {
        currentTurnAssistant.appendChild(bubble);
    } else {
        chatMessages.appendChild(bubble);
    }
    scrollToBottom(chatMessages);
}

function getToolLabel(name, args) {
    const entry = TOOL_LABELS[name];
    if (entry) return `${entry.icon} ${entry.label(args || {})}`;
    return `\u{1F527} ${name}`;
}

function appendThinkingTimelineItem(payload, eventId) {
    if (!currentThinkingBlock) return;
    if (currentTurnContainer && currentTurnAssistant) {
        if (currentThinkingBlock.nextSibling !== currentTurnAssistant) {
            currentTurnContainer.insertBefore(currentThinkingBlock, currentTurnAssistant);
        }
    }
    currentThinkingBlock.classList.remove('hidden');
    const timeline = currentThinkingBlock.querySelector('.thinking-timeline');
    const empty = currentThinkingBlock.querySelector('.thinking-empty');
    const status = currentThinkingBlock.querySelector('.thinking-status');
    const spinner = currentThinkingBlock.querySelector('.thinking-spinner');
    const title = currentThinkingBlock.querySelector('.thinking-title');
    if (!timeline) return;
    if (empty) {
        empty.dataset.hasItems = 'true';
        empty.classList.add('hidden');
    }
    const pendingCount = Number(currentThinkingBlock.dataset.pendingCount || '0') + 1;
    currentThinkingBlock.dataset.pendingCount = String(pendingCount);
    if (status) status.textContent = 'Running';
    if (spinner) spinner.classList.add('active');
    if (currentThinkingBlock.classList.contains('collapsed')) {
        currentThinkingBlock.classList.remove('collapsed');
        const body = currentThinkingBlock.querySelector('.thinking-body');
        if (body) body.classList.remove('hidden');
        timeline.classList.remove('hidden');
        const caret = currentThinkingBlock.querySelector('.thinking-caret');
        if (caret) caret.textContent = '▴';
    }

    const label = getToolLabel(payload.name, payload.args);
    const item = document.createElement('div');
    item.className = 'thinking-item pending';
    item.dataset.eventId = eventId;
    const kind = payload.name === 'send_message_to_contact' ? 'Agent interaction' : 'Tool call';
    item.innerHTML = `
        <div class="thinking-content">
            <div class="thinking-label">${escHtml(label)}</div>
            <div class="thinking-meta">${escHtml(kind)}</div>
        </div>
        <div class="thinking-actions">
            <span class="thinking-status">Running</span>
        </div>
    `;
    item.addEventListener('click', () => {
        setChatTab('reasoning');
        const target = document.getElementById(eventId);
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'center' });
            target.classList.add('reasoning-highlight');
            setTimeout(() => target.classList.remove('reasoning-highlight'), 1200);
        }
    });
    timeline.appendChild(item);
    if (title) {
        const total = timeline.querySelectorAll('.thinking-item').length;
        title.textContent = `Reviewed ${total} actions`;
    }
    scrollToBottom(chatMessages);
}

function completeThinkingTimelineItem() {
    if (!currentThinkingBlock) return;
    const timeline = currentThinkingBlock.querySelector('.thinking-timeline');
    const status = currentThinkingBlock.querySelector('.thinking-status');
    const spinner = currentThinkingBlock.querySelector('.thinking-spinner');
    if (!timeline) return;
    const item = timeline.querySelector('.thinking-item.pending');
    if (!item) return;
    item.classList.remove('pending');
    item.classList.add('done');
    const itemStatus = item.querySelector('.thinking-status');
    if (itemStatus) itemStatus.textContent = 'Done';
    const pendingCount = Math.max(0, Number(currentThinkingBlock.dataset.pendingCount || '0') - 1);
    currentThinkingBlock.dataset.pendingCount = String(pendingCount);
    const stillPending = timeline.querySelector('.thinking-item.pending');
    if (pendingCount === 0 || !stillPending) {
        if (status) status.textContent = 'Finished';
        if (spinner) spinner.classList.remove('active');
    }
}

// Responses are shown only once at the end; intermediate text stays out of chat.

function finalizeThinkingBlock() {
    if (!currentThinkingBlock) return;
    const status = currentThinkingBlock.querySelector('.thinking-status');
    const spinner = currentThinkingBlock.querySelector('.thinking-spinner');
    const timeline = currentThinkingBlock.querySelector('.thinking-timeline');
    if (status) status.textContent = 'Finished';
    if (spinner) spinner.classList.remove('active');
    if (timeline) {
        currentThinkingBlock.dataset.pendingCount = '0';
        timeline.querySelectorAll('.thinking-item.pending').forEach((item) => {
            item.classList.remove('pending');
            item.classList.add('done');
            const itemStatus = item.querySelector('.thinking-status');
            if (itemStatus) itemStatus.textContent = 'Done';
        });
    }
}

function appendToolActivity(payload, container = chatReasoning) {
    const key = (payload.name || '') + JSON.stringify(payload.args || {});
    if (key === lastToolCallKey) return;
    lastToolCallKey = key;

    const eventId = `tool-${currentSessionId || 'session'}-${toolEventCounter++}`;
    thinkingEventQueue.push(eventId);

    let created = null;
    if (payload.name === 'send_message_to_contact') {
        created = appendAgentExchange(payload, container, eventId);
    } else {
        created = appendToolCard(payload, container, eventId);
    }

    appendThinkingTimelineItem(payload, eventId);
    return created;
}

function appendAgentExchange(payload, container, eventId) {
    const args = payload.args || {};
    const contactName = args.contact_name || args.name || 'contact';
    const outgoingMsg = args.message || '';
    const myAgentName = currentUser?.handle || 'Agent';
    const myColor = getChatColor(myAgentName);
    const contactColor = getChatColor(contactName);

    const div = document.createElement('div');
    div.className = 'agent-exchange reasoning-card';
    div.id = eventId;
    div.setAttribute('data-agent', contactName);
    div.setAttribute('data-tool', 'send_message_to_contact');
    div.setAttribute('data-contact', contactName);

    // My agent's outgoing bubble (small)
    const myAvatar = createColoredAvatar(myAgentName, myColor, 'sm');
    const header = document.createElement('div');
    header.className = 'flex items-center gap-2 mb-1';
    header.appendChild(myAvatar);
    const headerLabel = document.createElement('span');
    headerLabel.className = 'text-xs font-medium';
    headerLabel.style.color = myColor.text;
    headerLabel.textContent = myAgentName;
    header.appendChild(headerLabel);
    const arrow = document.createElement('span');
    arrow.className = 'text-xs text-gray-500';
    arrow.textContent = '\u2192';
    header.appendChild(arrow);
    const targetLabel = document.createElement('span');
    targetLabel.className = 'text-xs font-medium';
    targetLabel.style.color = contactColor.text;
    targetLabel.textContent = contactName;
    header.appendChild(targetLabel);
    div.appendChild(header);

    // Thread area with request/response
    const thread = document.createElement('div');
    thread.className = 'exchange-thread';

    const requestBlock = document.createElement('div');
    requestBlock.className = 'exchange-block';
    requestBlock.innerHTML = `<div class="exchange-label">Request</div>`;
    if (outgoingMsg) {
        const sent = document.createElement('div');
        sent.className = 'exchange-sent-mini';
        sent.textContent = outgoingMsg;
        requestBlock.appendChild(sent);
    }
    thread.appendChild(requestBlock);

    const connecting = document.createElement('div');
    connecting.className = 'exchange-connecting';
    connecting.innerHTML = `<span style="background:${contactColor.dot}"></span><span style="background:${contactColor.dot}"></span><span style="background:${contactColor.dot}"></span>`;
    thread.appendChild(connecting);

    const responseBlock = document.createElement('div');
    responseBlock.className = 'exchange-block response';
    responseBlock.innerHTML = `<div class="exchange-label">Response</div>`;
    const replyArea = document.createElement('div');
    replyArea.className = 'exchange-reply-bubble';
    replyArea.textContent = 'Waiting for response...';
    responseBlock.appendChild(replyArea);
    thread.appendChild(responseBlock);

    div.appendChild(thread);
    const narration = document.createElement('div');
    narration.className = 'exchange-narration hidden';
    narration.innerHTML = `<div class="exchange-label">Reasoning</div><div class="exchange-narration-text"></div>`;
    div.insertBefore(narration, thread);
    const label = document.createElement('div');
    label.className = 'reasoning-checkpoint';
    label.textContent = 'Agent Interaction';
    container.appendChild(label);

    container.appendChild(div);
    pendingAgentExchanges.push(div);
    if (container === chatReasoning) {
        scrollToBottom(container);
    }
    return div;
}

function appendToolCard(payload, container, eventId) {
    const label = getToolLabel(payload.name, payload.args);
    const agentColor = getChatColor(currentUser?.handle || 'Agent');
    const div = document.createElement('div');
    div.className = 'reasoning-card';
    div.id = eventId;
    div.setAttribute('data-tool', payload.name || '');

    const checkpoint = document.createElement('div');
    checkpoint.className = 'reasoning-checkpoint';
    checkpoint.textContent = 'Tool Call';

    div.innerHTML = `
        <div class="reasoning-header">
            <div class="reasoning-icon" style="background:${agentColor.bg}; border-color:${agentColor.border}; color:${agentColor.text}">
                \u{1F527}
            </div>
            <div class="reasoning-title">
                <div class="reasoning-label">${escHtml(label)}</div>
                <div class="reasoning-meta">${escHtml(payload.name || 'tool')}</div>
            </div>
            <div class="reasoning-status pending">Running</div>
        </div>
        <div class="reasoning-body">
            <div class="reasoning-section narration hidden">
                <div class="reasoning-section-title">Reasoning</div>
                <div class="reasoning-narration-text text-sm text-gray-300 whitespace-pre-wrap"></div>
            </div>
            <div class="reasoning-section">
                <div class="reasoning-section-title">Arguments</div>
                <pre class="reasoning-code">${escHtml(JSON.stringify(payload.args || {}, null, 2))}</pre>
            </div>
            <div class="reasoning-section response hidden">
                <div class="reasoning-section-title">Response</div>
                <pre class="reasoning-code response-text"></pre>
            </div>
        </div>
    `;

    container.appendChild(checkpoint);
    container.appendChild(div);
    pendingToolCards.push(div);
    if (container === chatReasoning) {
        scrollToBottom(container);
    }
    return div;
}

function attachNarrationToLastAction(text) {
    const trimmed = text.trim();
    if (!trimmed) return;
    const lastTool = pendingToolCards[pendingToolCards.length - 1];
    const lastExchange = pendingAgentExchanges[pendingAgentExchanges.length - 1];
    const target = lastExchange || lastTool;
    if (!target) return;

    if (target.classList.contains('agent-exchange')) {
        const narr = target.querySelector('.exchange-narration');
        const textEl = target.querySelector('.exchange-narration-text');
        if (narr && textEl) {
            textEl.textContent = trimmed;
            narr.classList.remove('hidden');
        }
        return;
    }

    const section = target.querySelector('.reasoning-section.narration');
    const textEl = target.querySelector('.reasoning-narration-text');
    if (section && textEl) {
        textEl.textContent = trimmed;
        section.classList.remove('hidden');
    }
}

function attachNarrationToAction(target, text) {
    if (!target) return;
    const trimmed = text.trim();
    if (!trimmed) return;

    const eventId = target.id || target.dataset.eventId;
    if (eventId && currentThinkingBlock) {
        const item = currentThinkingBlock.querySelector(`.thinking-item[data-event-id="${eventId}"]`);
        if (item) {
            let note = item.querySelector('.thinking-note');
            if (!note) {
                note = document.createElement('div');
                note.className = 'thinking-note';
                const content = item.querySelector('.thinking-content');
                if (content) content.appendChild(note);
            }
            note.textContent = trimmed;
        }
    }

    if (target.classList.contains('agent-exchange')) {
        const narr = target.querySelector('.exchange-narration');
        const textEl = target.querySelector('.exchange-narration-text');
        if (narr && textEl) {
            textEl.textContent = trimmed;
            narr.classList.remove('hidden');
        }
        return;
    }

    const section = target.querySelector('.reasoning-section.narration');
    const textEl = target.querySelector('.reasoning-narration-text');
    if (section && textEl) {
        textEl.textContent = trimmed;
        section.classList.remove('hidden');
    }
}

function extractCleanResponse(responseText) {
    let clean = responseText;
    try {
        const parsed = JSON.parse(responseText);
        if (parsed.result?.artifacts?.[0]?.parts?.[0]?.text) {
            clean = parsed.result.artifacts[0].parts[0].text;
        } else if (parsed.text) {
            clean = parsed.text;
        } else if (typeof parsed === 'string') {
            clean = parsed;
        }
    } catch { /* use raw text */ }
    return clean;
}

function completeToolActivity(payload, container = chatReasoning) {
    if (payload.name === 'send_message_to_contact' && pendingAgentExchanges.length > 0) {
        const lastExchange = pendingAgentExchanges.shift();
        const responseText = payload.response || '';
        const cleanResponse = extractCleanResponse(responseText);
        const truncated = cleanResponse;

        const contactName = lastExchange.getAttribute('data-contact') || 'contact';
        const contactColor = getChatColor(contactName);

        const replyArea = lastExchange.querySelector('.exchange-reply-bubble');
        if (replyArea) {
            replyArea.innerHTML = '';
            const avatar = createColoredAvatar(contactName, contactColor, 'sm');
            replyArea.appendChild(avatar);
            const replyBubble = document.createElement('div');
            replyBubble.className = 'msg-bubble-colored px-3 py-2 text-sm whitespace-pre-wrap text-gray-200';
            replyBubble.style.backgroundColor = contactColor.bg;
            replyBubble.style.borderColor = contactColor.border;
            replyBubble.textContent = truncated || 'No response captured.';
            replyArea.appendChild(replyBubble);
        }
        lastExchange.classList.add('completed');
    } else if (payload.name === 'send_message_to_contact') {
        const exchanges = container.querySelectorAll('.agent-exchange:not(.completed)');
        const lastExchange = exchanges[exchanges.length - 1];
        if (lastExchange) {
            const responseText = payload.response || '';
            const cleanResponse = extractCleanResponse(responseText);
            const truncated = cleanResponse.length > 500 ? cleanResponse.slice(0, 500) + '...' : cleanResponse;
            const contactName = lastExchange.getAttribute('data-contact') || 'contact';
            const contactColor = getChatColor(contactName);
            const replyArea = lastExchange.querySelector('.exchange-reply-bubble');
            if (replyArea) {
                replyArea.innerHTML = '';
                const avatar = createColoredAvatar(contactName, contactColor, 'sm');
                replyArea.appendChild(avatar);
                const replyBubble = document.createElement('div');
                replyBubble.className = 'msg-bubble-colored px-3 py-2 text-sm whitespace-pre-wrap text-gray-200';
                replyBubble.style.backgroundColor = contactColor.bg;
                replyBubble.style.borderColor = contactColor.border;
                replyBubble.textContent = truncated || 'No response captured.';
                replyArea.appendChild(replyBubble);
            }
            lastExchange.classList.add('completed');
        }
    } else if (pendingToolCards.length > 0) {
        const lastCard = pendingToolCards.shift();
        lastCard.classList.add('completed');
        const status = lastCard.querySelector('.reasoning-status');
        if (status) {
            status.textContent = 'Done';
            status.classList.remove('pending');
            status.classList.add('done');
        }
        const responseText = payload.response || '';
        if (responseText) {
            const truncated = responseText;
            const responseSection = lastCard.querySelector('.reasoning-section.response');
            const responseTextEl = lastCard.querySelector('.response-text');
            if (responseSection && responseTextEl) {
                responseTextEl.textContent = truncated;
                responseSection.classList.remove('hidden');
            }
        }
    }
    thinkingEventQueue.shift();
    completeThinkingTimelineItem();
    if (container === chatReasoning) {
        scrollToBottom(container);
    }
}

function appendChatReasoningPreview(payload, eventId) {
    const label = getToolLabel(payload.name, payload.args);
    const div = document.createElement('div');
    div.className = 'chat-reasoning-preview collapsed';
    div.innerHTML = `
        <div class="preview-header">
            <div class="preview-title">Thinking</div>
            <button class="preview-toggle" type="button">Expand</button>
        </div>
        <div class="preview-summary">${escHtml(label)}</div>
        <div class="preview-details hidden">
            <div class="preview-detail-label">Tool</div>
            <div class="preview-detail-value">${escHtml(payload.name || 'tool')}</div>
        </div>
        <div class="preview-actions">
            <button class="preview-link" type="button">View in Reasoning</button>
        </div>
    `;
    div.querySelector('.preview-toggle').addEventListener('click', () => {
        const details = div.querySelector('.preview-details');
        const isHidden = details.classList.toggle('hidden');
        div.classList.toggle('collapsed', isHidden);
        div.querySelector('.preview-toggle').textContent = isHidden ? 'Expand' : 'Collapse';
    });
    div.querySelector('.preview-link').addEventListener('click', () => {
        setChatTab('reasoning');
        const target = document.getElementById(eventId);
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'center' });
            target.classList.add('reasoning-highlight');
            setTimeout(() => target.classList.remove('reasoning-highlight'), 1200);
        }
    });
    chatMessages.appendChild(div);
    scrollToBottom(chatMessages);
}

function appendSystemMessage(text) {
    const div = document.createElement('div');
    div.className = 'text-center text-sm text-red-400 py-2 animate-float-in';
    div.textContent = text;
    chatMessages.appendChild(div);
}

function streamTextToBubble(bubble, text, onDone) {
    if (!bubble) {
        if (onDone) onDone();
        return;
    }
    if (activeStreamTimer) {
        clearInterval(activeStreamTimer);
        activeStreamTimer = null;
    }
    const target = bubble.querySelector('.bubble-content');
    if (!target) {
        if (onDone) onDone();
        return;
    }
    const words = text.split(/(\s+)/);
    let idx = 0;
    target.textContent = '';
    activeStreamTimer = setInterval(() => {
        if (idx >= words.length) {
            clearInterval(activeStreamTimer);
            activeStreamTimer = null;
            target.innerHTML = renderMarkdown(text);
            target.classList.add('markdown-body');
            if (onDone) onDone();
            return;
        }
        target.textContent += words[idx];
        idx += 1;
        scrollToBottom(chatMessages);
    }, 22);
}

// ─── Onboarding ─────────────────────────────────────────────────
async function loadOnboarding() {
    const merchantsSection = document.getElementById('onboarding-merchants-section');
    const agentsContainer = document.getElementById('onboarding-agents');
    const peopleSection = document.getElementById('onboarding-people-section');
    const peopleContainer = document.getElementById('onboarding-people');
    const emptyMsg = document.getElementById('onboarding-empty');

    agentsContainer.innerHTML = '';
    peopleContainer.innerHTML = '';

    // Fetch both agents and users in parallel
    const [agentsResp, usersResp] = await Promise.all([
        apiFetch(`${API}/platform/agents`),
        apiFetch(`${API}/platform/users`),
    ]);
    const agents = await agentsResp.json();
    const users = await usersResp.json();

    // Render platform agents (personal + merchant)
    if (agents.length > 0) {
        merchantsSection.classList.remove('hidden');
        for (const a of agents) {
            const typeLabel = (a.type || 'agent').replace(/^\w/, c => c.toUpperCase());
            const card = document.createElement('div');
            card.className = 'platform-agent-card';
            card.innerHTML = `
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                        <div class="text-sm font-medium text-white">${escHtml(a.name)}</div>
                        <span class="agent-type-badge ${escHtml(a.type || 'agent')}">${escHtml(typeLabel)}</span>
                    </div>
                    <div class="text-xs text-muted mt-0.5">${escHtml(a.description || '')}</div>
                </div>
                <button class="add-agent-btn bg-primary/20 hover:bg-primary/40 text-primary text-xs px-3 py-1.5 rounded-lg transition shrink-0" data-id="${a.id}">+ Add</button>
            `;
            card.querySelector('.add-agent-btn').addEventListener('click', async (e) => {
                const btn = e.currentTarget;
                btn.disabled = true;
                btn.textContent = 'Added';
                btn.classList.remove('hover:bg-primary/40', 'text-primary');
                btn.classList.add('text-green-400', 'cursor-default');
                await apiFetch(`${API}/platform/agents/${a.id}/add`, { method: 'POST' });
            });
            agentsContainer.appendChild(card);
        }
    } else {
        merchantsSection.classList.add('hidden');
    }

    // Render platform users
    if (users.length > 0) {
        peopleSection.classList.remove('hidden');
        for (const u of users) {
            const initial = (u.display_name || u.handle)[0].toUpperCase();
            const card = document.createElement('div');
            card.className = 'user-card';
            card.innerHTML = `
                <div class="user-avatar">${escHtml(initial)}</div>
                <div class="flex-1 min-w-0">
                    <div class="text-sm font-medium text-white">${escHtml(u.display_name || u.handle)}</div>
                    <div class="text-xs text-muted mt-0.5">@${escHtml(u.handle)}</div>
                </div>
                <button class="add-user-btn bg-primary/20 hover:bg-primary/40 text-primary text-xs px-3 py-1.5 rounded-lg transition shrink-0" data-handle="${escHtml(u.handle)}">+ Add</button>
            `;
            card.querySelector('.add-user-btn').addEventListener('click', async (e) => {
                const btn = e.currentTarget;
                btn.disabled = true;
                btn.textContent = 'Added';
                btn.classList.remove('hover:bg-primary/40', 'text-primary');
                btn.classList.add('text-green-400', 'cursor-default');
                await apiFetch(`${API}/platform/users/${u.handle}/add`, { method: 'POST' });
            });
            peopleContainer.appendChild(card);
        }
    } else {
        peopleSection.classList.add('hidden');
    }

    // Show empty message if nothing to add
    if (agents.length === 0 && users.length === 0) {
        emptyMsg.classList.remove('hidden');
    } else {
        emptyMsg.classList.add('hidden');
    }

    document.getElementById('onboarding-done-btn').addEventListener('click', async () => {
        await apiFetch(`${API}/auth/complete-onboarding`, { method: 'POST' });
        currentUser.is_onboarded = true;
        localStorage.setItem('user', JSON.stringify(currentUser));
        showPage('chat');
        const sessions = await loadSessions();
        if (sessions.length > 0) {
            await selectSession(sessions[0].id, sessions[0].title);
        } else {
            const resp = await apiFetch(`${API}/sessions`, {
                method: 'POST',
                body: JSON.stringify({}),
            });
            const session = await resp.json();
            await loadSessions();
            await selectSession(session.id, session.title);
        }
    });
}

// ─── Contacts Page ──────────────────────────────────────────────
async function loadContactsPage() {
    // Fetch agents, users, and contacts in parallel
    const [platformResp, usersResp] = await Promise.all([
        apiFetch(`${API}/platform/agents`),
        apiFetch(`${API}/platform/users`),
    ]);
    const platformAgents = await platformResp.json();
    const platformUsers = await usersResp.json();

    // Render discover agents
    const discoverSection = document.getElementById('discover-section');
    const discoverContainer = document.getElementById('discover-agents');

    if (platformAgents.length > 0) {
        discoverSection.classList.remove('hidden');
        discoverContainer.innerHTML = '';
        for (const a of platformAgents) {
            const card = document.createElement('div');
            card.className = 'platform-agent-card';
            card.innerHTML = `
                <div class="flex-1 min-w-0">
                    <div class="text-sm font-medium text-white">${escHtml(a.name)}</div>
                    <div class="text-xs text-muted mt-0.5">${escHtml(a.description || '')}</div>
                </div>
                <button class="add-agent-btn bg-primary/20 hover:bg-primary/40 text-primary text-xs px-3 py-1.5 rounded-lg transition shrink-0" data-id="${a.id}">+ Add</button>
            `;
            card.querySelector('.add-agent-btn').addEventListener('click', async (e) => {
                const btn = e.currentTarget;
                btn.disabled = true;
                btn.textContent = 'Added';
                btn.classList.remove('hover:bg-primary/40', 'text-primary');
                btn.classList.add('text-green-400', 'cursor-default');
                await apiFetch(`${API}/platform/agents/${a.id}/add`, { method: 'POST' });
                await renderMyContacts();
            });
            discoverContainer.appendChild(card);
        }
    } else {
        discoverSection.classList.add('hidden');
    }

    // Render discover people
    const peopleSection = document.getElementById('discover-people-section');
    const peopleContainer = document.getElementById('discover-people');

    if (platformUsers.length > 0) {
        peopleSection.classList.remove('hidden');
        peopleContainer.innerHTML = '';
        for (const u of platformUsers) {
            const initial = (u.display_name || u.handle)[0].toUpperCase();
            const card = document.createElement('div');
            card.className = 'user-card';
            card.innerHTML = `
                <div class="user-avatar">${escHtml(initial)}</div>
                <div class="flex-1 min-w-0">
                    <div class="text-sm font-medium text-white">${escHtml(u.display_name || u.handle)}</div>
                    <div class="text-xs text-muted mt-0.5">@${escHtml(u.handle)}</div>
                </div>
                <button class="add-user-btn bg-primary/20 hover:bg-primary/40 text-primary text-xs px-3 py-1.5 rounded-lg transition shrink-0" data-handle="${escHtml(u.handle)}">+ Add</button>
            `;
            card.querySelector('.add-user-btn').addEventListener('click', async (e) => {
                const btn = e.currentTarget;
                btn.disabled = true;
                btn.textContent = 'Added';
                btn.classList.remove('hover:bg-primary/40', 'text-primary');
                btn.classList.add('text-green-400', 'cursor-default');
                await apiFetch(`${API}/platform/users/${u.handle}/add`, { method: 'POST' });
                await renderMyContacts();
            });
            peopleContainer.appendChild(card);
        }
    } else {
        peopleSection.classList.add('hidden');
    }

    await renderMyContacts();
}

async function renderMyContacts() {
    const resp = await apiFetch(`${API}/contacts`);
    const contacts = await resp.json();
    const container = document.getElementById('my-contacts-list');
    container.innerHTML = '';

    if (contacts.length === 0) {
        container.innerHTML = '<p class="text-muted text-sm">No contacts yet. Add agents from the discover section above or invite by URL.</p>';
        return;
    }

    const groups = { pending: [], personal: [], merchant: [] };
    for (const c of contacts) {
        if (c.status === 'pending') {
            groups.pending.push(c);
        } else {
            (groups[c.type] || groups.merchant).push(c);
        }
    }

    for (const [type, items] of Object.entries(groups)) {
        if (items.length === 0) continue;
        const heading = document.createElement('div');
        heading.className = 'text-xs uppercase tracking-wider text-muted font-semibold mb-2 mt-4';
        if (type === 'pending') heading.textContent = 'Pending Requests';
        else heading.textContent = type === 'personal' ? 'Friends' : 'Merchants';
        container.appendChild(heading);

        for (const c of items) {
            const div = document.createElement('div');
            div.className = 'contact-item px-4 py-3 flex items-center justify-between group bg-panel rounded-lg border border-border';
            div.innerHTML = `
                <div class="flex items-center gap-3 min-w-0">
                    <span class="status-dot ${c.status}"></span>
                    <div class="min-w-0">
                        <div class="text-sm font-medium text-white truncate">${escHtml(c.name)}</div>
                        <div class="text-xs text-muted truncate">${escHtml(c.description || '')}</div>
                    </div>
                </div>
                <div class="flex gap-2 opacity-0 group-hover:opacity-100 transition">
                    ${c.status === 'pending'
                        ? `<button class="approve-btn text-xs text-green-400 hover:text-green-300 px-2 py-1 rounded" title="Approve">Approve</button>
                           <button class="reject-btn text-xs text-red-400 hover:text-red-300 px-2 py-1 rounded" title="Reject">Reject</button>`
                        : `<button class="view-card-btn text-xs text-muted hover:text-primary px-2 py-1 rounded" title="View Card">Card</button>
                           <button class="ping-btn text-xs text-muted hover:text-green-400 px-2 py-1 rounded" title="Ping">Ping</button>
                           <button class="del-btn text-xs text-muted hover:text-red-400 px-2 py-1 rounded" title="Remove">&times;</button>`}
                </div>
            `;
            if (c.status === 'pending') {
                div.querySelector('.approve-btn').addEventListener('click', async (e) => {
                    e.stopPropagation();
                    await apiFetch(`${API}/contacts/${c.id}/approve`, { method: 'POST' });
                    await renderMyContacts();
                });
                div.querySelector('.reject-btn').addEventListener('click', async (e) => {
                    e.stopPropagation();
                    await apiFetch(`${API}/contacts/${c.id}/reject`, { method: 'POST' });
                    await renderMyContacts();
                });
            } else {
                div.querySelector('.view-card-btn').addEventListener('click', (e) => {
                    e.stopPropagation();
                    showAgentCard(c.id, c.name);
                });
                div.querySelector('.ping-btn').addEventListener('click', async (e) => {
                    e.stopPropagation();
                    await apiFetch(`${API}/contacts/${c.id}/ping`, { method: 'POST' });
                    await renderMyContacts();
                });
                div.querySelector('.del-btn').addEventListener('click', async (e) => {
                    e.stopPropagation();
                    await apiFetch(`${API}/contacts/${c.id}`, { method: 'DELETE' });
                    await loadContactsPage();
                });
            }
            container.appendChild(div);
        }
    }

    // Ping all in background
    if (contacts.length > 0) {
        apiFetch(`${API}/contacts/ping-all`, { method: 'POST' })
            .then(r => r.json())
            .then(results => {
                for (const r of results) {
                    const dot = container.querySelector(`.ping-btn`)?.closest('.contact-item')?.querySelector('.status-dot');
                    // More targeted update
                    container.querySelectorAll('.contact-item').forEach(item => {
                        const pingBtn = item.querySelector('.ping-btn');
                        if (pingBtn) {
                            const statusDot = item.querySelector('.status-dot');
                            // We'd need id matching; just re-render
                        }
                    });
                }
            }).catch(() => {});
    }
}

// ─── Invite Modal (used by contacts page) ───────────────────────
document.getElementById('contacts-invite-btn').addEventListener('click', openInviteModal);

function openInviteModal() {
    inviteModal.classList.remove('hidden');
    inviteModal.classList.add('flex');
    inviteUrl.value = '';
    inviteError.classList.add('hidden');
    inviteUrl.focus();
}

inviteCancel.addEventListener('click', () => {
    inviteModal.classList.add('hidden');
    inviteModal.classList.remove('flex');
});

inviteConfirm.addEventListener('click', async () => {
    const url = inviteUrl.value.trim();
    if (!url) return;
    inviteError.classList.add('hidden');

    try {
        const resp = await apiFetch(`${API}/contacts/invite`, {
            method: 'POST',
            body: JSON.stringify({ agent_card_url: url }),
        });
        const data = await resp.json();
        if (!resp.ok) {
            inviteError.textContent = data.detail || 'Failed to invite agent';
            inviteError.classList.remove('hidden');
            return;
        }
        inviteModal.classList.add('hidden');
        inviteModal.classList.remove('flex');
        // Refresh contacts page if visible
        const contactsPage = document.getElementById('page-contacts');
        if (!contactsPage.classList.contains('hidden')) {
            await loadContactsPage();
        }
    } catch (err) {
        inviteError.textContent = 'Network error: ' + err.message;
        inviteError.classList.remove('hidden');
    }
});

// ─── Agent Card Modal ───────────────────────────────────────────
agentCardClose.addEventListener('click', () => {
    agentCardModal.classList.add('hidden');
    agentCardModal.classList.remove('flex');
});

async function showAgentCard(contactId, contactName) {
    agentCardModal.classList.remove('hidden');
    agentCardModal.classList.add('flex');
    agentCardTitle.textContent = contactName;
    agentCardLoading.classList.remove('hidden');
    agentCardError.classList.add('hidden');
    agentCardContent.classList.add('hidden');

    try {
        const resp = await apiFetch(`${API}/contacts/${contactId}/agent-card`);
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'Failed to fetch agent card');
        }
        const card = await resp.json();
        agentCardLoading.classList.add('hidden');
        agentCardContent.classList.remove('hidden');

        document.getElementById('agent-card-desc').textContent = card.description || 'No description';
        document.getElementById('agent-card-url').textContent = card.url || card.agent_card_url || '';
        document.getElementById('agent-card-version').textContent = card.version || 'N/A';

        const skillsContainer = document.getElementById('agent-card-skills');
        const skillsSection = document.getElementById('agent-card-skills-section');
        skillsContainer.innerHTML = '';

        if (card.skills && card.skills.length > 0) {
            skillsSection.classList.remove('hidden');
            const groups = new Map();
            for (const skill of card.skills) {
                let category = 'General';
                if (skill.category) {
                    category = skill.category;
                } else if (skill.tags && skill.tags.length > 0) {
                    const tagCategory = skill.tags.find(t => t.toLowerCase().startsWith('category:'));
                    if (tagCategory) category = tagCategory.split(':')[1].trim() || category;
                }
                let displayName = skill.name;
                if (!skill.category && skill.name) {
                    const match = skill.name.match(/^([^:-]{3,32})\s*[:\-]\s*(.+)$/);
                    if (match) {
                        category = match[1].trim();
                        displayName = match[2].trim();
                    }
                }
                if (!groups.has(category)) groups.set(category, []);
                groups.get(category).push({
                    ...skill,
                    displayName,
                });
            }

            for (const [category, skills] of groups.entries()) {
                const groupEl = document.createElement('div');
                groupEl.className = 'agent-skill-group';
                groupEl.innerHTML = `<div class="agent-skill-group-title">${escHtml(category)}</div>`;
                const list = document.createElement('div');
                list.className = 'space-y-2';
                for (const skill of skills) {
                    const el = document.createElement('div');
                    el.className = 'bg-surface rounded-lg p-3';
                    const tagsHtml = (skill.tags || []).map(t =>
                        `<span class="text-xs bg-indigo-900/40 text-indigo-300 px-2 py-0.5 rounded">${escHtml(t)}</span>`
                    ).join(' ');
                    el.innerHTML = `
                        <div class="text-sm font-medium text-white">${escHtml(skill.displayName || skill.name)}</div>
                        ${skill.description ? `<div class="text-xs text-muted mt-1">${escHtml(skill.description)}</div>` : ''}
                        ${tagsHtml ? `<div class="flex flex-wrap gap-1 mt-2">${tagsHtml}</div>` : ''}`;
                    list.appendChild(el);
                }
                groupEl.appendChild(list);
                skillsContainer.appendChild(groupEl);
            }
        } else {
            skillsSection.classList.add('hidden');
        }
    } catch (err) {
        agentCardLoading.classList.add('hidden');
        agentCardError.classList.remove('hidden');
        agentCardError.textContent = err.message || 'Could not reach agent';
    }
}

// ─── Settings ───────────────────────────────────────────────────
let settingsSkillList = [];
let settingsLibraryReady = false;

const SKILL_LIBRARY_PRESETS = [
    {
        category: 'Research',
        skills: ['Market analysis', 'Competitive intel', 'Customer interviews', 'Trend spotting'],
    },
    {
        category: 'Writing',
        skills: ['Executive summaries', 'Product briefs', 'Email drafting', 'Storytelling'],
    },
    {
        category: 'Planning',
        skills: ['Project plans', 'Roadmapping', 'Decision matrices', 'Risk assessment'],
    },
    {
        category: 'Commerce',
        skills: ['Deal negotiation', 'Vendor comparison', 'Pricing strategy', 'Procurement'],
    },
    {
        category: 'Travel',
        skills: ['Trip planning', 'Itinerary optimization', 'Local recommendations', 'Budget travel'],
    },
    {
        category: 'Wellness',
        skills: ['Meal planning', 'Fitness routines', 'Sleep optimization', 'Habit coaching'],
    },
];

const SKILL_LIBRARY_INTEGRATIONS = [
    {
        name: 'Google Workspace',
        description: 'Search Drive, summarize Docs, and draft emails from context.',
        skills: ['Docs synthesis', 'Drive search', 'Email follow-ups'],
    },
    {
        name: 'Notion',
        description: 'Query workspace pages, update databases, and create meeting notes.',
        skills: ['Workspace search', 'Meeting notes', 'Project updates'],
    },
    {
        name: 'Slack',
        description: 'Monitor channels, summarize threads, and craft replies.',
        skills: ['Thread summaries', 'Team updates', 'Response drafting'],
    },
    {
        name: 'GitHub',
        description: 'Review PRs, summarize issues, and track engineering status.',
        skills: ['Issue triage', 'PR summaries', 'Release notes'],
    },
    {
        name: 'Calendar',
        description: 'Propose schedules, optimize meetings, and add follow-ups.',
        skills: ['Scheduling', 'Agenda drafting', 'Meeting follow-ups'],
    },
];

function parseSkillList(raw) {
    return raw
        .split(/[\n,]/)
        .map(item => item.trim())
        .filter(Boolean);
}

function setSettingsSkills(list) {
    const seen = new Set();
    settingsSkillList = [];
    for (const skill of list) {
        const key = skill.toLowerCase();
        if (seen.has(key)) continue;
        seen.add(key);
        settingsSkillList.push(skill);
    }
}

function renderSettingsSkillChips() {
    const chips = document.getElementById('settings-skill-chips');
    const textarea = document.getElementById('settings-agent-skills');
    if (!chips || !textarea) return;
    chips.innerHTML = '';
    for (const skill of settingsSkillList) {
        const chip = document.createElement('span');
        chip.className = 'settings-skill-chip';
        const label = document.createElement('span');
        label.textContent = skill;
        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.setAttribute('aria-label', 'Remove skill');
        removeBtn.dataset.skill = skill;
        removeBtn.textContent = '×';
        chip.appendChild(label);
        chip.appendChild(removeBtn);
        chips.appendChild(chip);
    }
    textarea.value = settingsSkillList.join(', ');
}

function initSettingsSkillLibrary() {
    if (settingsLibraryReady) return;
    const presetsPanel = document.getElementById('settings-library-presets');
    const integrationsPanel = document.getElementById('settings-library-integrations');
    if (!presetsPanel || !integrationsPanel) return;
    presetsPanel.innerHTML = '';
    integrationsPanel.innerHTML = '';

    for (const group of SKILL_LIBRARY_PRESETS) {
        const section = document.createElement('div');
        section.className = 'settings-library-category';
        section.innerHTML = `<div class="settings-library-category-title">${escHtml(group.category)}</div>`;
        const chips = document.createElement('div');
        chips.className = 'settings-library-chips';
        for (const skill of group.skills) {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'settings-library-chip';
            chip.dataset.skill = `${group.category}: ${skill}`;
            chip.textContent = skill;
            chips.appendChild(chip);
        }
        section.appendChild(chips);
        presetsPanel.appendChild(section);
    }

    for (const integration of SKILL_LIBRARY_INTEGRATIONS) {
        const card = document.createElement('div');
        card.className = 'settings-integration-card';
        card.innerHTML = `
            <div class="settings-integration-title">${escHtml(integration.name)}</div>
            <div class="settings-integration-desc">${escHtml(integration.description)}</div>
        `;
        const actions = document.createElement('div');
        actions.className = 'settings-integration-actions';
        for (const skill of integration.skills) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.dataset.skill = `Integrations: ${skill}`;
            btn.textContent = skill;
            actions.appendChild(btn);
        }
        card.appendChild(actions);
        integrationsPanel.appendChild(card);
    }

    settingsLibraryReady = true;
}

function loadSettings() {
    document.getElementById('settings-handle').textContent = `@${currentUser.handle}`;
    document.getElementById('settings-email').textContent = currentUser.email;
    document.getElementById('settings-display-name').value = currentUser.display_name || '';
    document.getElementById('settings-agent-id').textContent = currentUser.handle;
    document.getElementById('settings-agent-instructions').value = currentUser.agent_instructions || '';
    const rawSkills = currentUser.agent_skills || '';
    document.getElementById('settings-agent-skills').value = rawSkills;
    setSettingsSkills(parseSkillList(rawSkills));
    renderSettingsSkillChips();
    initSettingsSkillLibrary();
    const autoInbox = document.getElementById('settings-auto-inbox');
    const socialPulse = document.getElementById('settings-social-pulse');
    const socialFreq = document.getElementById('settings-social-frequency');
    const feedEngagement = document.getElementById('settings-feed-engagement');
    const feedFreq = document.getElementById('settings-feed-frequency');
    const a2aMaxTurns = document.getElementById('settings-a2a-max-turns');
    if (autoInbox) autoInbox.checked = !!currentUser.auto_inbox_enabled;
    if (socialPulse) socialPulse.checked = !!currentUser.social_pulse_enabled;
    if (socialFreq) socialFreq.value = currentUser.social_pulse_frequency || 'weekly';
    if (feedEngagement) feedEngagement.checked = !!currentUser.feed_engagement_enabled;
    if (feedFreq) feedFreq.value = currentUser.feed_engagement_frequency || 'daily';
    if (a2aMaxTurns) a2aMaxTurns.value = String(currentUser.a2a_max_turns || 3);
}

function getSimulationMessageEl() {
    return document.getElementById('sim-msg');
}

document.getElementById('settings-save-btn').addEventListener('click', async () => {
    const displayName = document.getElementById('settings-display-name').value.trim();
    const msg = document.getElementById('settings-msg');
    try {
        const resp = await apiFetch(`${API}/auth/profile`, {
            method: 'PATCH',
            body: JSON.stringify({ display_name: displayName }),
        });
        if (resp.ok) {
            const updated = await resp.json();
            currentUser.display_name = updated.display_name;
            localStorage.setItem('user', JSON.stringify(currentUser));
            // Update nav avatar
            document.getElementById('nav-avatar').textContent = (currentUser.display_name || currentUser.handle)[0].toUpperCase();
            msg.textContent = 'Saved!';
            msg.className = 'text-sm text-green-400';
            msg.classList.remove('hidden');
            setTimeout(() => msg.classList.add('hidden'), 2000);
        } else {
            const err = await resp.json();
            msg.textContent = err.detail || 'Failed to save';
            msg.className = 'text-sm text-red-400';
            msg.classList.remove('hidden');
        }
    } catch (err) {
        msg.textContent = 'Network error';
        msg.className = 'text-sm text-red-400';
        msg.classList.remove('hidden');
    }
});

document.getElementById('settings-agent-save-btn').addEventListener('click', async () => {
    const instructions = document.getElementById('settings-agent-instructions').value.trim();
    const skills = settingsSkillList.length > 0
        ? settingsSkillList.join(', ')
        : document.getElementById('settings-agent-skills').value.trim();
    const autoInbox = document.getElementById('settings-auto-inbox')?.checked || false;
    const socialPulse = document.getElementById('settings-social-pulse')?.checked || false;
    const socialFreq = document.getElementById('settings-social-frequency')?.value || 'weekly';
    const feedEngagement = document.getElementById('settings-feed-engagement')?.checked || false;
    const feedFreq = document.getElementById('settings-feed-frequency')?.value || 'daily';
    const turnsRaw = Number(document.getElementById('settings-a2a-max-turns')?.value || 3);
    const a2aMaxTurns = Math.max(1, Math.min(10, Number.isFinite(turnsRaw) ? Math.trunc(turnsRaw) : 3));
    const msg = document.getElementById('settings-agent-msg');
    try {
        const resp = await apiFetch(`${API}/auth/agent-profile`, {
            method: 'PATCH',
            body: JSON.stringify({
                agent_instructions: instructions,
                agent_skills: skills,
                auto_inbox_enabled: autoInbox,
                social_pulse_enabled: socialPulse,
                social_pulse_frequency: socialFreq,
                feed_engagement_enabled: feedEngagement,
                feed_engagement_frequency: feedFreq,
                a2a_max_turns: a2aMaxTurns,
            }),
        });
        if (resp.ok) {
            const updated = await resp.json();
            currentUser.agent_instructions = updated.agent_instructions || '';
            currentUser.agent_skills = updated.agent_skills || '';
            currentUser.auto_inbox_enabled = !!updated.auto_inbox_enabled;
            currentUser.social_pulse_enabled = !!updated.social_pulse_enabled;
            currentUser.social_pulse_frequency = updated.social_pulse_frequency || 'weekly';
            currentUser.feed_engagement_enabled = !!updated.feed_engagement_enabled;
            currentUser.feed_engagement_frequency = updated.feed_engagement_frequency || 'daily';
            currentUser.a2a_max_turns = updated.a2a_max_turns || 3;
            localStorage.setItem('user', JSON.stringify(currentUser));
            msg.textContent = 'Agent settings saved!';
            msg.className = 'text-sm text-green-400';
            msg.classList.remove('hidden');
            setTimeout(() => msg.classList.add('hidden'), 2000);
        } else {
            const err = await resp.json();
            msg.textContent = err.detail || 'Failed to save';
            msg.className = 'text-sm text-red-400';
            msg.classList.remove('hidden');
        }
    } catch {
        msg.textContent = 'Network error';
        msg.className = 'text-sm text-red-400';
        msg.classList.remove('hidden');
    }
});

const simFriendsBtn = document.getElementById('sim-friends-btn');
if (simFriendsBtn) {
    simFriendsBtn.addEventListener('click', async () => {
        const msg = getSimulationMessageEl();
        if (!msg) return;
        msg.textContent = 'Running friends simulation...';
        try {
            const resp = await apiFetch(`${API}/debug/simulate/friends`, { method: 'POST' });
            const data = await resp.json();
            msg.textContent = `Simulation complete. Threads: ${data.count || 0}, max turns: ${data.turn_limit || currentUser.a2a_max_turns || 3}.`;
        } catch (err) {
            msg.textContent = err.message || 'Simulation failed';
        }
    });
}

const settingsSkillInput = document.getElementById('settings-skill-input');
const settingsSkillAdd = document.getElementById('settings-skill-add');
const settingsSkillTextarea = document.getElementById('settings-agent-skills');
const settingsSkillChips = document.getElementById('settings-skill-chips');

function addSkillsFromInput(raw) {
    if (!raw) return;
    const list = parseSkillList(raw);
    if (list.length === 0) return;
    setSettingsSkills([...settingsSkillList, ...list]);
    renderSettingsSkillChips();
}

if (settingsSkillAdd && settingsSkillInput) {
    settingsSkillAdd.addEventListener('click', () => {
        addSkillsFromInput(settingsSkillInput.value.trim());
        settingsSkillInput.value = '';
        settingsSkillInput.focus();
    });
    settingsSkillInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            addSkillsFromInput(settingsSkillInput.value.trim());
            settingsSkillInput.value = '';
        }
    });
}

if (settingsSkillTextarea) {
    settingsSkillTextarea.addEventListener('blur', () => {
        setSettingsSkills(parseSkillList(settingsSkillTextarea.value || ''));
        renderSettingsSkillChips();
    });
}

if (settingsSkillChips) {
    settingsSkillChips.addEventListener('click', (event) => {
        const button = event.target.closest('button[data-skill]');
        if (!button) return;
        const skill = button.dataset.skill;
        settingsSkillList = settingsSkillList.filter(item => item !== skill);
        renderSettingsSkillChips();
    });
}

const settingsLibrary = document.querySelector('.settings-library');
if (settingsLibrary) {
    settingsLibrary.addEventListener('click', (event) => {
        const tabBtn = event.target.closest('.settings-library-tab');
        if (tabBtn) {
            const tab = tabBtn.dataset.libraryTab;
            const tabs = settingsLibrary.querySelectorAll('.settings-library-tab');
            tabs.forEach(btn => btn.classList.toggle('active', btn === tabBtn));
            const presetPanel = document.getElementById('settings-library-presets');
            const integrationPanel = document.getElementById('settings-library-integrations');
            if (presetPanel && integrationPanel) {
                presetPanel.classList.toggle('hidden', tab !== 'presets');
                integrationPanel.classList.toggle('hidden', tab !== 'integrations');
            }
            return;
        }
        const skillBtn = event.target.closest('[data-skill]');
        if (skillBtn) {
            addSkillsFromInput(skillBtn.dataset.skill || '');
        }
    });
}

// ─── Helpers ────────────────────────────────────────────────────
function scrollToBottom(container) {
    const target = container || getActiveChatContainer();
    if (!target) return;
    target.scrollTop = target.scrollHeight;
}

// ─── Inbox Page ─────────────────────────────────────────────────
let currentConvId = null;
let currentConvPartner = null;
let isProcessingInbox = false;
let inboxPollTimer = null;
let latestTaskAlertCount = 0;
const TASK_NOTIFY_SEEN_KEY = 'task_notify_seen_map_v1';

// Track rendered state to avoid full DOM rebuilds on poll
let _lastConvListHash = '';
let _renderedMsgIds = new Set();

async function loadInboxPage() {
    _lastConvListHash = '';  // force full render on page load
    _renderedMsgIds = new Set();
    await loadConversationList(true);
    setInboxTab('messages');
    startInboxPolling();
    await updateNotificationBadges();
}

function startInboxPolling() {
    if (inboxPollTimer) clearInterval(inboxPollTimer);
    updateNotificationBadges();
    inboxPollTimer = setInterval(async () => {
        const inboxVisible = !document.getElementById('page-inbox').classList.contains('hidden');
        if (inboxVisible) {
            if (currentConvId) {
                await loadConversationMessages(currentConvId);
            }
            await loadConversationList();
        }
        await updateNotificationBadges();
    }, 4000);
}

function stopInboxPolling() {
    if (inboxPollTimer) clearInterval(inboxPollTimer);
    inboxPollTimer = null;
}

function setInboxTab(tab) {
    if (!inboxTabMessages || !inboxTabTasks || !inboxMessagesPane || !inboxTasksPane) return;
    const isMessages = tab === 'messages';
    inboxTabMessages.classList.toggle('active', isMessages);
    inboxTabTasks.classList.toggle('active', !isMessages);
    inboxMessagesPane.classList.toggle('hidden', !isMessages);
    inboxTasksPane.classList.toggle('hidden', isMessages);
    if (inboxSidebar) inboxSidebar.classList.toggle('hidden', !isMessages);
    if (!isMessages) {
        markTaskAlertsSeen();
        loadTasksPage();
    }
}

if (inboxTabMessages && inboxTabTasks) {
    inboxTabMessages.addEventListener('click', async () => {
        setInboxTab('messages');
        await updateNotificationBadges();
    });
    inboxTabTasks.addEventListener('click', async () => {
        setInboxTab('tasks');
        await updateNotificationBadges();
    });
}

// Sidebar color map (persists across sidebar re-renders)
let _sidebarColorMap = {};
let _sidebarColorIdx = { val: 0 };

async function loadConversationList(forceRender = false) {
    const list = document.getElementById('inbox-conv-list');
    const empty = document.getElementById('inbox-conv-empty');

    try {
        const resp = await apiFetch(`${API}/inbox/conversations`);
        const convos = await resp.json();

        const hash = convos.map(c =>
            `${c.id}:${c.unread_count}:${c.status}:${c.last_message?.message?.slice(0, 30) || ''}`
        ).join('|');

        if (!forceRender && hash === _lastConvListHash) return;
        _lastConvListHash = hash;

        list.innerHTML = '';

        if (convos.length === 0) {
            empty.classList.remove('hidden');
            return;
        }
        empty.classList.add('hidden');

        for (const c of convos) {
            const div = document.createElement('div');
            const isActive = c.id === currentConvId;
            const isStopped = c.status === 'stopped';
            const partnerColor = getParticipantColor(c.partner, _sidebarColorMap, _sidebarColorIdx);

            div.className = `inbox-conv-item group ${isActive ? 'active' : ''} ${isStopped ? 'stopped' : ''}`;
            if (isActive) div.style.borderLeftColor = partnerColor.text;
            div.setAttribute('data-conv-id', c.id);
            div.setAttribute('data-partner', c.partner);

            const initial = (c.partner || '?')[0].toUpperCase();
            const preview = c.last_message ? c.last_message.message.slice(0, 50) : 'No messages';
            const unread = c.unread_count || 0;

            // Build avatar with partner color
            const avatarHtml = `<div class="inbox-conv-avatar" style="background:${partnerColor.bg};border:1.5px solid ${partnerColor.border};color:${partnerColor.text}">${escHtml(initial)}</div>`;

            div.innerHTML = `
                ${avatarHtml}
                <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between">
                        <span class="text-sm font-medium text-white truncate">${escHtml(c.partner)}</span>
                        ${unread > 0 ? `<span class="inbox-conv-badge">${unread}</span>` : ''}
                    </div>
                    <div class="text-xs text-muted truncate mt-0.5">${escHtml(preview)}</div>
                </div>
                ${isStopped ? '<span class="text-xs text-red-400 ml-1">stopped</span>' : ''}
                <button class="inbox-conv-delete text-muted hover:text-red-400 opacity-0 group-hover:opacity-100 ml-1 text-xs transition" data-conv-id="${c.id}" title="Delete">&times;</button>
            `;
            div.addEventListener('click', (e) => {
                if (e.target.classList.contains('inbox-conv-delete')) return;
                openConversation(c.id, c.partner, c.status);
            });
            div.querySelector('.inbox-conv-delete').addEventListener('click', async (e) => {
                e.stopPropagation();
                await apiFetch(`${API}/inbox/conversations/${c.id}`, { method: 'DELETE' });
                if (currentConvId === c.id) {
                    currentConvId = null;
                    document.getElementById('inbox-chat-messages').innerHTML = '';
                    document.getElementById('inbox-chat-header').innerHTML = '<span class="text-sm text-muted">Select a conversation</span>';
                    document.getElementById('inbox-action-bar').classList.add('hidden');
                    _renderedMsgIds = new Set();
                }
                _lastConvListHash = '';
                await loadConversationList(true);
            });
            list.appendChild(div);
        }
    } catch (err) {
        list.innerHTML = `<p class="text-red-400 text-sm p-3">${err.message}</p>`;
    }
}

async function openConversation(convId, partner, convStatus) {
    currentConvId = convId;
    currentConvPartner = partner;
    resetInboxColors();

    // Highlight in sidebar
    const partnerColor = getParticipantColor(partner, _sidebarColorMap, _sidebarColorIdx);
    document.querySelectorAll('.inbox-conv-item').forEach(el => {
        const isActive = el.getAttribute('data-conv-id') === convId;
        el.classList.toggle('active', isActive);
        el.style.borderLeftColor = isActive ? partnerColor.text : 'transparent';
    });

    // Update header with colored avatar
    const header = document.getElementById('inbox-chat-header');
    const initial = (partner || '?')[0].toUpperCase();
    header.innerHTML = `
        <div class="flex items-center gap-3">
            <div class="inbox-conv-avatar-sm" style="background:${partnerColor.bg};border:1.5px solid ${partnerColor.border};color:${partnerColor.text}">${escHtml(initial)}</div>
            <span class="text-sm font-medium" style="color:${partnerColor.text}">${escHtml(partner)}</span>
        </div>
    `;

    // Show action bar
    const actionBar = document.getElementById('inbox-action-bar');
    actionBar.classList.remove('hidden');

    const stopBtn = document.getElementById('inbox-stop-btn');
    const statusEl = document.getElementById('inbox-conv-status');
    const sendInput = document.getElementById('inbox-send-input');

    if (convStatus === 'stopped') {
        stopBtn.textContent = 'Resume';
        stopBtn.className = 'bg-panel border border-border hover:border-green-400 text-muted hover:text-green-400 text-sm px-4 py-2.5 rounded-lg transition shrink-0';
        sendInput.disabled = true;
        document.getElementById('inbox-send-btn').disabled = true;
        statusEl.textContent = 'Conversation stopped';
        statusEl.className = 'text-xs text-red-400/80';
    } else {
        stopBtn.textContent = 'Stop';
        stopBtn.className = 'bg-panel border border-border hover:border-red-400 text-muted hover:text-red-400 text-sm px-4 py-2.5 rounded-lg transition shrink-0';
        sendInput.disabled = false;
        document.getElementById('inbox-send-btn').disabled = false;
        statusEl.textContent = 'Agents auto-responding';
        statusEl.className = 'text-xs text-green-400/80';
    }

    sendInput.focus();

    const container = document.getElementById('inbox-chat-messages');
    container.innerHTML = '';
    _renderedMsgIds = new Set();
    await loadConversationMessages(convId, true);
    await loadConversationList(true);
    await updateNotificationBadges();
}

async function loadConversationMessages(convId, scrollToEnd = false) {
    const container = document.getElementById('inbox-chat-messages');

    try {
        const resp = await apiFetch(`${API}/inbox/conversations/${convId}/messages`);
        const messages = await resp.json();

        // Only append messages not already rendered — never clear/rebuild
        for (const m of messages) {
            if (!_renderedMsgIds.has(m.id)) {
                _renderedMsgIds.add(m.id);
                renderInboxMessage(container, m);
            }
        }

        // Only scroll on explicit user action (open conversation, send message)
        if (scrollToEnd) {
            container.scrollTop = container.scrollHeight;
        }
    } catch (err) {
        // Only show error on initial load (empty container)
        if (container.children.length === 0) {
            container.innerHTML = `<p class="text-red-400 text-sm">${err.message}</p>`;
        }
    }
}

function renderInboxMessage(container, m) {
    const isFromMe = m.is_from_me;

    if (isFromMe) {
        // Outbound — right-aligned indigo
        const div = document.createElement('div');
        div.className = 'flex justify-end animate-float-in';
        div.innerHTML = `
            <div class="max-w-md">
                <div class="text-xs text-muted mb-1 text-right">You (via agent)</div>
                <div class="bubble-user px-4 py-2.5 text-sm whitespace-pre-wrap">${escHtml(m.message)}</div>
                <div class="text-xs text-muted mt-1 text-right">${escHtml(m.created_at)}</div>
            </div>
        `;
        container.appendChild(div);
    } else {
        // Inbound — colored bubble with avatar
        const senderName = m.sender_name || 'Unknown';
        const color = getInboxColor(senderName);
        const statusTag = m.status === 'unread'
            ? '<span class="inbox-msg-status unread">new</span>'
            : m.status === 'processed'
            ? '<span class="inbox-msg-status processed">responded</span>'
            : '';

        const wrapper = document.createElement('div');
        wrapper.className = 'flex items-start gap-2.5 animate-float-in';

        const avatar = createColoredAvatar(senderName, color, 'md');
        wrapper.appendChild(avatar);

        const content = document.createElement('div');
        content.className = 'max-w-md';

        // Name + status tag
        const nameRow = document.createElement('div');
        nameRow.className = 'flex items-center gap-2 mb-1';
        nameRow.innerHTML = `<span class="text-xs font-medium" style="color:${color.text}">${escHtml(senderName)}</span>${statusTag}`;
        content.appendChild(nameRow);

        // Colored bubble
        const bubble = document.createElement('div');
        bubble.className = 'msg-bubble-colored px-4 py-2.5 text-sm text-gray-200';
        bubble.style.backgroundColor = color.bg;
        bubble.style.borderColor = color.border;
        bubble.setAttribute('data-msg-id', m.id);
        bubble.innerHTML = renderMarkdown(m.message);
        bubble.classList.add('markdown-body');
        content.appendChild(bubble);

        // Processing log as inline exchanges
        if (m.processing_log && m.processing_log.length > 0) {
            const logEl = renderProcessingLog(m.processing_log);
            content.appendChild(logEl);
        }

        // Timestamp
        const ts = document.createElement('div');
        ts.className = 'text-xs text-muted mt-1';
        ts.textContent = m.created_at;
        content.appendChild(ts);

        wrapper.appendChild(content);
        container.appendChild(wrapper);
    }
}

function renderProcessingLog(log) {
    const fragment = document.createElement('div');
    fragment.className = 'mt-2 space-y-1';

    // Group function_call + function_response pairs
    for (let i = 0; i < log.length; i++) {
        const entry = log[i];
        if (entry.type === 'function_call' && entry.name === 'send_message_to_contact') {
            // Render as inline agent exchange
            const contactName = entry.args?.contact_name || entry.args?.name || 'contact';
            const contactColor = getInboxColor(contactName);
            const outMsg = entry.args?.message || '';

            const exchDiv = document.createElement('div');
            exchDiv.className = 'inbox-agent-exchange';

            // Outgoing mini bubble
            if (outMsg) {
                const sent = document.createElement('div');
                sent.className = 'inbox-exchange-sent';
                sent.textContent = outMsg.length > 150 ? outMsg.slice(0, 150) + '...' : outMsg;
                exchDiv.appendChild(sent);
            }

            // Check for response
            const nextEntry = log[i + 1];
            if (nextEntry && nextEntry.type === 'function_response') {
                const respText = extractCleanResponse(nextEntry.response || '');
                const truncated = respText.length > 200 ? respText.slice(0, 200) + '...' : respText;

                const replyRow = document.createElement('div');
                replyRow.className = 'inbox-exchange-reply';
                const replyAvatar = createColoredAvatar(contactName, contactColor, 'sm');
                replyRow.appendChild(replyAvatar);
                const replyBubble = document.createElement('div');
                replyBubble.className = 'msg-bubble-colored px-3 py-1.5 text-gray-200';
                replyBubble.style.backgroundColor = contactColor.bg;
                replyBubble.style.borderColor = contactColor.border;
                replyBubble.innerHTML = renderMarkdown(truncated);
                replyBubble.classList.add('markdown-body');
                replyRow.appendChild(replyBubble);
                exchDiv.appendChild(replyRow);
                i++; // skip the response entry
            }

            fragment.appendChild(exchDiv);
        } else if (entry.type === 'function_call') {
            // Other tool calls as compact pills
            const label = getToolLabel(entry.name, entry.args);
            const pill = document.createElement('div');
            pill.className = 'inbox-tool-pill';
            pill.innerHTML = `<span class="text-green-400">\u2713</span> <span>${escHtml(label)}</span>`;
            fragment.appendChild(pill);

            // Skip matching response
            if (log[i + 1]?.type === 'function_response') i++;
        }
    }
    return fragment;
}

// ─── Send message in conversation ───────────────────────────────
const inboxSendForm = document.getElementById('inbox-send-form');
if (inboxSendForm) {
    inboxSendForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!currentConvId) return;
        const input = document.getElementById('inbox-send-input');
        const message = input.value.trim();
        if (!message) return;

        input.value = '';
        const sendBtn = document.getElementById('inbox-send-btn');
        sendBtn.disabled = true;

        try {
            await apiFetch(`${API}/inbox/conversations/${currentConvId}/send`, {
                method: 'POST',
                body: JSON.stringify({ message }),
            });
        } catch (err) {
            console.error('Send error:', err);
        }

        sendBtn.disabled = false;
        // Show new message, scroll to it
        await loadConversationMessages(currentConvId, true);
        input.focus();
    });
}

// ─── Stop / Resume conversation ─────────────────────────────────
const inboxStopBtn = document.getElementById('inbox-stop-btn');
if (inboxStopBtn) {
    inboxStopBtn.addEventListener('click', async () => {
        if (!currentConvId) return;
        const btn = document.getElementById('inbox-stop-btn');
        const isStopped = btn.textContent.trim() === 'Resume';

        if (isStopped) {
            await apiFetch(`${API}/inbox/conversations/${currentConvId}/resume`, { method: 'POST' });
            await openConversation(currentConvId, currentConvPartner, 'active');
        } else {
            await apiFetch(`${API}/inbox/conversations/${currentConvId}/stop`, { method: 'POST' });
            await openConversation(currentConvId, currentConvPartner, 'stopped');
        }
        await loadConversationList();
    });
}

// ─── Clear all conversations ────────────────────────────────────
const clearAllBtn = document.getElementById('inbox-clear-all-btn');
if (clearAllBtn) {
    clearAllBtn.addEventListener('click', async () => {
        if (!confirm('Delete all conversations?')) return;
        await apiFetch(`${API}/inbox/conversations`, { method: 'DELETE' });
        currentConvId = null;
        _renderedMsgIds = new Set();
        _lastConvListHash = '';
        document.getElementById('inbox-chat-messages').innerHTML = '';
        document.getElementById('inbox-chat-header').innerHTML = '<span class="text-sm text-muted">Select a conversation</span>';
        document.getElementById('inbox-action-bar').classList.add('hidden');
        await loadConversationList(true);
    });
}

// ─── Tasks Page ─────────────────────────────────────────────────

// Known agent names for coloring progress steps
const TASK_AGENT_PATTERNS = /(asking|contacting|from|replied|response from|checking with)\s+(\w+)/i;

function getProgressDotClass(stepText) {
    const match = stepText.match(TASK_AGENT_PATTERNS);
    if (match) {
        const agentName = match[2];
        const color = getChatColor(agentName);
        return `dot-${color.name}`;
    }
    return '';
}

async function loadTasksPage() {
    const container = document.getElementById('tasks-list');
    const emptyMsg = document.getElementById('tasks-empty');
    container.innerHTML = '';

    try {
        const resp = await apiFetch(`${API}/tasks`);
        const tasks = await resp.json();

        if (tasks.length === 0) {
            emptyMsg.classList.remove('hidden');
            return;
        }
        emptyMsg.classList.add('hidden');

        for (const t of tasks) {
            const card = document.createElement('div');
            const statusAccent = t.status === 'running' ? 'task-running' : t.status === 'completed' ? 'task-completed' : t.status === 'failed' ? 'task-failed' : '';
            card.className = `task-card ${statusAccent}`;
            const statusClass = t.status === 'completed' ? 'completed' : t.status === 'failed' ? 'failed' : t.status === 'running' ? 'running' : '';
            const resultClass = t.status === 'failed' ? 'result-failed' : '';

            const progressLines = (t.progress_log || []).map(p => escHtml(p.msg || p || '')).join('\n');
            const resultFull = escHtml(t.result_summary || '');
            card.innerHTML = `
                <div class="task-card-header">
                    <div class="flex-1 min-w-0">
                        <div class="text-sm font-medium text-white truncate">${escHtml(t.intent)}</div>
                        <div class="text-xs text-muted mt-0.5">
                            <span class="task-status ${statusClass}">${t.status.toUpperCase()}</span>
                            ${t.phase ? `<span class="phase-indicator">${escHtml(t.phase)}</span>` : ''}
                        </div>
                    </div>
                    <span class="text-xs text-muted">${escHtml(t.created_at)}</span>
                </div>
                ${t.progress_log && t.progress_log.length > 0 ? `
                    <div class="task-timeline">
                        ${t.progress_log.slice(-5).map(p => {
                            const stepText = p.msg || p;
                            const dotClass = getProgressDotClass(stepText);
                            return `
                            <div class="progress-step">
                                <span class="progress-dot ${dotClass}"></span>
                                <span class="text-xs text-gray-400">${escHtml(stepText)}</span>
                            </div>`;
                        }).join('')}
                    </div>
                ` : ''}
                ${t.result_summary && (t.status === 'completed' || t.status === 'failed') ? `
                    <div class="task-result ${resultClass}">
                        <div class="text-xs text-muted font-semibold mb-1">Result</div>
                        <div class="text-sm text-gray-300 markdown-body">${renderMarkdown(t.result_summary.slice(0, 500) + (t.result_summary.length > 500 ? '...' : ''))}</div>
                    </div>
                ` : ''}
                ${t.status === 'running' ? `
                    <div class="task-actions">
                        <button class="cancel-task-btn text-xs text-red-400 hover:text-red-300 transition" data-id="${t.id}">Cancel</button>
                    </div>
                ` : ''}
                <details class="task-details mt-2">
                    <summary class="task-details-summary">View full timeline</summary>
                    <div class="task-details-body">
                        <div class="task-details-section">
                            <div class="task-details-title">All interactions / decisions</div>
                            <pre class="task-details-pre">${progressLines || 'No timeline entries.'}</pre>
                        </div>
                        <div class="task-details-section">
                            <div class="task-details-title">Final result</div>
                            <pre class="task-details-pre">${resultFull || 'No result yet.'}</pre>
                        </div>
                    </div>
                </details>
            `;
            const cancelBtn = card.querySelector('.cancel-task-btn');
            if (cancelBtn) {
                cancelBtn.addEventListener('click', async () => {
                    await apiFetch(`${API}/tasks/${t.id}/cancel`, { method: 'POST' });
                    await loadTasksPage();
                });
            }
            container.appendChild(card);
        }
        await updateNotificationBadges();
    } catch (err) {
        container.innerHTML = `<p class="text-red-400 text-sm">Failed to load tasks: ${err.message}</p>`;
    }
}

// ─── Background Task Submit ─────────────────────────────────────
document.getElementById('bg-task-btn').addEventListener('click', async () => {
    const message = chatInput.value.trim();
    if (!message || !currentSessionId) return;

    chatInput.value = '';
    appendUserBubble(message);
    appendSystemMessage('Submitted as background task — check the Tasks page for progress.');
    scrollToBottom();

    try {
        await apiFetch(`${API}/tasks`, {
            method: 'POST',
            body: JSON.stringify({ intent: message, session_id: currentSessionId }),
        });
    } catch (err) {
        appendSystemMessage('Failed to create task: ' + err.message);
    }
});

function getSeenTaskMap() {
    try {
        return JSON.parse(localStorage.getItem(TASK_NOTIFY_SEEN_KEY) || '{}');
    } catch {
        return {};
    }
}

function setSeenTaskMap(map) {
    localStorage.setItem(TASK_NOTIFY_SEEN_KEY, JSON.stringify(map));
}

function seedTaskSeenIfMissing() {
    if (!currentUser?.handle) return;
    const map = getSeenTaskMap();
    if (typeof map[currentUser.handle] !== 'number') {
        map[currentUser.handle] = Date.now();
        setSeenTaskMap(map);
    }
}

function markTaskAlertsSeen() {
    if (!currentUser?.handle) return;
    const map = getSeenTaskMap();
    map[currentUser.handle] = Date.now();
    setSeenTaskMap(map);
    latestTaskAlertCount = 0;
}

function parseSqliteTimestamp(ts) {
    if (!ts) return NaN;
    const normalized = String(ts).includes('T')
        ? String(ts)
        : String(ts).replace(' ', 'T') + 'Z';
    return Date.parse(normalized);
}

async function fetchTaskAlertCount() {
    const seenMap = getSeenTaskMap();
    const seenTs = Number(seenMap[currentUser?.handle] || 0);
    const resp = await apiFetch(`${API}/tasks`);
    const tasks = await resp.json();
    return tasks.filter(t => {
        if (!(t.status === 'completed' || t.status === 'failed')) return false;
        const updated = parseSqliteTimestamp(t.updated_at || t.completed_at || t.created_at || '');
        return Number.isFinite(updated) && updated > seenTs;
    }).length;
}

// ─── Inbox / Tasks Notifications ───────────────────────────────
async function updateNotificationBadges() {
    let unreadCount = 0;
    let taskCount = 0;
    try {
        const resp = await apiFetch(`${API}/inbox/unread-count`);
        const data = await resp.json();
        unreadCount = data.count || 0;
    } catch {
        unreadCount = 0;
    }
    try {
        taskCount = await fetchTaskAlertCount();
    } catch {
        taskCount = 0;
    }
    latestTaskAlertCount = taskCount;

    const navBadge = document.getElementById('inbox-badge');
    const inboxTabBadge = document.getElementById('inbox-tab-badge');
    const tasksTabBadge = document.getElementById('tasks-tab-badge');
    const totalNav = unreadCount + latestTaskAlertCount;

    if (navBadge) {
        if (totalNav > 0) {
            navBadge.classList.remove('hidden');
            navBadge.textContent = totalNav > 9 ? '9+' : totalNav;
        } else {
            navBadge.classList.add('hidden');
        }
    }

    if (inboxTabBadge) {
        if (unreadCount > 0) {
            inboxTabBadge.classList.remove('hidden');
            inboxTabBadge.textContent = unreadCount > 9 ? '9+' : unreadCount;
        } else {
            inboxTabBadge.classList.add('hidden');
        }
    }

    if (tasksTabBadge) {
        if (latestTaskAlertCount > 0) {
            tasksTabBadge.classList.remove('hidden');
            tasksTabBadge.textContent = latestTaskAlertCount > 9 ? '9+' : latestTaskAlertCount;
        } else {
            tasksTabBadge.classList.add('hidden');
        }
    }
}

// ─── Boot ───────────────────────────────────────────────────────
init();
