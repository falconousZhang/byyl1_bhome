# PDF 思考题与羁绊说明

> 对应《大作业2：中间代码生成器》PDF 中"部分羁绊"、"说明"、"思考"三节的项目实现情况。

---

## 一、部分羁绊

### 羁绊 1：2.2 赋值语句 + 类型规则（如 8.1）

**PDF 要求**：类型多于一种，变量赋值时需检测类型是否对应，不对应应报错。

**项目实现**：已完整覆盖（语义检查 A）。

类型兼容性由 `types_compatible(declared, assigned)` 函数（`semantic.py:68`）实现结构化深度比较，检查场景包括：

| 场景 | 代码位置 |
|------|---------|
| `let mut x: [i32; 3] = [1, 2];` — 数组大小不符 | `_check_literal_shape()` |
| `let mut x: i32 = [1, 2, 3];` — 根类型不符 | `_visit_let()` 中 type mismatch |
| `x = a + b;` — 赋值 lvalue 与 rhs 类型不符 | `_visit_assign()` |
| `fn foo() -> i32 { return [1,2,3]; }` — return 类型不符 | `visit_stmt` ReturnStmt |
| 函数调用实参类型不符 | `_visit_call()` 检查 N |

```rust
// 触发示例（见 err.8.2.rs / err.9.2.rs）
let mut a: [i32; 3] = [1, 2];       // ERROR: 声明 3 元素，字面量 2 元素
let mut t: (i32, i32) = (1, 2, 3);  // ERROR: 声明 2 元素，字面量 3 元素
```

---

### 羁绊 2：5.2 for 循环 + 8.2 数组（非数组类型不可迭代）

**PDF 要求**：数组是可迭代结构；其他类型被 for 循环访问时应报错。

**项目实现**：已完整覆盖（语义检查 B）。

在 `_visit_for()` (`semantic.py:549`) 中：

```python
iter_type = self._infer(node.iterable)
if iter_type is not None and not isinstance(iter_type, TypeArray):
    self._err(f"Cannot iterate over non-array type {type_str(iter_type)}", ...)
```

两种合法的 for 迭代对象：
1. 数组变量：`for x in arr { ... }`（`arr` 类型必须是 `[T; N]`）
2. 范围表达式：`for i in 0..10 { ... }`（`RangeExpr`，专门处理）

---

### 羁绊 3：2.2 赋值 + 6.1 不可变属性 + 循环（如 5.2）

**PDF 要求**：循环中对不可变变量赋值应报错。

**项目实现**：已完整覆盖（语义检查 C），且不限于循环中——任何位置对不可变变量赋值都会报错。

`_is_mutable_lvalue()` (`semantic.py:240`) 递归判断 lvalue 的可变性，覆盖：

- 简单变量：`a = 1;`（`a` 未声明 `mut`）
- 解引用写：`*r = 1;`（`r` 必须是 `&mut T`）
- 数组元素：`arr[0] = 1;`（`arr` 必须是 `mut`）
- 元组字段：`t.0 = 1;`（`t` 必须是 `mut`）

```rust
// 触发示例（见 err.6.4.rs）
let r: &i32 = &x;
*r = 5;   // ERROR: Cannot assign to immutable expression
```

---

## 二、说明

### 产生式改写与扩展

**PDF 建议**：可对文档中的产生式改写，或扩展 Rust 语法。

**项目实现**：做了以下改写和扩展——

**改写 1：表达式文法分层（消除移进-归约冲突）**

原始文法的问题：将所有算术和比较放在同一层 `expr` 会产生大量 S/R 冲突（运算符优先级无法表达）。

改写为六层分层文法：

```
expr    → cmp
cmp     → add (('=='|'!='|'<'|'>'|'<='|'>=') add)*
add     → mul (('+'|'-') mul)*
mul     → unary (('*'|'/') unary)*
unary   → '-' unary | '&' unary | '&mut' unary | '*' unary | postfix
postfix → postfix '[' expr ']' | postfix '.' NUM | primary
primary → NUM | IDENT | IDENT '(' arg_list ')' | '(' expr ')' | ...
```

每层只与相邻层交互，运算符优先级通过文法结构隐式编码，完全消除了算术/比较运算的 S/R 冲突。

**改写 2：元组字面量与括号表达式的歧义消解**

原始文法 `primary → '(' expr ')'` 和 `primary → '(' expr_list ')'` 对单元素情况存在歧义：  
`(x)` 到底是括号表达式还是单元素元组？

改写方案：引入 `tuple_inner`，要求元组字面量的第一个元素后必须跟逗号：

```
primary    → '(' expr ')'          -- 括号表达式（永远不是元组）
primary    → '(' tuple_inner ')'   -- 元组字面量
tuple_inner → ε                    -- 空元组 ()
tuple_inner → expr ',' tuple_elems -- 至少有一个元素且带尾逗号
```

这样 `(x)` 唯一归约为括号表达式，`(x,)` 唯一归约为单元素元组，无歧义。

**扩展：函数调用（规则 3.5）**

原 PDF 文法未给出 `arg_list` 的完整产生式，项目新增：

```
primary  → IDENT '(' arg_list ')'
arg_list → ε
arg_list → expr
arg_list → expr ',' arg_list
```

---

### LR(1) 无法处理的羁绊（加分项）

**PDF 提示**：存在极个别羁绊会使 LR(1) 无法处理，可分析或改写。

**发现的冲突：悬挂 else（dangling-else）**

文法中 `if` 表达式有两条产生式：

```
if_expr → IF expr block
if_expr → IF expr block ELSE block
```

当 LR(1) 分析器解析完 `IF expr block` 之后，下一个 token 是 `ELSE` 时，面临：
- **归约**：将 `IF expr block` 归约为 `if_expr`（ELSE 属于外层 if）
- **移进**：将 `ELSE` 移进（ELSE 属于当前 if）

这是经典的 S/R 冲突，任何 LR 方法（SLR/LALR/LR(1)）都无法通过单纯改写无歧义 LL 文法来消除，因为这个歧义来自语言本身，而非文法形式。

**能否改写文法消除？**

可以，但代价较大。常见方案是引入"已匹配 if"和"未匹配 if"两类非终结符：

```
matched_if   → IF expr block ELSE matched_if
matched_if   → IF expr block ELSE block
unmatched_if → IF expr block
unmatched_if → IF expr block ELSE unmatched_if
```

这样每个 ELSE 都强制绑定到最近的 IF，文法变为无歧义。但产生式数量翻倍，代码量大幅增加，且需要对所有包含 if 的语句做相同处理，工程成本高。

**项目采用的方案**：保持原文法，**移进优先**（shift wins）。LR(1) 表构造时检测到 S/R 冲突，直接选择移进，等价于"ELSE 绑定到最近的 IF"——与真实 Rust 和大多数语言的语义一致。

在 `parser_lr1.py:609` 中：

```python
# Shift-reduce conflict: prefer shift (resolves dangling-else)
conflicts.append(f"state {sid}: S/R conflict on '{la}' (shift wins over reduce prod {pid})")
```

该冲突在运行时会被打印出来，可通过 `lr1_tables.pkl` 缓存前的控制台输出观察到。

---

## 三、思考

### 思考 1：1.4 形参列表可以识别怎样的语言？

形参列表的产生式（`parser_lr1.py:125`）：

```
param_list → ε
param_list → param
param_list → param COMMA param_list
```

**列表结构本身**是正则语言，对应正则表达式 `(param (, param)*)?`，可用有限自动机识别。

**但 `param` 包含类型注解**（如 `mut x: &mut [i32; 3]`），其中 `type` 产生式有嵌套递归：

```
type → '[' type ';' NUM ']'    -- 数组类型（可嵌套 [[i32;3];5]）
type → '(' type_list ')'       -- 元组类型（可嵌套）
type → '&' type / '&mut' type  -- 引用类型（可嵌套）
```

嵌套结构需要栈计数（匹配括号），正则自动机无法做到——因此 `param_list` 整体是一个**上下文无关语言**（CFL），而非正则语言。

直观类比：`param_list` 的"逗号分隔"部分像正则，但每个 `param` 内部的类型嵌套（`[[[i32;1];2];3]`）相当于括号匹配，需要 PDA（下推自动机）来识别，所以整体是 CFL。

---

### 思考 2：9.1 元组 比 8.1 数组 多了几条产生式？为什么？

**统计（基于 `parser_lr1.py`）**：

| 功能 | 数组（8.x）| 元组（9.x）|
|------|-----------|-----------|
| 类型产生式 | `type → '[' type ';' NUM ']'`（1 条） | `type → '(' type_list ')'` + `type_list` 3 条（共 4 条）|
| 字面量产生式 | `primary → '[' array_elems ']'` + `array_elems` 3 条（共 4 条）| `primary → '(' tuple_inner ')'` + `tuple_inner` 2 条 + `tuple_elems` 3 条 + `primary → '(' expr ')'`（共 7 条）|
| 访问产生式 | `postfix → postfix '[' expr ']'`（1 条） | `postfix → postfix '.' NUM`（1 条）|
| **合计** | **6 条** | **12 条** |

元组比数组多 **6 条**产生式，原因如下：

**原因 1：需要与括号表达式消歧**

`(x)` 是括号表达式，`(x,)` 才是单元素元组——必须用尾逗号区分。因此元组字面量需要独立的 `tuple_inner` / `tuple_elems` 辅助非终结符，而数组字面量 `[...]` 没有歧义，`array_elems` 结构简单。

**原因 2：空元组 `()` 合法，空数组字面量不合法**

`()` 是合法的单元素类型（unit），对应 `tuple_inner → ε`。  
数组必须有固定大小（`[T; N]`，N 在类型层确定），`[]` 不构成有意义的数组字面量。

**原因 3：元组类型的元素类型各不相同**

数组类型 `[i32; 3]` 只需一个元素类型 + 一个常量大小，1 条产生式足够。  
元组类型 `(i32, bool, &i32)` 每个位置类型独立，必须用 `type_list` 展开，需要额外 3 条产生式。

**原因 4：访问语法形式相同，但语义不同**

数组用 `expr[i]`（运行时下标），元组用 `expr.0`（编译期常量字段），两者都是 1 条产生式，但元组字段必须是字面量整数，不能是变量——这在语法层通过 `postfix → postfix DOT NUM` 的 `NUM` 终结符强制保证。
