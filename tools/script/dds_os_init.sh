#!/bin/bash

SCRIPT_VERSION="1.1"

# Define configuration values
SWAPPINESS=1
OVERCOMMIT_MEMORY=0
MAX_MAP_COUNT=131072
TCP_KEEPALIVE_TIME=120
TCP_RETRIES2=8

NEED_REBOOT=false
REBOOT_INFO="The system needs to be rebooted to take effect of the following changes:\n"

# OS type keywords
OS_KEY_CENTOS="CentOS Linux"
OS_KEY_REDHAT="Red Hat Enterprise Linux Server"
OS_KEY_KYLIN="Kylin Linux Advanced Server"
OS_KEY_SUSE="SLES"  # SUSE Linux Enterprise Server
OS_KEY_UBUNTU="Ubuntu"
OS_KEY_OPENEULER="openEuler"
OS_KEY_UOS1="UOS Server 20"
OS_KEY_UOS2="UnionTech OS Server 20"


WRITE_LOG=true
LOG_FILE="dds_os_init.log.$(date +%Y%m%d%H%M%S)"

function print_log() {
    local message="$1"
    if [ "$WRITE_LOG" = true ]; then
        echo "$message" >> "$LOG_FILE"
    else
        echo "$message"
    fi
}

# Get OS type and version
function get_os_info() {
   if [[ -f /etc/os-release ]]; then
      source /etc/os-release
      OS=$NAME
      VER=$VERSION_ID
   else
      OS=$(uname -s)
      VER=$(uname -r)
   fi

   case "$OS" in
      ${OS_KEY_CENTOS} | ${OS_KEY_REDHAT} | ${OS_KEY_KYLIN} | ${OS_KEY_SUSE} | ${OS_KEY_UBUNTU} | ${OS_KEY_OPENEULER} | ${OS_KEY_UOS1} | ${OS_KEY_UOS2} )
         echo -e "[INFO] Operating System: $OS $VER"
         ;;
      *)
         echo -e "[ERROR] Unsupported OS: $OS $VER"
         exit 1
         ;;
   esac
}

function disable_firewall() {
   print_log "===Stop and disable firewall==="
   case "$OS" in
      ${OS_KEY_CENTOS} | ${OS_KEY_REDHAT} | ${OS_KEY_KYLIN} | ${OS_KEY_OPENEULER} | ${OS_KEY_UOS1} | ${OS_KEY_UOS2} )
         systemctl stop firewalld > /dev/null 2>&1
         systemctl disable firewalld > /dev/null 2>&1
         ;;
      ${OS_KEY_SUSE})
         if [[ $VER =~ ^11\.[0-9]+$ ]]; then
             service SuSEfirewall2 stop
             chkconfig SuSEfirewall2 off
             chkconfig SuSEfirewall2_setup off
         elif [[ $VER =~ ^12\.[0-9]+$ ]]; then
             systemctl stop SuSEfirewall2
             systemctl disable SuSEfirewall2
         elif [[ $VER =~ ^15\.[0-9]+$ ]]; then
             systemctl stop firewalld
             systemctl disable firewalld
         fi
         ;;
      ${OS_KEY_UBUNTU})
         ufw disable
         ;;
      *)
         echo -e "[ERROR] Unsupported OS: $OS $VER"
         exit 1
      ;;
   esac
   echo -e "[INFO] Stop and disable firewall successfully."
}

function disable_iptables() {
   print_log "===Stop and disable iptables==="
   case "$OS" in
      ${OS_KEY_KYLIN} | ${OS_KEY_OPENEULER})
         systemctl stop iptables
         systemctl disable iptables > /dev/null 2>&1
         ;;
      *)
      echo -e "[WARNING] Stopping and disabling iptables is not supported, please do it manually."
      return
      ;;
   esac
   echo -e "[INFO] Stop and disable iptables successfully."
}

function disable_SELinux() {
   local selinux_config_file="/etc/selinux/config"
   # For some linux distributions, SELinux is not installed by default, e.g. Ubuntu
   if [[ -f "${selinux_config_file}" ]]; then
      print_log "===Disable SELinux==="
      selinux_status=$(grep "^SELINUX=" "${selinux_config_file}" | cut -d= -f2)
      if [[ "${selinux_status}" == "enforcing" || "${selinux_status}" == "permissive" ]]; then
         sed -i "s/SELINUX=.*/SELINUX=disabled/g" "${selinux_config_file}"
         NEED_REBOOT=true
         REBOOT_INFO="${REBOOT_INFO}* Disable SELinux\n"
      fi
   else
      echo -e "[INFO] SELinux is not enabled."
      return
   fi
   echo -e "[INFO] Disable SELinux successfully."
}

# Helper function to set a kernel parameter
function set_kernel_param() {
  local param="$1"
  local value="$2"
  local file="/etc/sysctl.conf"

  # Search for existing parameter line
  local line=$(grep -E "^\s*$param\s*=" "$file")
  if [[ -n "$line" ]]; then
    # Update existing line
    sed -i "s/$param\s*=.*/$param = $value/" "$file"
  else
    # Add new parameter line
    echo "$param = $value" >> "$file"
  fi
}

function set_kernel_parameters() {
   # Backup the original configuration file.
   print_log "===Change kernel parameters==="
   bak_time=$(date +%Y%m%d%H%M%S)
   bak_file="/etc/sysctl.conf.bak_${bak_time}"
   print_log "Backup /etc/sysctl.conf to $bak_file"
   cp /etc/sysctl.conf /etc/sysctl.conf.bak_${bak_time}
   # Set all kernel parameters
   set_kernel_param vm.swappiness "$SWAPPINESS"
   set_kernel_param vm.overcommit_memory "$OVERCOMMIT_MEMORY"
   set_kernel_param vm.max_map_count "$MAX_MAP_COUNT"
   set_kernel_param net.ipv4.tcp_keepalive_time "$TCP_KEEPALIVE_TIME"
   set_kernel_param net.ipv4.tcp_retries2 "$TCP_RETRIES2"

   if [ "$WRITE_LOG" = true ]; then
      sysctl -p >> $LOG_FILE
   else
      sysctl -p
   fi

   echo -e "[INFO] Change kernel parameters successfully."
}

function disable_transparent_hugepage() {
   # Check if Transparent Huge Pages is enabled
   if [[ "" != "$(cat /sys/kernel/mm/transparent_hugepage/enabled | grep '\[never\]')" &&
         "" != "$(cat /sys/kernel/mm/transparent_hugepage/defrag | grep '\[never\]')" ]]; then
      echo -e "[INFO] Transparent Huge Pages is not enabled."
      return
   fi

   local rc_file="/etc/rc.d/rc.local"
   if [[ -f "${rc_file}" ]]; then
      print_log "===Disable Transparent Huge Pages==="
      echo "echo never > /sys/kernel/mm/transparent_hugepage/enabled" >> "${rc_file}"
      echo "echo never > /sys/kernel/mm/transparent_hugepage/defrag" >> "${rc_file}"
      chmod +x "${rc_file}"
      source "${rc_file}"
   else
      if [[ $(ps -p 1 | awk 'NR>1 {print $4}') == "systemd" ]]; then
         print_log "The system is using systemd. Create a systemd service named disable-thp to disable Transparent Huge Pages..."
         echo "[Unit]
         Description=Disable Transparent Huge Pages(THP)
         [Service]
         Type=oneshot
         ExecStart=/bin/sh -c 'echo never > /sys/kernel/mm/transparent_hugepage/enabled && echo never > /sys/kernel/mm/transparent_hugepage/defrag'
         [Install]
         WantedBy=multi-user.target" > /etc/systemd/system/disable-thp.service
         systemctl daemon-reload
         systemctl enable disable-thp.service
         systemctl start disable-thp.service
      fi
   fi
   echo -e "[INFO] Disable Transparent Huge Pages successfully."
}

function show_help() {
    echo "Usage: $0 [-argument]"
    echo "  -v          Display script version."
    echo "  -h| --help  Display help message."
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -v)
            echo ${SCRIPT_VERSION}
            exit 0
            ;;
        -h |--help)
            show_help
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            ;;
    esac
done

# check if I'm root or a sudoer
if [[ $EUID -ne 0 ]]; then
   echo -e "[ERROR] This script must be run as root."
   exit 1
fi

echo -e "=====Begin to configure the OS for SequoiaDB DDS====="
get_os_info
#disable_firewall
#disable_iptables
#disable_SELinux
set_kernel_parameters
disable_transparent_hugepage
echo -e "===============Configuration complete================"

if [[ "$NEED_REBOOT" = true ]]; then
   echo -e "$REBOOT_INFO"
fi
