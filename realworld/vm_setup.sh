#!/bin/bash
# Dijalankan DI DALAM VM (Ubuntu), sebagai root:
#   server : sudo bash vm_setup.sh server <nama-node> <tailscale-authkey>
#   agent  : sudo bash vm_setup.sh agent  <nama-node> <tailscale-authkey> <ip-tailscale-server> <token>
# Memasang Tailscale (supaya VM di WiFi berbeda tetap saling terhubung) lalu k3s (Kubernetes).
set -e
ROLE=$1; NAME=$2; KEY=$3

curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --authkey="$KEY" --hostname="$NAME"
IP=$(tailscale ip -4)
echo "IP Tailscale $NAME = $IP"

if [ "$ROLE" = "server" ]; then
  curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --node-name $NAME --node-ip $IP --advertise-address $IP --tls-san $IP --flannel-iface tailscale0 --disable traefik --disable metrics-server --write-kubeconfig-mode 644" sh -
  echo; echo "=== CATAT 2 NILAI INI UNTUK TEMANMU ==="
  echo "IP server : $IP"
  echo "Token     : $(cat /var/lib/rancher/k3s/server/node-token)"
else
  SERVER=$4; TOKEN=$5
  curl -sfL https://get.k3s.io | K3S_URL="https://$SERVER:6443" K3S_TOKEN="$TOKEN" INSTALL_K3S_EXEC="agent --node-name $NAME --node-ip $IP --flannel-iface tailscale0" sh -
fi
