#!/bin/bash

JDK_REPOSITORY_URL="http://gitlab.sequoiadb.com/sequoiadb/jdk/raw/master/"
JDK_INSTALL_FILE_NAME="installJDK.sh"

# SAC 安装目录下的 conf 目录下要保存的文件
KEEP_CONF_FILES=("samples" "service" "dds-conf-desc" "sdb-conf-desc" "default-alert-metric-config.yml.en" "default-alert-metric-config.yml.zh"
                  "default-alert-rule-tmpl.yml.en" "default-alert-rule-tmpl.yml.zh" "default-collect-strategy.yml"
                  "default-dds-collect-strategy.yml" "deploy.yml" "discover.yml" "discover-dds.yml"
                  "agentlist.yml" "sequoiadb.p12" "serverlist.yml" "sshtrust.yml" "upgrade_rule.csv")

# print help message
function help()
{
   echo ""
   echo "  Usage:  ./build.sh [OPTION]..."
   echo ""
   echo "  ./build.sh [-s | --scope <scope>]          run compilation directly"
   echo "  ./build.sh -c [--clean]                    clean up the compilation environment"
   echo "  ./build.sh -h [--help]                     print help message"
   echo "  ./build.sh -p [--package]                  compile and package into sac-<version>-release.tar.gz"
   echo "  ./build.sh -t [--test]                     compile and run unit tests"
   echo ""
   echo "Options:"
   echo "  -s, --scope                                specify compile scope: frontend, backend or both, default value is both"
   exit 0
}

function check_and_install_necessary_module() {
    # check and install PyYAML
    pip show PyYAML > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "PyYAML not installed, Installing..."
        pip install PyYAML==5.2
        local ret=$?
        if [ $ret -ne 0 ]; then
            echo "ERROR: Failed to install PyYAML(5.2), error code: $ret"
            exit $ret
        else
            echo "PyYAML(5.2) installed successfully"
        fi
    fi

    # check and install paramiko
    pip show paramiko > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "paramiko not installed, Installing..."
        pip install paramiko==1.13.0
        local ret=$?
        if [ $ret -ne 0 ]; then
            echo "ERROR: Failed to install paramiko(1.13.0), error code: $ret"
            exit $ret
        else
            echo "paramiko(1.13.0) installed successfully"
        fi
    fi

    # check and install scp
    pip show scp > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "scp not installed, Installing..."
        pip install scp==0.15.0
        local ret=$?
        if [ $ret -ne 0 ]; then
            echo "ERROR: Failed to install scp(0.15.0), error code: $ret"
            exit $ret
        else
            echo "scp(0.15.0) installed successfully"
        fi
    fi
}

function check()
{
  echo "Starting check build sac environment ..."

  if [ ! -d $path/src ]; then
    echo "ERROR: Directory 'src' does not exist."
    exit 1
  fi

  # install default JDK
  if [[ ! -f $LOCAL_JDK_URL_INFO_FILE_PATH || ! -f $LOCAL_JDK_INSTALL_FILE_PATH || ! -d $LOCAL_JDK_INSTALL_DIR ]]; then
    echo "install default JDK from ${JDK_REPOSITORY_URL} ..."
    test -d $SAC_BUILD_PACKAGES_PATH || mkdir -p $SAC_BUILD_PACKAGES_PATH
    cd $SAC_BUILD_PACKAGES_PATH
    wget -nc "${JDK_REPOSITORY_URL}${JDK_INSTALL_FILE_NAME}" > /dev/null 2>&1
    local ret=$?
    if [ $ret -ne 0 ]; then
      echo "ERROR: Failed to download ${JDK_INSTALL_FILE_NAME} from ${JDK_REPOSITORY_URL}, error code: $ret"
      exit $ret
    fi
    test -x ${JDK_INSTALL_FILE_NAME} || chmod u+x ${JDK_INSTALL_FILE_NAME}
    . ./${JDK_INSTALL_FILE_NAME}
    if [ $? -ne 0 ]; then
      echo "ERROR: Failed to execute shell ${JDK_INSTALL_FILE_NAME}"
      exit $ret
    fi
  else
    cd $SAC_BUILD_PACKAGES_PATH
    test -x ${JDK_INSTALL_FILE_NAME} || chmod u+x ${JDK_INSTALL_FILE_NAME}
    . ./${JDK_INSTALL_FILE_NAME}
  fi

  # check if Maven installed
  if [[ ! `command -v mvn` ]]; then
    echo "ERROR: Maven not installed detected."
    exit 1
  fi

  # check if NPM installed
  if [[ ! `command -v npm` ]]; then
    echo "ERROR: NPM not installed detected."
    exit 1
  fi

  # check if Python installed
  if [[ ! `command -v python` ]]; then
    echo "ERROR: Python not installed detected."
    exit 1
  else
    # check and install necessary module
    check_and_install_necessary_module
    ret=$?
    if [ $ret -ne 0 ]; then
        exit $ret
    fi
  fi

  echo "Success: success to check build sac environment"
}

function array_contains()
{
  local search_string="$1"
  shift
  local array=("$@")

  for element in "${array[@]}"
  do
    if [[ "$element" == "$search_string" ]]
    then
      return 0
    fi
  done

  return 1
}

# remove directory before compiling
function rm_dir()
{

  test -d $SAC_BUILD_PATH && cd $SAC_BUILD_PATH && rm -rf `ls | grep -v "packages"`

  rm -rf $path/src/server/*/shared-lib

}

# create directory before compiling
function mk_dir()
{

  test -d $SAC_BUILD_PATH/sac || mkdir -p $SAC_BUILD_PATH/sac
  test -d $SAC_BUILD_PATH/sac/agent/sac-agent || mkdir -p $SAC_BUILD_PATH/sac/agent/sac-agent
  test -d $SAC_BUILD_PATH/sac/agent/sac-agent/lib || mkdir -p $SAC_BUILD_PATH/sac/agent/sac-agent/lib
  test -d $SAC_BUILD_PATH/sac/bin || mkdir -p $SAC_BUILD_PATH/sac/bin
  test -d $SAC_BUILD_PATH/sac/conf || mkdir -p $SAC_BUILD_PATH/sac/conf
  test -d $SAC_BUILD_PATH/sac/lib || mkdir -p $SAC_BUILD_PATH/sac/lib
  test -d $SAC_BUILD_PATH/sac/lib/java || mkdir -p $SAC_BUILD_PATH/sac/lib/java
  test -d $SAC_BUILD_PATH/sac/lib/shared-lib || mkdir -p $SAC_BUILD_PATH/sac/lib/shared-lib
  test -d $SAC_BUILD_PATH/sac/lib/server-lib || mkdir -p $SAC_BUILD_PATH/sac/lib/server-lib
  test -d $SAC_BUILD_PATH/sac/tools/backup || mkdir -p $SAC_BUILD_PATH/sac/tools/backup
  test -d $SAC_BUILD_PATH/sac/tools/inspect || mkdir -p $SAC_BUILD_PATH/sac/tools/inspect
  test -d $SAC_BUILD_PATH/sac/tools/inspect/bin || mkdir -p $SAC_BUILD_PATH/sac/tools/inspect/bin
  test -d $SAC_BUILD_PATH/sac/tools/inspect/lib || mkdir -p $SAC_BUILD_PATH/sac/tools/inspect/lib
  test -d $SAC_BUILD_PATH/sac/tools/daemon || mkdir -p $SAC_BUILD_PATH/sac/tools/daemon
  test -d $SAC_BUILD_PATH/sac/tools/deployment || mkdir -p $SAC_BUILD_PATH/sac/tools/deployment
  test -d $SAC_BUILD_PATH/sac/tools/deployment/sdb-dds-cc || mkdir -p $SAC_BUILD_PATH/sac/tools/deployment/sdb-dds-cc
  test -d $SAC_BUILD_PATH/sac/tools/maintain/m2s || mkdir -p $SAC_BUILD_PATH/sac/tools/maintain/m2s
  test -d $SAC_BUILD_PATH/sac/tools/on-OOM || mkdir -p $SAC_BUILD_PATH/sac/tools/on-OOM
  test -d $SAC_BUILD_PATH/sac/tools/post-install || mkdir -p $SAC_BUILD_PATH/sac/tools/post-install
  test -d $SAC_BUILD_PATH/sac/tools/script || mkdir -p $SAC_BUILD_PATH/sac/tools/script
  test -d $SAC_BUILD_PATH/sac/tools/ssh || mkdir -p $SAC_BUILD_PATH/sac/tools/ssh
  test -d $SAC_BUILD_PATH/sac/tools/upgrade || mkdir -p $SAC_BUILD_PATH/sac/tools/upgrade
  test -d $SAC_BUILD_PATH/sac/web || mkdir -p $SAC_BUILD_PATH/sac/web

}

# clean up the compilation environment
function clean()
{
  echo "Starting clean up the compilation environment ..."

  local ret=0
  if [[ $scope =~ "frontend" ]]; then
    # clean up frontend environment
    test -d $path/src/web/dist && rm -rf $path/src/web/dist
  elif [[ $scope =~ "backend" ]]; then
    # clean up backend environment
    cd $path/src/server
    mvn clean
    ret=$?
  else
    test -d $path/src/web/dist && rm -rf $path/src/web/dist
    cd $path/src/server
    mvn clean
    ret=$?
  fi
  if [[ $ret != 0 ]]; then
    echo "ERROR: Failed to clean up the compilation environment"
    exit 1
  fi

}

# rewrite VERSION.info to generate VERSION
function rewrite()
{
  type="SAC"
  git_version=`git rev-parse HEAD`
  build_time="`date +%Y-%m-%d-%H.%M.%S`"
  version_info=$(cat $path/VERSION.info)
  version_info=${version_info/\{type\}/$type}
  version_info=${version_info/\{git_version\}/$git_version}
  version_info=${version_info/\{build_time\}/$build_time}
  echo "$version_info" > $SAC_BUILD_PATH/sac/VERSION

  type="Agent"
  version_info=$(cat $path/VERSION.info)
  version_info=${version_info/\{type\}/$type}
  version_info=${version_info/\{git_version\}/$git_version}
  version_info=${version_info/\{build_time\}/$build_time}
  echo "$version_info" > $SAC_BUILD_PATH/sac/agent/sac-agent/VERSION
}

# compile backend
function compile_backend()
{
  # bin
  test -d $path/bin && cp -r $path/bin/* $SAC_BUILD_PATH/sac/bin

  # conf
  test -d $path/conf && cp -r $path/conf/* $SAC_BUILD_PATH/sac/conf
  cd $SAC_BUILD_PATH/sac/conf
  local current_files=`ls`
  for file in ${current_files[@]}
  do
    if ! array_contains "$file" "${KEEP_CONF_FILES[@]}"
    then
      rm -rf $file
    fi
  done

  # lib
  cd $path/src/server

  # get the first line of $path/VERSION.info to get the sac version
  version_info=$(head -n +1 $path/VERSION.info)
  sac_version=${version_info##*" "}
  # set the version of sourcecode
  mvn versions:set -DnewVersion=$sac_version
  mvn versions:commit

  local ret=0
  if [[ $need_compile_and_run_tests = true ]]; then
    mvn clean package -Dmaven.test.skip=false
    ret=$?
  else
    mvn clean package -Dmaven.test.skip=true
    ret=$?
  fi
  if [[ $ret != 0 ]];
  then
    echo "ERROR: Failed to compile backend jar file"
    exit 1
  fi

  jars=`find $path/src/server -name sac*.jar -not -path "*/test/*" -not -path "*/sac-statistical/*" -not -path "*/sac-common/*" -not -path "*/sac-agent-common/*" -not -path "*/sac-agent-plugin/*" -not -path "*/sac-audit-*/*" -not -path "*/sac-task-manager/*" -not -path "*/sac-dms/*" -not -path "*/shared-lib/*"`
  cd $path
  # 声明关联数组统计文件出现次数
  declare -A file_counts
  declare -a sac_server_names=()
  # traverse each jar and move it to the corresponding location
  for jar in ${jars[@]}
  do
    filename=$(basename "$jar")
    if [[ $filename =~ "sac-agent-collector" ]]; then
      cp -f $jar $SAC_BUILD_PATH/sac/agent/sac-agent/lib
    elif [[ "$filename" =~ ^(sac-[^-]+(-[^-]+)*)-exec\.jar$ ]]; then
      sac_server_name="${BASH_REMATCH[1]}"
      if [[ ! " ${sac_server_names[@]} " =~ " ${sac_server_name} " ]]; then
        sac_server_names+=("$sac_server_name")
      fi
      cp -f $jar $SAC_BUILD_PATH/sac/lib/$sac_server_name.jar
      dir="$path/src/server/$sac_server_name/shared-lib"
      if [[ -d "$dir" ]]; then
        # 仅处理普通文件（排除目录）
        for file in "$dir"/*; do
          if [[ -f "$file" ]]; then
            filename=$(basename "$file")
            ((file_counts["$filename"]++))
          fi
        done
      fi
    fi
  done


  for sac_server_name in "${sac_server_names[@]}"
  do
    dir="$path/src/server/$sac_server_name/shared-lib"
    dest_shared="$SAC_BUILD_PATH/sac/lib/shared-lib"
    dest_server="$SAC_BUILD_PATH/sac/lib/server-lib/$sac_server_name-lib"

    # 创建目标目录（共享目录和服务子目录）
    mkdir -p "$dest_shared" "$dest_server"

    if [[ -d "$dir" ]]; then
      # 处理当前服务的每个文件
      for file in "$dir"/*; do
        if [[ -f "$file" ]]; then
          filename=$(basename "$file")
          total_servers=${#sac_server_names[@]}

          # 判断是否所有服务均有此文件
          if [[ ${file_counts["$filename"]} -eq "$total_servers" ]]; then
            cp -f "$file" "$dest_shared/"
          else
            cp -f "$file" "$dest_server/"
          fi
        fi
      done
    fi
  done

  # java
  tar -zxvf $path/thirdparty/java/OpenJDK8U-jdk_aarch64_linux_8u292b10.tar.gz -C $SAC_BUILD_PATH/sac/lib/java
  mv $SAC_BUILD_PATH/sac/lib/java/jre $SAC_BUILD_PATH/sac/lib/java/aarch64

  tar -zxvf $path/thirdparty/java/OpenJDK8U-jdk_x64_linux_8u292b10.tar.gz -C $SAC_BUILD_PATH/sac/lib/java
  mv $SAC_BUILD_PATH/sac/lib/java/jre $SAC_BUILD_PATH/sac/lib/java/x86_64

  # license
  cp -r $path/license $SAC_BUILD_PATH/sac

  # tools
  # compile sac-deploy-tool
  cp -f $path/src/tools/sac-deploy-tool/target/sac-deploy-tool.jar $SAC_BUILD_PATH/sac/tools/deployment/sac-deploy-tool.jar

  # compile sdb-ssh-tool
  cp -f $path/src/tools/sdb-ssh-tool/target/sdb-ssh-tool.jar $SAC_BUILD_PATH/sac/tools/ssh/sdb-ssh-tool.jar

  # compile sac-upgrade-tool
  cp -f $path/src/tools/sac-upgrade-tool/target/sac-upgrade-tool.jar $SAC_BUILD_PATH/sac/tools/upgrade/sac-upgrade-tool.jar

  # compile sdb-dds-cc_<version>.tar.gz 解压到 tools/deployment/sdb-dds-cc/sdb-dds-cc
  tar -xzf "$path/tools/dds-cc/sdb-dds-cc_"*.tar.gz -C "$SAC_BUILD_PATH/sac/tools/deployment/sdb-dds-cc" --strip-components=1

  # compile m2s_v2.0.0.tar.gz 解压到 tools/maintain/m2s
  tar -xzf "$path/tools/m2s/m2s_"*.tar.gz -C "$SAC_BUILD_PATH/sac/tools/maintain/m2s" --strip-components=1

  # backup
  cp -rf $path/tools/backup/* $SAC_BUILD_PATH/sac/tools/backup

  # inspect
  cp -f $path/src/tools/sac-inspect-tool/target/sac-inspect-tool.jar $SAC_BUILD_PATH/sac/tools/inspect/lib/sac-inspect-tool.jar
  cp -f $path/src/tools/sac-inspect-tool/bin/* $SAC_BUILD_PATH/sac/tools/inspect/bin
  cp -f $path/src/tools/sac-inspect-tool/Readme.md $SAC_BUILD_PATH/sac/tools/inspect/Readme.md

  # daemon
  cp -f $path/tools/daemon/* $SAC_BUILD_PATH/sac/tools/daemon

  # on-OOM
  cp -f $path/tools/on-OOM/* $SAC_BUILD_PATH/sac/tools/on-OOM

  # post-install
  cp -f $path/tools/post-install/* $SAC_BUILD_PATH/sac/tools/post-install

  # dds_os_init.sh
  cp -f $path/tools/script/* $SAC_BUILD_PATH/sac/tools/script

  # sac-agent
  test -d $path/agent/sac-agent && cp -r $path/agent/sac-agent/* $SAC_BUILD_PATH/sac/agent/sac-agent
  test -d $path/agent/sac-agent/conf/samples && cp $path/agent/sac-agent/conf/samples/* $SAC_BUILD_PATH/sac/agent/sac-agent/conf

  # dds-backup-agent
  local backup_agent_version_prefix="Backup Agent version"
  local backup_agent_name_prefix="Backup Agent name"
  local backup_agent_version=`grep "$backup_agent_version_prefix" $path/BACKUP_AGENT_NAME.info | sed "s/$backup_agent_version_prefix: //"`
  local backup_agent_name=`grep "$backup_agent_name_prefix" $path/BACKUP_AGENT_NAME.info | sed "s/$backup_agent_name_prefix: //"`
  python $path/dev/script/fetch_package.py --search-base-dir="/data/share_new/7.版本归档_NEW/SequoiaMisc/dds_backup_agent" --version=$backup_agent_version --name=$backup_agent_name --download-dir=$SAC_BUILD_PACKAGES_PATH
  ret=$?
  if [[ $ret != 0 ]]; then
    echo "ERROR: Failed to fetch dds backup agent package, name: $backup_agent_name, download_dir: $SAC_BUILD_PACKAGES_PATH"
    exit 1
  fi

  tar -zxvf $SAC_BUILD_PACKAGES_PATH/$backup_agent_name -C $SAC_BUILD_PATH/sac/agent
  mv $SAC_BUILD_PATH/sac/agent/dds-backup-agent_* $SAC_BUILD_PATH/sac/agent/dds-backup-agent

}

# compile frontend
function compile_frontend()
{
  test -d $path/src/web/node_modules || cp -R $path/thirdparty/web/node_modules $path/src/web/node_modules
  cd $path/src/web
  chmod u+x ./node_modules/.bin/*
  chmod u+x ./node_modules/@esbuild/linux-x64/bin/*
  chmod u+x ./node_modules/@esbuild/linux-arm64/bin/*
  npm run build
  local ret=$?
  if [[ $ret != 0 ]];
  then
    echo "ERROR: Failed to compile frontend static file"
    exit 1
  fi
  if [[ -d $path/src/web/dist ]]; then
    mv -f dist/* $SAC_BUILD_PATH/sac/web
  fi
}

function compile()
{

  check
  clean
  rm_dir
  mk_dir

  echo "Starting compile ..."
  if [[ $scope =~ "frontend" ]]; then
    compile_frontend
  elif [[ $scope =~ "backend" ]]; then
    compile_backend
  else
    compile_frontend
    compile_backend
  fi

  rewrite
}

function package()
{

  echo "Starting package ..."

  # get the first line of $path/VERSION.info to get the sac version
  version_info=$(head -n +1 $path/VERSION.info)
  sac_version=${version_info##*" "}

  cd $SAC_BUILD_PATH
  tar -zcvf sac-$sac_version-release.tar.gz sac >> /dev/null 2>&1

  echo "Success: success to package and sac-$sac_version-release.tar.gz could be found in $SAC_BUILD_PATH."
  echo "Use 'tar -zxvf sac-$sac_version-release.tar.gz' to unpack it."
}

function compile_and_package()
{
  compile
  package
}

function package_sac_elf_files()
{
  local dest_path=$1
  # compile elf-deploy-tool
  test -d $dest_path/tools/deployment || mkdir -p $dest_path/tools/deployment
  cp -f $path/src/tools/elf-deploy-tool/target/elf-deploy-tool.jar $dest_path/tools/deployment/elf-deploy-tool.jar

  # bin file
  test -d $dest_path/bin || mkdir -p $dest_path/bin
  cp -f $path/thirdparty/elf/bin/el_ctl $dest_path/bin
  cp -f $path/thirdparty/elf/bin/elf_admin $dest_path/bin

  # conf file
  test -d $dest_path/config || mkdir -p $dest_path/config
  cp -f $path/thirdparty/elf/conf/cluster-info.yml $dest_path/config
  cp -f $path/thirdparty/elf/conf/el-deploy.yml $dest_path/config
  cp -f $path/thirdparty/elf/conf/nodelist.yml $dest_path/config
  cp -f $path/thirdparty/elf/conf/serverlist.yml $dest_path/config

  # daemon file
  test -d $dest_path/tools/daemon || mkdir -p $dest_path/tools/daemon
  cp -f $path/thirdparty/elf/tools/daemon/el_daemon $dest_path/tools/daemon
  cp -f $path/thirdparty/elf/tools/daemon/el_daemon_ctl $dest_path/tools/daemon

  # filebeat bin file
  test -d $dest_path/filebeat-linux_x86_64/bin || mkdir -p $dest_path/filebeat-linux_x86_64/bin
  cp -f $path/thirdparty/elf/filebeat/bin/filebeat_ctl $dest_path/filebeat-linux_x86_64/bin
  test -d $dest_path/filebeat-linux_aarch64/bin || mkdir -p $dest_path/filebeat-linux_aarch64/bin
  cp -f $path/thirdparty/elf/filebeat/bin/filebeat_ctl $dest_path/filebeat-linux_aarch64/bin

  # filebeat daemon file
  test -d $dest_path/filebeat-linux_x86_64/tools/daemon || mkdir -p $dest_path/filebeat-linux_x86_64/tools/daemon
  cp -f $path/thirdparty/elf/filebeat/tools/daemon/filebeat_daemon $dest_path/filebeat-linux_x86_64/tools/daemon/filebeat_daemon
  cp -f $path/thirdparty/elf/filebeat/tools/daemon/filebeat_daemon_ctl $dest_path/filebeat-linux_x86_64/tools/daemon/filebeat_daemon_ctl
  test -d $dest_path/filebeat-linux_aarch64/tools/daemon || mkdir -p $dest_path/filebeat-linux_aarch64/tools/daemon
  cp -f $path/thirdparty/elf/filebeat/tools/daemon/filebeat_daemon $dest_path/filebeat-linux_aarch64/tools/daemon/filebeat_daemon
  cp -f $path/thirdparty/elf/filebeat/tools/daemon/filebeat_daemon_ctl $dest_path/filebeat-linux_aarch64/tools/daemon/filebeat_daemon_ctl
}

function package_elf_files()
{
  local dest_path=$1
  local type=$2

  # Elasticsearch files
  test -d $dest_path/elasticsearch || mkdir -p $dest_path/elasticsearch
  cp -r $path/thirdparty/elf/$type/elasticsearch-7.17.7/* $dest_path/elasticsearch

  # Logstash files
  test -d $dest_path/logstash || mkdir -p $dest_path/logstash
  cp -r $path/thirdparty/elf/$type/logstash-7.17.7/* $dest_path/logstash

  # Filebeat files
  test -d $dest_path/filebeat-linux_x86_64 || mkdir -p $dest_path/filebeat-linux_x86_64
  cp -r $path/thirdparty/elf/linux_x86_64/filebeat-7.17.7/* $dest_path/filebeat-linux_x86_64
  test -d $dest_path/filebeat-linux_aarch64 || mkdir -p $dest_path/filebeat-linux_aarch64
  cp -r $path/thirdparty/elf/linux_arrch64/filebeat-7.17.7/* $dest_path/filebeat-linux_aarch64
}

function compile_and_package_elf()
{

  echo "compiling elf-deploy-tool ..."
  # get elf-deploy-tool.jar
  cd $path/src/server

  # get the first line of $path/VERSION.info to get the sac version
  version_info=$(head -n +1 $path/VERSION.info)
  sac_version=${version_info##*" "}
  # set the version of sourcecode
  mvn versions:set -DnewVersion=$sac_version
  mvn versions:commit

  local ret=0
  mvn clean package -Dmaven.test.skip=true
  ret=$?
  if [[ $ret != 0 ]];
  then
    echo "ERROR: Failed to compile elf-deploy-tool jar file"
    exit 1
  fi
  echo "success to compile elf-deploy-tool"

  echo "packaging Elasticsearch, Logstash and Filebeat ..."
  # linux-aarch64
  test -d $SAC_BUILD_PATH/sequoiasac-elf && rm -rf $SAC_BUILD_PATH/sequoiasac-elf
  mkdir -p $SAC_BUILD_PATH/sequoiasac-elf
  package_sac_elf_files $SAC_BUILD_PATH/sequoiasac-elf
  package_elf_files $SAC_BUILD_PATH/sequoiasac-elf linux_arrch64
  # create elasticsearch plugins path
  test -d $SAC_BUILD_PATH/sequoiasac-elf/elasticsearch/plugins || mkdir -p $SAC_BUILD_PATH/sequoiasac-elf/elasticsearch/plugins
  # create elasticsearch logs path
  test -d $SAC_BUILD_PATH/sequoiasac-elf/elasticsearch/logs || mkdir -p $SAC_BUILD_PATH/sequoiasac-elf/elasticsearch/logs
  # create logstash data path
  test -d $SAC_BUILD_PATH/sequoiasac-elf/logstash/data || mkdir -p $SAC_BUILD_PATH/sequoiasac-elf/logstash/data
  # tar
  cd $SAC_BUILD_PATH
  chmod -R u=rwx,g=rx,o=rx sequoiasac-elf
  # get the first line of $path/VERSION.info to get the sac version
  version_info=$(head -n +1 $path/VERSION.info)
  sac_version=${version_info##*" "}
  test -f sequoiasac-elf-${sac_version}-linux_aarch64-enterprise.tar.gz && rm -f sequoiasac-elf-${sac_version}-linux_aarch64-enterprise.tar.gz
  tar -zcvf sequoiasac-elf-${sac_version}-linux_aarch64-enterprise.tar.gz sequoiasac-elf >> /dev/null 2>&1
  test -d $SAC_BUILD_PATH/sequoiasac-elf && rm -rf $SAC_BUILD_PATH/sequoiasac-elf

  # linux-x86_64
  test -d $SAC_BUILD_PATH/sequoiasac-elf || mkdir -p $SAC_BUILD_PATH/sequoiasac-elf
  package_sac_elf_files $SAC_BUILD_PATH/sequoiasac-elf
  package_elf_files $SAC_BUILD_PATH/sequoiasac-elf linux_x86_64
 # create elasticsearch plugins path
  test -d $SAC_BUILD_PATH/sequoiasac-elf/elasticsearch/plugins || mkdir -p $SAC_BUILD_PATH/sequoiasac-elf/elasticsearch/plugins
  # create elasticsearch logs path
  test -d $SAC_BUILD_PATH/sequoiasac-elf/elasticsearch/logs || mkdir -p $SAC_BUILD_PATH/sequoiasac-elf/elasticsearch/logs
  # create logstash data path
  test -d $SAC_BUILD_PATH/sequoiasac-elf/logstash/data || mkdir -p $SAC_BUILD_PATH/sequoiasac-elf/logstash/data
  # tar
  cd $SAC_BUILD_PATH
  chmod -R u=rwx,g=rx,o=rx sequoiasac-elf
  test -f sequoiasac-elf-${sac_version}-linux_x86_64-enterprise.tar.gz && rm -f sequoiasac-elf-${sac_version}-linux_x86_64-enterprise.tar.gz
  tar -zcvf sequoiasac-elf-${sac_version}-linux_x86_64-enterprise.tar.gz sequoiasac-elf >> /dev/null 2>&1
  test -d $SAC_BUILD_PATH/sequoiasac-elf && rm -rf $SAC_BUILD_PATH/sequoiasac-elf

  echo "success to package Elasticsearch, Logstash and Filebeat, packaged file list: "
  echo "$SAC_BUILD_PATH/sequoiasac-elf-${sac_version}-linux_aarch64-enterprise.tar.gz"
  echo "$SAC_BUILD_PATH/sequoiasac-elf-${sac_version}-linux_x86_64-enterprise.tar.gz"

  exit 0
}

# get path
dir_name=`dirname $0`
if [[ ${dir_name:0:1} != "/" ]]; then
  SAC_PATH=$(pwd)/$dir_name
else
  SAC_PATH=$dir_name
fi

cd $SAC_PATH && path=`pwd`

SAC_BUILD_PATH=$path/build
SAC_BUILD_PACKAGES_PATH=$SAC_BUILD_PATH/packages
LOCAL_JDK_URL_INFO_FILE_PATH=$SAC_BUILD_PACKAGES_PATH/jdkUrl.info
LOCAL_JDK_INSTALL_FILE_PATH=$SAC_BUILD_PACKAGES_PATH/$JDK_INSTALL_FILE_NAME
LOCAL_JDK_INSTALL_DIR=$SAC_BUILD_PACKAGES_PATH/openJDK-8u292

scope="both"
test $# -eq 0 && { compile && exit 0; }

ARGS=`getopt -o chps:t --long clean,help,package,scope:,test -- "$@"`
ret=$?
test $ret -ne 0 && exit $ret

eval set -- "${ARGS}"

need_compile=true
need_clean=false
need_compile_and_run_tests=false
need_compile_and_package=false
need_compile_and_package_el=false
while true
do
  case "$1" in
    -c | --clean)
      need_clean=true
      need_compile=false
      shift
      ;;

    -s | --scope)
      test -z $2 || scope=$2
      if [[ $scope =~ "elf" ]]; then
        need_compile=false
      fi
      shift 2
      ;;

    -t | --test)
      need_compile_and_run_tests=true
      need_compile=false
      shift
      ;;

    -p | --package)
      need_compile_and_package=true
      need_compile=false
      shift
      ;;

    -h | --help)
      help
      exit 0
      ;;

    --)
      shift
      break
      ;;

    *)
      echo "Unknown option: "$option
      echo "Try './build.sh --help' for more information."
      exit 1
  esac
done

if [[ $need_clean = true ]]; then
  clean
  rm_dir
fi

if [[ $need_compile = true || $need_compile_and_run_tests = true ]]; then
  compile
fi

if [[ $need_compile_and_package = true && $need_compile_and_run_tests = true ]]; then
  package
fi

if [[ $need_compile_and_package = true && $need_compile_and_run_tests = false ]]; then
  compile_and_package
fi

if [[ $scope =~ "elf" ]]; then
  check
  compile_and_package_elf
fi

