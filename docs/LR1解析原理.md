# LR(1) 语法分析原理与实现

> 对应实现文件：`src/parser_lr1.py`

---

## 一、什么是 LR(1) 分析

**LR** 代表：**L**eft-to-right scanning（从左到右读入），**R**ightmost derivation in reverse（反向最右推导）。括号里的 **1** 表示向前看（lookahead）**1 个**终结符。

LR(1) 分析是一种**自底向上**的分析方法。它不像递归下降那样"预测"接下来要匹配什么，而是把已经读入的符号压栈，当栈顶符号串能匹配某条产生式的右部时，就执行"归约"，把这串符号替换成对应的非终结符。

### 与其他分析方法的对比

| 方法 | 方向 | 向前看 | 实现难度 | 表达能力 |
|------|------|--------|---------|---------|
| 递归下降 (RD) | 自顶向下 | 1+ 个 | 低（手写） | 中（LL 文法） |
| LALR(1) (PLY) | 自底向上 | 1 个（合并） | 高（工具生成） | 强 |
| **LR(1)** | 自底向上 | 1 个（精确） | 很高（手写） | 最强 |

LR(1) 与 LALR(1) 的核心差别：LALR 会把"核心相同但 lookahead 不同"的状态**合并**，可能引入新的归约-归约冲突；LR(1) 保留每个状态的完整 lookahead，冲突更少、信息更精确。

---

## 二、文法定义

分析器的基础是一套形式文法。本项目共 86 条产生式，非终结符 25 个。

### 关键设计：分层表达式文法

原始 PLY 文法用 `%prec` 指令声明运算符优先级来解决移进-归约冲突；LR(1) 手写版本改用**分层文法**，把优先级直接编码进非终结符的层次中：

```
expr    →  cmp
cmp     →  cmp (== | != | < | > | <= | >=) add  |  add
add     →  add (+ | -) mul                       |  mul
mul     →  mul (* | /) unary                     |  unary
unary   →  - unary  |  * unary  |  & mut unary  |  & unary  |  postfix
postfix →  postfix [ expr ]  |  postfix . NUM   |  primary
primary →  NUM | IDENT | ( expr ) | ( tuple_inner ) | [ array_elems ]
         | func_body | if expr func_body else func_body | loop func_body
```

优先级从低到高依次是：比较 < 加减 < 乘除 < 一元 < 后缀 < 基元。

这种设计的好处是：**文法本身天然无二义**，LR(1) 表格对所有二元运算符都不产生冲突，唯一需要特殊处理的是"悬挂 else"问题。

### 产生式的数据结构

```python
class _P:
    id    # 产生式编号（0 开始）
    lhs   # 左部非终结符，如 'expr'
    rhs   # 右部符号元组，如 ('cmp', 'PLUS', 'add')
    fn    # 语义动作：fn(vals) → AST 节点
```

每条产生式的 `fn` 接收一个列表 `vals`：
- 终结符位置：Token 对象（有 `.value`、`.line`）
- 非终结符位置：该位置归约后得到的 AST 节点

---

## 三、FIRST 集

**FIRST(X)** = 从符号 X 出发，所有可能推导出的串的第一个终结符的集合。

如果 X 可以推导出空串 ε，则 ε ∈ FIRST(X)。

### 计算算法（不动点迭代）

```python
初始化：FIRST(terminal) = {terminal}
        FIRST(nonterminal) = {}

重复直到没有变化：
    for 每条产生式 A → X1 X2 ... Xn:
        for i = 1 to n:
            FIRST(A) ∪= FIRST(Xi) - {ε}
            if ε ∉ FIRST(Xi):
                break           # Xi 不能推出 ε，停止
        else:
            FIRST(A) ∪= {ε}    # 所有 Xi 都能推出 ε
```

### 本项目的 FIRST 集示例

| 非终结符 | FIRST |
|---------|-------|
| `expr` | `{NUM, IDENT, LPAREN, LBRACKET, LBRACE, IF, LOOP, MINUS, STAR, AMP}` |
| `stmt` | `{SEMI, RETURN, LET, IF, WHILE, FOR, LOOP, BREAK, CONTINUE, ...expr 的 FIRST...}` |
| `var_attr` | `{MUT, ε}` |
| `type_list` | `{I32, AMP, LPAREN, LBRACKET, ε}` |

### FIRST 集用于计算 lookahead

在闭包运算中，当我们有项 `A → α · B β, la`（点后面是非终结符 B），新加入的项的 lookahead 为：

```
FIRST(β la)  =  FIRST(β) 若 ε ∉ FIRST(β)
                FIRST(β) - {ε} ∪ {la}  若 ε ∈ FIRST(β)
```

---

## 四、LR(1) 项

**LR(1) 项**（item）是一个三元组：

```
(产生式编号, 点的位置, 向前看符号)
```

写作：`A → α · β, a`

- **α**：点左边——已经在栈上的符号
- **β**：点右边——还需要读入/归约的符号
- **a**：向前看符号——只有当下一个输入符号是 a 时，才在 β = ε 时执行归约

### 示例

对于产生式 `add → add PLUS mul`：

| 项 | 含义 |
|----|------|
| `add → · add PLUS mul, $` | 还没开始读，期望读入一个 add |
| `add → add · PLUS mul, $` | 已经归约出 add，等待 PLUS |
| `add → add PLUS · mul, $` | 已读 PLUS，期望归约出 mul |
| `add → add PLUS mul ·, $` | 完整匹配，可以归约（当下一个是 `$` 时）|

---

## 五、闭包运算（Closure）

给定一组"种子项"，闭包把所有**可能紧接着要分析的产生式**也加进来。

### 算法

```
closure(items):
    result = items
    worklist = list(items)
    while worklist 非空:
        取出项 (pid, dot, la)
        p = prods[pid]
        if dot >= len(p.rhs): continue   # 点在末尾，无需扩展
        
        B = p.rhs[dot]                   # 点后面的符号
        if B 是终结符: continue
        
        β = p.rhs[dot+1:]               # 点后面 B 之后的序列
        new_las = FIRST(β + (la,))      # 新 lookahead
        
        for B 的每条产生式 B → γ:
            for each a in new_las:
                item = (B→γ 的编号, 0, a)
                if item ∉ result:
                    加入 result 和 worklist
    return frozenset(result)
```

### 示例

状态 0 的种子项（增广文法起始规则）：`S' → · program, $`

闭包后展开 program 的所有产生式，再展开 decl_list，再展开 decl，再展开 func_decl……最终状态 0 包含了所有"可能在最顶层看到的"项。

---

## 六、Goto 运算

`goto(state, sym)` = 从当前状态读入符号 sym 后，转移到的新状态。

```
goto(state, sym):
    kernel = {(pid, dot+1, la)  |  (pid, dot, la) ∈ state  且  rhs[dot] == sym}
    return closure(kernel)
```

即：把点越过 sym 的那些项收集为新状态的"种子"，再求闭包。

---

## 七、构造项目集族（Canonical Collection）

用 **BFS** 从初始状态出发，枚举所有可达状态。

```
states  = [I0]        # I0 = closure({(0, 0, '$')})
queue   = [0]
index   = {I0: 0}

while queue 非空:
    si = queue.pop()
    state = states[si]
    
    # 收集点后面出现的所有符号
    next_syms = {rhs[dot] | (pid,dot,la) ∈ state, dot < len(rhs)}
    
    for sym in next_syms:
        new_state = goto(state, sym)
        if new_state ∉ index:
            index[new_state] = len(states)
            states.append(new_state)
            queue.append(index[new_state])
        
        if sym 是非终结符: GOTO[si][sym] = index[new_state]
        else:              ACTION[si][sym] = ('s', index[new_state])
```

本项目文法共产生 **591 个状态**（首次构造约需 0.3 秒，之后从缓存加载）。

---

## 八、构造 ACTION / GOTO 表

遍历每个状态中的每个项：

```
对于项 (pid, dot, la) 在状态 si 中：

  case 1：点在末尾 (dot == len(rhs))
    if lhs == "S'" and la == '$':
        ACTION[si]['$'] = ('acc',)          # 接受
    else:
        ACTION[si][la]  = ('r', pid)        # 归约

  case 2：点后是终结符 T (dot < len(rhs))
    ACTION[si][T] = ('s', goto_state)       # 移进（已在 BFS 中填写）

  case 3：点后是非终结符 NT
    GOTO[si][NT] = goto_state               # 已在 BFS 中填写
```

### 冲突处理

本文法经过分层设计，只剩一类冲突：**悬挂 else 的移进-归约冲突**。

当状态中同时有：
- 归约项：`if_stmt → IF expr func_body ·, ELSE`（想在看到 ELSE 时归约）
- 移进动作：`if_stmt → IF expr func_body · ELSE func_body`（想移进 ELSE）

规则：**移进优先**（shift wins）。

这样 `else` 总是与最近的 `if` 配对，符合各语言惯例。

```python
if la in ACTION[si]:
    existing = ACTION[si][la]
    if existing[0] == 's':
        pass          # 已有移进，保留（移进优先）
    elif existing[0] == 'r':
        if pid < existing[1]:
            ACTION[si][la] = ('r', pid)   # 归约-归约：选编号小的产生式
else:
    ACTION[si][la] = ('r', pid)
```

---

## 九、驱动程序（解析算法）

LR(1) 驱动程序用两个并行的栈模拟下推自动机：

```
state_stack = [0]     # 状态栈
val_stack   = [None]  # 值栈（Token 或 AST 节点）
pos = 0               # 当前读入位置
```

```
loop:
    state = state_stack[-1]
    sym   = tokens[pos].type  (或 '$' 如果到末尾)
    act   = ACTION[state].get(sym)

    if act is None:
        记录错误 "Syntax error at '...'"
        跳过当前 token（简单错误恢复）
        continue

    if act == ('acc',):
        break → 返回 val_stack[-1]（Program 节点）

    if act == ('s', tgt):          # 移进
        state_stack.append(tgt)
        val_stack.append(tokens[pos])
        pos += 1

    if act == ('r', pid):          # 归约
        p = prods[pid]
        n = len(p.rhs)
        vals = val_stack[-n:]      # 取出 n 个值
        state_stack = state_stack[:-n]
        val_stack   = val_stack[:-n]
        result = p.fn(vals)        # 执行语义动作，构建 AST 节点
        if p.lhs == 'func_decl':
            irgen._func(result)          # 归约完成时立即生成四元式
        new_state = GOTO[state_stack[-1]][p.lhs]
        state_stack.append(new_state)
        val_stack.append(result)
```

---

## 十、完整示例：解析 `1 + 2 * 3`

词法流：`NUM(1)  PLUS  NUM(2)  STAR  NUM(3)  $`

| 步骤 | 动作 | 状态栈 | 值栈 |
|------|------|--------|------|
| 初始 | — | `[0]` | `[—]` |
| 1 | shift(NUM) | `[0, s_num]` | `[—, 1]` |
| 2 | reduce primary→NUM | `[0, s_pf]` | `[—, NumLit(1)]` |
| 3 | reduce postfix→primary | `[0, s_un]` | `[—, NumLit(1)]` |
| 4 | reduce unary→postfix | `[0, s_mul]` | `[—, NumLit(1)]` |
| 5 | reduce mul→unary | `[0, s_add]` | `[—, NumLit(1)]` |
| 6 | shift(PLUS) | `[0, s_add, s_+]` | `[—, NumLit(1), +]` |
| 7 | shift(NUM) | `[0, s_add, s_+, s_num]` | `[—, NumLit(1), +, 2]` |
| 8 | reduce primary→NUM | … | `[—, NumLit(1), +, NumLit(2)]` |
| 9 | reduce postfix/unary/mul→… | … | `[—, NumLit(1), +, mul=NumLit(2)]` |
| 10 | shift(STAR) | 继续压栈 STAR | |
| 11 | shift(NUM) / reduce chain | … | `[—, NumLit(1), +, NumLit(2), *, NumLit(3)]` |
| 12 | reduce mul→mul*unary | … | `[—, NumLit(1), +, BinOp(*,2,3)]` |
| 13 | reduce add→add+mul | … | `[—, BinOp(+, 1, BinOp(*,2,3))]` |
| 14 | reduce cmp/expr | … | `[—, expr]` |
| … | accept | — | Program |

注意第 10 步：当 `mul` 在栈上、看到 `STAR` 时，查 ACTION 表得到"移进"（而不是归约 `add → mul`），这正是乘法优先级高于加法的体现——分层文法把这个决策编码在了状态转移中。

---

## 十一、表格缓存机制

构建 591 个状态的 ACTION/GOTO 表耗时约 0.3 秒。为避免每次启动都重建，表格在首次构建后序列化为文件：

```
src/__pycache__/lr1_tables.pkl
```

再次导入时直接加载，启动时间 < 10ms。语义动作（lambda 函数）无法序列化，因此每次从文法定义重新获取，只有表格数值被缓存。

---

## 十二、LR(1) 与 LALR(1) 的差异

本项目对两种方法都做了验证，44 个样例全部输出相同的 IR。

| 特性 | LR(1)（手写） | LALR(1)（PLY） |
|------|------------|--------------|
| 状态数 | 591 | ~300（合并同核心状态） |
| 向前看精度 | 每个状态独立 lookahead | 合并后共享 lookahead |
| 构造复杂度 | 高 | 低（在 LR(1) 基础上再合并）|
| 冲突风险 | 最低 | 合并可能引入新冲突 |
| 本项目中的实际冲突数 | 48 个（全为悬挂 else） | 相同（PLY 也用移进优先） |
