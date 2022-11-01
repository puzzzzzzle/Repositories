# myrepos 批量仓库管理

## 工具地址
1. http://myrepos.branchable.com/
1. git://myrepos.branchable.com/
##  eg:
1. mr co 克隆所有
2. mr up
3. mr status
4. 

## 批量注册
1. `ls |xargs -I {} sh -c  'cd {} && pwd && mr reg  && cd -'`