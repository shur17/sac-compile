#!/bin/bash

#   exit code list:
#   77    permission denied

# check user
# if neither root nor sac user, exit with PERMISSION_DENIED
function check_user()
{
  SAC_USER=`ls -l $AGENT_PATH/tools/on-OOM/on_out_of_memory.sh | awk '{print $3}'`

  local cur_user=`whoami`
  if [ "$cur_user" != "$SAC_USER" -a "$cur_user" != "root" ]
  then
    echo "ERROR: './on_out_of_memory.sh' requires [$SAC_USER] permission" >&2
    exit 77
  fi
}

# if root: change to sac user to execute command
# if sac user: execute command
function exec_cmd()
{
   local cmd="$1"
   local cur_user=`whoami`

   if [ $cur_user == "root" ]
   then
      su - $SAC_USER -c "${cmd}" > /dev/null 2>&1
      return $?
   else
      eval "${cmd}" > /dev/null 2>&1
      return $?
   fi
}

function on_out_of_memory()
{
  # rename sac-agent-collector.hprof to sac-agent-collector-latest.hprof
  local hprof_file=$AGENT_PATH/conf/sac-agent-collector.hprof
  local latest_hprof_file=$AGENT_PATH/conf/sac-agent-collector-latest.hprof
  exec_cmd "test -f $hprof_file && mv -f $hprof_file $latest_hprof_file"
}

#get path
function get_path()
{
  dir_name=`dirname $0`
  if [[ ${dir_name:0:1} != "/" ]]; then
    AGENT_OOM_PATH=$(pwd)/$dir_name
  else
    AGENT_OOM_PATH=$dir_name
  fi

  cd $AGENT_OOM_PATH/../../ && AGENT_PATH=`pwd`
}


get_path

check_user

on_out_of_memory