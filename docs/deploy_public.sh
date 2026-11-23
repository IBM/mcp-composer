#!/bin/bash
set -euo pipefail

# Same publish path as deploy.sh. Kept so older instructions still work.
HERE="$(cd "$(dirname "$0")" && pwd)"
exec "$HERE/deploy.sh"
