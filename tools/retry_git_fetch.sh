#!/usr/bin/env bash
# Source this file. Retries only an idempotent fetch, never checkout/patch/build.
retry_git_fetch() {
    local attempt delay result
    for attempt in 1 2 3 4 5; do
        if git -c http.lowSpeedLimit=1024 -c http.lowSpeedTime=90 "$@"; then
            return 0
        else
            result=$?
        fi
        [[ $attempt -lt 5 ]] || return "$result"
        delay=$((attempt * 10))
        echo "Source fetch failed (attempt $attempt/5); retrying in ${delay}s" >&2
        sleep "$delay"
    done
}
