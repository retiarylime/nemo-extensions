#!/bin/bash
# Fix dconf permission issues for Nemo

echo "🔧 Fixing dconf permission issues..."

# Remove existing dconf directory and recreate with proper permissions
if [ -d "/run/user/1000/dconf" ]; then
    rm -rf /run/user/1000/dconf/
fi

mkdir -p /run/user/1000/dconf/
chmod 700 /run/user/1000/dconf/

echo "✅ dconf permissions fixed"
echo "ℹ️  Now restart Nemo: pkill -f nemo && sleep 2 && nemo &"