#!/bin/bash

#   exit code list:
#   0     successful termination
#   1     unsuccessful termination
#   2     module does not exist
#   64    command line usage error


dir_name=`dirname $0`

if [[ ${dir_name:0:1} != "/" ]]; then
  SAC_PATH=$(pwd)/$dir_name
else
  SAC_PATH=$dir_name
fi

SERVER_REPORT_PATH=$SAC_PATH
SERVER_LOG_PATH=$SAC_PATH

SERVER_TESTCASES_DIR=$SAC_PATH/testcases/server/server-testcases
SERVER_TARGET_DIR=$SERVER_TESTCASES_DIR/target
SERVER_TEST_PATH=$SERVER_TESTCASES_DIR
SERVER_TEST_DIR=$SERVER_TEST_PATH/test_dir

SERVER_TEST_TOOL_DIR=$SAC_PATH/testcases/server/sac-test-tool

SERVER_CLEAN_NEED=false
SERVER_COMPILE_NEED=false

WEB_TEST_PATH=$SAC_PATH/testcases/web/Cypress
WEB_REPORT_PATH=$WEB_TEST_PATH/mochawesome-report


# sac project root directory
SAC_SERVER_PATH=$SAC_PATH/src/server

SAC_ALL_MODULE=(
  "sac-registration-center"
  "sac-gateway"
  "sac-user-center"
  "sac-task-manager"
  "sac-common-rpc"
  "sac-common-cmd"
  "sac-common-util"
  "sac-common-define"
  "sac-common-database"
  "sac-common-broadcast"
  "sac-monitor"
  "sac-audit-client"
  "sac-deployment"
  "sac-config"
  "sac-agent-collector"
  "sac-collector"
  "sac-alert"
  "sac-maintainer"
  "sac-deploy-tool"
  "sac-upgrade-tool"
  "sdb-ssh-tool"
  "elf-deploy-tool"
  )

declare -A SAC_MODULE_DICT
SAC_MODULE_DICT["sac-agent-collector"]="sac-agent/sac-agent-collector"
SAC_MODULE_DICT["sac-audit-client"]="sac-audit/sac-audit-client"
SAC_MODULE_DICT["sac-common-broadcast"]="sac-common/broadcast"
SAC_MODULE_DICT["sac-common-database"]="sac-common/database"
SAC_MODULE_DICT["sac-common-define"]="sac-common/define"
SAC_MODULE_DICT["sac-common-rpc"]="sac-common/rpc"
SAC_MODULE_DICT["sac-common-cmd"]="sac-common/cmd"
SAC_MODULE_DICT["sac-common-util"]="sac-common/util"
SAC_MODULE_DICT["sac-deploy-tool"]="../tools/sac-deploy-tool"
SAC_MODULE_DICT["sac-upgrade-tool"]="../tools/sac-upgrade-tool"
SAC_MODULE_DICT["sdb-ssh-tool"]="../tools/sdb-ssh-tool"
SAC_MODULE_DICT["elf-deploy-tool"]="../tools/elf-deploy-tool"

function help() {
  echo "runtest.sh is a tool for testing SAC."
  echo ""
  echo "Usage:  runtest.sh unit [-m test-module] [-q quiet] [--testcases]"
  echo "        runtest.sh integration [-m test-module] [-q quiet] [--testcases]"
  echo "        runtest.sh system [-t server-testng-conf] [-e server-environment-params] [-p server-package] [-c server-class] [-r server-report-path] [-l server-log-path]"
  echo "        runtest.sh web [--web-url] [--web-spec]"
  echo ""
  echo "Options: -h, --help                           output help message, then exit"
  echo "         -t, --server-testng-conf             the location of the testng-conf"
  echo "         -e, --server-environment-params      the parameters used to build the test environment, use \";\" to separate"
  echo "         -p, --server-package                 the full name of packages to test, use \";\" to separate"
  echo "         -c, --server-class                   the full name of classes to test, use \";\" to separate"
  echo "         -r, --server-report-path             the path of the reports, the default path is the test-path"
  echo "         -l, --server-log-path                the path of the logs, the default path is the test-path"
  echo "         -q, --quiet                          quiet output, only show errors"
  echo "         -m, --test-module                    the name of the module to be tested"
  echo "         --testcases                          the name of the class or method to be tested, use \",\" to separate, e.g. \"TestClass1,TestClass2#testMethod\""
  echo ""
  # the parameters of web test
  echo "         --web-url                            the url of the website to test"
  echo "         --web-spec                           the specified files or directories to test, use \",\" to separate"
  echo ""
  echo "Optional Module Name List:"
  for module_name in ${SAC_ALL_MODULE[@]}
  do
    echo "  $module_name"
  done
}

function jdk_env_check() {
  echo "INFO: Starting check jdk environment ..."
  # check whether the JDK has been installed
  if [[ ! `command -v java` ]]; then
    echo "ERROR: JDK not installed detected."
    exit 1
  fi
  echo "INFO: Success to check jdk environment"
}

function maven_env_check() {
  echo "INFO: Starting check maven environment ..."
  # check whether the Maven has been installed
  if [[ ! `command -v mvn` ]]; then
    echo "ERROR: Maven not installed detected."
    exit 1
  fi
  echo "INFO: Success to check maven environment"
}

function server_environment_check() {
  jdk_env_check
  maven_env_check
}

function web_environment_check() {
  if [[ ! `command -v npm` ]]; then
    echo "ERROR: Npx not installed detected."
    exit 1
  fi
  if [[ ! `command -v npx` ]]; then
    echo "ERROR: Npx not installed detected."
    exit 1
  fi
  echo "Success: Success to check web test environment"
}

function package_sac_test_tool() {
  cd $SERVER_TEST_TOOL_DIR
  mvn clean
  mvn package
  local ret=$?
  if [[ $ret != 0 ]]; then
    echo "ERROR: Failed to package test-tool"
    exit $ret
  fi
  test -d $SERVER_TESTCASES_DIR/lib || mkdir $SERVER_TESTCASES_DIR/lib

  mv $SERVER_TEST_TOOL_DIR/target/sac-test-tool-1.0-SNAPSHOT.jar $SERVER_TESTCASES_DIR/lib

}

function system_test_clean() {
  server_environment_check
  cd $SERVER_TESTCASES_DIR
  mvn clean
  test -d $SEVER_TARGET_DIR && rm -rf $SERVER_TARGET_DIR
  test -d $SERVER_TEST_DIR && rm -rf $SERVER_TEST_DIR
}

function system_test_compile() {
  server_environment_check
  package_sac_test_tool
  cd $SERVER_TESTCASES_DIR
  mvn install:install-file -Dfile=$SERVER_TESTCASES_DIR/lib/sac-test-tool-1.0-SNAPSHOT.jar -DgroupId=com.sequoiadb \
  -DartifactId=sac-test-tool -Dversion=1.0-SNAPSHOT -Dpackaging=jar
  mvn -DskipTests assembly:assembly
  test -d $SERVER_TEST_DIR && rm -rf $SERVER_TEST_DIR
  mkdir $SERVER_TEST_DIR
  cp -r $SERVER_TARGET_DIR/sac-test-jar-with-dependencies.jar $SERVER_TEST_DIR/sac-test.jar
  cp -r $SERVER_TARGET_DIR/sac-test/* $SERVER_TEST_DIR
}

function run_system_test() {
  echo "INFO: Start to run system test ..."
  test -d $SERVER_TEST_DIR
  local result=$?
  if [[ $result != 0 ]]; then
    echo "ERROR: Did not find the test_dir, please compile first"
    exit 1
  fi
  test -z $TESTNG_CONF || args="$args -t $TESTNG_CONF"
  test -z $ENVIRONMENT_PARAMS || args="$args -e $ENVIRONMENT_PARAMS"
  test -z $PACKAGE_NAME || args="$args -p $PACKAGE_NAME"
  test -z $CLASS_NAME || args="$args -c $CLASS_NAME"
  args="$args -r $SERVER_REPORT_PATH"
  java -Xms1024m -Xmx1024m -Dtest.dir=$SERVER_TEST_DIR -Dlog.dir=$SERVER_LOG_PATH -jar $SERVER_TEST_DIR/sac-test.jar $args
  echo "INFO: Finish running test"
}

function install_sac_pom() {
  echo "INFO: Installing sac pom to local maven repository ..."
  cd $SAC_SERVER_PATH
  mvn clean install -D'skipTests'=true -N -q
  echo "INFO: Installed sac pom to local maven repository"
}

function sel_module_and_testcase() {
  if [ -n "$TEST_MODULE" ]; then
    # specify module
    if [[ " ${SAC_ALL_MODULE[*]} " != *" $TEST_MODULE "* ]]; then
      echo "ERROR: '$TEST_MODULE' is an illegal module name"
      echo "INFO: Try './runtest.sh --help' to view all module names"
      exit 2
    fi
    model=${SAC_MODULE_DICT["$TEST_MODULE"]:-$TEST_MODULE}
    TEST_MODULE_OPTS="-pl $model"

    echo "INFO: Installing sac-common to local maven repository ..."
    cd $SAC_SERVER_PATH/sac-common
    mvn clean install -q -D"maven.test.redirectTestOutputToFile"=true -D"maven.test.skip"=true
    echo "INFO: Installed sac-common to local maven repository"

    if [[ "$TEST_MODULE" == "sac-deployment" ]]; then
    echo "INFO: Installing sac-audit to local maven repository ..."
      cd $SAC_SERVER_PATH/sac-audit
      mvn clean install -q -D"maven.test.redirectTestOutputToFile"=true -D"maven.test.skip"=true
    echo "INFO: Installed sac-audit to local maven repository"
    fi
  fi

  # specify test case
  if [ -n "$TESTCASES" ]; then
    if [ -z "$TEST_MODULE" ]; then
      echo "ERROR: No test module was specified"
      exit 64
    fi
    TESTNG_TESTCASES_OPTS="-Dtest=$TESTCASES"
  fi
}

function echo_report_path() {
  echo "INFO: SAC test report directory: $HOME/sac-test"
}

function unit_test() {
  maven_env_check
  install_sac_pom
  sel_module_and_testcase

  cd $SAC_SERVER_PATH

  echo "INFO: Start to run the unit test cases ..."
  mvn clean test $TEST_MODULE_OPTS $TESTNG_TESTCASES_OPTS $QUIET_OPTS -D"maven.test.failure.ignore"=true -D"sac.protocol"=http
  echo "INFO: Finish running the unit test case"

  echo_report_path
}

function integration_test() {
  maven_env_check
  install_sac_pom
  sel_module_and_testcase

  cd $SAC_SERVER_PATH

  echo "INFO: Start to run the unit test cases ..."
  mvn clean test $TEST_MODULE_OPTS $TESTNG_TESTCASES_OPTS $QUIET_OPTS -Pint -D"maven.test.failure.ignore"=true -D"sac.protocol"=http
  echo "INFO: Finish running the integration test case"

  echo_report_path
}

function system_test() {
  echo "INFO: Start to clean environment ..."
  system_test_clean
  echo "INFO: Finish cleaning environment"

  echo "INFO: Start to compile ..."
  system_test_compile
  echo "INFO: Finish compiling"

  run_system_test
}

function web_test() {
  web_environment_check

  test -d $WEB_TEST_PATH
  local result=$?
  if [[ $result != 0 ]];then
    echo "ERROR: Did not find the web_test_dir, please check whether the directory exist"
    exit 1
  fi
  chmod -R 777 $WEB_TEST_PATH
  cd $WEB_TEST_PATH
  test -d $WEB_REPORT_PATH && rm -rf $WEB_REPORT_PATH
  test -z $WEB_URL || params="$params --config baseUrl=\"$WEB_URL\""
  if [ $WEB_TESTCASES ]; then
    npx cypress run $params --spec $WEB_TESTCASES
  else
    npx cypress run $params
  fi
}


ARGS=`getopt -o hqe:p:c:r:l:m:C:n: --long help,quiet,server-testng-conf:,server-environment-params:,\
server-package:,server-class:,server-report-directory:,server-log-directory:,web-url:,web-spec:,test-module:,testcases: -- "$@"`
ret=$?
test $ret -ne 0 && exit $ret

eval set -- "${ARGS}"

while true
do
  case "$1" in
    -p | --server-package)                  PACKAGE_NAME=$2
                                            shift 2
                                            ;;
    -t | --server-testng-conf)              TESTNG_CONF=$2
                                            shift 2
                                            ;;
    -e | --server-environment-params)       ENVIRONMENT_PARAMS=$2
                                            shift 2
                                            ;;
    -c | --server-class)                    CLASS_NAME=$2
                                            shift 2
                                            ;;
    -r | --server-report-directory)         SERVER_REPORT_PATH=$2
                                            shift 2
                                            ;;
    -l | --server-log-directory)            SERVER_LOG_PATH=$2
                                            shift 2
                                            ;;
    -m | --test-module)                     TEST_MODULE=$2
                                            shift 2
                                            ;;
    --testcases)                            TESTCASES=$2
                                            shift 2
                                            ;;
    --web-url)                              WEB_URL=$2
                                            shift 2
                                            ;;
    --web-spec)                             WEB_TESTCASES=$2
                                            shift 2
                                            ;;
    -q | --quiet )                          QUIET_OPTS="-q -D\"maven.test.redirectTestOutputToFile\"=true"
                                            shift 1
                                            ;;
    -h | --help )                           help
                                            exit 0
                                            ;;
    --)                                     shift
                                            break
                                            ;;
    *)                                      echo "ERROR: Internal error!"
                                            echo "INFO: Try './runtest.sh --help' for more information."
                                            exit 64
                                            ;;
  esac
done

case $1 in
  system)                                   mode=$1
                                            shift 1
                                            ;;
  integration)                              mode=$1
                                            shift 1
                                            ;;
  unit)                                     mode=$1
                                            shift 1
                                            ;;
  web)                                      mode=$1
                                            shift 1
                                            ;;
  *)                                        echo "ERROR: Internal error!"
                                            echo "INFO: Try './runtest.sh --help' for more information."
                                            exit 64
                                            ;;
esac

if [ "$*" != "" ]; then
  echo "ERROR: too many arguments: $*" >&2
  echo "INFO: Try './runtest.sh --help' for more information."
  exit 64
fi

case $mode in
  unit)                                     unit_test
                                            ;;
  integration)                              integration_test
                                            ;;
  system)                                   system_test
                                            ;;
  web)                                      web_test
                                            ;;
esac

exit 0

