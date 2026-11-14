# 交付说明：冒号时间段（YAML 1.1 sexagesimal）被静默转为数值的处置

## 1. 现象与根因定位

### 1.1 现象复现

配置中的时间段写法在默认加载口径下被解析为六十进制整数/浮点数：

| 配置原文 | 默认 `safe_load` 产物 | 类型 |
| --- | --- | --- |
| `1:30` | `90` | `int`（1×60+30） |
| `8:00` | `480` | `int`（8×60） |
| `190:20:30` | `685230` | `int`（190×3600+20×60+30） |
| `12:30:59` | `45059` | `int` |
| `190:20:30.15` | `685230.15` | `float` |

与告警中“一小时三十分变成 90、八小时变成 480”逐字吻合。下游按字符串取值的对账逻辑因此全部失配。

### 1.2 解析层根因（resolver + constructor 两层联动）

1. **隐式解析层 `lib/yaml/resolver.py`**：默认 `Resolver` 注册的 `tag:yaml.org,2002:int`
   正则含 sexagesimal 分支 `[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+`；`tag:yaml.org,2002:float`
   正则含 `[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*`。因此 `1:30` 这类无显式标签的
   plain scalar 在 resolve 阶段即被打上 int/float 标签，而非默认的 str 标签。
2. **构造层 `lib/yaml/constructor.py`**：`SafeConstructor.construct_yaml_int`
   （`elif ':' in value:` 分支）与 `construct_yaml_float` 对冒号分段按 **base 60 加权求和**
   （末段 ×1、向前逐段 ×60），把标量文本构造成 Python 数值。

两层均为既有实现，本次未改动其中任何既有分支。

## 2. 该行为与规范的关系结论

**结论：默认行为符合 PyYAML 一贯实现的 YAML 1.1 规范，不是实现缺陷；但与 YAML 1.2 规范冲突。
业务侧期望的“时间段保持字符串”对应 YAML 1.2 Core Schema 口径。**

依据：

1. **YAML 1.1**（https://yaml.org/type/int.html、https://yaml.org/type/float.html）：
   int 的 regular expression 明确包含 `[-+]?[1-9][0-9_]*(:[0-5]?[0-9])+`，float 包含
   `[-+]?[0-9][0-9_]*(:[0-5]?[0-9])+\.[0-9_]*`，即 sexagesimal（base 60）数字是 1.1
   规范内的合法隐式整数/浮点数写法。PyYAML 的 resolver 正则与 constructor 六十进制
   加权逻辑即对该规范的实现。仓库内 `tests/legacy_tests/data/yaml11.schema`
   （如 `'190:20:30': ['int', '685230', '685230']`）、`construct-int.data/.code`、
   `construct-float.data/.code`、`spec-02-19.data` 等测试数据将该产物作为规范期望值锁定。
2. **YAML 1.2**（Core Schema，https://yaml.org/spec/1.2.2/#1032-core-schema）：
   int 解析规则仅保留十进制、`0o` 八进制、`0x` 十六进制；float 不再包含冒号分段。
   sexagesimal 写法在 1.2 下匹配不到任何非 str 的隐式解析规则，按 resolved-equals-plain
   原则回退为字符串。
3. PyYAML 自身定位为 YAML 1.1 实现（`setup.py` 描述 "a complete YAML 1.1 parser"），
   且该解析行为自始存在、被既有测试与下游依赖锁定，属于**规范内既有解析行为**，
   不能在默认口径上直接修改（否则是不兼容变更）。

## 3. 改造内容（不动规范内既有解析行为，显式 opt-in 关闭/替换）

### 3.1 默认口径零变更

- `Resolver` 及其 int/float 正则、`construct_yaml_int`/`construct_yaml_float` 全部保持原样。
- `SafeLoader`/`FullLoader`/`Loader`/`UnsafeLoader` 及 `yaml.safe_load`/`full_load`/
  `unsafe_load`/`yaml.load(...)` 的产物与改造前**逐字一致**（由全量既有 1287 项测试
  原样通过佐证，其中包含锁定 sexagesimal 数值产物的 yaml11.schema 等 legacy 用例）。

### 3.2 新增显式关闭途径（业务侧主动切换后，时间段原样保留为字符串）

`lib/yaml/resolver.py`：

- 新增 `BaseResolver.replace_implicit_resolver(tag, regexp)` 类方法：**原位替换**已注册
  隐式解析器的正则，保持 resolver 在各首字符桶中的既有顺序；对未注册 tag 抛
  `ResolverError`。子类调用时按既有 copy-on-write 惯例复制解析表，不污染父类。
- 新增 `NoSexagesimalResolver(Resolver)`：仅把 int/float 两条正则替换为删除 sexagesimal
  分支后的等价正则，其余 resolver（bool/null/timestamp/merge/…）原样继承。
  冒号标量因此匹配不到 int/float，按 `DEFAULT_SCALAR_TAG` 回退为 `str`，constructor
  不经任何修改即走 `construct_yaml_str` 返回原文。

`lib/yaml/loader.py`：

- 新增三个纯 Python Loader：`SafeLoaderNoSexagesimal`、`FullLoaderNoSexagesimal`、
  `UnsafeLoaderNoSexagesimal`，构造器与对应默认 Loader 相同，仅以
  `NoSexagesimalResolver` 替换 MRO 中的 `Resolver`。
- 注意：libyaml C 扩展（`CSafeLoader` 等）在 C 层完成隐式解析，不受 Python resolver 表
  影响；本能力仅覆盖纯 Python Loader（当前环境无 `_yaml` 扩展，C 系测试自动跳过）。

### 3.3 业务侧使用方式

```python
import yaml

# 方式一：直接使用现成 Loader（推荐）
data = yaml.load(stream, Loader=yaml.SafeLoaderNoSexagesimal)
for doc in yaml.load_all(stream, Loader=yaml.FullLoaderNoSexagesimal):
    ...

# 方式二：在自定义 Loader 上替换/关闭特定隐式解析规则（正则可自定义）
import re
class MyLoader(yaml.SafeLoader):
    pass
MyLoader.replace_implicit_resolver(
    'tag:yaml.org,2002:int',
    re.compile(r'''^(?:[-+]?0b[0-1_]+
                |[-+]?0[0-7_]+
                |[-+]?(?:0|[1-9][0-9_]*)
                |[-+]?0x[0-9a-fA-F_]+)$''', re.X))
# 或直接继承现成的 NoSexagesimalResolver 组装自定义 Loader
from yaml.reader import Reader
from yaml.scanner import Scanner
from yaml.parser import Parser
from yaml.composer import Composer
from yaml.constructor import SafeConstructor
from yaml.resolver import NoSexagesimalResolver
class MyLoader2(Reader, Scanner, Parser, Composer,
                SafeConstructor, NoSexagesimalResolver):
    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        SafeConstructor.__init__(self)
        NoSexagesimalResolver.__init__(self)
```

切换后效果（嵌套结构同样生效）：

```text
period: 1:30            -> {'period': '1:30'}   （str，原样保留）
windows: [1:30, 8:00]   -> {'windows': ['1:30', '8:00']}
1:30: ninety minutes    -> {'1:30': 'ninety minutes'}   （映射键同样保留字符串）
n: 42                   -> {'n': 42}          （普通十进制 int 不受影响）
2020-01-02 03:04:05     -> datetime.datetime(...)（timestamp 不受影响）
```

显式标签优先级不变：`!!str 1:30` 恒为字符串；`!!int 1:30` 即使在新口径下仍按显式标签
构造为 `90`。

## 4. 测试与验证

新增 `tests/test_sexagesimal.py`（69 个用例），对照矩阵覆盖：

- **两种口径**：默认 YAML 1.1 口径（int/float 数值产物、节点 tag 为 int/float）
  vs. NoSexagesimal 口径（原样字符串、节点 tag 为 str），三个 Loader 家族全部参数化；
- **嵌套结构场景**：mapping 套 sequence 套 mapping 的深嵌套文档、sequence of mappings、
  mapping 内嵌 flow sequence、冒号标量作为 mapping key、`load_all` 多文档；
- **非 sexagesimal 类型不回退**：十进制/二进制/十六进制/八进制 int、普通 float、`.inf`/
  `.nan`、bool、null、timestamp、普通字符串在两种口径下产物与类型逐字一致；
- **解析表隔离与顺序**：新 resolver 表是独立副本、默认 `Resolver` 表未被修改、替换前后
  resolver 条目顺序保持、`add_implicit_resolver` 仍保持追加语义、未知 tag 替换抛
  `ResolverError`。

全量结果（Python 3.12.9，纯 Python 实现）：

```text
1356 passed, 1 warning   # 1287 项既有测试 + 69 项新增；warning 为无 libyaml 扩展的既有跳过提示
```

分别以 `sys.path` 指向 `lib/`（源码树）与 `build/lib/`（Makefile test 入口）各执行一次，
结果一致。

## 5. 变更文件清单

| 文件 | 变更 |
| --- | --- |
| `lib/yaml/resolver.py` | 新增 `replace_implicit_resolver`、`NoSexagesimalResolver`；默认 `Resolver` 与既有正则零改动 |
| `lib/yaml/loader.py` | 新增三个 `*LoaderNoSexagesimal`；既有 Loader 零改动 |
| `tests/test_sexagesimal.py` | 新增，两种口径 × 嵌套结构对照测试 |
| `CHANGES` | 记录本次新增能力 |
| `build/lib/yaml/{resolver,loader}.py` | 与 `lib/` 同步（`build/` 未纳入 git 跟踪，仅为本地测试入口） |
