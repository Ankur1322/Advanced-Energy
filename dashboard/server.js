const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
require('dotenv').config({ path: path.join(__dirname, '.env') });
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const app = express();
const PORT = process.env.PORT || 3000;

// Path configuration
const PROJECT_ROOT = path.resolve(__dirname, '..');
const PYTHON_VENV_PATH = process.env.PYTHON_PATH || path.join(PROJECT_ROOT, '.venv', 'bin', 'python3');
const QUERY_API_PATH = path.join(PROJECT_ROOT, 'query_api.py');
const TREE_FILE_PATH = path.join(PROJECT_ROOT, 'all_products_tree.txt');
const PRODUCTS_OUTPUT_DIR = path.join(PROJECT_ROOT, 'output');
const MEMORY_FILE_PATH = process.env.MEMORY_FILE || path.join(PROJECT_ROOT, 'data', 'conversations.json');
const MAX_TURNS = Number(process.env.MAX_MEMORY_TURNS || 20);
const MAX_MESSAGE_CHARS = 4000;
const MEMORY_TTL_MS = 1000 * 60 * 60 * 24 * 30;

const conversations = new Map();
try {
  if (fs.existsSync(MEMORY_FILE_PATH)) {
    const saved = JSON.parse(fs.readFileSync(MEMORY_FILE_PATH, 'utf8'));
    for (const [id, turns] of Object.entries(saved)) {
      if (Array.isArray(turns)) conversations.set(id, turns.slice(-MAX_TURNS * 2));
    }
  }
} catch (error) {
  console.warn('Conversation memory could not be loaded:', error.message);
}

function saveConversations() {
  const directory = path.dirname(MEMORY_FILE_PATH);
  fs.mkdirSync(directory, { recursive: true });
  const tempPath = `${MEMORY_FILE_PATH}.tmp`;
  fs.writeFileSync(tempPath, JSON.stringify(Object.fromEntries(conversations)), 'utf8');
  fs.renameSync(tempPath, MEMORY_FILE_PATH);
}

function cleanText(value) {
  return typeof value === 'string' ? value.trim().slice(0, MAX_MESSAGE_CHARS) : '';
}

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// 1. Get Dashboard System Status & Stats
app.get('/api/status', (req, res) => {
  const dbExists = fs.existsSync(path.join(PROJECT_ROOT, 'chroma_db'));
  const modelExists = fs.existsSync(path.join(PROJECT_ROOT, 'chroma_db/embedding_model.pkl'));
  const outputExists = fs.existsSync(PRODUCTS_OUTPUT_DIR);
  
  // Basic stats
  let totalCategories = 0;
  let totalSubProducts = 0;
  
  if (outputExists) {
    try {
      const productsPath = path.join(PRODUCTS_OUTPUT_DIR, 'Products');
      const targetDir = fs.existsSync(productsPath) ? productsPath : PRODUCTS_OUTPUT_DIR;
      
      const dirs = fs.readdirSync(targetDir);
      totalCategories = dirs.filter(d => fs.statSync(path.join(targetDir, d)).isDirectory()).length;
      
      // Recursive count of details.txt / product_details.txt
      const countSubProducts = (dir) => {
        let count = 0;
        const files = fs.readdirSync(dir);
        for (const file of files) {
          const filePath = path.join(dir, file);
          const stat = fs.statSync(filePath);
          if (stat.isDirectory()) {
            count += countSubProducts(filePath);
          } else if (file === 'details.txt' || file === 'product_details.txt') {
            count++;
          }
        }
        return count;
      };
      totalSubProducts = countSubProducts(targetDir);
    } catch (e) {
      console.error('Error calculating stats:', e);
    }
  }

  res.json({
    status: 'online',
    database: {
      initialized: dbExists && modelExists,
      path: 'chroma_db',
      model_loaded: modelExists
    },
    scraper: {
      has_scraped_data: outputExists,
      total_categories: totalCategories,
      total_subproducts: totalSubProducts
    },
    gemini_key_configured: !!(process.env.GEMINI_API_KEY || '').trim()
  });
});

// 2. Chat / Q&A RAG Query Endpoint
app.post('/api/chat', (req, res) => {
  const query = cleanText(req.body?.query);
  if (!query) {
    return res.status(400).json({ error: 'Query is required' });
  }

  const conversationId = cleanText(req.body?.conversationId) || crypto.randomUUID();
  const history = (conversations.get(conversationId) || []).slice(-MAX_TURNS * 2);
  // Prefer the server-side secret. Client-provided keys are supported for local testing only.
  const activeApiKey = (process.env.GEMINI_API_KEY || req.body?.apiKey || '').trim();

  // Spawn Python bridge
  const env = { ...process.env };
  if (activeApiKey) {
    env.GEMINI_API_KEY = activeApiKey;
  } else {
    delete env.GEMINI_API_KEY; // Run in Mock Mode if no key
  }

  console.log(`Executing RAG query: "${query}" (API Key provided: ${!!activeApiKey})`);

  const pythonPath = fs.existsSync(PYTHON_VENV_PATH) ? PYTHON_VENV_PATH : (process.env.PYTHON || 'python3');
  const pyProcess = spawn(pythonPath, [QUERY_API_PATH, query, JSON.stringify(history)], {
    cwd: PROJECT_ROOT,
    env,
    stdio: ['ignore', 'pipe', 'pipe']
  });
  const timeout = setTimeout(() => pyProcess.kill('SIGTERM'), Number(process.env.QUERY_TIMEOUT_MS || 90000));
  pyProcess.on('error', (error) => {
    clearTimeout(timeout);
    if (!res.headersSent) res.status(500).json({ error: 'Unable to start AI engine', details: error.message });
  });

  let stdoutData = '';
  let stderrData = '';

  pyProcess.stdout.on('data', (data) => {
    stdoutData += data.toString();
  });

  pyProcess.stderr.on('data', (data) => {
    stderrData += data.toString();
  });

  pyProcess.on('close', (code) => {
    clearTimeout(timeout);
    if (code !== 0) {
      console.error(`Python script failed with exit code ${code}`);
      console.error(`Stderr: ${stderrData}`);
      return res.status(500).json({
        error: 'Execution failed',
        details: stderrData || stdoutData
      });
    }

    try {
      const jsonResponse = JSON.parse(stdoutData.trim());
      const answer = cleanText(jsonResponse.answer);
      const turns = [...history,
        { role: 'user', content: query, at: new Date().toISOString() },
        { role: 'assistant', content: answer, at: new Date().toISOString() }
      ].slice(-MAX_TURNS * 2);
      conversations.set(conversationId, turns);
      saveConversations();
      res.json({ ...jsonResponse, conversationId });
    } catch (err) {
      console.error('Failed to parse Python JSON output:', stdoutData);
      res.status(500).json({
        error: 'Invalid response from AI engine',
        raw: stdoutData,
        details: err.message
      });
    }
  });
});

// 3. Get Product Directory Taxonomy Tree
app.get('/api/tree', (req, res) => {
  if (fs.existsSync(TREE_FILE_PATH)) {
    try {
      const treeText = fs.readFileSync(TREE_FILE_PATH, 'utf-8');
      res.json({ tree: treeText });
    } catch (e) {
      res.status(500).json({ error: 'Failed to read tree file', details: e.message });
    }
  } else {
    res.status(404).json({ error: 'Product taxonomy tree not found. Please run the scraper first.' });
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`====================================================`);
  console.log(`⚡ Advanced Energy Dashboard running on http://localhost:${PORT}`);
  console.log(`====================================================`);
});
