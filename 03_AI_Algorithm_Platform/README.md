# 算法平台算法运行容器

## 算法适配

### 算法文件规范

算法开发者需要创建符合以下规范的Python文件：

1. **文件命名**：算法文件名需与算法名称一致, 扩展名为.py（例如：`image_processing.py`对应算法名称`image_processing`）
2. **函数定义**：必须实现名为`algorithm`的函数, 函数签名如下：

   ```python
   def algorithm(zip_path: Path, **kwargs) -> bytes:
       # 算法逻辑实现
       return zip_bytes  # 返回ZIP格式的字节流
   ```

3. **参数说明**：
   - `zip_path`: 输入文件的临时目录路径（Path对象）
   - `**kwargs`: 动态参数, 根据算法需求定义
   - 返回值：必须是ZIP格式的字节流, 用于封装处理结果

### 算法处理流程

1. 系统接收ZIP格式的输入文件并解压到临时目录
2. 调用算法的`algorithm`函数, 传入临时目录路径和参数
3. 执行算法逻辑
4. 算法处理完成后返回ZIP格式字节流
5. 系统自动清理临时文件

**建议参照模板文件**

## API文档

### 算法管理API

#### 创建算法

- **URL**: `/create`
- **方法**: POST
- **请求参数**:

  | 参数名       | 类型     | 描述                  |
  |--------------|----------|-----------------------|
  | file         | File     | 算法Python文件        |
  | algo_name    | FormData | 算法名称              |
  | args         | FormData | 参数定义（JSON格式）  |
  | args_intro   | FormData | 参数说明（JSON格式）  |
  | intro        | FormData | 算法简介              |

- **成功响应**: 200 OK, 返回算法创建成功消息
- **失败响应**: 400 算法已存在, 500 服务器错误
- args 示例 `{"参数名":默认值,...}`
- args_intro 示例 `{"参数名":"参数说明",...}`

#### 删除算法

- **URL**: `/delete`
- **方法**: POST
- **请求参数**:

  | 参数名    | 类型     | 描述       |
  |-----------|----------|------------|
  | algo_name | FormData | 算法名称   |

- **成功响应**: 200 OK, 返回算法删除成功消息
- **失败响应**: 404 算法不存在, 500 服务器错误

#### 更新算法

- **URL**: `/update`
- **方法**: POST
- **请求参数**: 同创建算法
- **成功响应**: 200 OK, 返回算法更新成功消息
- **失败响应**: 404 算法不存在, 500 服务器错误

#### 列出所有算法

- **URL**: `/list`
- **方法**: GET
- **响应**: 200 OK, 返回JSON格式的算法列表

### 模型管理API

#### 创建模型

- **URL**: `/create_model`
- **方法**: POST
- **请求参数**:

  | 参数名    | 类型     | 描述       |
  |-----------|----------|------------|
  | file      | File     | 模型文件   |
  | model_name| FormData | 模型名称   |
  | intro     | FormData | 模型简介   |

- **成功响应**: 200 OK, 返回模型创建成功消息
- **失败响应**: 400 模型已存在, 500 服务器错误

#### 删除模型

- **URL**: `/delete_model`
- **方法**: POST
- **请求参数**:

  | 参数名    | 类型     | 描述       |
  |-----------|----------|------------|
  | model_name| FormData | 模型名称   |

- **成功响应**: 200 OK, 返回模型删除成功消息
- **失败响应**: 404 模型不存在, 500 服务器错误

#### 列出所有模型

- **URL**: `/model_list`
- **方法**: GET
- **响应**: 200 OK, 返回JSON格式的模型列表 (包括文件相对路径, 便于算法开发者使用)

### 任务执行API

#### 处理任务

- **URL**: `/process`
- **方法**: POST
- **请求参数**:

  | 参数名    | 类型     | 描述                          |
  |-----------|----------|-------------------------------|
  | file      | File     | 输入ZIP文件                   |
  | task_id   | FormData | 任务ID                      |
  | algo_name | FormData | 算法名称                      |
  | args_json | FormData | 算法参数（JSON格式字符串）    |

- **成功响应**: 200 OK, 返回处理结果ZIP文件
- **失败响应**: 400 缺少任务ID, 500 处理错误, 504 处理超时
- args_json 示例 `{"参数名":值,...}`

#### 停止任务

- **URL**: `/stop`
- **方法**: POST
- **请求参数**:

  | 参数名   | 类型     | 描述       |
  |----------|----------|------------|
  | task_id  | FormData | 任务ID     |

- **成功响应**: 200 OK, 返回任务停止成功消息
- **失败响应**: 404 任务不存在, 500 服务器错误

#### 获取运行中任务

- **URL**: `/running-tasks`
- **方法**: GET
- **响应**: 200 OK, 返回JSON格式的运行中任务 id 列表, 例如：`{"running_tasks": [1, 2, 3]}`

#### 日志

- **URL**: `/logs`
- **方法**: GET
- **响应**: 200 OK, 返回完整的日志信息
- **注意**: 用于获取任务执行过程中的详细日志信息, 可用于调试和监控

## 部署

### 环境准备

1. 克隆项目到本地
2. 将算法所需依赖添加到`additional_requirements.txt`
3. （可选）如需使用GPU, 修改Dockerfile并指定GPU版本依赖

### 构建镜像

```bash
docker build -t algorithm_container .

docker save -o algorithm_container.tar algorithm_container

scp algorithm_container.tar user@server:/path/to/destination

docker load -i algorithm_container.tar
```

### 运行容器

```bash
# 基础运行（CPU）
docker run -d -p xxxx:8000 -v $(pwd)/model:/app/model  -v $(pwd)/model_config.yaml:/app/model_config.yaml  -v $(pwd)/config.yaml:/app/config.yaml  -v $(pwd)/algo:/app/algo  -v $(pwd)/app.log:/app/app.log --name algorithm_container algorithm_container

# 使用GPU运行
docker run -d --gpus all -p xxxx:8000 -v $(pwd)/model:/app/model  -v $(pwd)/model_config.yaml:/app/model_config.yaml  -v $(pwd)/config.yaml:/app/config.yaml  -v $(pwd)/algo:/app/algo  -v $(pwd)/app.log:/app/app.log --name algorithm_container algorithm_container
```
