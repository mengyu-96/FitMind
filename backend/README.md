# FitMind 后端开发环境

当前交付：独立Python环境、依赖定义和锁定清单、环境冒烟检查。应用API、数据库迁移和真实模型接入尚未实现。

## 环境位置

- 本机Conda：`D:\anaconda\Scripts\conda.exe`
- 项目环境：`D:\work\FitMind\.conda\fitmind-backend`
- Python基线：3.12；不向base环境安装项目依赖。
- 包缓存位于项目`.cache`，环境与缓存已加入`.gitignore`。

采用Python3.12以保持后端、数据库驱动与AI编排依赖的统一兼容基线。Conda管理Python运行时，pip管理应用依赖，避免两套包管理器反复覆盖同一应用包。

## 使用现有环境

在项目根目录PowerShell执行，无需先配置`conda init`：

```powershell
& '.\.conda\fitmind-backend\python.exe' --version
& '.\.conda\fitmind-backend\python.exe' -m pip check
& '.\.conda\fitmind-backend\python.exe' '.\backend\scripts\verify_environment.py'
```

若终端已配置Conda shell hook，可使用`conda activate D:\work\FitMind\.conda\fitmind-backend`。IDE选择该目录下的python.exe。

## 重建环境

`environment.yml`定义跨机器可解析的运行时规格。`conda-win-64.explicit.txt`为当前Windows精确运行时导出，不能直接用于Linux。`requirements.in`定义直接依赖及兼容范围，`requirements.lock.txt`固定本轮验证后的全部pip包版本。

```powershell
$env:CONDA_PKGS_DIRS = 'D:\work\FitMind\.cache\conda-pkgs'
& 'D:\anaconda\Scripts\conda.exe' create --prefix 'D:\work\FitMind\.conda\fitmind-backend' --file '.\backend\environment.yml' --yes
& '.\.conda\fitmind-backend\python.exe' -m pip install -r '.\backend\requirements.lock.txt'
& '.\.conda\fitmind-backend\python.exe' -m pip check
& '.\.conda\fitmind-backend\python.exe' '.\backend\scripts\verify_environment.py'
```

以上create命令用于尚不存在的环境；现有环境不重复创建或覆盖。Windows精确重建时可将`--file`换为`conda-win-64.explicit.txt`。pip锁定清单是版本锁定，未包含包hash；Linux生产环境需要在目标平台重新解析、测试并生成独立锁定清单，不直接宣称跨平台完全一致。

## Agent实施基线

使用LangGraph StateGraph编排主教练与专项子图，生产检查点由PostgreSQL维护；工具网关、领域事务、用户级租约、预算和确认票据由应用负责，见[Agent优化设计](../docs/19-Agent架构优化设计.md)。

`verify_environment.py`验证FastAPI请求、Pydantic校验、LangGraph中断/恢复及不同thread的状态分离，并导入数据库/向量/Redis模块。它使用内存检查点和本地测试客户端，不调用外部模型，不证明数据库连接、真实鉴权、跨进程恢复或并发事务已完成。

实际验证结果记录在[环境验证记录](../docs/20-本地环境与验证记录.md)。
