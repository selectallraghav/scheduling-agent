#!/bin/bash
set -e

echo "🧹 Cleaning files with secrets..."

# Clean create_repo.sh
cat > create_repo.sh << 'EOF'
#!/bin/bash
# Script to create GitHub repository via API
# Use: export GITHUB_TOKEN=your-token && ./create_repo.sh
TOKEN="${GITHUB_TOKEN:-}"
REPO_NAME="scheduling-agent"
USERNAME="selectallraghav"
if [ -z "$TOKEN" ]; then
    echo "❌ GITHUB_TOKEN not set"
    exit 1
fi
echo "🔨 Creating repository..."
response=$(curl -s -w "\n%{http_code}" -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/user/repos \
  -d "{\"name\":\"$REPO_NAME\",\"description\":\"Apexon Scheduling Agent\",\"private\":false}")
http_code=$(echo "$response" | tail -n1)
[ "$http_code" = "201" ] && echo "✅ Created!" || echo "⚠️  HTTP $http_code"
EOF

# Clean other files
echo "# Deprecated - use .env file" > set_env.sh
echo "streamlit run streamlit_scheduler.py" > run_app.sh
sed -i '' 's/"api_key": "[^"]*"/"api_key": "YOUR_API_KEY_HERE"/g' DARWIN_API_FIELDS.md 2>/dev/null || \
sed -i 's/"api_key": "[^"]*"/"api_key": "YOUR_API_KEY_HERE"/g' DARWIN_API_FIELDS.md

echo "🗑️  Removing old git history..."
rm -rf .git

echo "🔄 Initializing fresh repository..."
git init
git add .
git commit -m "Initial commit: Scheduling Agent with Darwin API integration"

echo "🔗 Setting remote..."
git remote add origin https://github.com/selectallraghav/scheduling-agent.git 2>/dev/null || \
git remote set-url origin https://github.com/selectallraghav/scheduling-agent.git

echo "✅ Ready to push! Run:"
echo "   git push -u origin main --force"
