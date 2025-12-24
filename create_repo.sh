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
