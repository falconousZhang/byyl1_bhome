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


def run_func(quads: list[dict], func_name: str, args: list) -> tuple:
    """
    Execute func_name with args.
    Returns (result, error_str).  result is int, list, or None (void).
    """
    # Locate function
    start = next((i for i, q in enumerate(quads)
                  if q['op'] == 'func_begin' and q['arg1'] == func_name), None)
    if start is None:
        return None, f"函数 '{func_name}' 未找到"

    # Collect parameter names
    ip = start + 1
    params = []
    while ip < len(quads) and quads[ip]['op'] == 'param':
        params.append(quads[ip]['arg1'])
        ip += 1

    if len(args) != len(params):
        return None, f"参数数量不匹配：期望 {len(params)} 个，给了 {len(args)} 个"

    env: dict = {}
    for name, val in zip(params, args):
        env[name] = val

    labels = _label_index(quads)
    MAX_STEPS = 200_000

    for step in range(MAX_STEPS):
        if ip >= len(quads):
            break
        q = quads[ip]
        op, a1, a2, r = q['op'], q['arg1'], q['arg2'], q['result']

        if op in ('func_begin', 'func_end', 'param'):
            break                               # reached end of function

        if op == 'label':
            ip += 1; continue

        if op == 'return':
            ret = _val(env, a1) if a1 != '_' else None
            if isinstance(ret, list):
                ret = list(ret)                 # copy so JSON-safe
            return ret, None

        if op == 'goto':
            ip = labels.get(r, ip + 1); continue

        if op == 'if_false':
            if _val(env, a1) == 0:
                ip = labels.get(r, ip + 1); continue

        elif op == ':=':
            v = env.get(a1, _val(env, a1))     # preserve list identity for arrays
            env[r] = v

        elif op == '+':  env[r] = _val(env, a1) + _val(env, a2)
        elif op == '-':  env[r] = _val(env, a1) - _val(env, a2)
        elif op == '*':  env[r] = _val(env, a1) * _val(env, a2)
        elif op == '/':
            b = _val(env, a2)
            if b == 0: return None, "除以零错误"
            a = _val(env, a1)
            env[r] = int(a / b)                # truncate toward zero

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
                val = _val(env, r)
                if 0 <= idx < len(arr):
                    arr[idx] = val

        elif op == '[]':
            arr = env.get(a1, [])
            idx = _val(env, a2)
            env[r] = arr[idx] if isinstance(arr, list) and 0 <= idx < len(arr) else 0

        elif op == 'arr_len':
            arr = env.get(a1, [])
            env[r] = len(arr) if isinstance(arr, list) else 0

        elif op == 'alloc()':
            env[r] = [0] * int(a1)

        elif op == '.:=':
            tup = env.get(a1)
            if isinstance(tup, list):
                idx = int(a2)
                if 0 <= idx < len(tup):
                    tup[idx] = _val(env, r)

        elif op == '.':
            tup = env.get(a1, [])
            idx = int(a2)
            env[r] = tup[idx] if isinstance(tup, list) and 0 <= idx < len(tup) else 0

        elif op in ('&', '&mut'):
            env[r] = ('__ref__', a1, env)      # reference = tagged (kind, var_name, env)

        elif op == 'deref':
            v = env.get(a1)
            if isinstance(v, tuple) and v[0] == '__ref__':
                env[r] = v[2].get(v[1], 0)
            else:
                env[r] = v if v is not None else 0

        elif op == 'deref_write':              # *a1 = a2
            v = env.get(a1)
            if isinstance(v, tuple) and v[0] == '__ref__':
                v[2][v[1]] = _val(env, a2)

        ip += 1

    return None, None                          # implicit void return


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
