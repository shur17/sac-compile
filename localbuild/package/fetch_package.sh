#!/bin/bash

# Define base URL
BASE_URL="http://192.168.29.80:8080"

# Get script file name
script_name=$(basename "$0")

# Check if --force argument exists
FORCE=false
if [[ " $* " =~ " --force " ]]; then
    FORCE=true
fi

# Check if --release argument exists
RELEASE=false
if [[ " $* " =~ " --release " ]]; then
    RELEASE=true
fi

# Switch to the script's directory
DOWNLOAD_DIR=$(dirname "$0")
cd $DOWNLOAD_DIR

# Define download function
download_package() {
    local ci_url=$1
    local pattern=$2
    url=${BASE_URL}/${ci_url}
    res=$(curl -s ${url})
    download_url=$(echo ${res} | grep -o "href=\"[^\"]*${pattern}\"" | sed 's/href="//' | sed 's/"$//')
    download_cmd="wget \"${url}${download_url}\""
    check_and_download "${pattern}" "${download_cmd}"
}

# download the package from the shared disk
download_release_package() {
    local package_name=$1
    local pattern=$2
    download_cmd="python \"${DOWNLOAD_DIR}/../../dev/script/fetch_package.py\" --name=\"${package_name}\" --download-dir=\"${DOWNLOAD_DIR}\""
    check_and_download "${pattern}" "${download_cmd}"
}

# Function to check if a file matching a pattern exists and handle overwrite
check_and_download() {
    local pattern=$1
    local download_cmd=$2
    matching_file=$(find . -type f -name "$(echo "${pattern}" | sed 's/\[^\"]\*/\*/g')")

    if [ -n "${matching_file}" ]; then
        if [ "${FORCE}" = false ]; then
            echo "File matching ${pattern} already exists."
            read -p "Overwrite with the latest version? (y/n, default=y): " choice
            choice=${choice:-y}
            case "${choice}" in
                y|Y )
                    rm -f "${matching_file}"
                    eval "${download_cmd}" ;;
                * )
                    echo "Skipping download..." ;;
            esac
        else
            rm -f "${matching_file}"
            eval "${download_cmd}"
        fi
    else
        eval "${download_cmd}"
    fi
}


# Use the download function to get different packages
if [ "$RELEASE" = true ]; then
    download_release_package "sdb-dds-cc_v1.0.7.tar.gz" "sdb-dds-cc_v[0-9.]*.tar.gz"
    download_release_package "sequoiadb-5.10-linux_x86_64-enterprise-installer.run" "sequoiadb-[0-9.]*-linux_[a-zA-Z0-9_]*-enterprise-installer.run"
    download_release_package "sequoiadb-dds-3.4.14-linux_x86_64-installer.run" "sequoiadb-dds-[0-9.]*-linux_[a-zA-Z0-9_]*-installer.run"
    download_release_package "sequoiasql-mariadb-3.4.12-linux_x86_64-installer.run" "sequoiasql-mysql-[0-9.]*-linux_x86_64-enterprise-installer.run"
    download_release_package "sequoiasql-mysql-3.4.12-linux_x86_64-enterprise-installer.run" "sequoiasql-mariadb-[0-9.]*-linux_x86_64-enterprise-installer.run"
else
    download_package "view/daily_tools/job/compile_dds_clusterconfig/" "sdb-dds-cc_v[0-9.]*.tar.gz"
    download_package "job/dailybuild_master_sequoiadb_x86/" "sequoiadb-[0-9.]*-linux_[a-zA-Z0-9_]*-enterprise-installer.run"
    download_package "view/daily_dds/job/compile_dds_x86/" "sequoiadb-dds-[0-9.]*-linux_[a-zA-Z0-9_]*-installer.run"
    download_package "view/daily_sql/job/dailybuild_master_mysql_x86/" "sequoiasql-mysql-[0-9.]*-linux_x86_64-enterprise-installer.run"
    download_package "view/daily_sql/job/dailybuild_3.4_mariadb_x86/" "sequoiasql-mariadb-[0-9.]*-linux_x86_64-enterprise-installer.run"
fi
download_package "view/daily_sac/job/compile_master_sequoiasac/" "sequoiasac-[0-9.]*-linux_x86_64-enterprise-installer.run"
download_package "view/daily_sac/job/compile_master_sequoiasac/" "build/sequoiasac-elf-[0-9.]*-linux_x86_64-enterprise.tar.gz"

echo "Download completed."
