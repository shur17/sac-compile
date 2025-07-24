#!/bin/bash

# Check if the script is running as root
if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root." 1>&2
   exit 1
fi

# Function to check if a specific setting exists in /etc/security/limits.conf
check_limits_setting() {
    local user=$1
    local type=$2
    local value=$3
    grep -q "^$user\s\+-\s\+$type\s\+$value" /etc/security/limits.conf
}

# Check and set limits for user 'sdbadmin'
set_limits() {
    local user="sdbadmin"
    local file="/etc/security/limits.conf"
    local settings=("nofile 65535" "nproc 4096" "fsize unlimited" "as unlimited")

    for setting in "${settings[@]}"; do
        if ! check_limits_setting $user ${setting% *} ${setting#* }; then
            echo "$user - ${setting% *} ${setting#* }" >> $file
            echo "Set $user's ${setting% *} to ${setting#* }."
        else
            echo "$user's ${setting% *} is already set to ${setting#* }, no modification needed."
        fi
    done
}

# Set the vm.max_map_count parameter in /etc/sysctl.conf
set_sysctl() {
    local param="vm.max_map_count"
    local value="262144"
    local file="/etc/sysctl.conf"

    if ! grep -q "^$param=$value" $file; then
        echo "$param=$value" >> $file
        sysctl -p
        echo "Set $param to $value."
    else
        echo "$param is already set to $value, no modification needed."
    fi
}

echo "Starting to check and set system parameters..."

# Adjust limits parameters
set_limits

# Adjust sysctl parameters
set_sysctl

echo "All system parameters checked and set."

