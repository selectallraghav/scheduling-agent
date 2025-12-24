#!/bin/bash
echo "🔐 Setting up Git credential helper..."
echo ""

# Configure credential helper
git config --global credential.helper osxkeychain 2>/dev/null || git config --global credential.helper store

echo "✅ Credential helper configured"
echo ""
echo "📝 When prompted:"
echo "   Username: selectallraghav"
echo "   Password: Paste your Personal Access Token"
echo ""
echo "🚀 Pushing..."
echo ""

git push -u origin main
