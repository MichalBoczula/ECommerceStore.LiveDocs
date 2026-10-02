#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
image="${1:?Usage: smoke-container.sh IMAGE [EXPECTED_SHA]}"
expected_sha="${2:-local}"
broken_container_id=""
container_id="$(docker run --detach --read-only --tmpfs /tmp:rw,size=16m,mode=1777 \
  --cap-drop ALL --security-opt no-new-privileges --publish 127.0.0.1::8080 "$image")"
cleanup() {
  result=$?
  if (( result != 0 )); then docker logs "$container_id" >&2 || true; fi
  docker rm --force "$container_id" >/dev/null || true
  if [[ -n "$broken_container_id" ]]; then docker rm --force "$broken_container_id" >/dev/null || true; fi
}
trap cleanup EXIT
test "$(docker inspect --format '{{.Config.User}}' "$container_id")" = "101:101"
docker exec "$container_id" nginx -t
port="$(docker port "$container_id" 8080/tcp | head -n 1)"
python3 scripts/smoke.py "http://$port" --expected-sha "$expected_sha"
# Hide baked-in content to prove a missing site cannot report itself ready.
broken_container_id="$(docker run --detach --read-only --tmpfs /tmp:rw,size=16m,mode=1777 \
  --tmpfs /usr/share/nginx/html:rw,size=1m --cap-drop ALL --security-opt no-new-privileges \
  --publish 127.0.0.1::8080 "$image")"
broken_port="$(docker port "$broken_container_id" 8080/tcp | head -n 1)"
python3 - "http://$broken_port" <<'PY'
import sys, time
sys.path.insert(0, 'scripts')
from smoke import request
for attempt in range(30):
    try:
        status, _, _ = request(sys.argv[1], '/health/ready')
        assert status == 503, f'Missing site must be unready, got {status}'
        status, _, _ = request(sys.argv[1], '/health/live')
        assert status == 200, 'Host should remain live when content is missing'
        print('Missing-site readiness check passed')
        break
    except OSError:
        if attempt == 29:
            raise
        time.sleep(1)
PY
