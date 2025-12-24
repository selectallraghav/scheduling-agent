#!/bin/bash
# Script to push code to GitHub repository

echo "🚀 Pushing code to GitHub..."
echo ""

# Try to push
git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Successfully pushed to GitHub!"
    echo "📦 Repository: https://github.com/selectallraghav/scheduling-agent"
else
    echo ""
    echo "❌ Push failed. Possible reasons:"
    echo "   1. Repository doesn't exist yet - create it at https://github.com/new"
    echo "   2. Authentication needed - see options below"
    echo ""
    echo "Authentication options:"
    echo "   • GitHub CLI: gh auth login"
    echo "   • SSH: git remote set-url origin git@github.com:selectallraghav/scheduling-agent.git"
    echo "   • Personal Access Token"
fi
