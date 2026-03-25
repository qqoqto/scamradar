#!/bin/bash
set -e

echo "🛡️  ScamRadar Phase 2 — Build Script"
echo "====================================="

# 1. Build frontend
echo ""
echo "📦 Building React frontend..."
cd frontend
npm install
npm run build
cd ..
echo "✅ Frontend built → frontend/dist/"

# 2. Install Python deps
echo ""
echo "🐍 Installing Python dependencies..."
pip install -r requirements.txt
echo "✅ Python deps installed"

# 3. Verify
echo ""
echo "🔍 Verifying build..."
if [ -f "frontend/dist/index.html" ]; then
    echo "✅ frontend/dist/index.html exists"
else
    echo "❌ frontend/dist/index.html NOT FOUND"
    exit 1
fi

echo ""
echo "🚀 Build complete! Ready to serve."
