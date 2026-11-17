#!/usr/bin/env bash
# Ack (settle) queued messages from finished rooms so they are not re-delivered. Usage: drain-old.sh <seat> <seconds> <room>...
export PATH=$HOME/.local/bin:$PATH
S=$1; T=$2; shift 2; ROOMS="$*"; END=$(( $(date +%s) + T )); n=0
while [ $(date +%s) -lt $END ]; do
  ids=$(band inbox --as guptashine5002/$S --json 2>/dev/null | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit()
it=d if isinstance(d,list) else next((v for v in d.values() if isinstance(v,list)),[])
rooms='$ROOMS'.split()
print(' '.join(m.get('message_id') or m.get('id') for m in it if m.get('chat_id') in rooms))")
  for i in $ids; do band ack --as guptashine5002/$S $i >/dev/null 2>&1 && n=$((n+1)); done
  sleep 0.5
done
echo "$S acked=$n"
