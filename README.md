# SAC
SAC is a distributed enterprise admin center based on the Spring Cloud micro-services framework.

# 项目目录结构
```
|--agent            # agent 配置文件、运行 jar 包、日志文件目录
|--bin              # 控制脚本目录
|--conf             # SAC 服务配置文件
|--README.md        # SAC 说明文档
|--VERSION.info     # SAC 版本信息
|--build.sh         # 编译打包脚本
```

# 编译打包

## 环境要求
|  软件环境   | 版本       |
|  ----     | ----       |
| jdk       | 1.8及以上   |
| maven     | 3.8.2及以上 |
| node.js   | 14.0及以上  |
| python    | 2.7及以上  |

## 编译打包
```shell
# 进入项目源码根目录，编译、打包项目
./build.sh -p
```
编译打包之后的产物在源码根目录/build/sac-${sac_version}-release.tar.gz
> 注：可以执行 ./build.sh -h 查看命令支持的更多参数
## 
编译打包后产生的目录结构：
```
|--agent         # agent 配置文件、运行 jar 包、日志文件目录
|--bin           # 控制脚本目录
|--build         # 打包产物
|--conf          # SAC 服务配置文件
|--lib           # SAC 服务运行 jar 包
|--logs          # SAC 服务日志文件
|--web           # SAC 前端页面打包目录
|--VERSION       # SAC 版本信息
```
