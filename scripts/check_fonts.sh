#!/bin/bash
# scripts/check_fonts.sh
# Verifies that caption ASS files use bundled OFL fonts (not DejaVu/system fonts).
# Must be re-run whenever a new clip is rendered.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ASSETS_FONTS_DIR="$PROJECT_ROOT/assets/fonts"
OUTPUTS_DIR="$PROJECT_ROOT/outputs/clips"
ERRORS=0
HAS_NEW_CLIP=false

# (a) Find the newest outputs/clips/sub_*.ass
# Get all .ass files in outputs/clips
ASS_FILES=()
if compgen -G "$OUTPUTS_DIR/sub_*.ass" > /dev/null; then
    for f in "$OUTPUTS_DIR"/sub_*.ass; do
        ASS_FILES+=("$f")
    done
    
    # Sort by modification time, newest last, then take the last (newest)
    NEWEST_ASS=$(ls -t "$OUTPUTS_DIR"/sub_*.ass 2>/dev/null | head -1)
    
    if [ -n "$NEWEST_ASS" ] && [ -f "$NEWEST_ASS" ]; then
        # (b) Print its first Style line and its file timestamp
        FIRST_STYLE=$(grep -m1 '^Style:' "$NEWEST_ASS" 2>/dev/null || echo "")
        FILE_TIMESTAMP=$(stat -c '%Y' "$NEWEST_ASS" 2>/dev/null || echo "0")
        FILE_DATE=$(date -d "@$FILE_TIMESTAMP" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "unknown")
        
        echo "=== Newest caption file: $NEWEST_ASS ==="
        echo "File timestamp: $FILE_DATE"
        echo "First Style line: $FIRST_STYLE"
        echo ""
        
        # Check if this file is older than 10 minutes
        CURRENT_TIME=$(date +%s)
        AGE_SECONDS=$((CURRENT_TIME - FILE_TIMESTAMP))
        AGE_MINUTES=$((AGE_SECONDS / 60))
        
        if [ "$AGE_MINUTES" -gt 10 ]; then
            echo "FAIL: Caption file is older than 10 minutes (age: ${AGE_MINUTES} min)."
            echo "      Make a new clip first before running this check."
            exit 1
        else
            HAS_NEW_CLIP=true
        fi
        
        # (c) Render it on black with ffmpeg and grep fontselect
        # Get absolute path to fonts dir
        FONTS_ABS_DIR=$(readlink -f "$ASSETS_FONTS_DIR" 2>/dev/null || realpath "$ASSETS_FONTS_DIR")
        
        if [ -z "$FONTS_ABS_DIR" ]; then
            echo "FAIL: Cannot resolve absolute path to assets/fonts directory."
            exit 1
        fi
        
        echo "Rendering ASS with fontsdir=$FONTS_ABS_DIR ..."
        FONTSELECT_OUTPUT=$(ffmpeg -v verbose -y -f lavfi -i color=black:s=1080x1920:r=10:d=4 \
            -vf "ass=$NEWEST_ASS:fontsdir=$FONTS_ABS_DIR" -f null - 2>&1 | grep -i "fontselect" || true)
        
        echo "$FONTSELECT_OUTPUT"
        
        # (d) PASS only if EVERY fontselect line ends in a path inside assets/fonts
        # Extract all fontselect paths
        FONTSELECT_LINES=$(echo "$FONTSELECT_OUTPUT" | grep -i "fontselect" || true)
        
        if [ -z "$FONTSELECT_LINES" ]; then
            echo "FAIL: No fontselect lines found in ffmpeg output."
            echo "      This suggests the font was not embedded properly."
            ERRORS=$((ERRORS + 1))
        else
            ALL_IN_ASSETS_DIR=true
            while IFS= read -r line; do
                # Extract the path after fontselect
                PATH_AFTER_FONTSELECT=$(echo "$line" | sed 's/.*fontselect//i' | xargs)
                # Check if it ends with assets/fonts/
                if echo "$PATH_AFTER_FONTSELECT" | grep -q "assets/fonts"; then
                    # Verify it's inside the correct assets/fonts dir
                    if echo "$PATH_AFTER_FONTSELECT" | grep -q "$ASSETS_FONTS_DIR"; then
                        : # OK - path is in the right directory
                    else
                        echo "FAIL: fontselect path '$PATH_AFTER_FONTSELECT' is not inside $ASSETS_FONTS_DIR"
                        ALL_IN_ASSETS_DIR=false
                        ERRORS=$((ERRORS + 1))
                    fi
                else
                    echo "FAIL: fontselect path '$PATH_AFTER_FONTSELECT' does not contain 'assets/fonts'"
                    ALL_IN_ASSETS_DIR=false
                    ERRORS=$((ERRORS + 1))
                fi
            done <<< "$FONTSELECT_LINES"
            
            if $ALL_IN_ASSETS_DIR; then
                echo "PASS: ALL fontselect lines end in paths inside $ASSETS_FONTS_DIR"
            fi
        fi
    else
        echo "FAIL: No .ass files found in $OUTPUTS_DIR"
        exit 1
    fi
else
    echo "FAIL: No .ass files found in $OUTPUTS_DIR"
    echo "      Render a clip first, then run this check."
    exit 1
fi

# Summary
if [ "$ERRORS" -eq 0 ]; then
    echo ""
    echo "=== check_fonts.sh: PASS ==="
    exit 0
else
    echo ""
    echo "=== check_fonts.sh: FAIL ($ERRORS error(s)) ==="
    exit 1
fi