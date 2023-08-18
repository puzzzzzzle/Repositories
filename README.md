# repm 批量仓库管理
- Python3.5+ 没有额外依赖
- 具体说明使用-h/--help查看
```
python .\repm.py -h
usage: repm.py [-h] {cmd,checkout,clone,status,update,test} ...

multi git repositories mng

positional arguments:
  {cmd,checkout,clone,status,update,test}
                        supported cmds:
    cmd                 run any cmd in each repository's dir
    checkout            recursive update repositories in config
    clone               clone repositories in config
    status              recursive update repositories in config
    update              update repositories in config
    test                test cmd args, just print input

options:
  -h, --help            show this help message and exit
```
```
python .\repm.py update -h
usage: repm.py update [-h] [--ignore_sub]

update repositories in config

options:
  -h, --help    show this help message and exit
  --ignore_sub  ignore update sub module, default is not set, add flags to set true (default: False)
```