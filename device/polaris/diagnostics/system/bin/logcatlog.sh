#!/system/bin/sh
# Staged replacement for ziyi's existing logcatlog service, not installed yet.
# Reuse its SELinux domain and file path. Log only crashes, max about 5 MiB.
umask 077
exec /system/bin/logcat -b crash -r 1024 -n 4 -v threadtime -v uid \
    -f /data/local/log/logcatlog.txt
