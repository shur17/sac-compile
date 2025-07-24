#!/bin/bash
set -Eeuo pipefail

if [ $# -ne 0 ]; then
    exec "$@"
fi

sac_deploy_status_filepath="/data/sac/sac_deploy_status"

sac_install_dir="/opt/sequoiasac"
sac_deploy_conf_filepath="${sac_install_dir}/conf/deploy.yml"
sac_admin_filepath="${sac_install_dir}/bin/sac_admin"
sac_ctl_filepath="${sac_install_dir}/bin/sac_ctl"
volume_path="/data/sac"

# usage: file_env VAR [DEFAULT]
#    ie: file_env 'XYZ_DB_PASSWORD' 'example'
# (will allow for "$XYZ_DB_PASSWORD_FILE" to fill in the value of
#  "$XYZ_DB_PASSWORD" from a file, especially for Docker's secrets feature)
file_env() {
	local var="$1"
	local fileVar="${var}_FILE"
	local def="${2:-}"
	if [ "${!var:-}" ] && [ "${!fileVar:-}" ]; then
		echo >&2 "error: both $var and $fileVar are set (but are exclusive)"
		exit 1
	fi
	local val="$def"
	if [ "${!var:-}" ]; then
		val="${!var}"
	elif [ "${!fileVar:-}" ]; then
		val="$(< "${!fileVar}")"
	fi
	export "$var"="$val"
	unset "$fileVar"
}

check_deployed() {
	if [ -f "$sac_deploy_status_filepath" ] && [ "$(cat $sac_deploy_status_filepath)" = "deployed" ] ; then
	    return 0
	fi
	return 1
}

set_deployed() {
	echo "deployed" > "$sac_deploy_status_filepath"
}

start_sac() {
    rm -rf ${sac_install_dir}/conf
    rm -rf ${sac_install_dir}/log
    rm -rf ${sac_install_dir}/logs

    ln -s ${volume_path}/conf ${sac_install_dir}/conf
    ln -s ${volume_path}/log ${sac_install_dir}/log
    ln -s ${volume_path}/logs ${sac_install_dir}/logs

    $sac_ctl_filepath startall
}

deploy_sac() {
    if [ -d ${sac_install_dir}/conf ]; then
        mv ${sac_install_dir}/conf ${volume_path}/
    else
        mkdir -p ${volume_path}/conf
    fi

    if [ -d ${sac_install_dir}/log ]; then
        mv ${sac_install_dir}/log ${volume_path}/
    else
        mkdir -p ${volume_path}/log
    fi

    if [ -d ${sac_install_dir}/logs ]; then
        mv ${sac_install_dir}/logs ${volume_path}/
    else
        mkdir -p ${volume_path}/logs
    fi

    ln -s ${volume_path}/conf ${sac_install_dir}/conf
    ln -s ${volume_path}/log ${sac_install_dir}/log
    ln -s ${volume_path}/logs ${sac_install_dir}/logs

    file_env 'SAC_INIT_DDS_URIS' '127.0.0.1:27017'
    file_env 'SAC_INIT_DDS_USERNAME'
    file_env 'SAC_INIT_DDS_PASSWORD'
    file_env 'SAC_INIT_DATABASE' 'sequoiasac'

	export yq_sac_log_path="${sac_install_dir}/log"

    yq -i '
	    .sacDatabase.database=strenv(SAC_INIT_DATABASE) |
		.logPath=strenv(yq_sac_log_path) |
		.sacDatabase.urls=strenv(SAC_INIT_DDS_URIS) | .sacDatabase.urls |= split(",")
	' $sac_deploy_conf_filepath

    deploy_cmd="$sac_admin_filepath deploysac"

	if [ -n "$SAC_INIT_DDS_USERNAME" ]; then
	    deploy_cmd="$deploy_cmd -u $SAC_INIT_DDS_USERNAME"
	fi

	if [ -n "$SAC_INIT_DDS_PASSWORD" ]; then
	    deploy_cmd="$deploy_cmd -p $SAC_INIT_DDS_PASSWORD"
	fi

	$deploy_cmd
	deploy_result=$?

	if [ $deploy_result -eq 0 ]; then
	    set_deployed
	fi

	return $deploy_result
}

check_services() {
	status_output=$($sac_ctl_filepath status)

	while IFS= read -r line; do
	    if [[ "$line" =~ ^SERVICE|^Total ]]; then
		    continue
		fi

		service=$(echo "$line" | awk '{print $1}')
		pid=$(echo "$line" | awk '{print $2}')

		if ! [[ "$pid" =~ ^[0-9]+$ ]]; then
			return 1
		fi
    done <<< "$status_output"
}

if check_deployed; then
    start_sac

	start_exit_code=$?
    if [ $start_exit_code -ne 0 ]; then
	    echo "The sac failed to start: exitCode=$start_exit_code"
		exit $start_exit_code
	fi
else
    deploy_sac

	deploy_exit_code=$?
    if [ $deploy_exit_code -ne 0 ]; then
	    echo "The sac failed to deploy: exitCode=$deploy_exit_code"
		exit $deploy_exit_code
	fi
fi

while true; do
    check_services
	sleep 10
done