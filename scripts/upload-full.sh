#!/usr/bin/env bash
# Upload a GoW2 package of 4 GiB or more (GOW2_PKG_GAME=1's out/GOW2-vXX.YY-full.pkg) to a console's /data/pkg, then
# remove the other GOW2-vXX.YY*.pkg there. Run from Windows (Git Bash), like ps4-kit's scripts/upload.sh.
#
#   scripts/upload-full.sh out/GOW2-v00.07-full.pkg <your PS4's IP>
#
# ps4-kit's upload.sh checks the size in the FTP listing, and GoldHEN's FTP server gives sizes modulo 2^32 for files of
# 4 GiB or more: it would take every big upload for a failed one and send it again. Here the listed size is compared
# with the real size and with the real size modulo 2^32, and the package is sent once.
set -euo pipefail
PKG="${1:?package path}"
CONSOLE="${2:-${PS4_HOST:-}}"
[ -n "$CONSOLE" ] || { echo "which console? give its IP as the 2nd argument or in PS4_HOST" >&2; exit 1; }
NAME="$(basename "$PKG")"
HOST="ftp://$CONSOLE:${PS4_FTP_PORT:-2121}"
SIZE="$(stat -c %s "$PKG")"
WRAPPED=$((SIZE % 4294967296))
export MSYS_NO_PATHCONV=1

echo "sending $NAME ($SIZE bytes) to $CONSOLE ..."
curl -sS -T "$PKG" "$HOST/data/pkg/"
listed="$(curl -sS "$HOST/data/pkg/" | tr -d '\r' | awk -v n="$NAME" '$NF == n { print $5 }')"
if [ "$listed" != "$SIZE" ] && [ "$listed" != "$WRAPPED" ]; then
    echo "console lists $NAME as '${listed:-missing}' bytes, not $SIZE (or $WRAPPED modulo 2^32): not removing anything" >&2
    exit 1
fi
echo "uploaded $NAME (listed size $listed)"
# As upload.sh: the console once undid uploads a moment later (2026-10-12), so the package must still be there after
# 10, 20 and 30 s before anything is removed. A 6 GB package is not sent again by itself.
for _ in 1 2 3; do
    sleep 10
    now="$(curl -sS "$HOST/data/pkg/" | tr -d '\r' | awk -v n="$NAME" '$NF == n { print $5 }')"
    if [ "$now" != "$listed" ]; then
        echo "console: $NAME went missing after the upload (listed '${now:-nothing}'): nothing removed" >&2
        exit 1
    fi
done
FAMILY="${NAME%-v[0-9][0-9].[0-9][0-9]*.pkg}"
for old in $(curl -sS --list-only "$HOST/data/pkg/" | tr -d '\r' | grep -E "^${FAMILY}-v[0-9]{2}[.][0-9]{2}[^/]*[.]pkg\$" | grep -vx "$NAME"); do
    if curl -sS "$HOST/" -Q "DELE /data/pkg/$old" > /dev/null; then echo "console: removed old $old"; else echo "console: could not remove $old"; fi
done
curl -sS --list-only "$HOST/data/pkg/" | tr -d '\r' | grep -E "^${FAMILY}-" | sed 's/^/console has: /'
