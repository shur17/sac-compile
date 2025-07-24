#!/bin/bash

file_path="/etc/security/limits.d/99-sequoiadb-dds-limits.conf"
new_value="65535"

if [ -f "$file_path" ]; then
    sed -i "s/nofile [0-9]*/nofile $new_value/g" $file_path
    sed -i "s/nproc [0-9]*/nproc $new_value/g" $file_path
fi
