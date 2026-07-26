"""IR interpreter — executes quadruple code directly."""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))


def _val(env: dict, v: str):
    """Resolve a quad operand to a Python value."""
    if v == '_':
        return 0
    if v.lstrip('-').isdigit():
        return int(v)
    return env.get(v, 0)


def _label_index(quads: list[dict]) -> dict:
    return {q['result']: i for i, q in enumerate(quads) if q['op'] == 'label'}


def _ref_get(ref):
    if not isinstance(ref, tuple):
        raise TypeError
    if ref[0] == '__ref__':
        return ref[2].get(ref[1], 0)
    if ref[0] == '__ref_index__':
        return ref[1][ref[2]]
    raise TypeError


def _ref_set(ref, value):
    if not isinstance(ref, tuple):
        raise TypeError
    if ref[0] == '__ref__':
        ref[2][ref[1]] = value
        return
    if ref[0] == '__ref_index__':
        ref[1][ref[2]] = value
        return
    raise TypeError


class _Runtime:
    """Shared execution state for nested and recursive IR calls."""

    MAX_STEPS = 200_000
    MAX_CALL_DEPTH = 1_000

    def __init__(self, quads: list[dict]):
        self.quads = quads
        self.labels = _label_index(quads)
        self.steps = 0
        self.call_depth = 0
        self.functions: dict[str, tuple[int, list[str]]] = {}
        for i, q in enumerate(quads):
            if q['op'] != 'func_begin':
                continue
            params = []
            j = i + 1
            while j < len(quads) and quads[j]['op'] == 'param':
                params.append(quads[j]['arg1'])
                j += 1
            self.functions[q['arg1']] = (j, params)

    def call(self, func_name: str, args: list) -> tuple:
        target = self.functions.get(func_name)
        if target is None:
            return None, f"函数 '{func_name}' 未找到"
        ip, params = target
        if len(args) != len(params):
            return None, f"参数数量不匹配：期望 {len(params)} 个，给了 {len(args)} 个"
        if self.call_depth >= self.MAX_CALL_DEPTH:
            return None, "函数调用层数过深"

        env = dict(zip(params, args))
        pending_args = []
        self.call_depth += 1
        try:
            return self._execute(ip, env, pending_args)
        finally:
            self.call_depth -= 1

    def _execute(self, ip: int, env: dict, pending_args: list) -> tuple:
        quads = self.quads
        labels = self.labels

        while self.steps < self.MAX_STEPS:
            self.steps += 1
            if ip >= len(quads):
                break
            q = quads[ip]
            op, a1, a2, r = q['op'], q['arg1'], q['arg2'], q['result']

            if op in ('func_begin', 'func_end', 'param'):
                break                           # reached end of function

            if op == 'label':
                ip += 1
                continue

            if op == 'return':
                ret = _val(env, a1) if a1 != '_' else None
                if isinstance(ret, list):
                    ret = list(ret)             # copy so JSON-safe
                return ret, None

            if op == 'goto':
                ip = labels.get(r, ip + 1)
                continue

            if op == 'if_false':
                if _val(env, a1) == 0:
                    ip = labels.get(r, ip + 1)
                    continue

            elif op == 'bounds':
                arr = env.get(a1)
                idx = _val(env, a2)
                if not isinstance(arr, list):
                    return None, f"'{a1}' 不是数组"
                size = len(arr)
                if not 0 <= idx < size:
                    return None, f"数组索引 {idx} 越界（长度 {size}）"

            elif op == ':=':
                v = env.get(a1, _val(env, a1)) # preserve list/reference identity
                env[r] = v

            elif op == '+':  env[r] = _val(env, a1) + _val(env, a2)
            elif op == '-':  env[r] = _val(env, a1) - _val(env, a2)
            elif op == '*':  env[r] = _val(env, a1) * _val(env, a2)
            elif op == '/':
                b = _val(env, a2)
                if b == 0:
                    return None, "除以零错误"
                env[r] = int(_val(env, a1) / b)  # truncate toward zero

            elif op == 'neg':  env[r] = -_val(env, a1)
            elif op == '<':    env[r] = 1 if _val(env, a1) <  _val(env, a2) else 0
            elif op == '>':    env[r] = 1 if _val(env, a1) >  _val(env, a2) else 0
            elif op == '<=':   env[r] = 1 if _val(env, a1) <= _val(env, a2) else 0
            elif op == '>=':   env[r] = 1 if _val(env, a1) >= _val(env, a2) else 0
            elif op == '==':   env[r] = 1 if _val(env, a1) == _val(env, a2) else 0
            elif op == '!=':   env[r] = 1 if _val(env, a1) != _val(env, a2) else 0

            elif op == 'alloc[]':
                env[r] = [0] * int(a1)

            elif op == '[]:=':
                arr = env.get(a1)
                if isinstance(arr, list):
                    idx = _val(env, a2)
                    if not 0 <= idx < len(arr):
                        return None, f"数组索引 {idx} 越界（长度 {len(arr)}）"
                    arr[idx] = env.get(r, _val(env, r))

            elif op == '[]':
                arr = env.get(a1)
                idx = _val(env, a2)
                if not isinstance(arr, list):
                    return None, f"'{a1}' 不是数组"
                if not 0 <= idx < len(arr):
                    return None, f"数组索引 {idx} 越界（长度 {len(arr)}）"
                env[r] = arr[idx]

            elif op == 'arr_len':
                arr = env.get(a1)
                if not isinstance(arr, list):
                    return None, f"'{a1}' 不是数组"
                env[r] = len(arr)

            elif op == 'alloc()':
                env[r] = [0] * int(a1)

            elif op == '.:=':
                tup = env.get(a1)
                idx = int(a2)
                if not isinstance(tup, list) or not 0 <= idx < len(tup):
                    return None, f"元组字段 {idx} 越界"
                tup[idx] = env.get(r, _val(env, r))

            elif op == '.':
                tup = env.get(a1)
                idx = int(a2)
                if not isinstance(tup, list) or not 0 <= idx < len(tup):
                    return None, f"元组字段 {idx} 越界"
                env[r] = tup[idx]

            elif op in ('&', '&mut'):
                env[r] = ('__ref__', a1, env)  # reference = (tag, name, env)

            elif op in ('index_addr', 'field_addr'):
                container = env.get(a1)
                idx = _val(env, a2)
                kind = '数组索引' if op == 'index_addr' else '元组字段'
                if not isinstance(container, list):
                    return None, f"'{a1}' 不是可取地址的复合值"
                if not 0 <= idx < len(container):
                    return None, f"{kind} {idx} 越界（长度 {len(container)}）"
                env[r] = ('__ref_index__', container, idx)

            elif op == 'deref':
                v = env.get(a1)
                try:
                    env[r] = _ref_get(v)
                except (TypeError, IndexError):
                    return None, f"'{a1}' 不是引用"

            elif op == 'deref_write':          # *a1 = a2
                v = env.get(a1)
                try:
                    _ref_set(v, env.get(a2, _val(env, a2)))
                except (TypeError, IndexError):
                    return None, f"'{a1}' 不是引用"

            elif op == 'push_param':
                # Nested calls consume only their own most recent arguments.
                pending_args.append(env.get(a1, _val(env, a1)))

            elif op == 'call':
                argc = int(a2)
                if argc > len(pending_args):
                    return None, f"调用 '{a1}' 时参数栈不足"
                call_args = pending_args[-argc:] if argc else []
                if argc:
                    del pending_args[-argc:]
                result, err = self.call(a1, call_args)
                if err:
                    return None, err
                env[r] = result if result is not None else 0

            ip += 1

        if self.steps >= self.MAX_STEPS:
            return None, "程序执行步数超过限制，可能存在无限循环"
        return None, None                      # implicit void return


def run_func(quads: list[dict], func_name: str, args: list) -> tuple:
    """
    Execute func_name with args, including nested and recursive calls.
    Returns (result, error_str).  result is int, list, or None (void).
    """
    return _Runtime(quads).call(func_name, args)


def list_funcs(quads: list[dict], ast) -> list[dict]:
    """Return function signatures for the execution UI."""
    from ast_nodes import TypeI32, TypeRef, TypeArray, TypeTuple

    def type_str(t):
        if t is None:            return 'i32'
        if isinstance(t, TypeI32):   return 'i32'
        if isinstance(t, TypeRef):
            m = 'mut ' if t.mutable else ''
            return f'&{m}{type_str(t.inner)}'
        if isinstance(t, TypeArray): return f'[i32;{t.size}]'
        if isinstance(t, TypeTuple): return f'({",".join(type_str(x) for x in t.types)})'
        return 'i32'

    result = []
    for fn in ast.decls:
        result.append({
            'name':       fn.name,
            'has_return': fn.ret_type is not None,
            'params': [
                {'name': p.name, 'type': type_str(p.type_node)}
                for p in fn.params
            ],
        })
    return result
