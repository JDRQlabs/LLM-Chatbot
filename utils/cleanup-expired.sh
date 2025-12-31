#!/usr/bin/env bash
#this script cleanups proto Hetzner servers whose TTL has expired
set -euo pipefail

now=$(date +%s)

echo "Running Hetzner proto cleanup at $(date)"

# Get server IDs
hcloud server list -o noheader -o columns=id | while read -r id; do
  desc=$(hcloud server describe "$id")

  name=$(echo "$desc" | awk '/^Name:/ {print $2}')

  purpose=$(echo "$desc" | awk '/purpose:/ {print $2}')
  ttl=$(echo "$desc" | awk '/ttl:/ {print $2}')
  created=$(echo "$desc" | awk '/created_at:/ {print $2}')

  # Safety gates
  [ "$purpose" != "proto" ] && continue
  [ -z "$ttl" ] && continue
  [ -z "$created" ] && continue

  case "$ttl" in
    *h) lifetime=$(( ${ttl%h} * 3600 )) ;;
    *m) lifetime=$(( ${ttl%m} * 60 )) ;;
    *)
      echo "Skipping $name ($id): unsupported ttl format ($ttl)"
      continue
      ;;
  esac

  expires=$(( created + lifetime ))

  if [ "$now" -ge "$expires" ]; then
    echo "Deleting expired proto server: $name ($id)"
    hcloud server delete "$id"
  else
    remaining=$(( expires - now ))
    echo "Keeping $name ($id): expires in ${remaining}s"
  fi
done
