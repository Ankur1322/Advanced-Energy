// app.js

// ============================================================================
// 1. THREE.JS LIQUID FLUID (WATERY) INTERACTIVE BACKGROUND
// ============================================================================
const initThreeBackground = () => {
  const canvas = document.querySelector('#three-bg');
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  
  const scene = new THREE.Scene();
  
  // Camera
  const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 100);
  camera.position.set(0, 0, 25);
  
  // Resize handler
  const resizeCanvas = () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  };
  window.addEventListener('resize', resizeCanvas);
  resizeCanvas();

  // Create an organic undulating watery wave plane using PlaneGeometry
  const planeWidth = 55;
  const planeHeight = 45;
  const gridSegments = 50;
  
  const geometry = new THREE.PlaneGeometry(planeWidth, planeHeight, gridSegments, gridSegments);
  
  // Custom slow waves by mutating the plane's vertex Z positions over time
  const posAttr = geometry.attributes.position;
  const initialPositions = posAttr.array.slice(); // Deep clone

  // Watery mesh material - transparent, glowing wireframe for a premium digital grid
  const material = new THREE.MeshBasicMaterial({
    color: 0x00b4ff,
    wireframe: true,
    transparent: true,
    opacity: 0.08,
    blending: THREE.AdditiveBlending
  });

  const waveMesh = new THREE.Mesh(geometry, material);
  waveMesh.rotation.x = -Math.PI / 2.3; // Angled perspective
  waveMesh.position.y = -6;
  scene.add(waveMesh);

  // Add floating glowing liquid bubbles (particles)
  const bubbleCount = 65;
  const bubbleGeometry = new THREE.BufferGeometry();
  const bubblePositions = new Float32Array(bubbleCount * 3);
  const bubbleSpeeds = [];

  for (let i = 0; i < bubbleCount * 3; i += 3) {
    bubblePositions[i] = (Math.random() - 0.5) * 45;
    bubblePositions[i+1] = (Math.random() - 0.5) * 35;
    bubblePositions[i+2] = (Math.random() - 0.5) * 10;
    
    bubbleSpeeds.push({
      x: (Math.random() - 0.5) * 0.015,
      y: (Math.random() - 0.5) * 0.015 + 0.005, // Slowly float upwards
      z: (Math.random() - 0.5) * 0.01
    });
  }

  bubbleGeometry.setAttribute('position', new THREE.BufferAttribute(bubblePositions, 3));
  const bubbleMaterial = new THREE.PointsMaterial({
    color: 0xaa50ff,
    size: 0.6,
    transparent: true,
    opacity: 0.4,
    blending: THREE.AdditiveBlending
  });

  const bubbleSystem = new THREE.Points(bubbleGeometry, bubbleMaterial);
  scene.add(bubbleSystem);

  // Mouse interaction variables
  let targetMouseX = 0;
  let targetMouseY = 0;
  let mouseX = 0;
  let mouseY = 0;

  window.addEventListener('mousemove', (e) => {
    targetMouseX = (e.clientX - window.innerWidth / 2) * 0.02;
    targetMouseY = (e.clientY - window.innerHeight / 2) * 0.02;
  });

  // Animation Loop
  const clock = new THREE.Clock();
  const animate = () => {
    requestAnimationFrame(animate);

    const time = clock.getElapsedTime();
    
    // Smooth mouse damping for silky iOS feel
    mouseX += (targetMouseX - mouseX) * 0.08;
    mouseY += (targetMouseY - mouseY) * 0.08;

    // 1. Animate Liquid Waves (Plane vertices undulation)
    const array = waveMesh.geometry.attributes.position.array;
    for (let i = 0; i < array.length; i += 3) {
      const x = initialPositions[i];
      const y = initialPositions[i+1];
      
      const wave1 = Math.sin(x * 0.15 + time * 1.2) * 2.0;
      const wave2 = Math.cos(y * 0.2 + time * 0.8) * 1.5;
      const wave3 = Math.sin((x + y) * 0.08 + time * 1.5) * 1.0;
      const mouseInfluence = Math.sin(x * 0.05 + mouseX) * Math.cos(y * 0.05 + mouseY) * 3.0;

      array[i+2] = wave1 + wave2 + wave3 + mouseInfluence;
    }
    waveMesh.geometry.attributes.position.needsUpdate = true;

    // 2. Animate Glowing Liquid Bubbles
    const bArray = bubbleSystem.geometry.attributes.position.array;
    for (let i = 0; i < bubbleCount; i++) {
      const idx = i * 3;
      
      bArray[idx] += bubbleSpeeds[i].x;
      bArray[idx+1] += bubbleSpeeds[i].y;
      bArray[idx+2] += bubbleSpeeds[i].z;

      // Recirculate bubbles if they float too high
      if (bArray[idx+1] > 20) {
        bArray[idx+1] = -20;
        bArray[idx] = (Math.random() - 0.5) * 45;
      }
      if (Math.abs(bArray[idx]) > 25) {
        bubbleSpeeds[i].x *= -1;
      }
    }
    bubbleSystem.geometry.attributes.position.needsUpdate = true;

    // Camera organic breathing float
    camera.position.x = mouseX * 0.25;
    camera.position.y = -mouseY * 0.25;
    camera.lookAt(0, 0, 0);

    renderer.render(scene, camera);
  };

  animate();
};


// ============================================================================
// 2. NESTED NAVIGATION ENGINE (PRIMARY + SECONDARY SIDEBARS)
// ============================================================================
const initNavigationEngine = () => {
  const primaryNavItems = document.querySelectorAll('.primary-nav-item');
  const secondaryNavItems = document.querySelectorAll('.submenu-item');
  const viewContents = document.querySelectorAll('.view-content');
  
  const titleEl = document.querySelector('#main-view-title');
  const subtitleEl = document.querySelector('#main-view-subtitle');

  const viewMetadata = {
    hub: { title: 'Cognitive Hub', subtitle: 'AE BOT conversational Spec sheets synthesis terminal' },
    datasources: { title: 'Product Data Sources', subtitle: 'Physical folder taxonomy of crawled AE data' },
    suggestions: { title: 'Curated Prompt Blueprints', subtitle: 'Curated prompt queries for high-priority AE product specs' },
    playground: { title: 'Retrieval Sandbox Playground', subtitle: 'Inspect raw similarity distances and retrieved document blocks' },
    tasks: { title: 'Ingestion tasks & Processes', subtitle: 'Live ingestion scraper logs and vectorization telemetry' },
    configure: { title: 'API Key Configuration', subtitle: 'Manage authorization variables for Google Gemini API' },
    train: { title: 'Embedding Model details', subtitle: 'Mathematical parameters of 128-dim TF-IDF + SVD vector spaces' }
  };

  // Helper to switch view safely with GSAP Fades
  const switchView = (targetViewId) => {
    const activeView = document.querySelector('.view-content.active');
    const targetView = document.querySelector(`#view-${targetViewId}`);

    if (activeView === targetView) return;

    // Phase 1: Fade out active view
    gsap.to(activeView, {
      opacity: 0,
      y: -15,
      duration: 0.25,
      ease: 'power2.in',
      onComplete: () => {
        activeView.classList.remove('active');

        // Update titles
        const meta = viewMetadata[targetViewId];
        titleEl.textContent = meta.title;
        subtitleEl.textContent = meta.subtitle;

        // Prepare target view
        targetView.classList.add('active');
        gsap.set(targetView, { opacity: 0, y: 15 });

        // Phase 2: Fade in target view
        gsap.to(targetView, {
          opacity: 1,
          y: 0,
          duration: 0.4,
          ease: 'power2.out'
        });
      }
    });

    // Synchronize secondary active sidebar states
    secondaryNavItems.forEach(item => {
      if (item.getAttribute('data-subtab') === targetViewId) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    // Synchronize primary narrow active icon states
    const primaryMapping = {
      hub: 'hub',
      playground: 'hub',
      suggestions: 'hub',
      datasources: 'datasources',
      tasks: 'datasources',
      configure: 'configure',
      train: 'train'
    };
    const targetPrimaryGroup = primaryMapping[targetViewId];
    primaryNavItems.forEach(item => {
      if (item.getAttribute('data-submenu') === targetPrimaryGroup) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });
  };

  // 1. Primary narrow Sidebar Click Handler
  primaryNavItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const targetSubmenu = item.getAttribute('data-submenu');
      switchView(targetSubmenu);
    });
  });

  // 2. Secondary Submenu Sidebar Click Handler
  secondaryNavItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const targetSubtab = item.getAttribute('data-subtab');
      switchView(targetSubtab);
    });
  });

  // 3. Collapsible Submenu Group
  const knowledgeHeader = document.querySelector('#knowledge-group-header');
  const knowledgeItems = document.querySelector('#knowledge-group-items');
  const chevron = document.querySelector('#knowledge-chevron');
  let groupExpanded = true;

  knowledgeHeader.addEventListener('click', () => {
    groupExpanded = !groupExpanded;
    
    // Smooth GSAP slide transition for collapsible menu
    if (groupExpanded) {
      gsap.to(chevron, { rotation: 0, duration: 0.3 });
      gsap.to(knowledgeItems, { height: 'auto', opacity: 1, duration: 0.4, ease: 'power2.out' });
    } else {
      gsap.to(chevron, { rotation: -90, duration: 0.3 });
      gsap.to(knowledgeItems, { height: 0, opacity: 0, duration: 0.4, ease: 'power2.in' });
    }
  });

  // 4. Settings shortcut from narrow bottom
  document.querySelector('#settings-shortcut').addEventListener('click', (e) => {
    e.preventDefault();
    switchView('configure');
  });

  // [NEW] Collapsible Secondary Sidebar
  const collapseBtn = document.querySelector('#sidebar-collapse-btn');
  const collapseIcon = document.querySelector('#collapse-icon');
  const secondarySidebar = document.querySelector('.secondary-sidebar');
  let sidebarCollapsed = false;

  collapseBtn.addEventListener('click', (e) => {
    e.preventDefault();
    sidebarCollapsed = !sidebarCollapsed;

    if (sidebarCollapsed) {
      // Collapse using GSAP
      gsap.to(secondarySidebar, {
        width: 0,
        opacity: 0,
        duration: 0.45,
        ease: 'power3.inOut'
      });
      // Move floating button to the primary border (76px - 14px = 62px)
      gsap.to(collapseBtn, {
        left: '62px',
        duration: 0.45,
        ease: 'power3.inOut',
        onComplete: () => {
          collapseIcon.name = 'chevron-forward-outline';
          collapseBtn.title = 'Expand Sidebar';
        }
      });
    } else {
      // Expand using GSAP
      gsap.to(secondarySidebar, {
        width: '250px',
        opacity: 1,
        duration: 0.45,
        ease: 'power3.inOut'
      });
      // Move floating button back to expanded position (76px + 250px - 14px = 312px)
      gsap.to(collapseBtn, {
        left: '312px',
        duration: 0.45,
        ease: 'power3.inOut',
        onComplete: () => {
          collapseIcon.name = 'chevron-back-outline';
          collapseBtn.title = 'Collapse Sidebar';
        }
      });
    }
    
    // Trigger resize manually to let Three.js wave background adjust instantly
    setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
    }, 450);
  });

  // [NEW] Light/Dark Theme Toggler
  const themeBtn = document.querySelector('#theme-toggle-btn');
  const themeIcon = document.querySelector('#theme-icon');
  themeBtn.addEventListener('click', () => {
    document.body.classList.toggle('light-theme');
    if (document.body.classList.contains('light-theme')) {
      themeIcon.name = 'sunny-outline';
    } else {
      themeIcon.name = 'moon-outline';
    }
  });
};


// ============================================================================
// 3. SYSTEM STATS & TELEMETRY INGESTION
// ============================================================================
const fetchSystemStatus = async () => {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();

    // Ingest stats into widgets safely
    const setSafe = (sel, val) => { const el = document.querySelector(sel); if(el) el.textContent = val; };
    setSafe('#stat-categories', data.scraper.total_categories);
    setSafe('#stat-subproducts', data.scraper.total_subproducts);
    setSafe('#datasource-categories-count', data.scraper.total_categories);
    setSafe('#datasource-products-count', data.scraper.total_subproducts);
    setSafe('#telemetry-profiles', data.scraper.total_subproducts);

    const dbVal = document.querySelector('#stat-vector-db');
    if (dbVal) {
      if (data.database.initialized) {
        dbVal.textContent = 'ONLINE';
        dbVal.style.color = 'var(--accent-green)';
      } else {
        dbVal.textContent = 'OFFLINE';
        dbVal.style.color = 'var(--accent-amber)';
      }
    }

    // Key configuration syncer
    const savedKey = sessionStorage.getItem('gemini_api_key') || '';
    if (data.gemini_key_configured || savedKey) {
      setEngineAuthorized(true);
    } else {
      setEngineAuthorized(false);
    }

  } catch (err) {
    console.error('Failed to grab live system stats telemetry:', err);
  }
};

const setEngineAuthorized = (active) => {
  const badge = document.querySelector('#badge-engine-state');
  const badgeText = document.querySelector('#badge-engine-text');
  
  if (badge && badgeText) {
    if (active) {
      badge.className = 'engine-badge active';
      badgeText.textContent = 'ENGINE ACTIVE';
    } else {
      badge.className = 'engine-badge inactive';
      badgeText.textContent = 'OFFLINE MOCK';
    }
  }
  
  // Sync placeholders inside inputs safely
  const input1 = document.querySelector('#api-key-input');
  const input2 = document.querySelector('#configure-api-key-input');
  
  if (active) {
    if (input1) input1.placeholder = '••••••••••••••••••••';
    if (input2) input2.placeholder = '••••••••••••••••••••';
  } else {
    if (input1) input1.placeholder = 'Enter Gemini Key...';
    if (input2) input2.placeholder = 'Paste GEMINI_API_KEY here...';
  }
};


// ============================================================================
// 4. TAXONOMY TREE MANAGER
// ============================================================================
let originalTaxonomyText = '';

const fetchTaxonomyHierarchy = async () => {
  const pre = document.querySelector('#taxonomy-hierarchy-text');
  try {
    const res = await fetch('/api/tree');
    if (!res.ok) {
      const err = await res.json();
      pre.textContent = err.error || 'Failed to read taxonomy tree.';
      return;
    }
    const data = await res.json();
    originalTaxonomyText = data.tree;
    pre.textContent = originalTaxonomyText;
  } catch (e) {
    pre.textContent = 'Error connecting to RAG tree API.';
  }
};

const initTaxonomyHierarchyFilter = () => {
  const input = document.querySelector('#taxonomy-search-input');
  const pre = document.querySelector('#taxonomy-hierarchy-text');

  input.addEventListener('input', () => {
    const val = input.value.trim().toLowerCase();
    if (!val) {
      pre.textContent = originalTaxonomyText;
      return;
    }

    // Perform live lines filter
    const lines = originalTaxonomyText.split('\n');
    const filtered = lines.map(line => {
      if (line.toLowerCase().includes(val)) {
        return `👉 ${line}`;
      }
      return line;
    });
    pre.textContent = filtered.join('\n');
  });
};


// ============================================================================
// 5. DOUBLE ACTIVATION GATES (SIDEBAR INPUT + CONFIGURE TAB)
// ============================================================================
const initActivationGates = () => {
  const sidebarInput = document.querySelector('#api-key-input');
  const sidebarBtn = document.querySelector('#api-key-submit');
  
  const configInput = document.querySelector('#configure-api-key-input');
  const configBtn = document.querySelector('#configure-api-key-submit');

  const executeActivation = (keyValue) => {
    const key = keyValue.trim();
    if (!key) return;

    sessionStorage.setItem('gemini_api_key', key);
    if (sidebarInput) sidebarInput.value = '';
    if (configInput) configInput.value = '';

    setEngineAuthorized(true);

    // Dynamic GSAP alerts & feedback
    const targets = ['.ios-card'];
    if (document.querySelector('#api-gate')) targets.push('#api-gate');
    
    gsap.to(targets, {
      borderColor: 'var(--accent-green)',
      boxShadow: '0 0 20px rgba(0, 200, 120, 0.15)',
      duration: 0.3,
      yoyo: true,
      repeat: 1
    });

    appendSystemLog('AE BOT ENGINE AUTHORIZED', 'Google Gemini API configuration synced successfully. Decoupled from offline mocks.');
  };

  if (sidebarBtn && sidebarInput) {
    sidebarBtn.addEventListener('click', () => executeActivation(sidebarInput.value));
    sidebarInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') executeActivation(sidebarInput.value);
    });
  }

  if (configBtn && configInput) {
    configBtn.addEventListener('click', () => executeActivation(configInput.value));
    configInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') executeActivation(configInput.value);
    });
  }

  // Boot key sync
  const key = sessionStorage.getItem('gemini_api_key') || '';
  if (key) {
    setEngineAuthorized(true);
  }
};


// ============================================================================
// 6. INTERACTIVE CURATED PROMPTS (SUGGESTIONS)
// ============================================================================
const initSuggestionsActions = () => {
  const cards = document.querySelectorAll('.suggestion-card');
  const chatInput = document.querySelector('#chat-input');
  const chatForm = document.querySelector('#chat-form');

  cards.forEach(card => {
    card.addEventListener('click', () => {
      const prompt = card.getAttribute('data-prompt');
      
      // Navigate to Chat Hub tab smoothly first
      const hubTabBtn = document.querySelector('.submenu-item[data-subtab="hub"]');
      hubTabBtn.click();

      // Paste prompt and submit
      chatInput.value = prompt;
      setTimeout(() => {
        chatForm.dispatchEvent(new Event('submit'));
      }, 350); // Small wait for GSAP fade-in tab transitions
    });
  });
};


// ============================================================================
// 7. SANDBOX PLAYGROUND (RAW VECTOR SEARCH)
// ============================================================================
const initSandboxPlayground = () => {
  const input = document.querySelector('#playground-query-input');
  const btn = document.querySelector('#playground-submit-btn');
  const resultsContainer = document.querySelector('#playground-results-list');

  if (btn) {
    btn.addEventListener('click', async () => {
    const q = input.value.trim();
    if (!q) return;

    resultsContainer.innerHTML = `
      <div class="typing-loader" style="margin: auto">
        <span></span>
        <span></span>
        <span></span>
      </div>
    `;

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q, apiKey: sessionStorage.getItem('gemini_api_key') || '' })
      });

      if (!res.ok) {
        resultsContainer.innerHTML = `<div class="empty-state" style="color: var(--accent-amber)">❌ Search failed. Vector schema unreachable.</div>`;
        return;
      }

      const data = await res.json();
      resultsContainer.innerHTML = '';

      if (!data.sources || data.sources.length === 0) {
        resultsContainer.innerHTML = `<div class="empty-state">No matching document chunks found in ChromaDB vector space.</div>`;
        return;
      }

      data.sources.forEach(src => {
        const resultCard = document.createElement('div');
        resultCard.className = 'source-item';
        resultCard.style.border = '1px solid rgba(180, 80, 255, 0.15)';
        resultCard.style.marginBottom = '12px';

        resultCard.innerHTML = `
          <div class="source-toggle" style="background: rgba(180, 80, 255, 0.03)" onclick="toggleSourceContent(this)">
            <span>Distance Chunk ${src.id}: <strong>${src.subproduct.split('\n')[0]}</strong></span>
            <span class="source-badge" style="background: rgba(180, 80, 255, 0.1); color: var(--accent-purple)">TFIDF+SVD Match</span>
          </div>
          <div class="source-content" style="display: block; font-family: var(--font-mono); font-size: 11px;">
            <p>${src.content.trim()}</p>
          </div>
        `;
        resultsContainer.appendChild(resultCard);
      });

    } catch (e) {
      resultsContainer.innerHTML = `<div class="empty-state" style="color: var(--accent-amber)">❌ Connection failed. Check Express console.</div>`;
    }
    });
  }
};


// ============================================================================
// 8. GSAP INITIAL STAGE CAROUSEL
// ============================================================================
const initGsapCascade = () => {
  // Narrow sidebar sliding
  gsap.from('.primary-sidebar', { x: -60, opacity: 0, duration: 0.9, ease: 'power3.out' });
  
  // Wider submenu sidebar opening like sliding curtains
  gsap.from('.secondary-sidebar', { x: -100, opacity: 0, duration: 1.1, delay: 0.1, ease: 'power4.out' });

  // Right pane rising up smoothly
  gsap.from('.content-panel', { y: 30, opacity: 0, duration: 0.8, delay: 0.15, ease: 'power3.out' });
  gsap.from('.chat-layout', { scale: 0.98, opacity: 0, duration: 0.95, delay: 0.35, ease: 'power4.out' });
};


// ============================================================================
// 9. CORE CHAT LOGS MANAGER
// ============================================================================
const initChatOrchestration = () => {
  const chatForm = document.querySelector('#chat-form');
  const conversationStorageKey = 'ae_bot_conversation_id';
  let conversationId = localStorage.getItem(conversationStorageKey) || crypto.randomUUID();
  localStorage.setItem(conversationStorageKey, conversationId);
  const chatInput = document.querySelector('#chat-input');
  const chatMessages = document.querySelector('#chat-messages-container');

  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const queryText = chatInput.value.trim();
    if (!queryText) return;

    chatInput.value = '';
    appendMessage('user', queryText);
    
    const loaderId = appendTypingLoader();
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
      const apiKey = sessionStorage.getItem('gemini_api_key') || '';
      
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: queryText, apiKey, conversationId })
      });

      removeTypingLoader(loaderId);

      if (!res.ok) {
        const errData = await res.json();
        appendMessage('ai', `❌ **RAG Error:** ${errData.details || errData.error}`);
        return;
      }

      const data = await res.json();
      if (data.conversationId) {
        conversationId = data.conversationId;
        localStorage.setItem(conversationStorageKey, conversationId);
      }
      appendAiResponse(data);

    } catch (err) {
      removeTypingLoader(loaderId);
      appendMessage('ai', `❌ **Network failure:** RAG server connection lost.`);
    }

    chatMessages.scrollTop = chatMessages.scrollHeight;
  });
};

const appendMessage = (sender, text) => {
  const chatMessages = document.querySelector('#chat-messages-container');
  const msgDiv = document.createElement('div');
  msgDiv.className = `message ${sender}-message`;

  const formattedText = formatMarkdown(text);

  msgDiv.innerHTML = `
    <div class="message-content">
      <div class="${sender === 'user' ? 'user-avatar' : 'ai-avatar'}">
        <ion-icon name="${sender === 'user' ? 'person-outline' : 'sparkles-outline'}"></ion-icon>
      </div>
      <div class="message-text">
        ${formattedText}
      </div>
    </div>
  `;

  chatMessages.appendChild(msgDiv);
  return msgDiv;
};

const appendSystemLog = (title, text) => {
  const chatMessages = document.querySelector('#chat-messages-container');
  const msgDiv = document.createElement('div');
  msgDiv.className = `message system-message`;

  msgDiv.innerHTML = `
    <div class="message-content">
      <div class="system-avatar">
        <ion-icon name="flash"></ion-icon>
      </div>
      <div class="message-text">
        <h3>${title}</h3>
        <p>${text}</p>
      </div>
    </div>
  `;

  chatMessages.appendChild(msgDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
};

const appendTypingLoader = () => {
  const chatMessages = document.querySelector('#chat-messages-container');
  const loaderId = 'loader-' + Date.now();
  const loaderDiv = document.createElement('div');
  loaderDiv.className = `message ai-message`;
  loaderDiv.id = loaderId;

  loaderDiv.innerHTML = `
    <div class="message-content">
      <div class="ai-avatar">
        <ion-icon name="sparkles-outline"></ion-icon>
      </div>
      <div class="message-text">
        <div class="typing-loader">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    </div>
  `;

  chatMessages.appendChild(loaderDiv);
  return loaderId;
};

const removeTypingLoader = (id) => {
  const loader = document.getElementById(id);
  if (loader) loader.remove();
};

const escapeHtml = (value = '') => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#039;');

const firstContentLine = (content = '', label = 'Description:') => {
  const line = String(content)
    .split('\n')
    .find(item => item.trim().startsWith(label));
  return line ? line.split(label, 2)[1].trim() : '';
};

const stripRawImageUrls = (text = '') => String(text)
  .replace(/^\s*Image URL:\s*`?https?:\/\/\S+`?\s*$/gmi, '')
  .replace(/^\s*[-*]\s*Image URL:\s*`?https?:\/\/\S+`?\s*$/gmi, '')
  .trim();

const renderProductPreviewCards = (sources = []) => {
  const productSources = sources
    .filter(src => src.image_url && src.image_url !== 'Not found')
    .slice(0, 3);

  if (!productSources.length) return '';

  const cards = productSources.map(src => {
    const productName = escapeHtml(String(src.subproduct || '').split('\n')[0] || 'Advanced Energy Product');
    const category = escapeHtml(src.category || 'Advanced Energy');
    const imageUrl = escapeHtml(src.image_url);
    const productUrl = src.url && src.url !== 'Not found' ? escapeHtml(src.url) : '';
    const description = escapeHtml(
      src.description && src.description !== 'Not found'
        ? src.description
        : firstContentLine(src.content, 'Description:')
    );

    return `
      <article class="chat-product-card">
        <div class="chat-product-image-shell">
          <img src="${imageUrl}" class="chat-product-image" alt="${productName}" loading="lazy" onerror="this.closest('.chat-product-image-shell').style.display='none'">
        </div>
        <div class="chat-product-details">
          <div class="chat-product-category">${category}</div>
          <h3>${productName}</h3>
          ${description ? `<p>${description}</p>` : ''}
          ${productUrl ? `<a href="${productUrl}" target="_blank" class="source-link-btn"><ion-icon name="open-outline"></ion-icon> View Product Page</a>` : ''}
        </div>
      </article>
    `;
  }).join('');

  return `<div class="chat-product-grid">${cards}</div>`;
};

const appendAiResponse = (data) => {
  const { answer, sources } = data;
  const chatMessages = document.querySelector('#chat-messages-container');
  
  const msgDiv = document.createElement('div');
  msgDiv.className = `message ai-message`;

  let sourcesHtml = '';
  if (sources && sources.length > 0) {
    sourcesHtml = `
      <div class="sources-section">
        <div class="sources-header">CITATIONS & RETRIEVED SPECS (${sources.length})</div>
        <div class="sources-container">
    `;

    sources.forEach(src => {
      const showImage = src.image_url && src.image_url !== 'Not found';
      const subproduct = escapeHtml(String(src.subproduct || '').split('\n')[0]);
      const imageUrl = escapeHtml(src.image_url || '');
      const productUrl = src.url && src.url !== 'Not found' ? escapeHtml(src.url) : '';
      sourcesHtml += `
        <div class="source-item">
          <div class="source-toggle" onclick="toggleSourceContent(this)">
            <span>Source ${src.id}: <strong>${subproduct}</strong></span>
            <span class="source-badge">RELEVANT</span>
          </div>
          <div class="source-content">
            ${showImage ? `<div class="source-product-image-wrapper"><img src="${imageUrl}" class="source-product-image" alt="${subproduct}" onerror="this.style.display='none'"></div>` : ''}
            <p>${escapeHtml(src.content || '').trim()}</p>
            ${productUrl ? `<a href="${productUrl}" target="_blank" class="source-link-btn"><ion-icon name="open-outline"></ion-icon> View Product Page</a>` : ''}
          </div>
        </div>
      `;
    });

    sourcesHtml += `
        </div>
      </div>
    `;
  }

  const formattedAnswer = formatMarkdown(stripRawImageUrls(answer));
  const productCardsHtml = renderProductPreviewCards(sources || []);

  msgDiv.innerHTML = `
    <div class="message-content">
      <div class="ai-avatar">
        <ion-icon name="sparkles-outline"></ion-icon>
      </div>
      <div class="message-text">
        <div class="ai-answer-body">
          ${formattedAnswer}
        </div>
        ${productCardsHtml}
        ${sourcesHtml}
      </div>
    </div>
  `;

  chatMessages.appendChild(msgDiv);
};

window.toggleSourceContent = (toggleEl) => {
  const content = toggleEl.nextElementSibling;
  const isVisible = content.style.display === 'block';
  content.style.display = isVisible ? 'none' : 'block';
};

const formatMarkdown = (text) => {
  let html = text;
  html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
  html = html.replace(/\*\*([\s\S]*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/^\s*[-*+]\s+(.*)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');
  html = html.replace(/<\/ul>\s*<ul>/g, '');
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color: var(--accent-blue); text-decoration: underline;">$1</a>');

  html = html.split('\n\n').map(p => {
    if (p.trim().startsWith('<li') || p.trim().startsWith('<pre') || p.trim().startsWith('<ul')) {
      return p;
    }
    return `<p>${p.replace(/\n/g, '<br>')}</p>`;
  }).join('');

  return html;
};


// ============================================================================
// 10. SYSTEM BOOTSTRAP
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  const safeCall = (fn, name) => {
    try {
      fn();
    } catch(e) {
      console.error('CRASH IN ' + name + ':', e);
    }
  };

  safeCall(initThreeBackground, 'initThreeBackground');
  safeCall(initNavigationEngine, 'initNavigationEngine');
  safeCall(fetchSystemStatus, 'fetchSystemStatus');
  safeCall(fetchTaxonomyHierarchy, 'fetchTaxonomyHierarchy');
  safeCall(initTaxonomyHierarchyFilter, 'initTaxonomyHierarchyFilter');
  safeCall(initActivationGates, 'initActivationGates');
  safeCall(initSuggestionsActions, 'initSuggestionsActions');
  safeCall(initSandboxPlayground, 'initSandboxPlayground');
  safeCall(initChatOrchestration, 'initChatOrchestration');
  safeCall(initGsapCascade, 'initGsapCascade');
});
