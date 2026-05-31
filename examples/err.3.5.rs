// 错误示例 3.5 — 函数调用语义错误
// 预期语义错误：
//   (1) void 函数作为赋值右值
//   (2) void 函数作为函数参数
//   (3) 实参数量与形参不一致
//   (4) 实参类型与形参不一致

fn void_func() {
}

fn add(a: i32, b: i32) -> i32 {
    a + b
}

fn consume(a: i32) {
}

fn err_void_as_rvalue() {
    let mut x: i32 = void_func();
}

fn err_void_as_arg() {
    consume(void_func());
}

fn err_arg_count() {
    let mut r: i32 = add(1, 2, 3);
}

fn err_arg_type(mut a: i32) {
    let mut t: i32 = 1;
    let mut r: i32 = add(t, 1 == 1);
}
#
