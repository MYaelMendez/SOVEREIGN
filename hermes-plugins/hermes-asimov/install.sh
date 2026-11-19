#!/bin/sh
# Install the hermes-asimov plugin into a Hermes Agent plugins directory.
# No credentials, tokens, or network access are required.
# This installer copies files only. It does NOT enable the plugin.
set -eu

# Resolve the directory containing this script so install works from anywhere.
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# Where to install: HERMES_HOME if set, otherwise $HOME/.hermes.
HERMES_HOME=${HERMES_HOME:-$HOME/.hermes}
TARGET="$HERMES_HOME/plugins/hermes-asimov"

if [ "$SCRIPT_DIR" = "$TARGET" ]; then
    echo "hermes-asimov is already at $TARGET — nothing to copy."
else
    # Start from a clean target directory.
    rm -rf "$TARGET"
    mkdir -p "$TARGET"

    # Copy the plugin payload. The existence guard keeps the installer usable
    # in a partial checkout; when the full plugin is present, every item is
    # copied. dashboard/, tests/, and docs/ arrive with the 0.2.0 surfaces.
    for item in plugin.yaml __init__.py cast.json scripts dashboard tests docs \
                README.md LICENSE NOTICE.md CHANGELOG.md; do
        if [ -e "$SCRIPT_DIR/$item" ]; then
            cp -R "$SCRIPT_DIR/$item" "$TARGET/"
        fi
    done
fi

if [ ! -f "$TARGET/scripts/asimov_protocol.py" ]; then
    echo "warning: scripts/asimov_protocol.py is not present in $TARGET" >&2
fi

cat <<EOF

hermes-asimov 0.2.0 installed to: $TARGET

This installer did NOT enable the plugin. Enable it with:
    hermes plugins enable hermes-asimov
(or add hermes-asimov to plugins.enabled via: hermes config set plugins.enabled)

Enabling takes effect in the NEXT Hermes session — restart Hermes afterwards.

The verb engine lives in the hermes-ae plugin (scripts/ae_verbs.py).
Without it, every asimov:// call fails closed with a refusal.
EOF
