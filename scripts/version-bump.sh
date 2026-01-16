#!/bin/bash
# Version bump script for agent-framework-neo4j
# Usage: ./scripts/version-bump.sh [major|minor|patch]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYPROJECT="$PROJECT_ROOT/packages/agent-framework-neo4j/pyproject.toml"
INIT_FILE="$PROJECT_ROOT/packages/agent-framework-neo4j/agent_framework_neo4j/__init__.py"

# Validate argument
if [[ $# -ne 1 ]] || [[ ! "$1" =~ ^(major|minor|patch)$ ]]; then
    echo "Usage: $0 [major|minor|patch]"
    echo "  major - Bump major version (X.0.0)"
    echo "  minor - Bump minor version (0.X.0)"
    echo "  patch - Bump patch version (0.0.X)"
    exit 1
fi

BUMP_TYPE="$1"

# Extract current version from pyproject.toml
CURRENT_VERSION=$(grep -E '^version = "' "$PYPROJECT" | head -1 | sed 's/version = "\(.*\)"/\1/')

if [[ -z "$CURRENT_VERSION" ]]; then
    echo "Error: Could not find version in $PYPROJECT"
    exit 1
fi

echo "Current version: $CURRENT_VERSION"

# Parse version components
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Bump the appropriate component
case "$BUMP_TYPE" in
    major)
        MAJOR=$((MAJOR + 1))
        MINOR=0
        PATCH=0
        ;;
    minor)
        MINOR=$((MINOR + 1))
        PATCH=0
        ;;
    patch)
        PATCH=$((PATCH + 1))
        ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"
echo "New version: $NEW_VERSION"

# Update pyproject.toml
sed -i '' "s/^version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" "$PYPROJECT"
echo "Updated: $PYPROJECT"

# Update __init__.py
sed -i '' "s/__version__ = \"$CURRENT_VERSION\"/__version__ = \"$NEW_VERSION\"/" "$INIT_FILE"
echo "Updated: $INIT_FILE"

echo ""
echo "Version bumped from $CURRENT_VERSION to $NEW_VERSION"
echo ""
echo "Next steps:"
echo "  1. Review changes: git diff"
echo "  2. Commit: git commit -am \"Bump version to $NEW_VERSION\""
echo "  3. Tag: git tag v$NEW_VERSION"
echo "  4. Build: uv build --package agent-framework-neo4j"
echo "  5. Publish: uv publish --token \$PYPI_TOKEN"
