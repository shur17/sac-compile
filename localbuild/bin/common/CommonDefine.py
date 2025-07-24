#!/usr/bin/python
# coding=utf-8
import os

# dir path
REMOTE_WORK_DIR = "/opt/sac-localbuild/"
BASE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
SAC_PRO_DIR = os.path.normpath(os.path.join(BASE_DIR, '..'))
WORK_DIR = os.path.normpath(os.path.join(BASE_DIR, 'workdir'))
TOOLS_DIR = os.path.normpath(os.path.join(BASE_DIR, 'tools'))
BIN_DIR = os.path.normpath(os.path.join(BASE_DIR, 'bin'))
CONF_DIR = os.path.normpath(os.path.join(BASE_DIR, 'conf'))
PACKAGE_DIR = os.path.normpath(os.path.join(BASE_DIR, 'package'))
TEMPLATE_DIR = os.path.normpath(os.path.join(BASE_DIR, 'template'))
DISINFO_DIR = os.path.normpath(os.path.join(WORK_DIR, 'dsinfo'))

TESTCASE_DIR = os.path.normpath(os.path.join(BASE_DIR, '..', '..', 'sac-auto-testcase'))

SDB_COLLECT_STRATEGY_PATH = os.path.normpath(os.path.join(TEMPLATE_DIR, 'default-collect-strategy.yml'))
DDS_COLLECT_STRATEGY_PATH = os.path.normpath(os.path.join(TEMPLATE_DIR, 'default-dds-collect-strategy.yml'))

# section
SECTION_SAC_DB = "sac_database.dds"
SECTION_BUSINESS_DB = "business_database"
SECTION_BUSINESS_DB_SDB = SECTION_BUSINESS_DB + ".sequoiadb"
SECTION_BUSINESS_DB_DDS = SECTION_BUSINESS_DB + ".dds"
SECTION_BUSINESS_DB_ELF = "elf"
SECTION_BUSINESS_SAC = "sac"

SUB_SECTION_MYSQL = "instances.mysql"
SUB_SECTION_MARIADB = "instances.mariadb"

# dsinfo file
DSINFO_SAC_DB = os.path.normpath(os.path.join(DISINFO_DIR, 'sac_database_dds.yml'))
DSINFO_BUSINESS_DB_SDB = os.path.normpath(os.path.join(DISINFO_DIR, 'business_database_sdb.yml'))
DSINFO_BUSINESS_DB_MYSQL = os.path.normpath(os.path.join(DISINFO_DIR, 'business_database_mysql.yml'))
DSINFO_BUSINESS_DB_MARIADB = os.path.normpath(os.path.join(DISINFO_DIR, 'business_database_mariadb.yml'))
DSINFO_BUSINESS_DB_DDS = os.path.normpath(os.path.join(DISINFO_DIR, 'business_database_dds.yml'))
DSINFO_BUSINESS_DB_ELF = os.path.normpath(os.path.join(DISINFO_DIR, 'business_database_elf.yml'))

SAC_INFO = os.path.normpath(os.path.join(WORK_DIR, 'sac.yml'))
