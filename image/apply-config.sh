#!/bin/bash
# =============================================================================
# SpeedBox - Script de configuration de la partition boot DietPi
# =============================================================================
# Usage : bash apply-config.sh /chemin/vers/partition/boot
#         bash apply-config.sh /media/user/bootfs
#
# Mot de passe par défaut : SpeedBox!
# À changer après installation : passwd
# =============================================================================

set -e

BOOT_DIR="${1:-}"

# Vérifications
if [ -z "$BOOT_DIR" ]; then
    echo "Usage: bash apply-config.sh /chemin/vers/partition/boot"
    echo "Exemple: bash apply-config.sh /media/user/bootfs"
    exit 1
fi

if [ ! -f "$BOOT_DIR/dietpi.txt" ]; then
    echo "Erreur: $BOOT_DIR/dietpi.txt introuvable."
    echo "Vérifiez que la partition boot est bien montée."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================"
echo "  SpeedBox - Configuration DietPi"
echo "============================================"

echo "[1/2] Application des paramètres dans dietpi.txt..."

sed -i 's/^AUTO_SETUP_GLOBAL_PASSWORD=.*/AUTO_SETUP_GLOBAL_PASSWORD=SpeedBox!/'   "$BOOT_DIR/dietpi.txt"
sed -i 's/^AUTO_SETUP_LOCALE=.*/AUTO_SETUP_LOCALE=C.UTF-8/'                        "$BOOT_DIR/dietpi.txt"
sed -i 's/^AUTO_SETUP_KEYBOARD_LAYOUT=.*/AUTO_SETUP_KEYBOARD_LAYOUT=fr/'           "$BOOT_DIR/dietpi.txt"
sed -i 's/^AUTO_SETUP_TIMEZONE=.*/AUTO_SETUP_TIMEZONE=Europe\/Paris/'              "$BOOT_DIR/dietpi.txt"
sed -i 's/^AUTO_SETUP_NET_ETHERNET_ENABLED=.*/AUTO_SETUP_NET_ETHERNET_ENABLED=1/'  "$BOOT_DIR/dietpi.txt"
sed -i 's/^AUTO_SETUP_NET_WIFI_ENABLED=.*/AUTO_SETUP_NET_WIFI_ENABLED=0/'          "$BOOT_DIR/dietpi.txt"
sed -i 's/^AUTO_SETUP_NET_HOSTNAME=.*/AUTO_SETUP_NET_HOSTNAME=SpeedBox/'           "$BOOT_DIR/dietpi.txt"
sed -i 's/^AUTO_SETUP_BOOT_WAIT_FOR_NETWORK=.*/AUTO_SETUP_BOOT_WAIT_FOR_NETWORK=1/' "$BOOT_DIR/dietpi.txt"
sed -i 's/^AUTO_SETUP_AUTOMATED=.*/AUTO_SETUP_AUTOMATED=1/'                        "$BOOT_DIR/dietpi.txt"
sed -i 's/^AUTO_SETUP_CUSTOM_SCRIPT_EXEC=.*/AUTO_SETUP_CUSTOM_SCRIPT_EXEC=1/'      "$BOOT_DIR/dietpi.txt"
sed -i 's/^AUTO_SETUP_AUTOSTART_TARGET_INDEX=.*/AUTO_SETUP_AUTOSTART_TARGET_INDEX=7/' "$BOOT_DIR/dietpi.txt"
sed -i 's/^AUTO_SETUP_AUTOSTART_LOGIN_USER=.*/AUTO_SETUP_AUTOSTART_LOGIN_USER=root/' "$BOOT_DIR/dietpi.txt"
sed -i 's/^AUTO_SETUP_SSH_SERVER_INDEX=.*/AUTO_SETUP_SSH_SERVER_INDEX=-1/'         "$BOOT_DIR/dietpi.txt"
sed -i 's/^SURVEY_OPTED_IN=.*/SURVEY_OPTED_IN=0/'                                  "$BOOT_DIR/dietpi.txt"

echo "  OK"

echo "[2/2] Copie du script d'installation automatique..."
cp "$SCRIPT_DIR/Automation_Custom_Script.sh" "$BOOT_DIR/"
chmod +x "$BOOT_DIR/Automation_Custom_Script.sh"
echo "  OK"

echo ""
echo "============================================"
echo "  Configuration terminée !"
echo ""
echo "  Mot de passe par défaut : SpeedBox!"
echo "  >> Changez-le après installation : passwd"
echo ""
echo "  Éjectez la carte SD, insérez-la dans le"
echo "  Raspberry Pi et démarrez."
echo "  SpeedBox sera accessible sur http://<IP>:5000"
echo "  (~5-10 min au premier boot)"
echo "============================================"
