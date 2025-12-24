#!/bin/bash
echo "🔑 Setting up SSH for GitHub..."
echo ""

# Generate SSH key if it doesn't exist
if [ ! -f ~/.ssh/id_ed25519 ]; then
    echo "Generating new SSH key..."
    ssh-keygen -t ed25519 -C "selectallraghav@github.com" -f ~/.ssh/id_ed25519 -N ""
    echo "✅ SSH key generated!"
else
    echo "✅ SSH key already exists!"
fi

echo ""
echo "📋 Next steps:"
echo "1. Copy your public key:"
echo "   cat ~/.ssh/id_ed25519.pub"
echo ""
echo "2. Add it to GitHub:"
echo "   https://github.com/settings/keys"
echo "   Click 'New SSH key' → Paste the key → Save"
echo ""
echo "3. Test connection:"
echo "   ssh -T git@github.com"
echo ""
echo "4. Update remote and push:"
echo "   git remote set-url origin git@github.com:selectallraghav/scheduling-agent.git"
echo "   git push -u origin main"
