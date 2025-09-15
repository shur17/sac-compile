#!/bin/bash

JDK_DOWNLOAD_BASE_URL="https://github.com/SequoiaDB/sdb-dependencies/releases/download/openJDK%2Fv1.8/"
JDK_X86_64_FILE_NAME="OpenJDK8U-jdk_x64_linux_8u292b10.tar.gz"
JDK_AARCH64_FILE_NAME="OpenJDK8U-jdk_aarch64_linux_8u292b10.tar.gz"

TMP_PATH="/tmp/sequoiasac"
DOWNLOAD_PATH="$TMP_PATH/download"
WEB_NODE_MODULES_URL="https://github.com/SequoiaDB/sdb-dependencies/releases/download/sac-dependencies/web-node_modules-6.12.tar.gz"
DDS_BACKUP_AGENT_URL="https://github.com/SequoiaDB/sdb-dependencies/releases/download/sac-dependencies/dds-backup-agent_1.4.2.tar.gz"

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

function check_frontend()
{
  echo "Starting check build sac frontend environment ..."

  if [ ! -d $path/src ]; then
    echo "ERROR: Directory 'src' does not exist."
    exit 1
  fi
  
  if [ ! -d $path/src/web/node_modules ]; then
    echo "WARNING: Directory 'src/web/node_modules' does not exist, download from GitHub."
    local downloadFile="${DOWNLOAD_PATH}/node_modules-6.12.tar.gz"
    if [ -e $downloadFile ]; then
      echo "INFO: ${downloadFile} is exist."
    else
      mkdir -p $DOWNLOAD_PATH
      wget -nc -O $downloadFile "${WEB_NODE_MODULES_URL}" > /dev/null 2>&1
      echo "INFO: 'src/web/node_modules' download complete."
    fi
    tar --no-same-owner -xzvf $downloadFile -C $path/src/web > /dev/null 2>&1
    echo "INFO: 'src/web/node_modules' install complete."
  fi

  # check if nodejs installed
  if [[ ! `command -v node` ]]; then
    echo "ERROR: Node.js not installed detected."
    exit 1
  fi

  # check if NPM installed
  if [[ ! `command -v npm` ]]; then
    echo "ERROR: NPM not installed detected."
    exit 1
  fi

  echo "Success: success to check build sac frontend environment"
}

function check_backend()
{
  echo "Starting check build sac backend environment ..."

  if [ ! -d $path/src ]; then
    echo "ERROR: Directory 'src' does not exist."
    exit 1
  fi

  # install default JDK
  install_jdk

  # check if Maven installed
  if [[ ! `command -v mvn` ]]; then
    echo "ERROR: Maven not installed detected."
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

  echo "Success: success to check build sac backend environment"
}

function check()
{
  check_frontend
  check_backend
}

function install_jdk() {
  # Only download & unpack if any directory or java binary is missing
  if [[ ! -d "$JDK_X86_64_INSTALL_DIR" || ! -f "$JDK_X86_64_INSTALL_DIR/bin/java" \
     || ! -d "$JDK_AARCH64_INSTALL_DIR" || ! -f "$JDK_AARCH64_INSTALL_DIR/bin/java" ]]; then

    test -d $DOWNLOAD_PATH || mkdir -p $DOWNLOAD_PATH

    echo "Downloading $JDK_X86_64_FILE_NAME ..."
    download_jdk "$JDK_X86_64_INSTALL_DIR" "$JDK_X86_64_FILE_NAME" \
      || exit $?

    echo "Downloading $JDK_AARCH64_FILE_NAME ..."
    download_jdk "$JDK_AARCH64_INSTALL_DIR" "$JDK_AARCH64_FILE_NAME" \
      || exit $?

    echo "All JDKs downloaded successfully."
  else
    echo "JDKs already exist. Skipping download."
  fi

  echo "Configuring Java environment..."
  configure_java_env "$JDK_X86_64_INSTALL_DIR" "$JDK_AARCH64_INSTALL_DIR" || {
    echo "ERROR: Failed to configure Java environment." >&2
    exit 1
  }
}

function download_jdk() {
  local arch_dir="$1"
  local file_name="$2"
  local url="${JDK_DOWNLOAD_BASE_URL%/}/$file_name"

  # Prepare target directory
  if [ -d "$arch_dir" ]; then
    rm -rf "$arch_dir"/*
  else
    mkdir -p "$arch_dir"
  fi

  # Download if not exists
  if [ ! -f "$DOWNLOAD_PATH/$file_name" ]; then
    wget -nc -O "$DOWNLOAD_PATH/$file_name" "$url" > /dev/null 2>&1

    local ret=$?
    if [ $ret -ne 0 ]; then
      echo "ERROR: Failed to download $file_name from $url (code $ret)" >&2
      return $ret
    fi
  else
    echo "Skipping download, file already exists: $file_name"
  fi

  # Unpack
  tar --no-same-owner -zxf "$DOWNLOAD_PATH/$file_name" -C "$arch_dir" --strip-components=1

  # Ensure java is executable
  local java_path="$arch_dir/bin/java"
  test -x "$java_path" || chmod u+x "$java_path"

  return 0
}

function configure_java_env() {
  # Arguments:
  #   $1 = x86_64 JDK install directory
  #   $2 = aarch64 JDK install directory
  local x86_dir="$1"
  local aarch64_dir="$2"
  local selected_dir

  # Detect architecture
  case "$(arch)" in
    x86_64|amd64)
      selected_dir="$x86_dir"
      ;;
    aarch64|arm64)
      selected_dir="$aarch64_dir"
      ;;
    *)
      echo "ERROR: Unsupported architecture: $(arch)" >&2
      return 1
      ;;
  esac

  # Only current shell
  export JAVA_HOME="$selected_dir"
  export PATH="$JAVA_HOME/bin:$PATH"
  export CLASSPATH=".:$JAVA_HOME/lib/dt.jar:$JAVA_HOME/lib/tools.jar"

  validate_java_path "$selected_dir/bin/java" || exit 1

  echo "Java environment configured for current session: JAVA_HOME=$selected_dir"

  return 0
}

function validate_java_path() {
  local expected_java_path="$1"

  local java_path
  java_path=$(which java 2>/dev/null)
  if [[ -z "$java_path" ]]; then
    echo "ERROR: 'java' command not found in PATH." >&2
    return 1
  fi

  if [[ "$java_path" == "$expected_java_path" ]]; then
    return 0
  else
    echo "ERROR: Java validation failed!"
    echo "Expected: $expected_java_path"
    echo "Actual:   $java_path"
    return 1
  fi
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
  rm -rf $path/src/tools/*/shared-lib
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

# 处理 shared-lib 和 classpath
# 参数1: 服务名数组 (用 "${array[@]}" 传)
# 参数2: 类型 server 或 tools
process_shared_libs()
{
  local sac_server_names=("$@")     # 接收所有参数
  local type="${sac_server_names[-1]}"  # 最后一个参数作为类型
  unset 'sac_server_names[${#sac_server_names[@]}-1]' # 去掉最后一个参数（类型）

  for sac_server_name in "${sac_server_names[@]}"; do
    if [[ "$type" == "server" ]]; then
      dir="$path/src/server/$sac_server_name/shared-lib"
      dest_shared="$SAC_BUILD_PATH/sac/lib/shared-lib"
      dest_classpath="$SAC_BUILD_PATH/sac/lib/classpath"
    elif [[ "$type" == "tools" ]]; then
      dir="$path/src/tools/$sac_server_name/shared-lib"
      dest_shared="$SAC_BUILD_PATH/sac/tools/lib/shared-lib"
      dest_classpath="$SAC_BUILD_PATH/sac/tools/lib/classpath"
    else
      echo "未知类型: $type"
      return 1
    fi

    # 创建目标目录
    mkdir -p "$dest_shared" "$dest_classpath"

    if [[ -d "$dir" ]]; then
      classpath_file="$dest_classpath/$sac_server_name.classpath"
      : > "$classpath_file"   # 清空/新建

      for file in "$dir"/*; do
        if [[ -f "$file" ]]; then
          filename=$(basename "$file")

          # 如果 shared-lib 下没有才复制
          test -f "$dest_shared/$filename" || cp -f "$file" "$dest_shared/"

          # 写入 classpath 文件
          echo "$filename" >> "$classpath_file"
        fi
      done
    fi
  done
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
  # compile dds-backup-agent-driver
  cd $path/lib/src/dds-backup-driver
  chmod u+x compile.sh && bash compile.sh --mode package
  cp "$(ls -t driver/target/dds-backup-driver-*-jar-with-dependencies.jar | head -n 1)" \
     $path/lib/dds-backup-driver-1.4.2.jar

  cd $path/src/server

  # check alert config file
  python $path/dev/script/check_alert_config_files.py

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

  jars=`find $path/src/server -name sac*.jar -not -path "*/sac-common/*" -not -path "*/shared-lib/*"`
  cd $path
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
    fi
  done


  process_shared_libs "${sac_server_names[@]}" server

  # java
  cp -r $JDK_X86_64_INSTALL_DIR/jre $SAC_BUILD_PATH/sac/lib/java/x86_64
  cp -r $JDK_AARCH64_INSTALL_DIR/jre $SAC_BUILD_PATH/sac/lib/java/aarch64

  # license
  cp -r $path/licenses $SAC_BUILD_PATH/sac

  # tools
  # compile sac-deploy-tool
  cp -f $path/src/tools/sac-deploy-tool/target/sac-deploy-tool-exec.jar $SAC_BUILD_PATH/sac/tools/deployment/sac-deploy-tool.jar

  # compile sdb-ssh-tool
  cp -f $path/src/tools/sdb-ssh-tool/target/sdb-ssh-tool-exec.jar $SAC_BUILD_PATH/sac/tools/ssh/sdb-ssh-tool.jar

  # compile sac-upgrade-tool
  cp -f $path/src/tools/sac-upgrade-tool/target/sac-upgrade-tool-exec.jar $SAC_BUILD_PATH/sac/tools/upgrade/sac-upgrade-tool.jar

  tool_names=("sac-deploy-tool" "sdb-ssh-tool" "sac-upgrade-tool")
  process_shared_libs "${tool_names[@]}" tools

  # compile sdb-dds-cc_<version>.tar.gz 解压到 tools/deployment/sdb-dds-cc/sdb-dds-cc
  tar --no-same-owner -xzf "$path/tools/dds-cc/sdb-dds-cc_"*.tar.gz -C "$SAC_BUILD_PATH/sac/tools/deployment/sdb-dds-cc" --strip-components=1

  # compile m2s_v2.0.0.tar.gz 解压到 tools/maintain/m2s
  tar --no-same-owner -xzf "$path/tools/m2s/m2s_"*.tar.gz -C "$SAC_BUILD_PATH/sac/tools/maintain/m2s" --strip-components=1

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
  local tmpBackupAgentFile="${DOWNLOAD_PATH}/dds-backup-agent_1.4.2.tar.gz"
  mkdir -p $DOWNLOAD_PATH
  wget -nc -O $tmpBackupAgentFile "${DDS_BACKUP_AGENT_URL}" > /dev/null 2>&1
  echo "INFO: 'dds_backup_agent' download complete."

  tar --no-same-owner -zxvf $tmpBackupAgentFile -C $SAC_BUILD_PATH/sac/agent
  mv $SAC_BUILD_PATH/sac/agent/dds-backup-agent_* $SAC_BUILD_PATH/sac/agent/dds-backup-agent
}

# compile frontend
function compile_frontend()
{
  cd $path/src/web
  chmod u+x $path/src/web/node_modules/.bin/*
  chmod u+x $path/src/web/node_modules/@esbuild/linux-x64/bin/*
  chmod u+x $path/src/web/node_modules/@esbuild/linux-arm64/bin/*
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
  if [[ $scope =~ "frontend" ]]; then
    check_frontend
  elif [[ $scope =~ "backend" ]]; then
    check_backend
  else
    check
  fi
  
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
JDK_X86_64_INSTALL_DIR=$path/thirdparty/java/x86_64
JDK_AARCH64_INSTALL_DIR=$path/thirdparty/java/aarch64

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

# Ensure DOWNLOAD_PATH exists and set permissions
if [[ ! -d "$TMP_PATH" ]]; then
  mkdir -p "$TMP_PATH"
  chmod 777 "$TMP_PATH"
elif [[ $EUID -eq 0 ]]; then
  # If directory exists and current user is root, update permissions
  chmod 777 "$TMP_PATH"
fi

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
