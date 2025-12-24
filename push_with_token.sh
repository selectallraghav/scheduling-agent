#!/bin/bash
# Script to push using Personal Access Token

echo "🚀 Pushing to GitHub with Personal Access Token..."
echo ""
echo "📝 Instructions:"
echo "1. If you haven't created a token yet:"
echo "   https://github.com/settings/tokens"
echo "   Generate new token (classic) with 'repo' scope"
echo ""
echo "2. When prompted for password, paste your token"
echo ""
echo "3. Or set it in the URL (replace YOUR_TOKEN):"
echo "   git remote set-url origin https://YOUR_TOKEN@github.com/selectallraghav/scheduling-agent.git"
echo ""

read -p "Do you want to set the token in the remote URL? (y/n): " answer
if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
    read -sp "Enter your Personal Access Token: " token
    echo ""
    git remote set-url origin https://${token}@github.com/selectallraghav/scheduling-agent.git
    echo "✅ Remote updated with token!"
    echo "Pushing..."
    git push -u origin main
else
    echo "Pushing (you'll be prompted for credentials)..."
    git push -u origin main
fi
