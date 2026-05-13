#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/launch_dashboard.sh" "$@"
