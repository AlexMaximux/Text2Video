/**
 * Text2Video Frontend Application
 * High-Performance Interactive Control Center with Zero-Lag State Machine
 */

document.addEventListener('DOMContentLoaded', () => {
    // State
    let currentTab = 'dashboard';
    let activeProject = null;
    let pollInterval = null;
    let timerInterval = null;
    let lastRunningState = false;
    let lastStepName = null;
    let stepStartTime = null;

    const SUBTITLE_PRESETS = {
        'viral-yellow': {
            font: 'Montserrat',
            size: 80,
            textColor: '#FFFFFF',
            highlightColor: '#FFD60A',
            outlineColor: '#000000',
            outlineThickness: 'medium',
            position: 'bottom'
        },
        'cyber-neon': {
            font: 'Poppins',
            size: 82,
            textColor: '#FFFFFF',
            highlightColor: '#00FF66',
            outlineColor: '#000000',
            outlineThickness: 'medium',
            position: 'bottom'
        },
        'fire-red': {
            font: 'Anton',
            size: 86,
            textColor: '#FFFFFF',
            highlightColor: '#FF3B30',
            outlineColor: '#000000',
            outlineThickness: 'heavy',
            position: 'bottom'
        },
        'electric-cyan': {
            font: 'Bebas Neue',
            size: 92,
            textColor: '#FFFFFF',
            highlightColor: '#00E5FF',
            outlineColor: '#000000',
            outlineThickness: 'medium',
            position: 'bottom'
        },
        'gold-luxury': {
            font: 'Oswald',
            size: 80,
            textColor: '#FFFFFF',
            highlightColor: '#FFB800',
            outlineColor: '#1A1A1A',
            outlineThickness: 'medium',
            position: 'bottom'
        },
        'clean-minimal': {
            font: 'Inter',
            size: 74,
            textColor: '#FFFFFF',
            highlightColor: '#E0E0E0',
            outlineColor: '#000000',
            outlineThickness: 'subtle',
            position: 'bottom'
        }
    };

    const FONT_CSS_MAP = {
        'Montserrat': "'Montserrat', sans-serif",
        'Poppins': "'Poppins', sans-serif",
        'Outfit': "'Outfit', sans-serif",
        'Plus Jakarta Sans': "'Plus Jakarta Sans', sans-serif",
        'Inter': "'Inter', sans-serif",
        'Bebas Neue': "'Bebas Neue', cursive, sans-serif",
        'Anton': "'Anton', sans-serif",
        'Oswald': "'Oswald', sans-serif",
        'Rubik': "'Rubik', sans-serif",
        'Arial Black': "'Arial Black', Gadget, sans-serif",
        'Impact': "Impact, Charcoal, sans-serif",
        'Trebuchet MS': "'Trebuchet MS', sans-serif"
    };

    let activeHighlightWordIndex = 0;
    let karaokeInterval = null;
    let isKaraokePlaying = false;
    let currentProjectFirstImage = null;

    // DOM Elements
    const projectSelector = document.getElementById('projectSelector');
    const btnRefreshProjects = document.getElementById('btnRefreshProjects');
    const logContainer = document.getElementById('logContainer');
    const statusPill = document.getElementById('statusPill');
    const statusText = document.getElementById('statusText');
    const statusTimer = document.getElementById('statusTimer');
    const logStatusBadge = document.getElementById('logStatusBadge');
    const btnCancelStep = document.getElementById('btnCancelStep');
    const btnTerminalCancel = document.getElementById('btnTerminalCancel');
    const autoScrollCheck = document.getElementById('autoScrollCheck');

    // Initialize
    init();

    function init() {
        setupNavigation();
        setupEventListeners();
        loadProjects();
        setupScriptStats();
        setupSubtitlePreview();
        startStatusPolling();
    }

    // Navigation Setup
    function setupNavigation() {
        // Sidebar tabs
        document.querySelectorAll('[data-tab]').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const tab = item.getAttribute('data-tab');
                switchTab(tab);
            });
        });

        // Clickable Dashboard Cards & Banner Buttons
        document.querySelectorAll('[data-nav-target]').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const targetTab = item.getAttribute('data-nav-target');
                switchTab(targetTab);
            });
        });
    }

    function switchTab(tabName) {
        currentTab = tabName;
        document.querySelectorAll('[data-tab]').forEach(item => {
            if (item.getAttribute('data-tab') === tabName) {
                item.className = 'nav-tab-active flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all group';
            } else {
                item.className = 'nav-tab-inactive flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all group';
            }
        });

        document.querySelectorAll('.tab-content').forEach(section => {
            section.classList.add('hidden');
        });

        const targetView = document.getElementById(`tab-content-${tabName}`);
        if (targetView) {
            targetView.classList.remove('hidden');
        }

        if (tabName === 'export') {
            // Use requestAnimationFrame + setTimeout to ensure the tab is fully visible before measuring
            requestAnimationFrame(() => {
                setTimeout(() => {
                    renderSubtitlePreview();
                    updatePreviewBackground();
                }, 80);
            });
        }

        // Refresh pipeline badges every time user goes to dashboard
        if (tabName === 'dashboard' && activeProject) {
            loadProjectDetails(activeProject);
        }
    }

    // Event Listeners
    function setupEventListeners() {
        if (btnRefreshProjects) {
            btnRefreshProjects.addEventListener('click', () => loadProjects(true));
        }

        if (projectSelector) {
            projectSelector.addEventListener('change', (e) => {
                activeProject = e.target.value;
                if (activeProject) {
                    loadProjectDetails(activeProject);
                }
            });
        }

        // New Project Modal handlers
        const btnSidebarNewProject = document.getElementById('btnSidebarNewProject');
        const newProjectModal = document.getElementById('newProjectModal');
        const btnCloseProjectModal = document.getElementById('btnCloseProjectModal');
        const btnCancelProjectModal = document.getElementById('btnCancelProjectModal');
        const btnConfirmCreateProject = document.getElementById('btnConfirmCreateProject');
        const newProjectNameInput = document.getElementById('newProjectNameInput');

        const openModal = () => {
            if (newProjectModal) {
                newProjectModal.classList.remove('hidden');
                if (newProjectNameInput) newProjectNameInput.focus();
            }
        };

        const closeModal = () => {
            if (newProjectModal) newProjectModal.classList.add('hidden');
            if (newProjectNameInput) newProjectNameInput.value = '';
        };

        if (btnSidebarNewProject) btnSidebarNewProject.addEventListener('click', openModal);
        if (btnCloseProjectModal) btnCloseProjectModal.addEventListener('click', closeModal);
        if (btnCancelProjectModal) btnCancelProjectModal.addEventListener('click', closeModal);

        if (btnConfirmCreateProject) {
            btnConfirmCreateProject.addEventListener('click', async () => {
                const projName = newProjectNameInput?.value || '';
                try {
                    const res = await fetch('/api/create-project', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name: projName })
                    });
                    const data = await res.json();
                    if (data.success && data.project) {
                        closeModal();
                        await loadProjects(false);
                        activeProject = data.project;
                        if (projectSelector) projectSelector.value = activeProject;
                        loadProjectDetails(activeProject);
                    } else {
                        alert(data.error || 'Failed to create project');
                    }
                } catch (err) {
                    alert('Error creating project on server');
                }
            });
        }

        // Restart Server Button handler
        const btnRestartServer = document.getElementById('btnRestartServer');
        if (btnRestartServer) {
            btnRestartServer.addEventListener('click', async () => {
                if (!confirm('Restart the Flask backend server?')) return;
                try {
                    btnRestartServer.disabled = true;
                    btnRestartServer.innerHTML = '<span class="material-symbols-outlined text-base spin">sync</span> Restarting...';
                    await fetch('/api/restart-server', { method: 'POST' });
                    setTimeout(() => window.location.reload(), 2000);
                } catch (err) {
                    setTimeout(() => window.location.reload(), 2000);
                }
            });
        }

        // Cancel / Stop Running Step Handlers
        const handleCancel = async () => {
            if (!confirm('Are you sure you want to stop the running task?')) return;
            try {
                const res = await fetch('/api/cancel-step', { method: 'POST' });
                const data = await res.json();
                console.log('Cancelled:', data.message);
            } catch (err) {
                console.error('Error cancelling task:', err);
            }
        };

        if (btnCancelStep) btnCancelStep.addEventListener('click', handleCancel);
        if (btnTerminalCancel) btnTerminalCancel.addEventListener('click', handleCancel);

        // Clear Logs handler
        const btnClearLogs = document.getElementById('btnClearLogs');
        if (btnClearLogs && logContainer) {
            btnClearLogs.addEventListener('click', () => {
                logContainer.textContent = 'Logs cleared.';
            });
        }

        // Profile Inputs Syncing across top bar, script tab, and voice tab
        const profileInput = document.getElementById('profileInput');
        const scriptProfileInput = document.getElementById('scriptProfileInput');
        const voiceProfileInput = document.getElementById('voiceProfileInput');

        const syncProfiles = (sourceVal) => {
            if (profileInput && profileInput.value !== sourceVal) profileInput.value = sourceVal;
            if (scriptProfileInput && scriptProfileInput.value !== sourceVal) scriptProfileInput.value = sourceVal;
            if (voiceProfileInput && voiceProfileInput.value !== sourceVal) voiceProfileInput.value = sourceVal;
        };

        if (profileInput) profileInput.addEventListener('input', (e) => syncProfiles(e.target.value));
        if (scriptProfileInput) scriptProfileInput.addEventListener('input', (e) => syncProfiles(e.target.value));
        if (voiceProfileInput) voiceProfileInput.addEventListener('input', (e) => syncProfiles(e.target.value));

        // Script save
        const btnSaveScript = document.getElementById('btnSaveScript');
        if (btnSaveScript) btnSaveScript.addEventListener('click', saveScript);

        // Prompts save
        const btnSavePrompts = document.getElementById('btnSavePrompts');
        if (btnSavePrompts) btnSavePrompts.addEventListener('click', savePrompts);

        // Step triggers
        document.querySelectorAll('[data-step-action]').forEach(btn => {
            btn.addEventListener('click', () => {
                const step = btn.getAttribute('data-step-action');
                triggerStep(step);
            });
        });

        // Full Pipeline trigger
        const btnRunPipeline = document.getElementById('btnRunPipeline');
        if (btnRunPipeline) {
            btnRunPipeline.addEventListener('click', triggerFullPipeline);
        }
    }

    // Live word count and reading time stats
    function setupScriptStats() {
        const scriptTextarea = document.getElementById('scriptTextarea');
        const scriptWordCount = document.getElementById('scriptWordCount');
        const scriptReadTime = document.getElementById('scriptReadTime');

        if (!scriptTextarea) return;

        const updateStats = () => {
            const text = scriptTextarea.value.trim();
            const words = text ? text.split(/\s+/).length : 0;
            const minutes = Math.ceil(words / 140); // average speaking rate ~140 wpm
            if (scriptWordCount) scriptWordCount.textContent = `${words} words`;
            if (scriptReadTime) scriptReadTime.textContent = `~${minutes} min speech`;
        };

        scriptTextarea.addEventListener('input', updateStats);
    }

    let currentProjectsList = [];

    // Load list of projects from API
    async function loadProjects(refreshDetails = false) {
        try {
            const res = await fetch('/api/projects');
            const data = await res.json();
            const projects = data.projects || [];
            currentProjectsList = projects;
            
            const countLabel = document.getElementById('projectsCountLabel');
            if (countLabel) countLabel.textContent = `${projects.length} workspaces`;

            if (projectSelector) {
                const saved = localStorage.getItem('text2video_active_project');
                projectSelector.innerHTML = '';
                projects.forEach(proj => {
                    const opt = document.createElement('option');
                    opt.value = proj.name;
                    const badge = proj.progress === 100 ? '🎬 100% Ready' : `${proj.progress}%`;
                    opt.textContent = `${proj.name} [${badge}]`;
                    projectSelector.appendChild(opt);
                });

                if (saved && projects.some(p => p.name === saved)) {
                    projectSelector.value = saved;
                    activeProject = saved;
                } else if (projects.length > 0) {
                    activeProject = projects[0].name;
                    projectSelector.value = activeProject;
                }
            }

            renderProjectsGrid(projects);

            if (activeProject && (refreshDetails || !lastRunningState)) {
                loadProjectDetails(activeProject);
            }
        } catch (err) {
            console.error('Failed to load projects:', err);
        }
    }

    // Render projects in dashboard card grid
    function renderProjectsGrid(projects) {
        const grid = document.getElementById('projectsGrid');
        if (!grid) return;

        if (projects.length === 0) {
            grid.innerHTML = '<div class="col-span-full text-on-surface-variant text-center py-12">No projects found. Click "+ New Project" above to create one.</div>';
            return;
        }

        grid.innerHTML = projects.map(proj => {
            const isCompleted = proj.progress === 100;
            const isRendering = activeProject === proj.name && lastRunningState;
            const statusBadge = isRendering 
                ? '<div class="px-2.5 py-1 bg-surface/80 backdrop-blur-md rounded border border-outline-variant/30 flex items-center gap-1.5"><div class="w-2 h-2 rounded-full bg-primary pulse-dot"></div><span class="text-[10px] font-mono text-primary uppercase tracking-wider font-bold">RUNNING</span></div>'
                : isCompleted 
                    ? '<div class="px-2.5 py-1 bg-surface/80 backdrop-blur-md rounded border border-outline-variant/30 flex items-center gap-1.5"><span class="material-symbols-outlined text-[14px] text-tertiary">check_circle</span><span class="text-[10px] font-mono text-tertiary uppercase tracking-wider font-bold">COMPLETED</span></div>'
                    : `<div class="px-2.5 py-1 bg-surface/80 backdrop-blur-md rounded border border-outline-variant/30 flex items-center gap-1.5"><span class="text-[10px] font-mono text-outline uppercase tracking-wider font-bold">${proj.progress}% READY</span></div>`;

            return `
                <div class="glass-panel rounded-2xl overflow-hidden group hover:border-primary/50 transition-all duration-300 cursor-pointer glow-hover flex flex-col justify-between" onclick="selectProject('${proj.name}')">
                    <div class="p-5 flex-1">
                        <div class="flex justify-between items-start mb-3">
                            <h4 class="font-bold text-on-surface text-base truncate max-w-[200px]">${proj.name}</h4>
                            ${statusBadge}
                        </div>
                        <div class="w-full bg-surface-container-lowest h-1.5 rounded-full overflow-hidden mb-4">
                            <div class="bg-gradient-to-r from-secondary to-primary h-full transition-all duration-500 rounded-full" style="width: ${proj.progress}%"></div>
                        </div>
                        <div class="grid grid-cols-2 gap-2 text-xs font-mono text-on-surface-variant pt-2 border-t border-outline-variant/10">
                            <div class="flex items-center gap-1.5">
                                <span class="${proj.has_script ? 'text-tertiary' : 'text-outline'}">●</span>
                                <span class="${proj.has_script ? 'text-on-surface font-medium' : 'text-outline'}">Script</span>
                            </div>
                            <div class="flex items-center gap-1.5">
                                <span class="${proj.has_audio ? 'text-tertiary' : 'text-outline'}">●</span>
                                <span class="${proj.has_audio ? 'text-on-surface font-medium' : 'text-outline'}">Voice</span>
                            </div>
                            <div class="flex items-center gap-1.5">
                                <span class="${proj.has_prompts ? 'text-tertiary' : 'text-outline'}">●</span>
                                <span class="${proj.has_prompts ? 'text-on-surface font-medium' : 'text-outline'}">Prompts</span>
                            </div>
                            <div class="flex items-center gap-1.5">
                                <span class="${proj.has_video ? 'text-tertiary' : 'text-outline'}">●</span>
                                <span class="${proj.has_video ? 'text-on-surface font-medium' : 'text-outline'}">Video</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    window.selectProject = function(projName) {
        activeProject = projName;
        localStorage.setItem('text2video_active_project', projName);
        if (projectSelector) projectSelector.value = projName;
        loadProjectDetails(projName);
    };

    // Load details for the currently active project
    async function loadProjectDetails(projName) {
        if (!projName) return;
        try {
            const res = await fetch(`/api/project/${encodeURIComponent(projName)}`);
            const data = await res.json();
            if (data.error) return;

            // Script tab
            const scriptTextarea = document.getElementById('scriptTextarea');
            if (scriptTextarea) {
                scriptTextarea.value = data.script || '';
                scriptTextarea.dispatchEvent(new Event('input'));
            }

            // Transcript text
            const transcriptViewer = document.getElementById('transcriptViewer');
            if (transcriptViewer) {
                transcriptViewer.textContent = data.transcript || 'No transcript generated yet.';
            }

            // Prompts tab
            const promptsTextarea = document.getElementById('promptsTextarea');
            if (promptsTextarea) {
                promptsTextarea.value = data.prompts || '';
            }

            // Audio Player
            const audioPlayerContainer = document.getElementById('audioPlayerContainer');
            const audioSource = document.getElementById('audioSource');
            const audioPlayer = document.getElementById('audioPlayer');
            if (audioPlayerContainer && audioPlayer && audioSource) {
                if (data.audio_url) {
                    audioPlayerContainer.classList.remove('hidden');
                    if (audioSource.src !== window.location.origin + data.audio_url) {
                        audioSource.src = data.audio_url;
                        audioPlayer.load();
                    }
                } else {
                    audioPlayerContainer.classList.add('hidden');
                }
            }

            // Images Gallery
            const imageGallery = document.getElementById('imageGallery');
            const galleryCountBadge = document.getElementById('galleryCountBadge');
            if (galleryCountBadge) {
                galleryCountBadge.textContent = `${data.images ? data.images.length : 0} frames`;
            }

            if (imageGallery) {
                if (data.images && data.images.length > 0) {
                    imageGallery.innerHTML = data.images.map(img => `
                        <div class="group relative rounded-xl overflow-hidden border border-outline-variant/20 aspect-video bg-surface-container-lowest shadow-md">
                            <img src="${img.url}" alt="${img.filename}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"/>
                            <div class="absolute bottom-0 inset-x-0 bg-surface-dim/85 backdrop-blur text-[10px] p-1 text-center font-mono truncate text-on-surface-variant">${img.filename}</div>
                        </div>
                    `).join('');
                } else {
                    imageGallery.innerHTML = '<div class="col-span-full text-center text-outline py-12">No generated images found yet.</div>';
                }
            }

            // Final Video Player & Download
            const videoPlayerContainer = document.getElementById('videoPlayerContainer');
            const videoEmptyState = document.getElementById('videoEmptyState');
            const videoSource = document.getElementById('videoSource');
            const videoPlayer = document.getElementById('videoPlayer');
            const btnDownloadVideo = document.getElementById('btnDownloadVideo');
            const videoStatusBadge = document.getElementById('videoStatusBadge');

            if (data.images && data.images.length > 0) {
                currentProjectFirstImage = data.images[0].url;
                updatePreviewBackground();
            }

            if (videoPlayerContainer && videoPlayer && videoSource) {
                if (data.video_url) {
                    videoPlayerContainer.classList.remove('hidden');
                    if (videoEmptyState) videoEmptyState.classList.add('hidden');
                    if (btnDownloadVideo) {
                        btnDownloadVideo.href = data.video_url;
                        btnDownloadVideo.classList.remove('hidden');
                    }
                    if (videoStatusBadge) {
                        videoStatusBadge.className = 'px-2 py-0.5 text-[10px] font-mono rounded bg-tertiary-container/40 text-tertiary font-bold';
                        videoStatusBadge.textContent = 'AVAILABLE';
                    }
                    const freshUrl = `${data.video_url}?t=${Date.now()}`;
                    videoSource.src = freshUrl;
                    videoPlayer.load();
                } else {
                    videoPlayerContainer.classList.add('hidden');
                    if (videoEmptyState) videoEmptyState.classList.remove('hidden');
                    if (btnDownloadVideo) btnDownloadVideo.classList.add('hidden');
                    if (videoStatusBadge) {
                        videoStatusBadge.className = 'px-2 py-0.5 text-[10px] font-mono rounded bg-outline-variant/30 text-on-surface-variant font-bold';
                        videoStatusBadge.textContent = 'NOT GENERATED';
                    }
                }
            }

            const activeProjectBadge = document.getElementById('activeProjectBadge');
            if (activeProjectBadge) {
                activeProjectBadge.textContent = `Active Project: ${projName}`;
            }

            // Update Bento Badges & Step Cards
            updatePipelineStepBadge('stepBadgeScript', data.has_script, 'stepCard1', '1');
            updatePipelineStepBadge('stepBadgeVoice', data.has_audio, 'stepCard2', '2');
            updatePipelineStepBadge('stepBadgeTranscribe', (data.has_transcript || data.has_prompts), 'stepCard3', '3');
            updatePipelineStepBadge('stepBadgeImages', data.has_images, 'stepCard5', '5');
            updatePipelineStepBadge('stepBadgeVideo', data.has_video, 'stepCard6', '6');

        } catch (err) {
            console.error('Failed to load project details:', err);
        }
    }

    function updatePipelineStepBadge(elementId, isComplete, cardId, stepNum) {
        const badge = document.getElementById(elementId);
        const card = cardId ? document.getElementById(cardId) : null;
        const numBadge = stepNum ? document.getElementById(`stepNum${stepNum}`) : null;

        if (badge) {
            if (isComplete) {
                badge.className = 'px-2 py-0.5 text-xs rounded bg-tertiary/20 text-tertiary border border-tertiary/40 font-mono font-bold flex items-center gap-1 shadow-sm';
                badge.innerHTML = '<span class="material-symbols-outlined text-[13px] text-tertiary">check_circle</span><span>Done</span>';
            } else {
                badge.className = 'px-2 py-0.5 text-xs rounded bg-surface-container-highest text-outline border border-outline/20 font-mono flex items-center gap-1';
                badge.innerHTML = '<span class="material-symbols-outlined text-[13px]">hourglass_empty</span><span>Pending</span>';
            }
        }

        if (card) {
            if (isComplete) {
                card.classList.add('border-tertiary/40', 'bg-tertiary/[0.04]');
                card.classList.remove('border-outline-variant/20');
            } else {
                card.classList.remove('border-tertiary/40', 'bg-tertiary/[0.04]');
            }
        }

        if (numBadge) {
            if (isComplete) {
                numBadge.className = 'w-8 h-8 rounded-full bg-tertiary/25 flex items-center justify-center text-tertiary border border-tertiary/40 text-xs font-mono font-bold';
            } else {
                numBadge.className = 'w-8 h-8 rounded-full bg-surface-container-highest flex items-center justify-center text-primary border border-outline-variant/30 text-xs font-mono font-bold';
            }
        }
    }

    // Save Script
    async function saveScript() {
        const scriptTextarea = document.getElementById('scriptTextarea');
        if (!activeProject || !scriptTextarea) return;

        try {
            const res = await fetch('/api/save-script', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project: activeProject, script: scriptTextarea.value })
            });
            const data = await res.json();
            alert(data.message || 'Script saved successfully!');
        } catch (err) {
            alert('Failed to save script');
        }
    }

    // Save Prompts
    async function savePrompts() {
        const promptsTextarea = document.getElementById('promptsTextarea');
        if (!activeProject || !promptsTextarea) return;

        try {
            const res = await fetch('/api/save-prompts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project: activeProject, prompts: promptsTextarea.value })
            });
            const data = await res.json();
            alert(data.message || 'Prompts saved successfully!');
        } catch (err) {
            alert('Failed to save prompts');
        }
    }

    // Gather parameter configs
    function gatherUIConfig() {
        const topic = document.getElementById('topicInput')?.value || '';
        const profile = document.getElementById('profileInput')?.value || 'Profile 1';
        const voice = document.getElementById('voiceIdInput')?.value || document.getElementById('voiceSelect')?.value || '2styzLg7OSeuhPP6uQ26';
        const whisperModel = document.getElementById('whisperModelSelect')?.value || 'base';
        const refImage = document.getElementById('refImageSelect')?.value || 'milo.jpeg';
        const imageModel = document.getElementById('modelSelect')?.value || 'nano-banana-2';
        const delay = document.getElementById('delayInput')?.value || '8.0';

        const fontName = document.getElementById('fontNameSelect')?.value || 'Montserrat';
        const fontSize = document.getElementById('fontSizeInput')?.value || null;
        const textColor = document.getElementById('textColorInput')?.value || '#FFFFFF';
        const highlightColor = document.getElementById('highlightColorInput')?.value || '#FFD60A';
        const outlineColor = document.getElementById('outlineColorInput')?.value || '#000000';
        const position = document.getElementById('positionSelect')?.value || 'bottom';
        const addCaptions = document.getElementById('addCaptionsCheck')?.checked ?? true;

        const projSelectVal = document.getElementById('projectSelector')?.value;
        const finalProject = activeProject || projSelectVal || 'Why_Aren_t_Humans_Nocturnal';

        return {
            project: finalProject,
            topic,
            profile,
            voice,
            whisper_model: whisperModel,
            image_model: imageModel,
            model: imageModel,
            reference: refImage,
            target_model: imageModel,
            delay,
            font_name: fontName,
            font_size: fontSize ? parseInt(fontSize) : null,
            text_color: textColor,
            highlight_color: highlightColor,
            outline_color: outlineColor,
            position,
            add_captions: addCaptions
        };
    }

    let isStepTriggering = false;

    // Trigger individual step
    async function triggerStep(stepName) {
        if (isStepTriggering) return;
        isStepTriggering = true;
        setTimeout(() => { isStepTriggering = false; }, 2000);

        const config = gatherUIConfig();
        const body = { step: stepName, ...config };

        if (stepName === 'video') {
            const currentProj = activeProject || document.getElementById('projectSelector')?.value;
            const activeProjData = currentProjectsList.find(p => p.name === currentProj);
            if (activeProjData && (!activeProjData.has_images || !activeProjData.has_audio)) {
                alert(`⚠️ Workspace Incomplete:\n\nProject "${currentProj}" is missing generated images or audio files.\n\nPlease select a ready workspace like "Why_Aren_t_Humans_Nocturnal" (100% Ready) in the top dropdown, or generate voice and images first.`);
                isStepTriggering = false;
                return;
            }
        }

        // Immediate visual feedback on buttons
        const actionButtons = document.querySelectorAll(`[data-step-action="${stepName}"]`);
        actionButtons.forEach(btn => {
            if (!btn.dataset.originalHtml) {
                btn.dataset.originalHtml = btn.innerHTML;
            }
            btn.innerHTML = `<span class="material-symbols-outlined text-base animate-spin">progress_activity</span> <span>Rendering Video...</span>`;
            btn.classList.add('pointer-events-none', 'opacity-80');
        });

        if (stepName === 'video') {
            const videoEmptyState = document.getElementById('videoEmptyState');
            if (videoEmptyState) {
                videoEmptyState.innerHTML = `
                    <div class="flex flex-col items-center justify-center space-y-3 py-6">
                        <span class="material-symbols-outlined text-4xl text-primary animate-spin">progress_activity</span>
                        <p class="text-sm font-bold text-primary">Rendering Video with Subtitles & FFmpeg...</p>
                        <p class="text-xs text-on-surface-variant max-w-md text-center">Burning word-highlighted captions onto 1080p video. See live logs in the terminal below.</p>
                    </div>
                `;
            }
        }

        try {
            const res = await fetch('/api/run-step', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const data = await res.json();

            if (data.error) {
                alert(`Error: ${data.error}`);
                actionButtons.forEach(btn => {
                    if (btn.dataset.originalHtml) {
                        btn.innerHTML = btn.dataset.originalHtml;
                        delete btn.dataset.originalHtml;
                    }
                    btn.classList.remove('pointer-events-none', 'opacity-80');
                });
            } else {
                console.log(`Step ${stepName} started cleanly.`);
                const logDrawer = document.getElementById('logContainer');
                if (logDrawer) {
                    logDrawer.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
        } catch (err) {
            alert('Failed to start step execution. Check backend server.');
            actionButtons.forEach(btn => {
                if (btn.dataset.originalHtml) {
                    btn.innerHTML = btn.dataset.originalHtml;
                    delete btn.dataset.originalHtml;
                }
                btn.classList.remove('pointer-events-none', 'opacity-80');
            });
        }
    }
    window.triggerStep = triggerStep;

    // Trigger full pipeline
    async function triggerFullPipeline() {
        const body = gatherUIConfig();

        try {
            const res = await fetch('/api/run-pipeline', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const data = await res.json();

            if (data.error) {
                alert(`Error starting pipeline: ${data.error}`);
            } else {
                console.log('Sequential pipeline started.');
            }
        } catch (err) {
            alert('Failed to start full pipeline');
        }
    }

    // Start auto polling for backend status & unbuffered logs
    function startStatusPolling() {
        pollInterval = setInterval(async () => {
            try {
                const res = await fetch('/api/status');
                const state = await res.json();
                
                const isRunning = state.is_running;

                // Stop Button visibility
                if (btnCancelStep) {
                    if (isRunning) btnCancelStep.classList.remove('hidden');
                    else btnCancelStep.classList.add('hidden');
                }
                if (btnTerminalCancel) {
                    if (isRunning) btnTerminalCancel.classList.remove('hidden');
                    else btnTerminalCancel.classList.add('hidden');
                }

                // Update Status Badge & Pill
                if (statusPill && statusText) {
                    if (isRunning) {
                        statusPill.className = 'w-2.5 h-2.5 rounded-full bg-primary pulse-dot';
                        statusText.textContent = `Running: ${state.current_step || 'task'}...`;
                        statusText.className = 'text-primary font-mono text-xs font-bold';

                        if (logStatusBadge) {
                            logStatusBadge.className = 'px-2 py-0.5 text-[10px] font-mono rounded bg-primary-container text-white uppercase font-bold animate-pulse';
                            logStatusBadge.textContent = 'RUNNING';
                        }
                    } else if (state.status === 'success') {
                        statusPill.className = 'w-2.5 h-2.5 rounded-full bg-tertiary';
                        statusText.textContent = 'Idle (Step Passed)';
                        statusText.className = 'text-tertiary font-mono text-xs';

                        if (logStatusBadge) {
                            logStatusBadge.className = 'px-2 py-0.5 text-[10px] font-mono rounded bg-tertiary-container/30 text-tertiary border border-tertiary/30 uppercase font-bold';
                            logStatusBadge.textContent = 'SUCCESS';
                        }
                    } else if (state.status === 'error') {
                        statusPill.className = 'w-2.5 h-2.5 rounded-full bg-error';
                        statusText.textContent = 'Step Failed (Halted)';
                        statusText.className = 'text-error font-mono text-xs font-bold';

                        if (logStatusBadge) {
                            logStatusBadge.className = 'px-2 py-0.5 text-[10px] font-mono rounded bg-error-container text-white uppercase font-bold';
                            logStatusBadge.textContent = 'ERROR';
                        }
                    } else if (state.status === 'cancelled') {
                        statusPill.className = 'w-2.5 h-2.5 rounded-full bg-outline';
                        statusText.textContent = 'Cancelled (Idle)';
                        statusText.className = 'text-on-surface-variant font-mono text-xs';

                        if (logStatusBadge) {
                            logStatusBadge.className = 'px-2 py-0.5 text-[10px] font-mono rounded bg-surface-container-highest text-outline uppercase font-bold';
                            logStatusBadge.textContent = 'CANCELLED';
                        }
                    } else {
                        statusPill.className = 'w-2.5 h-2.5 rounded-full bg-outline-variant';
                        statusText.textContent = 'System Ready';
                        statusText.className = 'text-on-surface-variant font-mono text-xs';

                        if (logStatusBadge) {
                            logStatusBadge.className = 'px-2 py-0.5 text-[10px] font-mono rounded bg-outline-variant/30 text-on-surface-variant uppercase font-bold';
                            logStatusBadge.textContent = 'IDLE';
                        }
                    }
                }

                // Action Buttons Disabled state
                document.querySelectorAll('[data-step-action], #btnRunPipeline').forEach(btn => {
                    if (isRunning) {
                        btn.classList.add('opacity-50', 'pointer-events-none');
                    } else {
                        btn.classList.remove('opacity-50', 'pointer-events-none');
                    }
                });

                // Update Terminal Logs with auto-scroll
                if (logContainer && state.logs) {
                    logContainer.textContent = state.logs.join('');
                    if (autoScrollCheck && autoScrollCheck.checked) {
                        logContainer.scrollTop = logContainer.scrollHeight;
                    }
                }

                // State transition from Running -> Stopped: reload project details ONCE
                if (lastRunningState && !isRunning) {
                    const currentProj = activeProject || document.getElementById('projectSelector')?.value || 'Why_Aren_t_Humans_Nocturnal';
                    loadProjectDetails(currentProj);
                    loadProjects(false);

                    // Restore any button original HTML
                    document.querySelectorAll('[data-step-action]').forEach(btn => {
                        if (btn.dataset.originalHtml) {
                            btn.innerHTML = btn.dataset.originalHtml;
                            delete btn.dataset.originalHtml;
                        }
                        btn.classList.remove('pointer-events-none', 'opacity-80');
                    });
                }

                lastRunningState = isRunning;

            } catch (err) {
                console.error('Error polling status:', err);
            }
        }, 1200);
    }

    // ----------------------------------------------------
    // SUBTITLE STYLING PRESETS & LIVE INTERACTIVE PREVIEW
    // ----------------------------------------------------

    // Define preset UI application function (hoisted & attached to window)
    function applyPresetFromUI(presetKey) {
        applySubtitlePreset(presetKey);
        document.querySelectorAll('.subtitle-preset-btn').forEach(b => {
            if (b.getAttribute('data-preset') === presetKey) {
                b.classList.add('active-preset', 'ring-2', 'ring-primary', 'bg-primary/20');
            } else {
                b.classList.remove('active-preset', 'ring-2', 'ring-primary', 'bg-primary/20');
            }
        });
        const activePresetBadge = document.getElementById('activePresetBadge');
        if (activePresetBadge && SUBTITLE_PRESETS[presetKey]) {
            const formatted = presetKey.replace('-', ' ').replace(/\b\w/g, c => c.toUpperCase());
            activePresetBadge.textContent = `Preset: ${formatted}`;
        }
    }
    window.applyPresetFromUI = applyPresetFromUI;

    function clearActivePresets() {
        document.querySelectorAll('.subtitle-preset-btn').forEach(b => {
            b.classList.remove('active-preset', 'ring-2', 'ring-primary', 'bg-primary/20');
        });
        const activePresetBadge = document.getElementById('activePresetBadge');
        if (activePresetBadge) {
            activePresetBadge.textContent = 'Preset: Custom';
        }
    }

    function applySubtitlePreset(presetKey) {
        const preset = SUBTITLE_PRESETS[presetKey];
        if (!preset) return;

        const fontNameSelect = document.getElementById('fontNameSelect');
        const fontSizeSlider = document.getElementById('fontSizeSlider');
        const fontSizeInput = document.getElementById('fontSizeInput');
        const fontSizeDisplay = document.getElementById('fontSizeDisplay');
        const textColorInput = document.getElementById('textColorInput');
        const textColorHex = document.getElementById('textColorHex');
        const highlightColorInput = document.getElementById('highlightColorInput');
        const highlightColorHex = document.getElementById('highlightColorHex');
        const outlineColorInput = document.getElementById('outlineColorInput');
        const outlineThicknessSelect = document.getElementById('outlineThicknessSelect');
        const positionSelect = document.getElementById('positionSelect');
        const fontTag = document.getElementById('fontPreviewTag');

        if (fontNameSelect) fontNameSelect.value = preset.font;
        if (fontTag) fontTag.textContent = `${preset.font} (Bold)`;
        if (fontSizeSlider) fontSizeSlider.value = preset.size;
        if (fontSizeInput) fontSizeInput.value = preset.size;
        if (fontSizeDisplay) fontSizeDisplay.textContent = `${preset.size} px`;
        if (textColorInput) textColorInput.value = preset.textColor;
        if (textColorHex) textColorHex.value = preset.textColor;
        if (highlightColorInput) highlightColorInput.value = preset.highlightColor;
        if (highlightColorHex) highlightColorHex.value = preset.highlightColor;
        if (outlineColorInput) outlineColorInput.value = preset.outlineColor;
        if (outlineThicknessSelect) outlineThicknessSelect.value = preset.outlineThickness;
        if (positionSelect) positionSelect.value = preset.position;

        renderSubtitlePreview();
    }
    window.applySubtitlePreset = applySubtitlePreset;

    function renderSubtitlePreview() {
        const overlay = document.getElementById('subtitleLiveOverlay');
        const stage = document.getElementById('subtitleStage');
        if (!overlay || !stage) return;

        const fontName = document.getElementById('fontNameSelect')?.value || 'Montserrat';
        const fontSizeVal = parseInt(document.getElementById('fontSizeInput')?.value || '80', 10);
        const textColor = document.getElementById('textColorInput')?.value || '#FFFFFF';
        const highlightColor = document.getElementById('highlightColorInput')?.value || '#FFD60A';
        const outlineColor = document.getElementById('outlineColorInput')?.value || '#000000';
        const outlineThickness = document.getElementById('outlineThicknessSelect')?.value || 'medium';
        const position = document.getElementById('positionSelect')?.value || 'bottom';
        const sampleText = document.getElementById('sampleCaptionInput')?.value || "Why aren't humans nocturnal like owls?";

        // Proportional sizing: at 1080p full frame, height is 1080.
        // In the preview container, height is approx 240-340px.
        const stageRect = stage.getBoundingClientRect();
        const stageHeight = stageRect.height || stage.clientHeight || stage.offsetHeight || 280;
        const scaledFontSize = Math.max(14, Math.round((fontSizeVal / 1080) * Math.max(stageHeight, 280)));

        let shadowCss = 'none';
        if (outlineThickness === 'subtle') {
            shadowCss = `1px 1px 0 ${outlineColor}, -1px -1px 0 ${outlineColor}, 1px -1px 0 ${outlineColor}, -1px 1px 0 ${outlineColor}, 0 2px 5px rgba(0,0,0,0.8)`;
        } else if (outlineThickness === 'medium') {
            shadowCss = `2px 2px 0 ${outlineColor}, -2px -2px 0 ${outlineColor}, 2px -2px 0 ${outlineColor}, -2px 2px 0 ${outlineColor}, 0 3px 8px rgba(0,0,0,0.9)`;
        } else if (outlineThickness === 'heavy') {
            shadowCss = `3px 3px 0 ${outlineColor}, -3px -3px 0 ${outlineColor}, 3px -3px 0 ${outlineColor}, -3px 3px 0 ${outlineColor}, 0 4px 10px rgba(0,0,0,1)`;
        }

        overlay.style.position = 'absolute';
        overlay.style.left = '0';
        overlay.style.right = '0';
        overlay.style.width = '100%';
        overlay.style.padding = '0 1.5rem';
        overlay.style.boxSizing = 'border-box';
        
        if (position === 'top') {
            overlay.style.top = '12%';
            overlay.style.bottom = 'auto';
            overlay.style.transform = 'none';
        } else if (position === 'middle') {
            overlay.style.top = '50%';
            overlay.style.bottom = 'auto';
            overlay.style.transform = 'translateY(-50%)';
        } else {
            overlay.style.bottom = '12%';
            overlay.style.top = 'auto';
            overlay.style.transform = 'none';
        }

        overlay.style.fontFamily = FONT_CSS_MAP[fontName] || `'${fontName}', sans-serif`;
        overlay.style.fontSize = `${scaledFontSize}px`;
        overlay.style.fontWeight = '900';
        overlay.style.textTransform = 'uppercase';

        const words = sampleText.trim().split(/\s+/).filter(Boolean);
        if (words.length === 0) {
            overlay.innerHTML = '<span class="text-outline text-xs font-mono">No text entered</span>';
            return;
        }

        if (activeHighlightWordIndex >= words.length) {
            activeHighlightWordIndex = 0;
        }

        overlay.innerHTML = words.map((w, idx) => {
            const isActive = idx === activeHighlightWordIndex;
            const color = isActive ? highlightColor : textColor;
            const activeClass = isActive ? 'sub-word-item sub-word-active' : 'sub-word-item';
            
            let textShadowStyle = '';
            if (shadowCss !== 'none') {
                if (isActive) {
                    textShadowStyle = `text-shadow: ${shadowCss}, 0 0 16px ${highlightColor}aa;`;
                } else {
                    textShadowStyle = `text-shadow: ${shadowCss};`;
                }
            } else {
                if (isActive) {
                    textShadowStyle = `text-shadow: 0 0 16px ${highlightColor}aa;`;
                } else {
                    textShadowStyle = 'text-shadow: none;';
                }
            }

            return `<span class="${activeClass}" data-word-idx="${idx}" style="color: ${color}; ${textShadowStyle} cursor: pointer;">${w}</span>`;
        }).join(' ');

        // Attach click listeners to individual word spans
        overlay.querySelectorAll('.sub-word-item').forEach(span => {
            span.addEventListener('click', (e) => {
                e.stopPropagation();
                const idx = parseInt(span.getAttribute('data-word-idx'), 10);
                activeHighlightWordIndex = idx;
                renderSubtitlePreview();
            });
        });
    }
    window.renderSubtitlePreview = renderSubtitlePreview;

    function updatePreviewBackground() {
        const bgSelect = document.getElementById('previewBgSelect');
        const stageImg = document.getElementById('subtitleStageImage');
        const stageGradient = document.getElementById('subtitleStageGradient');
        const stage = document.getElementById('subtitleStage');
        if (!bgSelect || !stage) return;

        const bgType = bgSelect.value;
        if (bgType === 'project' && currentProjectFirstImage) {
            if (stageImg) {
                stageImg.src = currentProjectFirstImage;
                stageImg.classList.remove('hidden');
            }
            if (stageGradient) {
                stageGradient.className = 'absolute inset-0 bg-gradient-to-t from-black/85 via-black/35 to-black/60 pointer-events-none';
            }
        } else if (bgType === 'studio') {
            if (stageImg) stageImg.classList.add('hidden');
            if (stageGradient) {
                stageGradient.className = 'absolute inset-0 bg-gradient-to-br from-slate-800 via-slate-900 to-black pointer-events-none';
            }
        } else {
            if (stageImg) stageImg.classList.add('hidden');
            if (stageGradient) {
                stageGradient.className = 'absolute inset-0 bg-gradient-to-t from-black/90 via-blue-950/40 to-black/80 pointer-events-none';
            }
        }
    }
    window.updatePreviewBackground = updatePreviewBackground;

    function toggleKaraokeAnimation() {
        const btn = document.getElementById('btnToggleKaraoke');
        const icon = document.getElementById('iconKaraoke');
        const text = document.getElementById('textKaraoke');

        if (isKaraokePlaying) {
            clearInterval(karaokeInterval);
            isKaraokePlaying = false;
            if (icon) icon.textContent = 'play_arrow';
            if (text) text.textContent = 'Play Animation';
            btn?.classList.remove('bg-primary/30');
        } else {
            isKaraokePlaying = true;
            if (icon) icon.textContent = 'pause';
            if (text) text.textContent = 'Pause';
            btn?.classList.add('bg-primary/30');

            karaokeInterval = setInterval(() => {
                const sampleText = document.getElementById('sampleCaptionInput')?.value || '';
                const words = sampleText.trim().split(/\s+/).filter(Boolean);
                if (words.length === 0) return;

                activeHighlightWordIndex = (activeHighlightWordIndex + 1) % words.length;
                renderSubtitlePreview();
            }, 450);
        }
    }

    function setupSubtitlePreview() {
        const fontNameSelect = document.getElementById('fontNameSelect');
        const fontSizeSlider = document.getElementById('fontSizeSlider');
        const fontSizeInput = document.getElementById('fontSizeInput');
        const fontSizeDisplay = document.getElementById('fontSizeDisplay');
        const textColorInput = document.getElementById('textColorInput');
        const textColorHex = document.getElementById('textColorHex');
        const highlightColorInput = document.getElementById('highlightColorInput');
        const highlightColorHex = document.getElementById('highlightColorHex');
        const outlineColorInput = document.getElementById('outlineColorInput');
        const outlineThicknessSelect = document.getElementById('outlineThicknessSelect');
        const positionSelect = document.getElementById('positionSelect');
        const sampleCaptionInput = document.getElementById('sampleCaptionInput');
        const previewBgSelect = document.getElementById('previewBgSelect');
        const btnToggleKaraoke = document.getElementById('btnToggleKaraoke');

        // Font family change
        if (fontNameSelect) {
            fontNameSelect.addEventListener('change', () => {
                const fontTag = document.getElementById('fontPreviewTag');
                if (fontTag) fontTag.textContent = `${fontNameSelect.value} (Bold)`;
                clearActivePresets();
                renderSubtitlePreview();
            });
        }

        // Font size sync (Slider <-> Input)
        if (fontSizeSlider && fontSizeInput) {
            fontSizeSlider.addEventListener('input', (e) => {
                fontSizeInput.value = e.target.value;
                if (fontSizeDisplay) fontSizeDisplay.textContent = `${e.target.value} px`;
                clearActivePresets();
                renderSubtitlePreview();
            });
            fontSizeInput.addEventListener('input', (e) => {
                fontSizeSlider.value = e.target.value;
                if (fontSizeDisplay) fontSizeDisplay.textContent = `${e.target.value} px`;
                clearActivePresets();
                renderSubtitlePreview();
            });
        }

        // Color pickers sync (Picker <-> Hex Text)
        if (textColorInput && textColorHex) {
            textColorInput.addEventListener('input', (e) => {
                textColorHex.value = e.target.value.toUpperCase();
                clearActivePresets();
                renderSubtitlePreview();
            });
            textColorHex.addEventListener('input', (e) => {
                if (/^#[0-9A-F]{6}$/i.test(e.target.value)) {
                    textColorInput.value = e.target.value;
                    clearActivePresets();
                    renderSubtitlePreview();
                }
            });
        }

        if (highlightColorInput && highlightColorHex) {
            highlightColorInput.addEventListener('input', (e) => {
                highlightColorHex.value = e.target.value.toUpperCase();
                clearActivePresets();
                renderSubtitlePreview();
            });
            highlightColorHex.addEventListener('input', (e) => {
                if (/^#[0-9A-F]{6}$/i.test(e.target.value)) {
                    highlightColorInput.value = e.target.value;
                    clearActivePresets();
                    renderSubtitlePreview();
                }
            });
        }

        if (outlineColorInput) {
            outlineColorInput.addEventListener('input', () => {
                clearActivePresets();
                renderSubtitlePreview();
            });
        }

        if (outlineThicknessSelect) {
            outlineThicknessSelect.addEventListener('change', () => {
                clearActivePresets();
                renderSubtitlePreview();
            });
        }

        if (positionSelect) {
            positionSelect.addEventListener('change', () => {
                clearActivePresets();
                renderSubtitlePreview();
            });
        }

        if (sampleCaptionInput) {
            sampleCaptionInput.addEventListener('input', () => {
                activeHighlightWordIndex = 0;
                renderSubtitlePreview();
            });
        }

        if (previewBgSelect) {
            previewBgSelect.addEventListener('change', updatePreviewBackground);
        }

        // Preset buttons click listeners
        document.querySelectorAll('.subtitle-preset-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const presetKey = btn.getAttribute('data-preset');
                applyPresetFromUI(presetKey);
            });
        });

        // Karaoke button
        if (btnToggleKaraoke) {
            btnToggleKaraoke.addEventListener('click', toggleKaraokeAnimation);
        }

        // Window resize listener to keep proportional preview
        window.addEventListener('resize', () => {
            if (currentTab === 'export') {
                renderSubtitlePreview();
            }
        });

        // Initial default preset load
        applyPresetFromUI('viral-yellow');
    }
});

