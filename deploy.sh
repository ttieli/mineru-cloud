#!/bin/bash
# Deploy the current development version of mineru_cli.py to the global stable directory

SRC="mineru_cli.py"
DEST="$HOME/.local/share/mineru/mineru_cli.py"

echo "Deploying $SRC to $DEST ..."

# Simple syntax check
python3 -m py_compile "$SRC"
if [ $? -ne 0 ]; then
    echo "Error: Syntax check failed. Aborting deployment."
    exit 1
fi

# Copy the file
cp "$SRC" "$DEST"

echo "Deployment successful! The global 'mineru' command is now updated."
