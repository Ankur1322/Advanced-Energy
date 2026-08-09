const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// Path configuration
const PROJECT_ROOT = '/home/ankur/Documents/Advanced Energy';
const PYTHON_VENV_PATH = path.join(PROJECT_ROOT, '.venv/bin/python3');
const QUERY_API_PATH = path.join(PROJECT_ROOT, 'query_api.py');
const TREE_FILE_PATH = path.join(PROJECT_ROOT, 'all_products_tree.txt');
const PRODUCTS_OUTPUT_DIR = path.join(PROJECT_ROOT, 'output');

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
  const { query, apiKey } = req.body;
  if (!query) {
    return res.status(400).json({ error: 'Query is required' });
  }

  // Use frontend-supplied API key, fallback to server's env key
  const activeApiKey = (apiKey || process.env.GEMINI_API_KEY || '').trim();

  // Spawn Python bridge
  const env = { ...process.env };
  if (activeApiKey) {
    env.GEMINI_API_KEY = activeApiKey;
  } else {
    delete env.GEMINI_API_KEY; // Run in Mock Mode if no key
  }

  console.log(`Executing RAG query: "${query}" (API Key provided: ${!!activeApiKey})`);

  const pyProcess = spawn(PYTHON_VENV_PATH, [QUERY_API_PATH, query], {
    cwd: PROJECT_ROOT,
    env
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
      res.json(jsonResponse);
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
