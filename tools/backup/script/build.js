/*
 * port: database port
 * database: dump database name
 * dumpPath: mongodump path
 * outputPath: dump path
 * username: database username
 * password: database password
 * authenticationDatabase: auth database name
 * scriptPath: output dump.sh path
 */

let isSacDb = false;
let outputCmd = '#!/bin/bash\n\n';
const sysRegex = /^sac_system/;
const backupRegex = /^backup_control/;
const ignoreList = ['backup_control.Log']

// buildCmd 方法里用到反引号 ` 包裹命令，因此如果变量里有反引号 ` 要先进行转义
if (username.length > 0 && password.length > 0) {
  username = username.replace(/`/g, '\\`');
  password = password.replace(/`/g, '\\`');
}

function buildCmd (name, type) {
   outputCmd = `${outputCmd}result=\`${dumpPath} --port=${port} --db=${database} --collection=${name}`
   
   if (username.length > 0 && password.length > 0) {
      outputCmd = `${outputCmd} -u='${username}' -p='${password}' --authenticationDatabase=${authenticationDatabase}`
   }

   if ((!sysRegex.test(name) && !backupRegex.test(name)) || type === 'timeseries' ||
       ignoreList.includes(name)) {
      outputCmd = `${outputCmd} -q='{"timestamp":0}'`;
   }
   
   outputCmd = `${outputCmd} --out=${outputPath} 2>&1\``;
   outputCmd = `${outputCmd}\nrc=$?\nif [ "$rc" != "0" ]; then\n   if [[ "$result" == *"only processes queries on metadata fields for timeseries collections"* ]]; then\n      rc=0\n   elif [[ "$result" == *"could not determine the metaField for"* ]]; then\n      rc=0\n   else\n      echo "$result"\n      exit 1\n   fi\nelse\n   rc=0\nfi\n`
}

const cls = db.getSiblingDB(database).getCollectionInfos({name:{$not:{$regex:"^system\\."}}});
for (let i in cls) {
   const clInfo = cls[i];
   const name = clInfo.name;
   const type = clInfo.type;
   if (type === 'collection' || type === 'timeseries') {
      if (sysRegex.test(name)) {
         isSacDb = true;
         break;
      }
   }
}

if (isSacDb) {
   for (let i in cls) {
      const clInfo = cls[i];
      const name = clInfo.name;
      const type = clInfo.type;
      if (type === 'collection' || type === 'timeseries') {
         buildCmd(name, type);
      }
   }
   fs.writeFileSync(scriptPath, outputCmd);
} else {
   print("Error: this is not the SAC database.");
   outputCmd = '#!/bin/bash\n\nexit 1';
   fs.writeFileSync(scriptPath, outputCmd);
}



